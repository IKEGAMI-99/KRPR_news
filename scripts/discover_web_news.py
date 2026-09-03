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
UA = "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/140 Safari/537.36 KiraparaNews-WebDiscovery/0.4"

WEB_SEARCHES = [
    ("JAPAN", "ja-JP", '"きらめきパラダイス" OR キラパラ', ("きらめきパラダイス", "キラパラ")),
    ("CHINA", "zh-CN", '"以闪亮之名"', ("以闪亮之名",)),
    ("GLOBAL", "en-US", '"Life Makeover" Archosaur game', ("life makeover",)),
    ("KOREA", "ko-KR", '"스타일라잇" 게임', ("스타일라잇",)),
]

# Dedicated publisher/listing pages that are server-rendered and can be read
# without credentials. These complement social sources with longer articles.
PUBLIC_LISTINGS = [
    (
        "JAPAN",
        "プレスリリース",
        "https://prtimes.jp/topics/keywords/%E3%82%AD%E3%83%A9%E3%83%91%E3%83%A9",
        ("きらめきパラダイス", "キラパラ"),
        ("/main/html/rd/p/",),
    ),
]

BILIBILI_UID = "676200579"


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def request(url: str, timeout: int = 12, referer: str | None = None):
    headers = {
        "User-Agent": UA,
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8,ko;q=0.7,zh-CN;q=0.6",
        "Accept": "text/html,application/xhtml+xml,application/rss+xml,application/xml,application/json;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
        return raw, response.headers, response.geturl()


def request_text(url: str, timeout: int = 12, referer: str | None = None) -> str:
    raw, headers, _ = request(url, timeout=timeout, referer=referer)
    charset = headers.get_content_charset() or "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def strip_tags(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def clean_text(value: str) -> str:
    value = strip_tags(value)
    value = re.sub(r"https?://\S+", "", value)
    return re.sub(r"[ \t]{2,}", " ", value).strip()


def compact_title(value: str) -> str:
    value = clean_text(value)
    if not value:
        return "新着ニュース"
    first = re.split(r"[\n。！？!?]", value, maxsplit=1)[0].strip()
    if len(first) < 6:
        first = value.replace("\n", " ")
    return first[:120].rstrip(" ,，、-｜|")


def normalize_url(base: str, value: str | None) -> str | None:
    if not value:
        return None
    value = html.unescape(value.strip())
    if value.startswith("//"):
        value = "https:" + value
    return urllib.parse.urljoin(base, value)


def parse_epoch(value: str) -> int:
    if not value:
        return 0
    try:
        return int(parsedate_to_datetime(value.strip()).timestamp())
    except Exception:
        pass
    try:
        from datetime import datetime
        v = value.strip().replace("/", "-").replace("年", "-").replace("月", "-").replace("日", " ")
        v = re.sub(r"\s+", " ", v).strip()
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", v):
            v += " 00:00:00"
        return int(datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp())
    except Exception:
        return 0


def relative_label(epoch: int) -> str:
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


def image_from_html(page: str, base: str) -> str | None:
    for pattern in (
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']',
    ):
        m = re.search(pattern, page or "", re.I)
        if m:
            return normalize_url(base, m.group(1))
    for m in re.finditer(r'<img[^>]+(?:src|data-src|data-original)=["\']([^"\']+)["\']', page or "", re.I):
        candidate = normalize_url(base, m.group(1))
        if not candidate or candidate.startswith("data:"):
            continue
        low = candidate.lower()
        if any(token in low for token in ("avatar", "favicon", "logo", "qrcode", "qr_", "emoji", "icon", "sprite")):
            continue
        return candidate
    return None


def meta_value(page: str, name: str) -> str:
    for pattern in (
        rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(name)}["\']',
    ):
        m = re.search(pattern, page or "", re.I)
        if m:
            return clean_text(m.group(1))
    return ""


def article_meta(url: str, region: str, platform: str, fallback_title: str = "", fallback_body: str = "", fallback_epoch: int = 0):
    try:
        page = request_text(url, timeout=10)
    except Exception as exc:
        print(f"article read failed {url}: {exc}")
        if not fallback_title:
            return None
        return {
            "id": stable_id(url),
            "region": region,
            "platform": platform,
            "title": compact_title(fallback_title),
            "body": (clean_text(fallback_body) or clean_text(fallback_title))[:2200],
            "sourceUrl": url,
            "publishedLabel": relative_label(fallback_epoch),
            "publishedAtEpoch": fallback_epoch,
            "imageUrl": None,
        }

    title = meta_value(page, "og:title")
    if not title:
        m = re.search(r'<h1[^>]*>(.*?)</h1>', page, re.I | re.S) or re.search(r'<title[^>]*>(.*?)</title>', page, re.I | re.S)
        title = clean_text(m.group(1)) if m else fallback_title

    body = meta_value(page, "og:description") or meta_value(page, "description")
    if len(body) < 60:
        paragraphs = []
        for raw in re.findall(r'<p[^>]*>(.*?)</p>', page, re.I | re.S):
            text = clean_text(raw)
            if len(text) < 25:
                continue
            paragraphs.append(text)
            if sum(len(x) for x in paragraphs) >= 1800:
                break
        if paragraphs:
            body = "\n".join(paragraphs)
    body = body or fallback_body or title

    epoch = fallback_epoch
    for pattern in (
        r'(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}(?:日)?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)',
        r'content=["\'](20\d{2}-\d{2}-\d{2}T[^"\']+)["\']',
    ):
        m = re.search(pattern, page, re.I)
        if m:
            parsed = parse_epoch(m.group(1))
            if parsed:
                epoch = parsed
                break

    if not title:
        return None
    return {
        "id": stable_id(url),
        "region": region,
        "platform": platform,
        "title": compact_title(title),
        "body": clean_text(body)[:2200],
        "sourceUrl": url,
        "publishedLabel": relative_label(epoch),
        "publishedAtEpoch": epoch,
        "imageUrl": image_from_html(page, url),
    }


def first_text(entry, names) -> str:
    for child in entry.iter():
        if child.tag.split("}")[-1] in names and child.text:
            return child.text.strip()
    return ""


def unwrap_bing_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        target = qs.get("url", [None])[0]
        if target:
            return urllib.parse.unquote(target)
    except Exception:
        pass
    return url


def bing_news(region: str, market: str, query: str, keywords, limit: int = 14):
    params = urllib.parse.urlencode({
        "q": query,
        "qft": 'sortbydate="1"',
        "format": "RSS",
        "mkt": market,
    })
    url = "https://www.bing.com/news/search?" + params
    try:
        xml_text = request_text(url, timeout=14)
        root = ET.fromstring(xml_text)
    except Exception as exc:
        print(f"Bing News failed {region}: {exc}")
        return []

    candidates = []
    for entry in root.findall(".//item")[: limit * 2]:
        raw_title = first_text(entry, {"title"})
        raw_body = first_text(entry, {"description", "summary"})
        published = first_text(entry, {"pubDate", "published", "date"})
        source_name = first_text(entry, {"Source", "source"})
        link = first_text(entry, {"link"})
        if not link:
            continue
        direct = unwrap_bing_url(link)
        haystack = (raw_title + "\n" + raw_body).lower()
        if not any(word.lower() in haystack for word in keywords):
            continue
        host = urllib.parse.urlparse(direct).netloc.lower()
        if any(domain in host for domain in ("x.com", "twitter.com", "youtube.com", "youtu.be", "tiktok.com", "weibo.com")):
            continue
        platform = f"Webニュース · {source_name}" if source_name else "Webニュース"
        candidates.append((direct, platform, raw_title, raw_body, parse_epoch(published)))
        if len(candidates) >= limit:
            break

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(candidates) or 1)) as pool:
        futures = [pool.submit(article_meta, url, region, platform, title, body, epoch) for url, platform, title, body, epoch in candidates]
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            if row:
                rows.append(row)
    if rows:
        print(f"{region} Webニュース: {len(rows)}")
    return rows


def public_listing(region: str, platform: str, index_url: str, keywords, link_tokens, limit: int = 12):
    try:
        page = request_text(index_url, timeout=12)
    except Exception as exc:
        print(f"listing failed {index_url}: {exc}")
        return []

    links = []
    seen = set()
    for match in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, re.I | re.S):
        url = normalize_url(index_url, match.group(1))
        anchor = clean_text(match.group(2))
        if not url or url in seen:
            continue
        if link_tokens and not any(token.lower() in url.lower() for token in link_tokens):
            continue
        if anchor and keywords and not any(word.lower() in anchor.lower() for word in keywords):
            continue
        seen.add(url)
        links.append(url)
        if len(links) >= limit * 2:
            break

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(links) or 1)) as pool:
        for row in pool.map(lambda u: article_meta(u, region, platform), links):
            if not row:
                continue
            haystack = (row["title"] + "\n" + row["body"]).lower()
            if keywords and not any(word.lower() in haystack for word in keywords):
                continue
            rows.append(row)
            if len(rows) >= limit:
                break
    if rows:
        print(f"{platform}: {len(rows)}")
    return rows


def bilibili_dynamic(limit: int = 16):
    url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?" + urllib.parse.urlencode({
        "host_mid": BILIBILI_UID,
        "timezone_offset": "-480",
        "features": "itemOpusStyle",
    })
    try:
        raw, _, _ = request(url, timeout=12, referer=f"https://space.bilibili.com/{BILIBILI_UID}/dynamic")
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception as exc:
        print(f"Bilibili public dynamic failed: {exc}")
        return []

    if payload.get("code") != 0:
        print(f"Bilibili public dynamic returned code={payload.get('code')}")
        return []

    rows = []
    for item in (payload.get("data") or {}).get("items") or []:
        if len(rows) >= limit:
            break
        item_id = str(item.get("id_str") or "").strip()
        if not item_id:
            continue
        modules = item.get("modules") or {}
        author = modules.get("module_author") or {}
        dynamic = modules.get("module_dynamic") or {}
        desc = dynamic.get("desc") or {}
        body = clean_text(desc.get("text") or "")
        major = dynamic.get("major") or {}

        image = None
        extra_title = ""
        draw = major.get("draw") or {}
        draw_items = draw.get("items") or []
        if draw_items:
            image = (draw_items[0] or {}).get("src")

        opus = major.get("opus") or {}
        if opus:
            extra_title = clean_text(opus.get("title") or "")
            summary = opus.get("summary") or {}
            if not body:
                body = clean_text(summary.get("text") or "")
            pics = opus.get("pics") or []
            if not image and pics:
                image = (pics[0] or {}).get("url")

        archive = major.get("archive") or {}
        if archive:
            extra_title = extra_title or clean_text(archive.get("title") or "")
            body = body or clean_text(archive.get("desc") or "")
            image = image or archive.get("cover")

        article = major.get("article") or {}
        if article:
            extra_title = extra_title or clean_text(article.get("title") or "")
            body = body or clean_text(article.get("desc") or "")
            covers = article.get("covers") or []
            if not image and covers:
                image = covers[0]

        text = body or extra_title
        if not text:
            continue
        epoch = int(author.get("pub_ts") or 0)
        source_url = f"https://t.bilibili.com/{item_id}"
        rows.append({
            "id": stable_id(source_url),
            "region": "CHINA",
            "platform": "公式Bilibili · 動態",
            "title": compact_title(extra_title or text),
            "body": text[:2200],
            "sourceUrl": source_url,
            "publishedLabel": relative_label(epoch),
            "publishedAtEpoch": epoch,
            "imageUrl": image,
        })
    if rows:
        print(f"公式Bilibili · 動態: {len(rows)} via public feed")
    return rows


def load_existing():
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def main():
    existing = load_existing()
    tasks = [lambda: bilibili_dynamic()]
    tasks += [lambda r=r, m=m, q=q, words=words: bing_news(r, m, q, words) for r, m, q, words in WEB_SEARCHES]
    tasks += [
        lambda r=r, p=p, url=url, words=words, tokens=tokens: public_listing(r, p, url, words, tokens)
        for r, p, url, words, tokens in PUBLIC_LISTINGS
    ]

    added = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(tasks))) as pool:
        futures = [pool.submit(task) for task in tasks]
        for future in concurrent.futures.as_completed(futures):
            try:
                added.extend(future.result())
            except Exception as exc:
                print(f"web discovery task failed: {exc}")

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

    # Also suppress obvious title-level duplicates coming from multiple aggregators.
    by_title = {}
    for row in sorted(merged.values(), key=lambda x: int(x.get("publishedAtEpoch") or 0), reverse=True):
        key = re.sub(r"\W+", "", (row.get("title") or "").lower())[:80]
        if key and key in by_title:
            old = by_title[key]
            old_is_primary = any(tag in (old.get("platform") or "") for tag in ("公式", "プレスリリース"))
            new_is_primary = any(tag in (row.get("platform") or "") for tag in ("公式", "プレスリリース"))
            if old_is_primary or not new_is_primary:
                continue
        by_title[key or row["sourceUrl"]] = row

    rows = sorted(by_title.values(), key=lambda x: int(x.get("publishedAtEpoch") or 0), reverse=True)[:800]
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts = {}
    for row in rows:
        key = f"{row.get('region')} / {row.get('platform')}"
        counts[key] = counts.get(key, 0) + 1
    print(f"web discovery merged: {len(rows)} items ({len(added)} fetched)")
    for key, count in sorted(counts.items()):
        print(f"  {key}: {count}")


if __name__ == "__main__":
    main()
