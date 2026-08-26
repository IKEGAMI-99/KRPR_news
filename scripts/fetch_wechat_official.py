#!/usr/bin/env python3
import concurrent.futures
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "news.json"
ACCOUNT = "以闪亮之名"
UA = "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/140 Mobile Safari/537.36 MicroMessenger/8.0 KiraparaNews-WeChat/0.3"
RSSHUB_HOSTS = [
    "https://rsshub.akr.moe",
    "https://rsshub.chn.moe",
    "https://rsshub.ethanliunyaa.com",
]


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def request(url: str, timeout: int = 9, referer: str | None = None):
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml,application/rss+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.6",
        "Cache-Control": "no-cache",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(6_000_000)
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            text = raw.decode(charset, errors="replace")
        except LookupError:
            text = raw.decode("utf-8", errors="replace")
        return text, response.geturl()


def strip_tags(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"</(?:p|section|div|li|h\d)\s*>", "\n", value, flags=re.I)
    value = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s*\n\s*\n+", "\n\n", value)
    return value.strip()


def clean_url(base: str, value: str | None) -> str | None:
    if not value:
        return None
    value = html.unescape(value.strip()).replace("\\/", "/")
    if value.startswith("//"):
        value = "https:" + value
    if value.startswith(("data:", "blob:")):
        return None
    try:
        url = urllib.parse.urljoin(base, value)
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        return url.replace("http://mmbiz.qpic.cn/", "https://mmbiz.qpic.cn/")
    except Exception:
        return None


def meta_value(page: str, name: str) -> str:
    for pattern in (
        rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(name)}["\']',
    ):
        m = re.search(pattern, page, re.I)
        if m:
            return strip_tags(m.group(1))
    return ""


def article_account(page: str) -> str:
    candidates = [meta_value(page, "author"), meta_value(page, "og:article:author")]
    for pattern in (
        r'\bnickname\s*=\s*["\']([^"\']+)',
        r'["\']nickname["\']\s*:\s*["\']([^"\']+)',
        r'<span[^>]+id=["\']js_name["\'][^>]*>(.*?)</span>',
        r'<a[^>]+id=["\']js_name["\'][^>]*>(.*?)</a>',
    ):
        m = re.search(pattern, page, re.I | re.S)
        if m:
            candidates.append(strip_tags(m.group(1)))
    return next((x for x in candidates if x), "")


def article_epoch(page: str) -> int:
    for pattern in (
        r'\bct\s*=\s*["\']?(\d{10})',
        r'["\'](?:publish_time|create_time)["\']\s*:\s*["\']?(\d{10})',
        r'\b(?:publish_time|create_time)\s*=\s*["\']?(\d{10})',
    ):
        m = re.search(pattern, page, re.I)
        if m:
            return int(m.group(1))
    value = meta_value(page, "article:published_time")
    if value:
        try:
            return int(parsedate_to_datetime(value).timestamp())
        except Exception:
            try:
                from datetime import datetime
                return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
            except Exception:
                pass
    return 0


def article_images(page: str, url: str) -> list[str]:
    content = page
    marker = re.search(r'id=["\']js_content["\']', page, re.I)
    if marker:
        content = page[marker.start():]
        end = re.search(r'<script\b|id=["\']js_pc_qr_code["\']|class=["\'][^"\']*rich_media_tool', content, re.I)
        if end:
            content = content[:end.start()]

    found = []
    cover = meta_value(page, "og:image")
    if cover:
        found.append(cover)
    for pattern in (
        r'<img[^>]+(?:data-src|data-original|src)=["\']([^"\']+)',
        r'<video[^>]+poster=["\']([^"\']+)',
    ):
        for match in re.finditer(pattern, content, re.I):
            candidate = clean_url(url, match.group(1))
            if not candidate:
                continue
            low = urllib.parse.unquote(candidate).lower()
            if any(token in low for token in ("qrcode", "qr_code", "avatar", "headimg", "logo", "icon", "emoji", "spacer", "pixel")):
                continue
            if candidate not in found:
                found.append(candidate)
    return found[:20]


def parse_article(url: str):
    try:
        page, final_url = request(url, timeout=9, referer="https://mp.weixin.qq.com/")
    except Exception as exc:
        print(f"WeChat article failed {url}: {exc}")
        return None

    if "mp.weixin.qq.com" not in urllib.parse.urlparse(final_url).netloc.lower():
        for pattern in (
            r'(https?://mp\.weixin\.qq\.com/s\?[^"\'<> ]+)',
            r'(https?://mp\.weixin\.qq\.com/s/[A-Za-z0-9_-]+)',
        ):
            m = re.search(pattern, page, re.I)
            if m:
                try:
                    page, final_url = request(html.unescape(m.group(1)), timeout=9, referer=url)
                except Exception:
                    return None
                break

    if "mp.weixin.qq.com" not in urllib.parse.urlparse(final_url).netloc.lower():
        return None

    account = article_account(page)
    if ACCOUNT not in account:
        return None

    title = meta_value(page, "og:title")
    if not title:
        m = re.search(r'<h1[^>]+id=["\']activity-name["\'][^>]*>(.*?)</h1>', page, re.I | re.S)
        title = strip_tags(m.group(1)) if m else ""
    if not title:
        return None

    body = ""
    marker = re.search(r'id=["\']js_content["\']', page, re.I)
    if marker:
        chunk = page[marker.start():]
        end = re.search(r'<script\b|id=["\']js_pc_qr_code["\']|class=["\'][^"\']*rich_media_tool', chunk, re.I)
        if end:
            chunk = chunk[:end.start()]
        body = strip_tags(chunk)
    if len(body) < 40:
        body = meta_value(page, "og:description") or meta_value(page, "description") or title

    images = article_images(page, final_url)
    epoch = article_epoch(page)
    return {
        "id": stable_id(final_url),
        "region": "CHINA",
        "platform": "公式WeChat",
        "title": title[:160],
        "body": body[:3200],
        "sourceUrl": final_url,
        "publishedLabel": time.strftime("%Y-%m-%d", time.localtime(epoch)) if epoch else "WeChat",
        "publishedAtEpoch": epoch,
        "imageUrl": images[0] if images else None,
        "imageUrls": images,
    }


def feed_links(xml_text: str, limit: int = 12) -> list[str]:
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    entries = root.findall(".//item") or [e for e in root.iter() if e.tag.split("}")[-1] == "entry"]
    found = []
    for entry in entries:
        author = ""
        link = ""
        for child in entry.iter():
            name = child.tag.split("}")[-1].lower()
            if name in ("author", "creator") and child.text and not author:
                author = strip_tags(child.text)
            if name == "link" and not link:
                link = child.attrib.get("href") or (child.text or "").strip()
        if author and ACCOUNT not in author:
            continue
        if link and link not in found:
            found.append(link)
        if len(found) >= limit:
            break
    return found


def discover_rsshub(limit: int = 12) -> list[str]:
    route = "/wechat/sogou/" + urllib.parse.quote(ACCOUNT, safe="")
    for host in RSSHUB_HOSTS:
        try:
            xml_text, _ = request(host.rstrip("/") + route, timeout=8)
            links = feed_links(xml_text, limit=limit)
            if links:
                print(f"RSSHub WeChat candidates: {len(links)} via {host}")
                return links
        except Exception as exc:
            print(f"RSSHub WeChat failed {host}: {exc}")
    return []


def discover_sogou(limit: int = 12) -> list[str]:
    params = urllib.parse.urlencode({"type": "2", "query": ACCOUNT, "page": "1", "ie": "utf8"})
    url = "https://weixin.sogou.com/weixin?" + params
    try:
        page, _ = request(url, timeout=8, referer="https://weixin.sogou.com/")
    except Exception as exc:
        print(f"Sogou WeChat search failed: {exc}")
        return []
    if any(token in page for token in ("请输入验证码", "异常访问", "antispider", "您的访问出错了")):
        print("Sogou WeChat search blocked by anti-bot")
        return []

    found = []
    blocks = re.findall(r'<li\b[^>]*>(.*?)</li>', page, re.I | re.S)
    for block in blocks:
        text = strip_tags(block)
        if ACCOUNT not in text:
            continue
        m = re.search(r'<h3[^>]*>.*?<a[^>]+href=["\']([^"\']+)["\']', block, re.I | re.S)
        if not m:
            continue
        target = clean_url(url, m.group(1))
        if target and target not in found:
            found.append(target)
        if len(found) >= limit:
            break
    print(f"Sogou WeChat candidates: {len(found)}")
    return found


def discover_bing(limit: int = 10) -> list[str]:
    query = f'site:mp.weixin.qq.com/s "{ACCOUNT}"'
    params = urllib.parse.urlencode({"q": query, "format": "rss", "setlang": "zh-hans"})
    url = "https://www.bing.com/search?" + params
    try:
        xml_text, _ = request(url, timeout=8)
        root = ET.fromstring(xml_text)
    except Exception as exc:
        print(f"Bing WeChat discovery failed: {exc}")
        return []
    found = []
    for item in root.findall(".//item"):
        link = (item.findtext("link") or "").strip()
        if "mp.weixin.qq.com" not in link:
            continue
        if link not in found:
            found.append(link)
        if len(found) >= limit:
            break
    print(f"Bing WeChat candidates: {len(found)}")
    return found


def main():
    try:
        rows = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        rows = []
    if not isinstance(rows, list):
        rows = []

    discovered = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(fn) for fn in (discover_rsshub, discover_sogou, discover_bing)]
        for future in concurrent.futures.as_completed(futures):
            try:
                discovered.extend(future.result())
            except Exception as exc:
                print(f"WeChat discovery task failed: {exc}")

    candidates = []
    for url in discovered:
        if url not in candidates:
            candidates.append(url)
        if len(candidates) >= 12:
            break

    added = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(candidates) or 1)) as pool:
        for row in pool.map(parse_article, candidates):
            if row:
                added.append(row)

    merged = {str(row.get("sourceUrl")): row for row in rows if row.get("sourceUrl")}
    for row in added:
        old = merged.get(row["sourceUrl"])
        if old:
            for key in ("titleJa", "bodyJa", "summaryJa", "aiProcessed", "aiModel"):
                if old.get(key) and not row.get(key):
                    row[key] = old[key]
        merged[row["sourceUrl"]] = row

    final = sorted(merged.values(), key=lambda x: int(x.get("publishedAtEpoch") or 0), reverse=True)[:260]
    OUT.write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"official WeChat articles merged: {len(added)}; total={len(final)}")


if __name__ == "__main__":
    main()
