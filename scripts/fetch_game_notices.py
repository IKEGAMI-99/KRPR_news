#!/usr/bin/env python3
"""Build a dedicated cache for Japanese in-game/login-screen notices.

The public Japanese client notices are backed by Archosaur's JEECMS pages.
Those pages are also collected into the main news feed, but the main feed is
aggressively capped and social posts can push older official notices out.  This
script keeps a small, independent last-known-good cache for the collapsible
"ゲームアプリ内お知らせ" panel.
"""

from __future__ import annotations

import concurrent.futures
import json
from pathlib import Path

from fetch_news import (
    article_links,
    extract_article_body,
    extract_article_epoch,
    extract_article_title,
    get,
    image_from_html,
    rel_label,
    stable_id,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "game_notices.json"
NEWS_PATH = ROOT / "data" / "news.json"

INDEX_URLS = (
    "https://cms.archosaur.com/jeecms/smhwjpnews/index.jhtml",
    "https://cms.archosaur.com/jeecms/smhwjpevent/index.jhtml",
    "https://kirapara.archosaur.com/",
)
PATH_TOKENS = ("/smhwjpnews/", "/smhwjpevent/")

# These known-good article pages are a resilience floor when JEECMS list pages
# return 5xx.  Live index discovery always takes precedence when it works.
DIRECT_FALLBACKS = (
    "https://cms.archosaur.com/jeecms/smhwjpevent/5903.jhtml",
    "https://cms.archosaur.com/jeecms/smhwjpnews/5875.jhtml",
    "https://cms.archosaur.com/jeecms/smhwjpevent/5876.jhtml",
    "https://cms.archosaur.com/jeecms/smhwjpevent/5852.jhtml",
    "https://cms.archosaur.com/jeecms/smhwjpevent/5832.jhtml",
    "https://cms.archosaur.com/jeecms/smhwjpevent/5677.jhtml",
    "https://cms.archosaur.com/jeecms/smhwjpnews/5570.jhtml",
    "https://cms.archosaur.com/jeecms/smhwjpnews/5528.jhtml",
)
MAX_CANDIDATES = 18
MAX_OUTPUT = 10


def load_json_list(path: Path) -> list[dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except Exception:
        return []


def is_notice_url(value: str | None) -> bool:
    value = str(value or "")
    return value.startswith("https://cms.archosaur.com/jeecms/smhwjpnews/") or value.startswith(
        "https://cms.archosaur.com/jeecms/smhwjpevent/"
    )


def candidate_urls() -> list[str]:
    urls: list[str] = []

    for index_url in INDEX_URLS:
        try:
            page = get(index_url, timeout=12)
            urls.extend(article_links(page, index_url, PATH_TOKENS))
        except Exception as exc:
            print(f"game notice index failed {index_url}: {exc}")

    # Preserve any official pages that survived in the main feed, even if the
    # live indexes are currently unhealthy.
    for row in load_json_list(NEWS_PATH):
        url = row.get("sourceUrl")
        if is_notice_url(url):
            urls.append(url)

    # Keep previously discovered URLs and a small hard-coded resilience floor.
    for row in load_json_list(OUT):
        url = row.get("sourceUrl")
        if is_notice_url(url):
            urls.append(url)
    urls.extend(DIRECT_FALLBACKS)

    return list(dict.fromkeys(urls))[:MAX_CANDIDATES]


def fetch_notice(url: str) -> dict | None:
    try:
        page = get(url, timeout=12)
        title = extract_article_title(page, "JAPAN")
        if not title or title == "新着ニュース":
            return None
        body = extract_article_body(page, "JAPAN") or title
        epoch = extract_article_epoch(page)
        return {
            "id": stable_id(url),
            "region": "JAPAN",
            "platform": "ゲーム内お知らせ",
            "noticeType": "event" if "/smhwjpevent/" in url else "news",
            "title": title,
            "body": body[:1800],
            "sourceUrl": url,
            "publishedLabel": rel_label(epoch),
            "publishedAtEpoch": epoch,
            "imageUrl": image_from_html(page, url),
        }
    except Exception as exc:
        print(f"game notice article failed {url}: {exc}")
        return None


def main() -> None:
    existing = {row.get("sourceUrl"): row for row in load_json_list(OUT) if is_notice_url(row.get("sourceUrl"))}
    urls = candidate_urls()
    if not urls and existing:
        print(f"no new candidates; keeping {len(existing)} cached game notices")
        return
    if not urls:
        raise SystemExit("no game notice candidates discovered")

    rows: list[dict] = []
    workers = min(6, len(urls))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(fetch_notice, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_map):
            url = future_map[future]
            row = future.result()
            if row:
                rows.append(row)
            elif url in existing:
                rows.append(existing[url])

    # If every request failed, leave the last-known-good file untouched.
    if not rows:
        if existing:
            print(f"all requests failed; keeping {len(existing)} cached game notices")
            return
        raise SystemExit("failed to fetch all game notices")

    deduped = {row.get("sourceUrl"): row for row in rows if row.get("sourceUrl")}
    output = sorted(
        deduped.values(),
        key=lambda row: int(row.get("publishedAtEpoch") or 0),
        reverse=True,
    )[:MAX_OUTPUT]
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved {len(output)} game app notices")


if __name__ == "__main__":
    main()
