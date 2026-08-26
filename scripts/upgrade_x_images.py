#!/usr/bin/env python3
import json
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"


def upgrade(url):
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return url
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return url

    host = parsed.netloc.lower().split(":", 1)[0]
    if host not in {"pbs.twimg.com", "pbs.twimg.com"}:
        return url

    # X/Twitter media links commonly arrive from RSS mirrors with name=small,
    # medium or 360x360. The same public image endpoint accepts name=orig and
    # returns the original uploaded artwork without using the X API.
    if not parsed.path.startswith(("/media/", "/tweet_video_thumb/", "/ext_tw_video_thumb/")):
        return url

    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    query["name"] = ["orig"]
    new_query = urllib.parse.urlencode(query, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def main():
    try:
        rows = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
    except Exception:
        rows = []
    if not isinstance(rows, list):
        rows = []

    changed = 0
    for row in rows:
        if row.get("platform") != "公式X":
            continue

        old_main = row.get("imageUrl")
        new_main = upgrade(old_main)
        if new_main != old_main:
            row["imageUrl"] = new_main
            changed += 1

        values = row.get("imageUrls") if isinstance(row.get("imageUrls"), list) else []
        upgraded = []
        seen = set()
        for raw in values:
            value = upgrade(raw)
            if not value or value in seen:
                continue
            seen.add(value)
            upgraded.append(value)
        if upgraded != values:
            row["imageUrls"] = upgraded
            changed += 1

    NEWS_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"X original-resolution URL upgrades: {changed}")


if __name__ == "__main__":
    main()
