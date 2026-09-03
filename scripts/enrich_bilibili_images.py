#!/usr/bin/env python3
import concurrent.futures
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from bilibili_image_urls import (
    canonicalize_bilibili_image_url,
    is_bilibili_image_host,
)

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"

BILIBILI_HOSTS = ("bilibili.com", "b23.tv")
GOOD_PATH_HINTS = (
    "/bfs/new_dyn/",
    "/bfs/article/",
    "/bfs/archive/",
    "/bfs/album/",
    "/bfs/dynamic/",
)
BAD_PATH_HINTS = (
    "/bfs/face/",
    "/bfs/garb/",
    "/bfs/vip/",
    "/bfs/emote/",
    "avatar",
    "icon",
    "logo",
    "badge",
)


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def request_text(url: str, timeout: int = 10, accept: str = "text/html,*/*;q=0.8") -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": accept,
        "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7",
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(6_000_000)
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, errors="replace")
        except LookupError:
            return raw.decode("utf-8", errors="replace")


def request_json(url: str, timeout: int = 10):
    return json.loads(request_text(url, timeout=timeout, accept="application/json,text/plain,*/*"))


def is_bilibili_row(row: dict) -> bool:
    if str(row.get("region") or "").upper() != "CHINA":
        return False
    platform = str(row.get("platform") or "").lower()
    source_url = str(row.get("sourceUrl") or "")
    try:
        host = urllib.parse.urlparse(source_url).netloc.lower()
    except Exception:
        host = ""
    return "bilibili" in platform or any(host.endswith(value) for value in BILIBILI_HOSTS)


def bilibili_dynamic_id(source_url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(source_url)
        host = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        patterns = (
            r"/(?:opus|dynamic)/(\d+)$",
            r"^/(\d+)$" if host.endswith("t.bilibili.com") else r"$^",
        )
        for pattern in patterns:
            match = re.search(pattern, path, re.I)
            if match:
                return match.group(1)
    except Exception:
        pass
    return ""


def normalize_image(raw, base: str = "https://www.bilibili.com/") -> str | None:
    if not raw:
        return None
    if isinstance(raw, dict):
        raw = raw.get("src") or raw.get("url") or raw.get("cover")
    if not isinstance(raw, str):
        return None
    value = html.unescape(raw.strip()).replace("\\/", "/")
    if value.startswith("//"):
        value = "https:" + value
    try:
        value = urllib.parse.urljoin(base, value)
        value = canonicalize_bilibili_image_url(value)
        parsed = urllib.parse.urlparse(value)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in ("http", "https") or not host:
            return None
        low = urllib.parse.unquote(value).lower()
        if not is_bilibili_image_host(host):
            return None
        if any(token in low for token in BAD_PATH_HINTS):
            return None
        if not any(token in low for token in GOOD_PATH_HINTS):
            return None
        return value
    except Exception:
        return None


def add_image(found: list[str], raw, base: str = "https://www.bilibili.com/") -> None:
    value = normalize_image(raw, base)
    if value and value not in found:
        found.append(value)


def collect_known_media(value, found: list[str], base: str) -> None:
    if isinstance(value, list):
        for item in value:
            collect_known_media(item, found, base)
        return
    if not isinstance(value, dict):
        return

    # Known Bilibili dynamic payload shapes.
    draw = value.get("draw")
    if isinstance(draw, dict):
        for item in draw.get("items") or []:
            if isinstance(item, dict):
                add_image(found, item.get("src") or item.get("url"), base)

    opus = value.get("opus")
    if isinstance(opus, dict):
        for item in opus.get("pics") or []:
            if isinstance(item, dict):
                add_image(found, item.get("url") or item.get("src"), base)

    archive = value.get("archive")
    if isinstance(archive, dict):
        add_image(found, archive.get("cover"), base)

    article = value.get("article")
    if isinstance(article, dict):
        for raw in article.get("covers") or []:
            add_image(found, raw, base)
        add_image(found, article.get("cover"), base)

    common = value.get("common")
    if isinstance(common, dict):
        add_image(found, common.get("cover"), base)

    # Keep walking nested payloads so newly wrapped major blocks still work.
    for child in value.values():
        if isinstance(child, (dict, list)):
            collect_known_media(child, found, base)


def fetch_pic_api(dynamic_id: str, source_url: str) -> list[str]:
    api = "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail/pic?" + urllib.parse.urlencode({"id": dynamic_id})
    payload = request_json(api)
    if not isinstance(payload, dict) or int(payload.get("code") or 0) != 0:
        return []
    found: list[str] = []
    data = payload.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                add_image(found, item.get("src") or item.get("url"), source_url)
    return found[:20]


def fetch_detail_api(dynamic_id: str, source_url: str) -> list[str]:
    features = "itemOpusStyle,opusBigCover,onlyfansVote,endFooterHidden,decorationCard,onlyfansAssetsV2,ugcDelete,onlyfansQaCard,commentsNewVersion"
    query = urllib.parse.urlencode({
        "id": dynamic_id,
        "timezone_offset": -480,
        "platform": "web",
        "features": features,
    })
    api = "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail?" + query
    payload = request_json(api)
    if not isinstance(payload, dict) or int(payload.get("code") or 0) != 0:
        return []
    found: list[str] = []
    collect_known_media(payload.get("data"), found, source_url)
    return found[:20]


def fetch_html_images(source_url: str) -> list[str]:
    try:
        page = request_text(source_url, timeout=10)
    except Exception:
        return []
    page = html.unescape(page).replace("\\/", "/")
    found: list[str] = []
    patterns = (
        r'https?://[^\s"\'<>]+?\.(?:jpe?g|png|webp)(?:@[^\s"\'<>]*)?',
        r'//[^\s"\'<>]+?\.(?:jpe?g|png|webp)(?:@[^\s"\'<>]*)?',
    )
    for pattern in patterns:
        for match in re.finditer(pattern, page, re.I):
            add_image(found, match.group(0), source_url)
    return found[:20]


def fetch_bilibili_images(source_url: str) -> tuple[list[str], str]:
    dynamic_id = bilibili_dynamic_id(source_url)
    if dynamic_id:
        try:
            images = fetch_pic_api(dynamic_id, source_url)
            if images:
                return images, "detail/pic"
        except Exception as exc:
            print(f"Bilibili detail/pic failed {dynamic_id}: {exc}")

        try:
            images = fetch_detail_api(dynamic_id, source_url)
            if images:
                return images, "detail"
        except Exception as exc:
            print(f"Bilibili detail failed {dynamic_id}: {exc}")

    images = fetch_html_images(source_url)
    return images, "html" if images else "none"


def normalized_existing_images(row: dict) -> list[str]:
    source_url = str(row.get("sourceUrl") or "https://www.bilibili.com/")
    values = []
    if isinstance(row.get("imageUrls"), list):
        values.extend(row.get("imageUrls") or [])
    if row.get("imageUrl"):
        values.append(row.get("imageUrl"))
    found: list[str] = []
    for raw in values:
        add_image(found, raw, source_url)
    return found[:20]


def enrich_one(row: dict) -> tuple[str, list[str], str]:
    source_url = str(row.get("sourceUrl") or "")
    images, method = fetch_bilibili_images(source_url)
    existing = normalized_existing_images(row)
    merged = []
    for url in images + existing:
        if url not in merged:
            merged.append(url)
    return source_url, merged[:20], method


def main() -> None:
    rows = read_json(NEWS_PATH, [])
    if not isinstance(rows, list):
        rows = []

    targets = [row for row in rows if is_bilibili_row(row) and row.get("sourceUrl")]
    results: dict[str, tuple[list[str], str]] = {}
    if targets:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(targets))) as pool:
            future_map = {pool.submit(enrich_one, row): str(row.get("sourceUrl") or "") for row in targets}
            for future in concurrent.futures.as_completed(future_map):
                source_url = future_map[future]
                try:
                    _url, images, method = future.result()
                except Exception as exc:
                    print(f"Bilibili image fallback failed {source_url}: {exc}")
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
    print(f"Bilibili native image enrichment: targets={len(targets)} changed={changed} recovered={recovered} multi={multi}")
    print("Bilibili methods: " + ", ".join(f"{key}={value}" for key, value in sorted(methods.items())))


if __name__ == "__main__":
    main()
