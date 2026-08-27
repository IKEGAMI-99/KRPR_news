#!/usr/bin/env python3
import concurrent.futures
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
UA = "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36"

BASE62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
WEIBO_HOSTS = ("weibo.com", "m.weibo.cn")
IMAGE_HOST_SUFFIXES = ("sinaimg.cn", "sinaimg.com")
BAD_IMAGE_TOKENS = (
    "avatar", "portrait", "head", "face", "icon", "logo", "badge", "emoji",
    "emoticon", "default", "qrcode", "qr-code", "sprite", "loading",
)
GOOD_SIZE_PATHS = ("/large/", "/bmiddle/", "/mw1024/", "/mw690/", "/orj960/", "/orj1080/")


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def request_text(url: str, timeout: int = 10, accept: str = "text/html,*/*;q=0.8", referer: str = "https://m.weibo.cn/") -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": accept,
        "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7",
        "Referer": referer,
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(6_000_000)
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, errors="replace")
        except LookupError:
            return raw.decode("utf-8", errors="replace")


def request_json(url: str, timeout: int = 10, referer: str = "https://m.weibo.cn/"):
    return json.loads(request_text(url, timeout=timeout, accept="application/json,text/plain,*/*", referer=referer))


def is_weibo_row(row: dict) -> bool:
    if str(row.get("region") or "").upper() != "CHINA":
        return False
    platform = str(row.get("platform") or "").lower()
    source_url = str(row.get("sourceUrl") or "")
    try:
        host = urllib.parse.urlparse(source_url).netloc.lower().removeprefix("www.")
    except Exception:
        host = ""
    return "weibo" in platform or any(host == value or host.endswith("." + value) for value in WEIBO_HOSTS)


def post_token(source_url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(source_url)
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            return ""
        if parts[0] in {"detail", "status", "statuses"} and len(parts) >= 2:
            return parts[1]
        # Standard desktop URL: /<uid>/<bid>
        if len(parts) >= 2 and re.fullmatch(r"[0-9A-Za-z]+", parts[-1]):
            return parts[-1]
        if len(parts) == 1 and re.fullmatch(r"[0-9A-Za-z]+", parts[0]):
            return parts[0]
    except Exception:
        pass
    return ""


def base62_decode(value: str) -> int:
    number = 0
    for char in value:
        index = BASE62.find(char)
        if index < 0:
            raise ValueError(char)
        number = number * 62 + index
    return number


def bid_to_mid(bid: str) -> str:
    """Convert the base62 token used in desktop Weibo URLs to numeric mid."""
    if not bid or bid.isdigit():
        return bid
    parts = []
    end = len(bid)
    while end > 0:
        start = max(0, end - 4)
        block = str(base62_decode(bid[start:end]))
        if start > 0:
            block = block.zfill(7)
        parts.append(block)
        end = start
    return "".join(reversed(parts))


def normalize_image(raw, base: str = "https://m.weibo.cn/") -> str | None:
    if isinstance(raw, dict):
        for key in ("url", "src", "pic", "cover", "poster"):
            if raw.get(key):
                raw = raw.get(key)
                break
    if not isinstance(raw, str) or not raw.strip():
        return None
    value = html.unescape(raw.strip()).replace("\\/", "/")
    if value.startswith("//"):
        value = "https:" + value
    try:
        value = urllib.parse.urljoin(base, value)
        parsed = urllib.parse.urlparse(value)
        host = parsed.netloc.lower()
        if parsed.scheme not in ("http", "https") or not host:
            return None
        if not any(host == suffix or host.endswith("." + suffix) for suffix in IMAGE_HOST_SUFFIXES):
            return None
        if parsed.scheme == "http":
            parsed = parsed._replace(scheme="https")
            value = urllib.parse.urlunparse(parsed)
        low = urllib.parse.unquote(value).lower()
        if any(token in low for token in BAD_IMAGE_TOKENS):
            return None
        # Prefer original/large artwork when Weibo exposes a small display-size path.
        for small in ("/thumbnail/", "/square/", "/thumb150/"):
            if small in value:
                value = value.replace(small, "/large/")
                break
        return value
    except Exception:
        return None


def add_image(found: list[str], raw, base: str) -> None:
    value = normalize_image(raw, base)
    if value and value not in found:
        found.append(value)


def collect_pic_object(value, found: list[str], base: str) -> None:
    if not isinstance(value, dict):
        add_image(found, value, base)
        return
    for key in ("largest", "large", "original", "bmiddle", "mw1024", "mw690", "url", "src"):
        if key in value:
            add_image(found, value.get(key), base)


def collect_status(status, found: list[str], base: str) -> None:
    if not isinstance(status, dict):
        return

    for key in ("original_pic", "bmiddle_pic", "thumbnail_pic"):
        add_image(found, status.get(key), base)

    pics = status.get("pics")
    if isinstance(pics, list):
        for pic in pics:
            collect_pic_object(pic, found, base)

    pic_infos = status.get("pic_infos")
    if isinstance(pic_infos, dict):
        for pic in pic_infos.values():
            collect_pic_object(pic, found, base)

    page_info = status.get("page_info")
    if isinstance(page_info, dict):
        for key in ("page_pic", "page_pic2", "page_pic_2", "cover", "poster"):
            add_image(found, page_info.get(key), base)
        media_info = page_info.get("media_info")
        if isinstance(media_info, dict):
            for key in ("poster", "preview_image", "cover_image", "page_pic", "video_cover"):
                add_image(found, media_info.get(key), base)

    mix = status.get("mix_media_info")
    if isinstance(mix, dict):
        for item in mix.get("items") or []:
            if not isinstance(item, dict):
                continue
            data = item.get("data") if isinstance(item.get("data"), dict) else item
            collect_pic_object(data, found, base)
            for key in ("cover", "poster", "page_pic"):
                add_image(found, data.get(key), base)

    retweeted = status.get("retweeted_status")
    if isinstance(retweeted, dict):
        collect_status(retweeted, found, base)


def status_candidates(source_url: str) -> list[str]:
    token = post_token(source_url)
    if not token:
        return []
    values = [token]
    try:
        mid = bid_to_mid(token)
        if mid and mid not in values:
            values.append(mid)
    except Exception:
        pass
    return values


def fetch_status_json(source_url: str) -> tuple[list[str], str]:
    found: list[str] = []
    for value in status_candidates(source_url):
        endpoints = [
            ("m-status", "https://m.weibo.cn/statuses/show?" + urllib.parse.urlencode({"id": value}), "https://m.weibo.cn/"),
            ("ajax-status", "https://weibo.com/ajax/statuses/show?" + urllib.parse.urlencode({"id": value}), source_url),
        ]
        for method, url, referer in endpoints:
            try:
                payload = request_json(url, referer=referer)
            except Exception:
                continue
            if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
                status = payload.get("data")
            else:
                status = payload
            collect_status(status, found, source_url)
            if found:
                return found[:20], method
    return [], "none"


def fetch_html_images(source_url: str) -> tuple[list[str], str]:
    token = post_token(source_url)
    pages = []
    if token:
        pages.append((f"https://m.weibo.cn/detail/{urllib.parse.quote(token)}", "m-detail"))
    pages.append((source_url, "desktop-html"))

    for page_url, method in pages:
        try:
            page = request_text(page_url, timeout=10, referer="https://m.weibo.cn/")
        except Exception:
            continue
        page = html.unescape(page).replace("\\/", "/")
        found: list[str] = []
        patterns = (
            r'https?://[^\s"\'<>]+?sinaimg\.(?:cn|com)/[^\s"\'<>]+?\.(?:jpe?g|png|webp)(?:\?[^\s"\'<>]*)?',
            r'//[^\s"\'<>]+?sinaimg\.(?:cn|com)/[^\s"\'<>]+?\.(?:jpe?g|png|webp)(?:\?[^\s"\'<>]*)?',
        )
        for pattern in patterns:
            for match in re.finditer(pattern, page, re.I):
                add_image(found, match.group(0), page_url)
        # Put obvious large/original paths first when serialized HTML contains both.
        found.sort(key=lambda url: 0 if any(hint in url.lower() for hint in GOOD_SIZE_PATHS) else 1)
        if found:
            return found[:20], method
    return [], "none"


def normalized_existing(row: dict) -> list[str]:
    base = str(row.get("sourceUrl") or "https://m.weibo.cn/")
    values = []
    if isinstance(row.get("imageUrls"), list):
        values.extend(row.get("imageUrls") or [])
    if row.get("imageUrl"):
        values.append(row.get("imageUrl"))
    found: list[str] = []
    for raw in values:
        add_image(found, raw, base)
    return found[:20]


def enrich_one(row: dict) -> tuple[str, list[str], str]:
    source_url = str(row.get("sourceUrl") or "")
    images, method = fetch_status_json(source_url)
    if not images:
        images, method = fetch_html_images(source_url)
    existing = normalized_existing(row)
    merged = []
    for url in images + existing:
        if url not in merged:
            merged.append(url)
    return source_url, merged[:20], method


def main() -> None:
    rows = read_json(NEWS_PATH, [])
    if not isinstance(rows, list):
        rows = []

    targets = [row for row in rows if is_weibo_row(row) and row.get("sourceUrl")]
    results: dict[str, tuple[list[str], str]] = {}
    if targets:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(targets))) as pool:
            future_map = {pool.submit(enrich_one, row): str(row.get("sourceUrl") or "") for row in targets}
            for future in concurrent.futures.as_completed(future_map):
                source_url = future_map[future]
                try:
                    _url, images, method = future.result()
                except Exception as exc:
                    print(f"Weibo native image fallback failed {source_url}: {exc}")
                    images, method = [], "error"
                results[source_url] = (images, method)

    changed = 0
    recovered = 0
    multi = 0
    methods: dict[str, int] = {}
    for row in rows:
        source_url = str(row.get("sourceUrl") or "")
        if source_url not in results:
            continue
        images, method = results[source_url]
        methods[method] = methods.get(method, 0) + 1
        before = list(row.get("imageUrls") or []) if isinstance(row.get("imageUrls"), list) else []
        before_has = bool(before or row.get("imageUrl"))
        if images:
            row["imageUrls"] = images
            row["imageUrl"] = images[0]
            if images != before:
                changed += 1
            if not before_has:
                recovered += 1
            if len(images) > 1:
                multi += 1

    write_json(NEWS_PATH, rows)
    print(f"Weibo native image enrichment: targets={len(targets)} changed={changed} recovered={recovered} multi={multi}")
    print("Weibo methods: " + ", ".join(f"{key}={value}" for key, value in sorted(methods.items())))


if __name__ == "__main__":
    main()
