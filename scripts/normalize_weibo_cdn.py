#!/usr/bin/env python3
import json
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
SINA_SUFFIXES = ("sinaimg.cn", "sinaimg.com")
HOST_SHARD = re.compile(r"(?:tvax|tva|wx|ww)(\d+)", re.I)
IMAGE_EXTENSIONS = re.compile(r"\.(?:jpe?g|png|webp|gif|avif)(?:$|[?#])", re.I)
NON_IMAGE_EXTENSIONS = re.compile(
    r"\.(?:js|mjs|css|html?|json|xml|txt|map|woff2?|ttf|otf|ico|svg)(?:$|[?#])",
    re.I,
)
IMAGE_PATH_HINTS = re.compile(
    r"/(?:large|bmiddle|mw\d+|orj\d+|thumbnail|thumb\w*|square\w*)/",
    re.I,
)


def read_rows():
    try:
        value = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    return value if isinstance(value, list) else []


def is_weibo_row(row: dict) -> bool:
    platform = str(row.get("platform") or "").lower()
    source = str(row.get("sourceUrl") or "")
    return "weibo" in platform or "weibo.com/" in source or "m.weibo.cn/" in source


def is_sina_host(host: str) -> bool:
    return any(host == suffix or host.endswith("." + suffix) for suffix in SINA_SUFFIXES)


def canonical_url(raw: str) -> str | None:
    if not isinstance(raw, str) or not raw.startswith(("http://", "https://")):
        return None
    try:
        parsed = urllib.parse.urlparse(raw)
        host = parsed.netloc.lower()
        if not is_sina_host(host):
            return raw

        value = urllib.parse.urlunparse(parsed._replace(scheme="https"))
        decoded_path = urllib.parse.unquote(parsed.path)
        if NON_IMAGE_EXTENSIONS.search(decoded_path):
            return None

        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            return None
        filename = parts[-1]

        # Extension-less Sina artwork is valid, but random JS/CSS/API assets on
        # *.sinaimg.cn must not become article images. Keep extension-less URLs
        # only when the path looks like an actual image-size endpoint or the host
        # is one of Weibo's normal image CDN shards.
        shard_match = HOST_SHARD.search(host)
        has_image_extension = bool(IMAGE_EXTENSIONS.search(decoded_path))
        has_image_path = bool(IMAGE_PATH_HINTS.search(decoded_path))
        if not has_image_extension and not has_image_path and not shard_match:
            return None

        if has_image_extension:
            shard = shard_match.group(1) if shard_match else "1"
            return f"https://wx{shard}.sinaimg.cn/large/{filename}"

        return value
    except Exception:
        return None


def main():
    rows = read_rows()
    changed_rows = 0
    changed_urls = 0
    rejected = 0
    for row in rows:
        if not is_weibo_row(row):
            continue
        original = []
        if isinstance(row.get("imageUrls"), list):
            original.extend(row.get("imageUrls") or [])
        if row.get("imageUrl"):
            original.append(row.get("imageUrl"))

        normalized = []
        for raw in original:
            value = canonical_url(raw)
            if not value:
                if raw:
                    rejected += 1
                continue
            if value in normalized:
                continue
            if value != raw:
                changed_urls += 1
            normalized.append(value)

        before = list(row.get("imageUrls") or []) if isinstance(row.get("imageUrls"), list) else []
        before_first = row.get("imageUrl")
        row["imageUrls"] = normalized[:20]
        row["imageUrl"] = normalized[0] if normalized else None
        if row.get("imageUrls") != before or row.get("imageUrl") != before_first:
            changed_rows += 1

    NEWS_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Weibo CDN normalization: rows={changed_rows} urls={changed_urls} rejected={rejected}")


if __name__ == "__main__":
    main()
