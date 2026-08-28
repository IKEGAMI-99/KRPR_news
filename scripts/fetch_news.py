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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "news.json"
UA = "Mozilla/5.0 KiraparaNews-GitHubCollector/0.3.13"

YOUTUBE_CHANNEL_IDS = {
    "JAPAN": "UC9MO21fNvt0F4-UK28kc_VQ",
    "GLOBAL": "UCaaIsX56nWN0fvGJXQ8yvhA",
    "KOREA": "UC-E6zjPaMmZk6dm9EfQ3gBg",
}

UNRELATED_YOUTUBE_TITLES = (
    "dragon raja",
    "noah's heart",
    "noah’s heart",
    "archosaur games’ ue5 teaser",
    "archosaur games' ue5 teaser",
)

RSSHUB_HOSTS = [
    "https://rsshub.app",
    "https://rsshub.rssforever.com",
    "https://rsshub.yfi.moe",
]

REGION_HOME_PAGES = {
    "JAPAN": "https://kirapara.archosaur.com/",
    "CHINA": "https://mystyle.archosaur.com/",
    "GLOBAL": "https://lifemakeover.archosaur.com/",
    "KOREA": "https://stylight.nex2fun.com/",
}

STATIC_FALLBACK_IMAGES = {
    "JAPAN": "https://kirapara.archosaur.com/new_script/img/pc/top_logo.png",
    "CHINA": "https://mystyle.archosaur.com/assets/260721/pc/images/p3/slider1.jpg",
    "KOREA": "https://stylight.nex2fun.com/assets/pc/img/page1/page1_slogan.png",
}

# Official web pages are intentionally included in addition to social feeds. Some
# CMS list URLs change over time, so every source has multiple public entry points.
CMS_SOURCES = [
    (
        "JAPAN",
        "公式サイト",
        [
            "https://cms.archosaur.com/jeecms/smhwjpnews/index.jhtml",
            "https://cms.archosaur.com/jeecms/smhwjpevent/index.jhtml",
            "https://kirapara.archosaur.com/",
        ],
        ("/smhwjpnews/", "/smhwjpevent/"),
    ),
    (
        "CHINA",
        "公式サイト",
        [
            "https://cms.zulong.com/jeecms/yslzm/index.jhtml?type=pc",
            "https://mystyle.archosaur.com/home/index.html",
        ],
        ("/yslzm", "/smhw", "/yx"),
    ),
    (
        "GLOBAL",
        "公式サイト",
        [
            "https://cms.archosaur.com/jeecms/smhwpcinhd/index.jhtml",
            "https://cms.archosaur.com/jeecms/smhwpenzx/index.jhtml",
            "https://cms.archosaur.com/jeecms/smhwpengg/index.jhtml",
            "https://lifemakeover.archosaur.com/",
        ],
        ("/smhwpcinhd/", "/smhwpenzx/", "/smhwpengg/", "/smsmhw"),
    ),
]

_official_image_cache = {}


def get(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8,ko;q=0.7,zh-CN;q=0.6",
            "Accept": "text/html,application/xhtml+xml,application/rss+xml,application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        charset = r.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, errors="replace")
        except LookupError:
            return raw.decode("utf-8", errors="replace")


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def strip_tags(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def clean_social_text(s: str, region: str) -> str:
    s = strip_tags(s)
    if region == "CHINA":
        s = re.sub(r"#[^#\n]{1,100}#", " ", s)
        s = re.sub(r"^\s*(?:以闪亮之名\s*)+", "", s)
        s = re.sub(r"@[^\s:：]+", "", s)
        s = s.replace("网页链接", "")
        lines = []
        for line in s.splitlines():
            line = line.strip()
            if not line:
                continue
            if any(marker in line for marker in ("下载传送门", "活动传送门", "转发微博")):
                continue
            lines.append(line)
        s = "\n".join(lines)

    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def compact_title(s: str, region: str) -> str:
    s = clean_social_text(s, region)
    if not s:
        return "新着ニュース"
    first = re.split(r"[\n。！？!?]", s, maxsplit=1)[0].strip()
    candidate = first if len(first) >= 6 else s.replace("\n", " ")
    return candidate[:100].rstrip(" ,，、-｜|")


def normalize_url(base: str, value: str | None):
    if not value:
        return None
    value = html.unescape(value.strip())
    if value.startswith("//"):
        return "https:" + value
    return urllib.parse.urljoin(base, value)


def image_from_html(s: str, base_url: str = ""):
    patterns = [
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']',
    ]
    for pattern in patterns:
        m = re.search(pattern, s or "", re.I)
        if m:
            candidate = normalize_url(base_url, m.group(1))
            if candidate and not is_placeholder_image(candidate):
                return candidate

    for m in re.finditer(r'<img[^>]+(?:src|data-src|data-original)=["\']([^"\']+)["\']', s or "", re.I):
        candidate = normalize_url(base_url, m.group(1))
        if not candidate or candidate.startswith("data:"):
            continue
        low = candidate.lower()
        if any(token in low for token in ("qrcode", "qr_", "qr-", "favicon", "icon", "logo", "avatar", "download", "store")):
            continue
        if not is_placeholder_image(candidate):
            return candidate
    return None


def is_placeholder_image(url: str | None) -> bool:
    if not url:
        return True
    low = url.lower()
    return any(
        token in low
        for token in (
            "timeline_card_small_super_default",
            "timeline_card_small_web_default",
            "timeline_card_small_default",
            "default_avatar",
            "default.png",
            "blank.gif",
            "spacer.gif",
        )
    )


def official_fallback_image(region: str):
    if region in _official_image_cache:
        return _official_image_cache[region]

    home = REGION_HOME_PAGES.get(region)
    discovered = None
    if home:
        try:
            page = get(home, timeout=10)
            discovered = image_from_html(page, home)
            if not discovered:
                candidates = re.findall(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']', page, re.I)
                scored = []
                for src in candidates:
                    full = normalize_url(home, src)
                    if not full or full.startswith("data:"):
                        continue
                    low = full.lower()
                    if any(token in low for token in ("ewm", "qrcode", "qr_", "qr-", "favicon", "icon", "logo", "download", "store")):
                        continue
                    score = sum(
                        token in low
                        for token in (
                            "keyvisual", "mainvisual", "visual", "banner", "slider", "slide", "kv", "hero", "top_bg", "top-bg"
                        )
                    )
                    if score > 0:
                        scored.append((score, full))
                if scored:
                    scored.sort(key=lambda x: x[0], reverse=True)
                    discovered = scored[0][1]
        except Exception as e:
            print(f"official image discovery failed {region}: {e}")

    result = discovered or STATIC_FALLBACK_IMAGES.get(region)
    _official_image_cache[region] = result
    return result


def parse_date_epoch(value: str) -> int:
    if not value:
        return 0
    value = value.strip()
    try:
        from email.utils import parsedate_to_datetime
        return int(parsedate_to_datetime(value).timestamp())
    except Exception:
        pass
    try:
        from datetime import datetime
        normalized = value.replace("/", "-").replace("年", "-").replace("月", "-").replace("日", " ")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", normalized):
            normalized += " 00:00:00"
        return int(datetime.fromisoformat(normalized.replace("Z", "+00:00")).timestamp())
    except Exception:
        return 0


def rel_label(epoch: int) -> str:
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


def feed_image(entry, body_raw: str, link: str):
    for child in entry.iter():
        local = child.tag.split("}")[-1].lower()
        if local == "thumbnail" and child.attrib.get("url"):
            return normalize_url(link, child.attrib.get("url"))
        if local in {"content", "enclosure"}:
            candidate = child.attrib.get("url")
            media_type = (child.attrib.get("type") or "").lower()
            medium = (child.attrib.get("medium") or "").lower()
            if candidate and (media_type.startswith("image") or medium == "image" or re.search(r"\.(?:jpe?g|png|webp)(?:\?|$)", candidate, re.I)):
                return normalize_url(link, candidate)
    return image_from_html(body_raw, link)


def parse_feed(xml_text: str, region: str, platform: str, limit: int = 12):
    root = ET.fromstring(xml_text)
    entries = [e for e in root if e.tag.endswith("entry")] if root.tag.endswith("feed") else root.findall(".//item")
    items = []

    for e in entries[:limit]:
        def first_text(names):
            for child in e.iter():
                local = child.tag.split("}")[-1]
                if local in names and child.text:
                    return child.text.strip()
            return ""

        raw_title = first_text({"title"})
        body_raw = first_text({"description", "summary", "content", "encoded"})
        published = first_text({"published", "updated", "pubDate"})
        video_id = first_text({"videoId"})

        link = ""
        for child in e.iter():
            if child.tag.split("}")[-1] == "link":
                link = child.attrib.get("href") or (child.text or "").strip()
                if link:
                    break
        if not link:
            guid = first_text({"guid"})
            if guid.startswith("http"):
                link = guid
        if not link and video_id:
            link = f"https://www.youtube.com/watch?v={video_id}"

        if not raw_title or not link:
            continue

        image = feed_image(e, body_raw, link)
        if not image and video_id:
            image = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

        title = compact_title(raw_title, region)
        body = clean_social_text(body_raw, region) or clean_social_text(raw_title, region)
        epoch = parse_date_epoch(published)
        if is_placeholder_image(image):
            image = official_fallback_image(region)

        items.append({
            "id": stable_id(link),
            "region": region,
            "platform": platform,
            "title": title,
            "body": body[:1800],
            "sourceUrl": link,
            "publishedLabel": rel_label(epoch),
            "publishedAtEpoch": epoch,
            "imageUrl": image,
        })
    return items


def resolve_youtube_channel_id(page_url: str):
    text = get(page_url)
    # Channel pages also contain IDs for recommended and embedded videos. The
    # canonical page owner must win over generic channelId fields.
    patterns = [
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'][^"\']*?/channel/(UC[a-zA-Z0-9_-]{22})',
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\'][^"\']*?/channel/(UC[a-zA-Z0-9_-]{22})',
        r'<meta[^>]+content=["\'][^"\']*?/channel/(UC[a-zA-Z0-9_-]{22})[^"\']*["\'][^>]+property=["\']og:url["\']',
        r'"browseId"\s*:\s*"(UC[a-zA-Z0-9_-]{22})"',
        r'"externalId"\s*:\s*"(UC[a-zA-Z0-9_-]{22})"',
        r'youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return None


def youtube_channel(region: str, platform: str, channel_id=None, page_urls=None):
    if not channel_id:
        for page in page_urls or []:
            try:
                channel_id = resolve_youtube_channel_id(page)
                if channel_id:
                    break
            except Exception as e:
                print(f"youtube page failed {page}: {e}")
    if not channel_id:
        return []
    return parse_feed(get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"), region, platform)


def rsshub(region: str, platform: str, path: str):
    # Try mirrors concurrently instead of waiting for dead public instances one by one.
    def fetch_host(host):
        try:
            return parse_feed(get(host + path, timeout=10), region, platform)
        except Exception as e:
            print(f"rsshub failed {host}{path}: {e}")
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(RSSHUB_HOSTS)) as pool:
        futures = [pool.submit(fetch_host, host) for host in RSSHUB_HOSTS]
        for future in concurrent.futures.as_completed(futures):
            rows = future.result()
            if rows:
                for other in futures:
                    other.cancel()
                return rows
    return []


def extract_article_title(page: str, region: str):
    patterns = [
        r'<h1[^>]*>(.*?)</h1>',
        r'<meta[^>]+(?:property|name)=["\']og:title["\'][^>]+content=["\']([^"\']+)',
        r'<title[^>]*>(.*?)</title>',
    ]
    for pattern in patterns:
        m = re.search(pattern, page, re.I | re.S)
        if m:
            value = compact_title(strip_tags(m.group(1)), region)
            if value and value != "新着ニュース":
                return value
    return "新着ニュース"


def extract_article_epoch(page: str):
    patterns = [
        r'(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}(?:日)?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)',
        r'content=["\'](20\d{2}-\d{2}-\d{2}T[^"\']+)["\']',
    ]
    for pattern in patterns:
        m = re.search(pattern, page, re.I)
        if m:
            epoch = parse_date_epoch(m.group(1))
            if epoch:
                return epoch
    return 0


def extract_article_body(page: str, region: str):
    cleaned = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", page, flags=re.I | re.S)
    paragraphs = []
    seen = set()
    for raw in re.findall(r"<(?:p|li)[^>]*>(.*?)</(?:p|li)>", cleaned, flags=re.I | re.S):
        text = clean_social_text(raw, region)
        if len(text) < 4:
            continue
        low = text.lower()
        if any(marker in low for marker in ("copyright", "all rights reserved", "follow us", "扫码下载", "google play", "app store")):
            continue
        if text in seen:
            continue
        seen.add(text)
        paragraphs.append(text)
        if sum(len(x) for x in paragraphs) >= 2400:
            break
    body = "\n".join(paragraphs).strip()
    if body:
        return body[:1800]

    meta = re.search(r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)', page, re.I)
    return clean_social_text(meta.group(1), region)[:1800] if meta else ""


def article_links(index_html: str, index_url: str, path_tokens):
    out = []
    seen = set()
    for href in re.findall(r'href\s*=\s*["\']([^"\']+)["\']', index_html, re.I):
        full = normalize_url(index_url, href)
        if not full or ".jhtml" not in full.lower():
            continue
        if "index.jhtml" in full.lower():
            continue
        if path_tokens and not any(token.lower() in full.lower() for token in path_tokens):
            continue
        if full not in seen:
            seen.add(full)
            out.append(full)
    return out


def cms_source(region: str, platform: str, index_urls, path_tokens, limit: int = 10):
    links = []
    for index_url in index_urls:
        try:
            page = get(index_url, timeout=12)
            links.extend(article_links(page, index_url, path_tokens))
        except Exception as e:
            print(f"cms index failed {index_url}: {e}")

    unique_links = list(dict.fromkeys(links))[:limit]
    if not unique_links:
        return []

    def fetch_article(url):
        try:
            page = get(url, timeout=12)
            title = extract_article_title(page, region)
            body = extract_article_body(page, region) or title
            epoch = extract_article_epoch(page)
            image = image_from_html(page, url)
            if is_placeholder_image(image):
                image = official_fallback_image(region)
            return {
                "id": stable_id(url),
                "region": region,
                "platform": platform,
                "title": title,
                "body": body,
                "sourceUrl": url,
                "publishedLabel": rel_label(epoch),
                "publishedAtEpoch": epoch,
                "imageUrl": image,
            }
        except Exception as e:
            print(f"cms article failed {url}: {e}")
            return None

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(unique_links))) as pool:
        for row in pool.map(fetch_article, unique_links):
            if row and row["title"] != "新着ニュース":
                rows.append(row)
    return rows


def load_existing():
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def main():
    existing = load_existing()

    sources = [
        lambda: youtube_channel("JAPAN", "公式YouTube", channel_id=YOUTUBE_CHANNEL_IDS["JAPAN"]),
        lambda: youtube_channel("GLOBAL", "公式YouTube", channel_id=YOUTUBE_CHANNEL_IDS["GLOBAL"]),
        lambda: youtube_channel("KOREA", "公式YouTube", channel_id=YOUTUBE_CHANNEL_IDS["KOREA"]),
        lambda: rsshub("CHINA", "公式Weibo · RSSHub", "/weibo/user/7521830234"),
        lambda: rsshub("CHINA", "公式Bilibili · RSSHub", "/bilibili/user/video/676200579"),
        lambda: rsshub("JAPAN", "公式X · RSSHub", "/twitter/user/kirapara_JP"),
        lambda: rsshub("GLOBAL", "公式X · RSSHub", "/twitter/user/LifeMakeover510"),
        lambda: rsshub("KOREA", "公式X · RSSHub", "/twitter/user/stylight_kr"),
    ]
    sources.extend(
        lambda region=region, platform=platform, urls=urls, tokens=tokens: cms_source(region, platform, urls, tokens)
        for region, platform, urls, tokens in CMS_SOURCES
    )

    fresh = []
    # Independent sources are I/O bound, so collect them concurrently. This cuts a
    # refresh from the sum of all source timeouts to roughly the slowest source.
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(sources))) as pool:
        futures = [pool.submit(fn) for fn in sources]
        for future in concurrent.futures.as_completed(futures):
            try:
                fresh.extend(future.result())
            except Exception as e:
                print(f"source failed: {e}")

    fresh_regions = {x.get("region") for x in fresh}
    for region in {"JAPAN", "CHINA", "GLOBAL", "KOREA"}:
        if region not in fresh_regions:
            fresh.extend([x for x in existing if x.get("region") == region])

    dedup = {}
    for row in fresh:
        url = row.get("sourceUrl")
        if not url:
            continue
        title_lower = str(row.get("title") or "").casefold()
        if str(row.get("platform") or "") == "公式YouTube" and any(
            token in title_lower for token in UNRELATED_YOUTUBE_TITLES
        ):
            print(f"skipped unrelated YouTube item: {row.get('title')}")
            continue
        row.pop("translatedTitle", None)
        row.pop("translatedBody", None)
        # Old caches used Python's randomized hash(). Rewrite every ID to a stable
        # URL-derived value so local translation/summary caches survive refreshes.
        row["id"] = stable_id(url)
        if is_placeholder_image(row.get("imageUrl")):
            row["imageUrl"] = official_fallback_image(row.get("region"))
        dedup[url] = row

    rows = sorted(
        dedup.values(),
        key=lambda x: int(x.get("publishedAtEpoch") or 0),
        reverse=True,
    )[:80]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {}
    for row in rows:
        key = f"{row.get('region')} / {row.get('platform')}"
        counts[key] = counts.get(key, 0) + 1
    print(f"wrote {len(rows)} original-language items")
    for key, count in sorted(counts.items()):
        print(f"  {key}: {count}")


if __name__ == "__main__":
    main()
