#!/usr/bin/env python3
import concurrent.futures
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36 KiraparaNews-XImageRepair/1.0"
MAX_DIRECT = 18


def status_id(url: str) -> str:
    match = re.search(r"/(?:status|statuses)/(\d+)", str(url or ""))
    return match.group(1) if match else ""


def is_x_status_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(str(url or ""))
    except Exception:
        return False
    host = parsed.netloc.lower().removeprefix("www.")
    return host in {"x.com", "twitter.com"} and bool(status_id(url))


def request_json(url: str, timeout: int = 7):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9,ko;q=0.8,ja;q=0.7",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(4_000_000)
        return json.loads(raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace"))


def normalize_twimg(raw: str) -> str:
    value = str(raw or "").replace("\\/", "/").strip()
    if not value.startswith(("http://", "https://")):
        return ""
    try:
        parsed = urllib.parse.urlparse(value)
    except Exception:
        return ""
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host != "pbs.twimg.com":
        return ""
    if not any(token in path for token in ("/media/", "/amplify_video_thumb/", "/ext_tw_video_thumb/")):
        return ""

    query = urllib.parse.parse_qs(parsed.query)
    if "/media/" in path:
        fmt = (query.get("format") or [""])[0].lower()
        if not fmt:
            suffix = Path(parsed.path).suffix.lower().lstrip(".")
            if suffix in {"jpg", "jpeg", "png", "webp"}:
                fmt = "jpg" if suffix == "jpeg" else suffix
        if fmt in {"jpg", "jpeg", "png", "webp"}:
            query["format"] = ["jpg" if fmt == "jpeg" else fmt]
        query["name"] = ["orig"]
        encoded = urllib.parse.urlencode([(key, item) for key, values in query.items() for item in values])
        return urllib.parse.urlunparse(("https", parsed.netloc, parsed.path, "", encoded, ""))
    return urllib.parse.urlunparse(("https", parsed.netloc, parsed.path, "", parsed.query, ""))


def collect_twimg(value, found: list[str] | None = None) -> list[str]:
    if found is None:
        found = []
    if isinstance(value, dict):
        for child in value.values():
            collect_twimg(child, found)
    elif isinstance(value, list):
        for child in value:
            collect_twimg(child, found)
    elif isinstance(value, str):
        candidate = normalize_twimg(value)
        if candidate and candidate not in found:
            found.append(candidate)
    return found[:20]


def fetch_direct_images(source_url: str) -> list[str]:
    tweet_id = status_id(source_url)
    if not tweet_id:
        return []

    endpoints = (
        f"https://api.fxtwitter.com/status/{tweet_id}",
        f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&lang=en",
    )
    last_error = None
    for endpoint in endpoints:
        try:
            images = collect_twimg(request_json(endpoint))
            if images:
                return images
        except Exception as exc:
            last_error = exc
    if last_error:
        print(f"X direct image fallback failed {tweet_id}: {last_error}")
    return []


def has_images(row: dict) -> bool:
    return bool(row.get("imageUrl") or (isinstance(row.get("imageUrls"), list) and row.get("imageUrls")))


def sanitize_sources(row: dict) -> bool:
    source_url = str(row.get("sourceUrl") or "")
    if not is_x_status_url(source_url):
        return False

    own = {
        "platform": str(row.get("platform") or "公式X"),
        "label": "X",
        "url": source_url,
    }
    cleaned = [own]
    seen = {source_url}
    for source in row.get("sources") or []:
        if not isinstance(source, dict):
            continue
        url = str(source.get("url") or "").strip()
        if not url or url in seen:
            continue
        # Old over-merges left several different X status URLs attached to one
        # card. Keep cross-platform sources, but never keep another X status.
        if is_x_status_url(url):
            continue
        seen.add(url)
        cleaned.append(source)

    old_sources = row.get("sources") if isinstance(row.get("sources"), list) else []
    old_count = int(row.get("sourceCount") or 0)
    changed = cleaned != old_sources or old_count != len(cleaned)
    if changed:
        row["sources"] = cleaned
        row["sourceCount"] = len(cleaned)
    return changed


def main():
    try:
        rows = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
    except Exception:
        rows = []
    if not isinstance(rows, list):
        rows = []

    changed = 0
    for row in rows:
        if isinstance(row, dict) and sanitize_sources(row):
            changed += 1

    missing = [
        row for row in rows
        if isinstance(row, dict)
        and str(row.get("platform") or "").startswith("公式X")
        and is_x_status_url(row.get("sourceUrl"))
        and not has_images(row)
    ]
    missing.sort(key=lambda row: int(row.get("publishedAtEpoch") or 0), reverse=True)
    missing = missing[:MAX_DIRECT]

    recovered = 0
    if missing:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(missing))) as pool:
            future_map = {
                pool.submit(fetch_direct_images, str(row.get("sourceUrl") or "")): row
                for row in missing
            }
            for future in concurrent.futures.as_completed(future_map):
                row = future_map[future]
                try:
                    images = future.result()
                except Exception:
                    images = []
                if not images:
                    continue
                row["imageUrls"] = images
                row["imageUrl"] = images[0]
                recovered += 1
                changed += 1

    if changed:
        NEWS_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"X split-source cleanup/image repair: changed={changed}; images recovered={recovered}/{len(missing)}")


if __name__ == "__main__":
    main()
