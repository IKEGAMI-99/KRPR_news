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
UA = "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/140 Safari/537.36 KiraparaNews/0.4"

# Public RSSHub instances are intentionally redundant. X/Instagram/TikTok routes
# are not enabled on every instance, so the first healthy feed wins.
RSSHUB_HOSTS = [
    "https://rsshub.pseudoyu.com",
    "https://rsshub.umzzz.com",
    "https://rsshub.yfi.moe",
    "https://rsshub.isrss.com",
    "https://rsshub.rssforever.com",
    "https://rsshub.rss.tips",
    "https://hub.slarker.me",
    "https://rsshub.stsecurity.moe",
    "https://rsshub.moonagic.com",
    "https://rsshub.app",
]

# These public instances are currently commonly used for X routes. They are tried
# before the general pool, but the collector never depends on any single host.
X_RSSHUB_HOSTS = [
    "https://rss.xxu.do",
    "https://rsshub.ethanliunyaa.com",
] + RSSHUB_HOSTS

X_ACCOUNTS = [
    ("JAPAN", "kirapara_JP"),
    ("GLOBAL", "LifeMakeover510"),
    ("KOREA", "stylight_kr"),
]

RSSHUB_SOURCES = [
    # Japan official social pages
    ("JAPAN", "公式Instagram", "/instagram/2/user/kiramekiparadise_jp"),
    ("JAPAN", "公式TikTok", "/tiktok/user/@kiramekiparadise_jp"),
    # Global official social pages
    ("GLOBAL", "公式Instagram", "/instagram/2/user/lifemakeover_global"),
    ("GLOBAL", "公式TikTok", "/tiktok/user/@lifemakeoverofficial"),
    # Korea official social pages
    ("KOREA", "公式Instagram", "/instagram/2/user/stylight_kr"),
    ("KOREA", "公式TikTok", "/tiktok/user/@stylightofficial"),
    # China: not only videos, but dynamic posts and articles too
    ("CHINA", "公式Bilibili · 動態", "/bilibili/user/dynamic/676200579"),
    ("CHINA", "公式Bilibili · 記事", "/bilibili/user/article/676200579"),
    # Extra Weibo route pool. The main collector also has Weibo, but this gives it
    # more mirrors when its small pool happens to be down.
    ("CHINA", "公式Weibo", "/weibo/user/7521830234"),
]

DIRECT_FEEDS = [
    # Steam announcements are a stable public feed and often contain global update news.
    ("GLOBAL", "公式Steam", "https://store.steampowered.com/feeds/news/app/2626940/?l=english"),
]

WEB_LISTINGS = [
    # Japanese publisher press releases. Filter prevents other Famous Heart games
    # from entering Kirapara News.
    (
        "JAPAN",
        "公式プレスリリース",
        "https://prtimes.jp/main/html/searchrlp/company_id/79590",
        ("きらめきパラダイス", "キラパラ"),
        ("/main/html/rd/p/",),
    ),
    # Korean official community pages published in the app-store listing.
    (
        "KOREA",
        "公式Naverラウンジ",
        "https://game.naver.com/lounge/stylight/home",
        ("스타일라잇",),
        ("/lounge/stylight/", "stylight"),
    ),
    (
        "KOREA",
        "公式Naverカフェ",
        "https://cafe.naver.com/stylightofficial",
        ("스타일라잇",),
        ("ArticleRead", "stylightofficial"),
    ),
]


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def request_text(url: str, timeout: int = 12, accept: str | None = None) -> str:
    headers = {
        "User-Agent": UA,
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8,ko;q=0.7,zh-CN;q=0.6",
        "Accept": accept or "text/html,application/xhtml+xml,application/rss+xml,application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
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
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value.strip()


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
    value = value.strip()
    try:
        return int(parsedate_to_datetime(value).timestamp())
    except Exception:
        pass
    try:
        from datetime import datetime
        v = value.replace("/", "-").replace("年", "-").replace("月", "-").replace("日", " ")
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


def image_from_html(value: str, base: str) -> str | None:
    patterns = [
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, value or "", re.I)
        if match:
            return normalize_url(base, match.group(1))
    for match in re.finditer(r'<img[^>]+(?:src|data-src|data-original)=["\']([^"\']+)["\']', value or "", re.I):
        candidate = normalize_url(base, match.group(1))
        if not candidate or candidate.startswith("data:"):
            continue
        low = candidate.lower()
        if any(x in low for x in ("avatar", "favicon", "logo", "qrcode", "qr_", "emoji", "icon")):
            continue
        return candidate
    return None


def first_text(entry, names) -> str:
    for child in entry.iter():
        if child.tag.split("}")[-1] in names and child.text:
            return child.text.strip()
    return ""


def parse_feed(xml_text: str, region: str, platform: str, limit: int = 16):
    root = ET.fromstring(xml_text)
    entries = [e for e in root if e.tag.endswith("entry")] if root.tag.endswith("feed") else root.findall(".//item")
    rows = []
    for entry in entries[:limit]:
        raw_title = first_text(entry, {"title"})
        body_raw = first_text(entry, {"description", "summary", "content", "encoded"})
        published = first_text(entry, {"published", "updated", "pubDate", "date"})
        link = ""
        for child in entry.iter():
            if child.tag.split("}")[-1] == "link":
                link = child.attrib.get("href") or (child.text or "").strip()
                if link:
                    break
        if not link:
            guid = first_text(entry, {"guid", "id"})
            if guid.startswith("http"):
                link = guid
        if not link or not raw_title:
            continue

        image = None
        for child in entry.iter():
            local = child.tag.split("}")[-1].lower()
            candidate = child.attrib.get("url")
            medium = (child.attrib.get("medium") or "").lower()
            mime = (child.attrib.get("type") or "").lower()
            if candidate and (local == "thumbnail" or medium == "image" or mime.startswith("image")):
                image = normalize_url(link, candidate)
                break
        if not image:
            image = image_from_html(body_raw, link)

        body = clean_text(body_raw) or clean_text(raw_title)
        epoch = parse_epoch(published)
        rows.append({
            "id": stable_id(link),
            "region": region,
            "platform": platform,
            "title": compact_title(raw_title),
            "body": body[:2200],
            "sourceUrl": link,
            "publishedLabel": relative_label(epoch),
            "publishedAtEpoch": epoch,
            "imageUrl": image,
        })
    return rows


def rsshub_first(region: str, platform: str, route: str, hosts=None):
    hosts = hosts or RSSHUB_HOSTS

    def one(host):
        url = host.rstrip("/") + route
        try:
            text = request_text(url, timeout=9, accept="application/rss+xml,application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.5")
            rows = parse_feed(text, region, platform)
            if rows:
                print(f"{platform}: {len(rows)} via {host}")
            return rows
        except Exception as exc:
            print(f"{platform} failed {host}: {exc}")
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(hosts))) as pool:
        futures = [pool.submit(one, host) for host in hosts]
        for future in concurrent.futures.as_completed(futures):
            rows = future.result()
            if rows:
                for other in futures:
                    other.cancel()
                return rows
    return []


def parse_xcancel_html(page: str, region: str, handle: str):
    rows = []
    blocks = re.findall(r'<div[^>]+class=["\'][^"\']*timeline-item[^"\']*["\'][^>]*>(.*?)</div>\s*</div>', page, re.I | re.S)
    for block in blocks[:12]:
        permalink = re.search(r'href=["\'](/[^"\']+/status/\d+[^"\']*)["\']', block, re.I)
        content = re.search(r'class=["\'][^"\']*tweet-content[^"\']*["\'][^>]*>(.*?)</div>', block, re.I | re.S)
        if not permalink or not content:
            continue
        path = html.unescape(permalink.group(1)).split("#")[0]
        x_url = "https://x.com" + path
        body = clean_text(content.group(1))
        if not body:
            continue
        date_match = re.search(r'title=["\']([^"\']+)["\']', block, re.I)
        epoch = parse_epoch(date_match.group(1)) if date_match else 0
        rows.append({
            "id": stable_id(x_url),
            "region": region,
            "platform": "公式X",
            "title": compact_title(body),
            "body": body[:2200],
            "sourceUrl": x_url,
            "publishedLabel": relative_label(epoch),
            "publishedAtEpoch": epoch,
            "imageUrl": image_from_html(block, "https://xcancel.com/" + handle),
        })
    return rows


def x_timeline(region: str, handle: str):
    # Primary path: RSSHub's X web route. No developer API key is used by this repo.
    route = f"/twitter/user/{urllib.parse.quote(handle)}/exclude_rts_replies?limit=16"
    rows = rsshub_first(region, "公式X", route, X_RSSHUB_HOSTS)
    if rows:
        return rows

    # Fallback: public Nitter-style frontend. This is intentionally ordinary HTML/RSS
    # fetching only; no login token, browser automation or anti-bot bypass is used.
    for url in (f"https://xcancel.com/{handle}/rss", f"https://xcancel.com/{handle}"):
        try:
            page = request_text(url, timeout=10)
            if "<rss" in page[:500].lower() or "<feed" in page[:500].lower():
                rows = parse_feed(page, region, "公式X")
            else:
                rows = parse_xcancel_html(page, region, handle)
            if rows:
                print(f"公式X @{handle}: {len(rows)} via xcancel")
                return rows
        except Exception as exc:
            print(f"X fallback failed {handle}: {exc}")
    return []


def direct_feed(region: str, platform: str, url: str):
    try:
        return parse_feed(request_text(url, timeout=12), region, platform)
    except Exception as exc:
        print(f"direct feed failed {url}: {exc}")
        return []


def article_meta(url: str, region: str, platform: str):
    try:
        page = request_text(url, timeout=10)
    except Exception as exc:
        print(f"article failed {url}: {exc}")
        return None

    def meta_value(name: str):
        pats = [
            rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(name)}["\']',
        ]
        for pat in pats:
            m = re.search(pat, page, re.I)
            if m:
                return clean_text(m.group(1))
        return ""

    title = meta_value("og:title")
    if not title:
        m = re.search(r'<h1[^>]*>(.*?)</h1>', page, re.I | re.S) or re.search(r'<title[^>]*>(.*?)</title>', page, re.I | re.S)
        title = clean_text(m.group(1)) if m else ""
    description = meta_value("og:description") or meta_value("description")

    if not description:
        parts = []
        for raw in re.findall(r'<p[^>]*>(.*?)</p>', page, re.I | re.S):
            text = clean_text(raw)
            if len(text) >= 20:
                parts.append(text)
            if sum(len(x) for x in parts) > 1800:
                break
        description = "\n".join(parts)

    epoch = 0
    date_patterns = [
        r'(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}(?:日)?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)',
        r'content=["\'](20\d{2}-\d{2}-\d{2}T[^"\']+)["\']',
    ]
    for pat in date_patterns:
        m = re.search(pat, page, re.I)
        if m:
            epoch = parse_epoch(m.group(1))
            if epoch:
                break

    if not title:
        return None
    return {
        "id": stable_id(url),
        "region": region,
        "platform": platform,
        "title": compact_title(title),
        "body": (description or title)[:2200],
        "sourceUrl": url,
        "publishedLabel": relative_label(epoch),
        "publishedAtEpoch": epoch,
        "imageUrl": image_from_html(page, url),
    }


def web_listing(region: str, platform: str, index_url: str, must_contain, link_tokens, limit: int = 12):
    try:
        page = request_text(index_url, timeout=12)
    except Exception as exc:
        print(f"listing failed {index_url}: {exc}")
        return []

    candidates = []
    seen = set()
    for match in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, re.I | re.S):
        url = normalize_url(index_url, match.group(1))
        anchor = clean_text(match.group(2))
        if not url or url in seen:
            continue
        if link_tokens and not any(token.lower() in url.lower() for token in link_tokens):
            continue
        if must_contain and anchor and not any(word.lower() in anchor.lower() for word in must_contain):
            # Keep empty/JS anchors because the article page itself may contain the title.
            continue
        seen.add(url)
        candidates.append(url)
        if len(candidates) >= limit * 2:
            break

    rows = []
    if not candidates:
        return rows
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(candidates))) as pool:
        for row in pool.map(lambda u: article_meta(u, region, platform), candidates):
            if not row:
                continue
            haystack = (row["title"] + "\n" + row["body"]).lower()
            if must_contain and not any(word.lower() in haystack for word in must_contain):
                continue
            rows.append(row)
            if len(rows) >= limit:
                break
    if rows:
        print(f"{platform}: {len(rows)} from public pages")
    return rows


def load_existing():
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def main():
    existing = load_existing()
    tasks = []
    tasks += [lambda region=r, handle=h: x_timeline(region, handle) for r, h in X_ACCOUNTS]
    tasks += [lambda r=r, p=p, route=route: rsshub_first(r, p, route) for r, p, route in RSSHUB_SOURCES]
    tasks += [lambda r=r, p=p, url=url: direct_feed(r, p, url) for r, p, url in DIRECT_FEEDS]
    tasks += [
        lambda r=r, p=p, url=url, words=words, tokens=tokens: web_listing(r, p, url, words, tokens)
        for r, p, url, words, tokens in WEB_LISTINGS
    ]

    added = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(14, len(tasks))) as pool:
        futures = [pool.submit(task) for task in tasks]
        for future in concurrent.futures.as_completed(futures):
            try:
                added.extend(future.result())
            except Exception as exc:
                print(f"enrichment task failed: {exc}")

    merged = {}
    for row in existing + added:
        url = row.get("sourceUrl")
        if not url:
            continue
        row["id"] = stable_id(url)
        old = merged.get(url)
        # Prefer the row with more body text / a real image when duplicate sources exist.
        if old:
            old_score = len(old.get("body") or "") + (500 if old.get("imageUrl") else 0)
            new_score = len(row.get("body") or "") + (500 if row.get("imageUrl") else 0)
            if new_score <= old_score:
                continue
        merged[url] = row

    rows = sorted(
        merged.values(),
        key=lambda item: int(item.get("publishedAtEpoch") or 0),
        reverse=True,
    )[:180]

    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {}
    for row in rows:
        key = f"{row.get('region')} / {row.get('platform')}"
        counts[key] = counts.get(key, 0) + 1
    print(f"enriched cache: {len(rows)} items ({len(added)} fetched in enrichment pass)")
    for key, count in sorted(counts.items()):
        print(f"  {key}: {count}")


if __name__ == "__main__":
    main()
