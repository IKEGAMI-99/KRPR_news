#!/usr/bin/env python3
import json
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
SINA_SUFFIXES = ("sinaimg.cn", "sinaimg.com")
SIZE_SEGMENTS = re.compile(r"^(?:large|bmiddle|mw\d+|orj\d+|thumb\w*|square\w*)$", re.I)
HOST_SHARD = re.compile(r"(?:tvax|tva|wx|ww)(\d+)", re.I)


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


def canonical_url(raw: str) -> str | None:
    if not isinstance(raw, str) or not raw.startswith(("http://", "https://")):
        return None
    try:
        parsed = urllib.parse.urlparse(raw)
        host = parsed.netloc.lower()
        if not any(host == suffix or host.endswith("." + suffix) for suffix in SINA_SUFFIXES):
            return raw

        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            return raw
        filename = parts[-1]
        if not re.search(r"\.(?:jpe?g|png|webp)$", filename, re.I):
            return raw

        match = HOST_SHARD.search(host)
        shard = match.group(1) if match else "1"
        # Weibo's wx*.sinaimg.cn/large form is considerably more reliable for
        # direct <img> use than RSS-returned tvax*/mw2000 URLs.
        return f"https://wx{shard}.sinaimg.cn/large/{filename}"
    except Exception:
        return raw


def main():
    rows = read_rows()
    changed_rows = 0
    changed_urls = 0
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
            if not value or value in normalized:
                continue
            if value != raw:
                changed_urls += 1
            normalized.append(value)

        before = list(row.get("imageUrls") or []) if isinstance(row.get("imageUrls"), list) else []
        before_first = row.get("imageUrl")
        if normalized:
            row["imageUrls"] = normalized[:20]
            row["imageUrl"] = normalized[0]
        if row.get("imageUrls") != before or row.get("imageUrl") != before_first:
            changed_rows += 1

    NEWS_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Weibo CDN normalization: rows={changed_rows} urls={changed_urls}")


if __name__ == "__main__":
    main()
