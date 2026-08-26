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
UA = "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/140 Safari/537.36 KiraparaNews-WebDiscovery/0.4.1"

SEARCHES = [
    ("JAPAN", "ja", "JP", "JP:ja", "ja-JP", ["きらめきパラダイス", "キラパラ"], ("きらめきパラダイス", "キラパラ")),
    ("CHINA", "zh-CN", "US", "US:en", "en-US", ["以闪亮之名"], ("以闪亮之名",)),
    ("GLOBAL", "en-US", "US", "US:en", "en-US", ["Life Makeover game", "Life Makeover Archosaur"], ("life makeover",)),
    ("KOREA", "ko", "KR", "KR:ko", "ko-KR", ["스타일라잇", "스타일라잇 게임"], ("스타일라잇",)),
]

PRTIMES_PAGES = [
    "https://prtimes.jp/topics/keywords/%E3%82%AD%E3%83%A9%E3%83%91%E3%83%A9",
    "https://prtimes.jp/main/action.php?page=searchkey&run=html&search_word=%E3%81%8D%E3%82%89%E3%82%81%E3%81%8D%E3%83%91%E3%83%A9%E3%83%80%E3%82%A4%E3%82%B9",
]

BLOCKED_DISCOVERY_HOSTS = (
    "x.com", "twitter.com", "youtube.com", "youtu.be", "tiktok.com",
    "instagram.com", "weibo.com", "facebook.com",
)


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def request(url: str, timeout: int = 12):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8,ko;q=0.7,zh-CN;q=0.6",
        "Accept": "text/html,application/xhtml+xml,application/rss+xml,application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            text = raw.decode(charset, errors="replace")
        except LookupError:
            text = raw.decode("utf-8", errors="replace")
        return text, response.geturl()


def clean(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"https?://\S+", "", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def title_of(value: str) -> str:
    value = clean(value)
    if not value:
        return "新着ニュース"
    first = re.split(r"[\n。！？!?]", value, maxsplit=1)[0].strip()
    if len(first) < 6:
        first = value.replace("\n", " ")
    return first[:120].rstrip(" ,，、-｜|")


def parse_epoch(value: str) -> int:
    if not value:
        return 0
    try:
        return int(parsedate_to_datetime(value.strip()).timestamp())
    except Exception:
        return 0


def rel(epoch: int) -> str:
    if not epoch:
        return "新着"
    diff = max(0, int(time.time()) - epoch)
    if diff < 3600:
        return f"{max(1, diff // 60)}分前"
    if diff < 86400:
        return f"{diff // 3600}時間前"
    if diff < 86400 * 7:
        return f"{diff // 86400}日前"
    return time.strftime("%Y-%m-%d", time.localtime(epoch))


def image_from_html(page: str, base: str):
    for pattern in (
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']',
    ):
        m = re.search(pattern, page or "", re.I)
        if m:
            return urllib.parse.urljoin(base, html.unescape(m.group(1)))
    return None


def meta(page: str, name: str):
    for pattern in (
        rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(name)}["\']',
    ):
        m = re.search(pattern, page or "", re.I)
        if m:
            return clean(m.group(1))
    return ""


def enrich_article(url: str, region: str, platform: str, fallback_title: str, fallback_body: str, epoch: int):
    try:
        page, final_url = request(url, timeout=9)
        if final_url and urllib.parse.urlparse(final_url).netloc:
            url = final_url
        page_title = meta(page, "og:title")
        if not page_title:
            m = re.search(r'<h1[^>]*>(.*?)</h1>', page, re.I | re.S) or re.search(r'<title[^>]*>(.*?)</title>', page, re.I | re.S)
            page_title = clean(m.group(1)) if m else ""
        body = meta(page, "og:description") or meta(page, "description")
        if len(body) < 80:
            paras = []
            for raw in re.findall(r'<p[^>]*>(.*?)</p>', page, re.I | re.S):
                txt = clean(raw)
                if len(txt) >= 30:
                    paras.append(txt)
                if sum(len(x) for x in paras) >= 1800:
                    break
            if paras:
                body = "\n".join(paras)
        return {
            "id": stable_id(url),
            "region": region,
            "platform": platform,
            "title": title_of(page_title or fallback_title),
            "body": (body or clean(fallback_body) or clean(fallback_title))[:2200],
            "sourceUrl": url,
            "publishedLabel": rel(epoch),
            "publishedAtEpoch": epoch,
            "imageUrl": image_from_html(page, url),
        }
    except Exception:
        return {
            "id": stable_id(url),
            "region": region,
            "platform": platform,
            "title": title_of(fallback_title),
            "body": (clean(fallback_body) or clean(fallback_title))[:2200],
            "sourceUrl": url,
            "publishedLabel": rel(epoch),
            "publishedAtEpoch": epoch,
            "imageUrl": None,
        }


def first(entry, names):
    for child in entry.iter():
        if child.tag.split("}")[-1] in names and child.text:
            return child.text.strip()
    return ""


def host_blocked(url: str):
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(part in host for part in BLOCKED_DISCOVERY_HOSTS)


def unwrap_bing(url: str):
    try:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        return urllib.parse.unquote(q.get("url", [url])[0])
    except Exception:
        return url


def parse_search_feed(xml_text: str, region: str, engine: str, keywords, limit=12):
    root = ET.fromstring(xml_text)
    entries = root.findall(".//item")
    candidates = []
    for entry in entries:
        raw_title = first(entry, {"title"})
        raw_body = first(entry, {"description", "summary"})
        published = first(entry, {"pubDate", "published", "date"})
        source = first(entry, {"source", "Source"})
        link = first(entry, {"link"})
        if not link or not raw_title:
            continue
        hay = (raw_title + "\n" + raw_body).lower()
        if not any(k.lower() in hay for k in keywords):
            continue
        if engine == "Bing":
            link = unwrap_bing(link)
        if host_blocked(link):
            continue
        platform = f"Webニュース · {source}" if source else "Webニュース"
        candidates.append((link, platform, raw_title, raw_body, parse_epoch(published)))
        if len(candidates) >= limit:
            break
    return candidates


def search_region(region, hl, gl, ceid, market, queries, keywords):
    all_candidates = []
    seen = set()
    for query in queries:
        # Bing News first because its RSS often exposes direct publisher URLs.
        bing = "https://www.bing.com/news/search?" + urllib.parse.urlencode({
            "q": query,
            "format": "RSS",
            "mkt": market,
        })
        try:
            xml, _ = request(bing, timeout=12)
            for candidate in parse_search_feed(xml, region, "Bing", keywords):
                if candidate[0] not in seen:
                    seen.add(candidate[0]); all_candidates.append(candidate)
        except Exception as exc:
            print(f"Bing fallback failed {region}/{query}: {exc}")

        # Google News RSS is an independent fallback. The news.google.com article
        # URL is still useful even when it cannot be resolved to the publisher URL.
        google = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
            "q": query,
            "hl": hl,
            "gl": gl,
            "ceid": ceid,
        })
        try:
            xml, _ = request(google, timeout=12)
            for candidate in parse_search_feed(xml, region, "Google", keywords):
                if candidate[0] not in seen:
                    seen.add(candidate[0]); all_candidates.append(candidate)
        except Exception as exc:
            print(f"Google News failed {region}/{query}: {exc}")

    # Keep a modest number per region so social/official posts remain dominant.
    all_candidates = all_candidates[:16]
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(all_candidates) or 1)) as pool:
        futures = [pool.submit(enrich_article, url, region, platform, title, body, epoch) for url, platform, title, body, epoch in all_candidates]
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            if row:
                rows.append(row)
    print(f"{region} independent web news: {len(rows)}")
    return rows


def prtimes():
    links = []
    seen = set()
    for page_url in PRTIMES_PAGES:
        try:
            page, _ = request(page_url, timeout=12)
        except Exception as exc:
            print(f"PR TIMES listing failed: {exc}")
            continue
        for href, anchor in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, re.I | re.S):
            url = urllib.parse.urljoin(page_url, html.unescape(href))
            if "/main/html/rd/p/" not in url or url in seen:
                continue
            text = clean(anchor)
            if text and "きらめきパラダイス" not in text and "キラパラ" not in text:
                continue
            seen.add(url)
            links.append(url)
            if len(links) >= 14:
                break
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(links) or 1)) as pool:
        for row in pool.map(lambda u: enrich_article(u, "JAPAN", "プレスリリース", "きらめきパラダイス", "", 0), links):
            hay = (row["title"] + "\n" + row["body"]).lower()
            if "きらめきパラダイス" in hay or "キラパラ" in hay:
                rows.append(row)
    print(f"PR TIMES direct: {len(rows)}")
    return rows


def load():
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return []


def main():
    existing = load()
    tasks = [lambda: prtimes()]
    tasks += [lambda r=r, hl=hl, gl=gl, ceid=ceid, market=market, qs=qs, keys=keys: search_region(r, hl, gl, ceid, market, qs, keys)
              for r, hl, gl, ceid, market, qs, keys in SEARCHES]

    added = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        for future in concurrent.futures.as_completed([pool.submit(t) for t in tasks]):
            try:
                added.extend(future.result())
            except Exception as exc:
                print(f"secondary discovery failed: {exc}")

    merged = {}
    for row in existing + added:
        url = row.get("sourceUrl")
        if not url:
            continue
        row["id"] = stable_id(url)
        old = merged.get(url)
        if old:
            old_score = len(old.get("body") or "") + (500 if old.get("imageUrl") else 0)
            new_score = len(row.get("body") or "") + (500 if row.get("imageUrl") else 0)
            if new_score <= old_score:
                continue
        merged[url] = row

    rows = sorted(merged.values(), key=lambda x: int(x.get("publishedAtEpoch") or 0), reverse=True)[:260]
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {}
    for row in rows:
        k = f"{row.get('region')} / {row.get('platform')}"
        counts[k] = counts.get(k, 0) + 1
    print(f"secondary discovery merged: {len(rows)} items ({len(added)} fetched)")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
