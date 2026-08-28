#!/usr/bin/env python3
import concurrent.futures
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
DATE_CACHE_PATH = ROOT / "data" / "article_dates.json"
UA = "Mozilla/5.0 KiraparaNews-DateNormalizer/1.1"
GOOGLE_NAMES = ("google news", "googleニュース", "google ニュース")
LEGACY_REMOVED_FIELDS = (
    "earlyInfo",
    "earlyInfoReason",
    "earlyInfoConfidence",
    "importanceScore",
    "weeklyTopic",
)


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical(url: str) -> str:
    try:
        p = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
        query = [(k, v) for k, v in query if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "fbclid"}]
        return urllib.parse.urlunparse((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/") or "/", "", urllib.parse.urlencode(query), ""))
    except Exception:
        return url


def parse_date(value: str) -> int:
    value = (value or "").strip()
    if not value:
        return 0
    value = value.replace("Z", "+00:00")
    try:
        return int(datetime.fromisoformat(value).timestamp())
    except Exception:
        pass
    m = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", value)
    if m:
        try:
            return int(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).timestamp())
        except Exception:
            pass
    return 0


def explicit_published(url: str) -> int:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja,en-US;q=0.8"})
        with urllib.request.urlopen(req, timeout=7) as r:
            page = r.read(2_500_000).decode(r.headers.get_content_charset() or "utf-8", errors="replace")
    except Exception:
        return 0

    patterns = [
        r'<meta[^>]+(?:property|name)=["\'](?:article:published_time|datePublished|datepublished|pubdate|publishdate)["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:article:published_time|datePublished|datepublished|pubdate|publishdate)["\']',
        r'["\']datePublished["\']\s*:\s*["\']([^"\']+)',
    ]
    now = int(time.time())
    for pattern in patterns:
        for match in re.finditer(pattern, page, re.I):
            epoch = parse_date(match.group(1))
            if 1_500_000_000 < epoch <= now + 86400:
                return epoch
    return 0


def label(epoch: int) -> str:
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


def main():
    rows = read_json(NEWS_PATH, [])
    cache = read_json(DATE_CACHE_PATH, {})
    if not isinstance(rows, list):
        rows = []
    if not isinstance(cache, dict):
        cache = {}

    kept = []
    removed_google = 0
    for row in rows:
        url = str(row.get("sourceUrl") or "")
        platform = str(row.get("platform") or "")
        host = urllib.parse.urlparse(url).netloc.lower()
        p_low = platform.lower()
        if host.endswith("news.google.com") or any(name in p_low for name in GOOGLE_NAMES):
            removed_google += 1
            continue
        kept.append(row)

    web_rows = [
        r for r in kept
        if str(r.get("platform") or "").startswith(("Webニュース", "プレスリリース"))
        and str(r.get("sourceUrl") or "").startswith("http")
    ]
    published = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = {
            pool.submit(explicit_published, str(r.get("sourceUrl"))): canonical(str(r.get("sourceUrl")))
            for r in web_rows[:100]
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                published[futures[future]] = future.result()
            except Exception:
                pass

    corrected = 0
    seen_urls = set()
    normalized = []
    for row in kept:
        for field in LEGACY_REMOVED_FIELDS:
            row.pop(field, None)

        url = str(row.get("sourceUrl") or "")
        key = canonical(url)
        if key in seen_urls:
            continue
        seen_urls.add(key)

        current = int(row.get("publishedAtEpoch") or 0)
        page_epoch = int(published.get(key) or 0)
        stored = int(cache.get(key) or 0)

        stable = stored or page_epoch or current
        if stable and stable != current:
            corrected += 1
        if stable:
            cache[key] = stable
            row["publishedAtEpoch"] = stable
            row["publishedLabel"] = label(stable)
        normalized.append(row)

    normalized.sort(key=lambda r: int(r.get("publishedAtEpoch") or 0), reverse=True)
    normalized = normalized[:260]
    live_keys = {canonical(str(r.get("sourceUrl") or "")) for r in normalized}
    cache = {k: v for k, v in cache.items() if k in live_keys}

    write_json(NEWS_PATH, normalized)
    write_json(DATE_CACHE_PATH, cache)
    print(f"Google News proxy rows removed: {removed_google}")
    print(f"article dates stabilized/corrected: {corrected}")
    print(f"normalized news rows: {len(normalized)}")


if __name__ == "__main__":
    main()
