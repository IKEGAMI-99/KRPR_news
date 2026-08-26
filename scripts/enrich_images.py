#!/usr/bin/env python3
import concurrent.futures
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "news.json"
UA = "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/140 Safari/537.36 KiraparaNews-ImageCollector/0.5"

SKIP_PAGE_HOSTS = (
    "x.com", "twitter.com", "youtube.com", "youtu.be", "tiktok.com",
    "instagram.com", "weibo.com", "bilibili.com", "news.google.com",
)

BAD_IMAGE_TOKENS = (
    "favicon", "apple-touch-icon", "siteicon", "site-icon", "logo", "brandmark",
    "avatar", "profile", "author", "qrcode", "qr-code", "qr_code", "/qr/", "_qr.",
    "sprite", "emoji", "emoticon", "sticker", "badge", "button", "loading",
    "spinner", "placeholder", "default_avatar", "default-image", "noimage", "no-image",
    "blank.", "spacer.", "pixel.", "tracking", "tracker", "beacon", "analytics",
    "googleplay", "google-play", "appstore", "app-store", "download_badge",
    "icon_", "/icon/", "/icons/", "share-icon", "social-icon", "footer", "header-logo",
)

GOOD_HINTS = (
    "article", "content", "news", "photo", "image", "img", "media", "gallery",
    "cover", "hero", "visual", "banner", "kv", "main", "upload", "press",
)


def request_text(url: str, timeout: int = 7) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8,ko;q=0.7,zh-CN;q=0.6",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.7",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(4_000_000)
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, errors="replace")
        except LookupError:
            return raw.decode("utf-8", errors="replace")


def normalize(base: str, value: str | None) -> str | None:
    if not value:
        return None
    value = html.unescape(value.strip()).replace("\\/", "/")
    if value.startswith("data:") or value.startswith("blob:"):
        return None
    if value.startswith("//"):
        value = "https:" + value
    try:
        value = urllib.parse.urljoin(base, value)
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        return value
    except Exception:
        return None


def bad_image(url: str | None) -> bool:
    if not url:
        return True
    low = urllib.parse.unquote(url).lower()
    path = urllib.parse.urlparse(low).path
    if path.endswith((".svg", ".ico")):
        return True
    if any(token in low for token in BAD_IMAGE_TOKENS):
        return True
    return False


def attrs(tag: str) -> dict[str, str]:
    out = {}
    for key, _quote, value in re.findall(r"([:\w-]+)\s*=\s*([\"'])(.*?)\2", tag, re.I | re.S):
        out[key.lower()] = html.unescape(value.strip())
    return out


def numeric_dimension(value: str | None) -> int:
    if not value:
        return 0
    m = re.search(r"\d+", value)
    return int(m.group(0)) if m else 0


def srcset_best(value: str | None) -> str | None:
    if not value:
        return None
    choices = []
    for part in value.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        score = 0
        if len(bits) > 1:
            m = re.match(r"(\d+)(?:w|x)?", bits[-1])
            if m:
                score = int(m.group(1))
        choices.append((score, bits[0]))
    if not choices:
        return None
    choices.sort(reverse=True)
    return choices[0][1]


def add_candidate(store: dict[str, int], base: str, raw: str | None, score: int):
    url = normalize(base, raw)
    if not url or bad_image(url):
        return
    store[url] = max(store.get(url, -10_000), score)


def extract_images(page: str, base: str) -> list[str]:
    candidates: dict[str, int] = {}

    # Explicit social/article preview images are normally the best thumbnail.
    meta_patterns = [
        (r'<meta[^>]+(?:property|name)=["\']og:image(?::url)?["\'][^>]+content=["\']([^"\']+)', 1000),
        (r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image(?::url)?["\']', 1000),
        (r'<meta[^>]+(?:property|name)=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)', 900),
        (r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']twitter:image(?::src)?["\']', 900),
    ]
    for pattern, score in meta_patterns:
        for match in re.finditer(pattern, page, re.I):
            add_candidate(candidates, base, match.group(1), score)

    # JSON-LD commonly contains article hero/gallery images even when HTML is lazy-loaded.
    for match in re.finditer(r'["\'](?:image|contentUrl|thumbnailUrl)["\']\s*:\s*["\'](https?:\\?/\\?/[^"\']+)["\']', page, re.I):
        add_candidate(candidates, base, match.group(1), 760)

    # Normal and lazy-loaded article images. Dimensions, class and alt text are used
    # to avoid turning a 64px site icon into a majestic full-width news thumbnail.
    for match in re.finditer(r'<img\b[^>]*>', page, re.I | re.S):
        tag = match.group(0)
        a = attrs(tag)
        raw = (
            a.get("data-original") or a.get("data-src") or a.get("data-lazy-src") or
            a.get("data-url") or srcset_best(a.get("srcset") or a.get("data-srcset")) or
            a.get("src")
        )
        url = normalize(base, raw)
        if not url or bad_image(url):
            continue

        width = numeric_dimension(a.get("width"))
        height = numeric_dimension(a.get("height"))
        if width and height and (width < 220 or height < 120 or width * height < 45_000):
            continue

        context = " ".join((url, a.get("class", ""), a.get("id", ""), a.get("alt", ""))).lower()
        score = 300
        score += sum(45 for hint in GOOD_HINTS if hint in context)
        if width and height:
            score += min(280, (width * height) // 12_000)
        if width >= 600:
            score += 100
        if height >= 300:
            score += 80
        add_candidate(candidates, base, url, score)

    # A few sites use CSS background images for press-release key visuals.
    for match in re.finditer(r'background(?:-image)?\s*:\s*url\(["\']?([^\)"\']+)', page, re.I):
        add_candidate(candidates, base, match.group(1), 350)

    ranked = sorted(candidates.items(), key=lambda pair: pair[1], reverse=True)
    return [url for url, _score in ranked[:20]]


def should_fetch_page(source_url: str) -> bool:
    try:
        host = urllib.parse.urlparse(source_url).netloc.lower()
        return bool(host) and not any(blocked in host for blocked in SKIP_PAGE_HOSTS)
    except Exception:
        return False


def enrich_row(row: dict) -> tuple[dict, bool, bool]:
    row = dict(row)
    source_url = row.get("sourceUrl") or ""
    previous_thumb = row.get("imageUrl")

    seed = []
    current_gallery = row.get("imageUrls")
    if isinstance(current_gallery, list):
        seed.extend(current_gallery)
    if previous_thumb:
        seed.append(previous_thumb)

    images = []
    seen = set()
    for raw in seed:
        url = normalize(source_url, raw)
        if url and not bad_image(url) and url not in seen:
            seen.add(url)
            images.append(url)

    if source_url and should_fetch_page(source_url):
        try:
            page = request_text(source_url)
            discovered = extract_images(page, source_url)
            # Article-derived images outrank legacy feed thumbnails because the latter
            # are where logos/icons most often slipped into the cache.
            for url in reversed(discovered):
                if url in seen:
                    images.remove(url)
                images.insert(0, url)
                seen.add(url)
        except Exception:
            pass

    # Keep a useful gallery but avoid dumping navigation chrome from very image-heavy pages.
    images = images[:20]
    row["imageUrls"] = images
    row["imageUrl"] = images[0] if images else None
    repaired = row.get("imageUrl") != previous_thumb
    multi = len(images) > 1
    return row, repaired, multi


def main():
    try:
        rows = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        rows = []
    if not isinstance(rows, list):
        rows = []

    enriched = []
    repaired = 0
    multi = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=22) as pool:
        futures = [pool.submit(enrich_row, row) for row in rows]
        for future in futures:
            row, was_repaired, has_multi = future.result()
            enriched.append(row)
            repaired += int(was_repaired)
            multi += int(has_multi)

    enriched.sort(key=lambda item: int(item.get("publishedAtEpoch") or 0), reverse=True)
    OUT.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with_images = sum(1 for row in enriched if row.get("imageUrls"))
    print(f"image enrichment: {with_images}/{len(enriched)} items have images")
    print(f"thumbnail repaired/changed: {repaired}")
    print(f"multi-image articles: {multi}")


if __name__ == "__main__":
    main()
