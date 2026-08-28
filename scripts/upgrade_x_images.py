#!/usr/bin/env python3
import json
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"

LEGACY_SIZE_SUFFIX = re.compile(r":(?:thumb|small|medium|large)$", re.I)
X_MEDIA_PREFIXES = ("/media/", "/tweet_video_thumb/", "/ext_tw_video_thumb/")


def upgrade(url):
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return url
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return url

    host = parsed.netloc.lower().split(":", 1)[0]
    if host != "pbs.twimg.com":
        return url
    if not parsed.path.startswith(X_MEDIA_PREFIXES):
        return url

    # Older Twitter feeds can still emit URLs like image.jpg:small.
    # Strip that path suffix before applying the modern size parameter.
    path = LEGACY_SIZE_SUFFIX.sub("", parsed.path)

    # Keep the source format when present, but always request the original upload.
    # parse_qsl preserves unrelated query fields better than parse_qs.
    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    pairs = [(k, v) for k, v in pairs if k.lower() != "name"]
    pairs.append(("name", "orig"))
    query = urllib.parse.urlencode(pairs, doseq=True)

    return urllib.parse.urlunparse(parsed._replace(path=path, query=query))


def main():
    try:
        rows = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
    except Exception:
        rows = []
    if not isinstance(rows, list):
        rows = []

    changed = 0
    upgraded_urls = 0
    for row in rows:
        old_main = row.get("imageUrl")
        new_main = upgrade(old_main)
        if new_main != old_main:
            row["imageUrl"] = new_main
            changed += 1
            upgraded_urls += 1

        values = row.get("imageUrls") if isinstance(row.get("imageUrls"), list) else []
        upgraded = []
        seen = set()
        for raw in values:
            value = upgrade(raw)
            if value != raw:
                upgraded_urls += 1
            if not value or value in seen:
                continue
            seen.add(value)
            upgraded.append(value)
        if upgraded != values:
            row["imageUrls"] = upgraded
            changed += 1

        # Keep imageUrl aligned with the normalized gallery order.
        if upgraded and row.get("imageUrl") != upgraded[0]:
            current = upgrade(row.get("imageUrl"))
            if current in upgraded:
                row["imageUrl"] = current
            elif not row.get("imageUrl"):
                row["imageUrl"] = upgraded[0]

    NEWS_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"X original-resolution URL upgrades: rows={changed} urls={upgraded_urls}")


if __name__ == "__main__":
    main()
