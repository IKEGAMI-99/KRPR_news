#!/usr/bin/env python3
import concurrent.futures
import hashlib
import html
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "news.json"
UA = "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/140 Safari/537.36 KiraparaNews-SocialRepair/1.0"

# Keep the first two hosts separate from the older pool: as of 2026-08 they
# advertise active Twitter/Bilibili routes and give us an independent recovery
# path when the long-used public RSSHub instances are unhealthy.
RSSHUB_HOSTS = [
    "https://rsshub.xqmmcqs.com",
    "https://rsshub.edwardcc.com",
    "https://rsshub.yfi.moe",
    "https://rsshub.stsecurity.moe",
    "https://rsshub.isrss.com",
    "https://rsshub.rssforever.com",
]

# rss.xxu.do is useful for X but does not consistently expose Bilibili routes.
# Keep it out of the common pool so a predictable 404 does not add noise to every
# Bilibili refresh.
X_RSSHUB_HOSTS = ["https://rss.xxu.do", *RSSHUB_HOSTS]

X_ACCOUNTS = [
    ("JAPAN", "kirapara_JP"),
    ("GLOBAL", "LifeMakeover510"),
    ("KOREA", "stylight_kr"),
]
BILIBILI_UID = "676200579"


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def request_text(url: str, timeout: int = 12) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.5",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8,zh-CN;q=0.7,ko;q=0.6",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, errors="replace")
        except LookupError:
            return raw.decode("utf-8", errors="replace")


def strip_tags(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def compact_title(value: str) -> str:
    value = strip_tags(value)
    value = re.sub(r"https?://\S+", "", value).strip()
    if not value:
        return "新着ニュース"
    first = re.split(r"[\n。！？!?]", value, maxsplit=1)[0].strip()
    if len(first) < 6:
        first = value.replace("\n", " ")
    return first[:120].rstrip(" ,，、-｜|")


def parse_epoch(value: str) -> int:
    if not value:
        return 0
    value = value.strip()
    try:
        return int(parsedate_to_datetime(value).timestamp())
    except Exception:
        pass
    try:
        from datetime import datetime
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except Exception:
        return 0


def relative_label(epoch: int) -> str:
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


def first_text(entry, names) -> str:
    for child in entry.iter():
        if child.tag.split("}")[-1] in names and child.text:
            return child.text.strip()
    return ""


def normalize_url(base: str, value: str | None) -> str | None:
    if not value:
        return None
    value = html.unescape(value.strip())
    if value.startswith("//"):
        value = "https:" + value
    return urllib.parse.urljoin(base, value)


def image_from_entry(entry, body_raw: str, link: str) -> str | None:
    for child in entry.iter():
        local = child.tag.split("}")[-1].lower()
        candidate = child.attrib.get("url")
        medium = (child.attrib.get("medium") or "").lower()
        mime = (child.attrib.get("type") or "").lower()
        if candidate and (local == "thumbnail" or medium == "image" or mime.startswith("image")):
            return normalize_url(link, candidate)
    match = re.search(r'<img[^>]+(?:src|data-src|data-original)=["\']([^"\']+)', body_raw or "", re.I)
    return normalize_url(link, match.group(1)) if match else None


def parse_feed(xml_text: str, region: str, platform: str, limit: int = 18):
    root = ET.fromstring(xml_text)
    entries = [e for e in root if e.tag.endswith("entry")] if root.tag.endswith("feed") else root.findall(".//item")
    rows = []
    for entry in entries[:limit]:
        raw_title = first_text(entry, {"title"})
        body_raw = first_text(entry, {"description", "summary", "content", "encoded"})
        published = first_text(entry, {"published", "updated", "pubDate", "date"})
        link = ""
        for child in entry.iter():
            if child.tag.split("}")[-1] == "link":
                link = child.attrib.get("href") or (child.text or "").strip()
                if link:
                    break
        if not link:
            guid = first_text(entry, {"guid", "id"})
            if guid.startswith("http"):
                link = guid
        if not link or not raw_title:
            continue
        link = html.unescape(link)
        if platform == "公式X":
            link = re.sub(r"^https?://(?:www\.)?(?:twitter|x)\.com/", "https://x.com/", link, flags=re.I)
        body = strip_tags(body_raw) or strip_tags(raw_title)
        body = re.sub(r"https?://\S+", "", body).strip()
        epoch = parse_epoch(published)
        rows.append({
            "id": stable_id(link),
            "region": region,
            "platform": platform,
            "title": compact_title(raw_title),
            "body": body[:2200],
            "sourceUrl": link,
            "publishedLabel": relative_label(epoch),
            "publishedAtEpoch": epoch,
            "imageUrl": image_from_entry(entry, body_raw, link),
        })
    return rows


def canonical_source_url(platform: str, value: str) -> str:
    value = html.unescape(str(value or "").strip())
    if platform != "公式X":
        return value
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return value
    if parsed.hostname and parsed.hostname.lower().removeprefix("www.") in {"x.com", "twitter.com"}:
        match = re.match(r"^/([^/]+)/status/(\d+)", parsed.path, re.I)
        if match:
            return f"https://x.com/{match.group(1)}/status/{match.group(2)}"
    return value


def merge_feed_rows(platform: str, feeds, limit: int = 20):
    """Merge healthy mirrors instead of trusting the quickest non-empty feed.

    Public RSSHub mirrors can return HTTP 200 with an old cached timeline.  The
    previous first-success policy therefore treated a stale mirror as success
    and silently skipped newer X posts.  Combining every healthy response makes
    the freshest post from any mirror win while still retaining a useful feed
    when some mirrors lag.
    """
    merged = {}
    for rows in feeds:
        for incoming in rows:
            if not isinstance(incoming, dict):
                continue
            row = dict(incoming)
            url = canonical_source_url(platform, row.get("sourceUrl") or "")
            if not url:
                continue
            row["sourceUrl"] = url
            row["id"] = stable_id(url)
            previous = merged.get(url)
            if previous is None:
                merged[url] = row
                continue
            previous_score = row_score(previous)
            incoming_score = row_score(row)
            if incoming_score > previous_score:
                merged[url] = row
            elif incoming_score == previous_score and int(row.get("publishedAtEpoch") or 0) > int(previous.get("publishedAtEpoch") or 0):
                merged[url] = row
    return sorted(
        merged.values(),
        key=lambda row: int(row.get("publishedAtEpoch") or 0),
        reverse=True,
    )[:limit]


def fetch_best(region: str, platform: str, routes, hosts=None, limit: int = 20):
    hosts = hosts or RSSHUB_HOSTS

    def fetch_candidate(candidate):
        host, route = candidate
        url = host.rstrip("/") + route
        try:
            rows = parse_feed(request_text(url, timeout=11), region, platform)
            if rows:
                return candidate, rows, None
            return candidate, [], "empty feed"
        except Exception as exc:
            return candidate, [], str(exc)

    candidates = [(host, route) for route in routes for host in hosts]
    feeds = []
    successes = []
    failures = []
    # All candidates start together so comparing mirrors does not make a refresh
    # take the sum of their timeouts.
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(24, len(candidates))) as pool:
        futures = [pool.submit(fetch_candidate, candidate) for candidate in candidates]
        for future in concurrent.futures.as_completed(futures):
            (host, route), rows, error = future.result()
            if rows:
                feeds.append(rows)
                successes.append(f"{host}{route}")
            if error:
                failures.append(f"{host}{route}: {error}")

    rows = merge_feed_rows(platform, feeds, limit=limit)
    if rows:
        latest = int(rows[0].get("publishedAtEpoch") or 0)
        print(
            f"social repair {platform}: {len(rows)} merged from "
            f"{len(successes)}/{len(candidates)} healthy feeds; latest={latest}"
        )
    else:
        print(f"social repair {platform}: no healthy feed ({len(failures)}/{len(candidates)} failed)")
    for error in failures[:3]:
        print(f"  {error}")
    if len(failures) > 3:
        print(f"  ... {len(failures) - 3} more failures")
    return rows


def load_news_text(text: str):
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def load_current():
    try:
        return load_news_text(OUT.read_text(encoding="utf-8"))
    except Exception:
        return []


def is_bilibili(row) -> bool:
    platform = str(row.get("platform") or "").lower()
    source = str(row.get("sourceUrl") or "").lower()
    return "bilibili" in platform or "bilibili.com" in source


def recent_historical_bilibili(max_commits: int = 80):
    try:
        output = subprocess.check_output(
            ["git", "rev-list", f"--max-count={max_commits}", "HEAD", "--", "data/news.json"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        print(f"Bilibili history lookup failed: {exc}")
        return []

    for sha in [line.strip() for line in output.splitlines() if line.strip()]:
        try:
            text = subprocess.check_output(
                ["git", "show", f"{sha}:data/news.json"],
                cwd=ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            continue
        rows = [row for row in load_news_text(text) if isinstance(row, dict) and is_bilibili(row)]
        if rows:
            rows.sort(key=lambda row: int(row.get("publishedAtEpoch") or 0), reverse=True)
            print(f"Bilibili history recovery: {len(rows[:30])} rows from {sha[:8]}")
            return rows[:30]
    print("Bilibili history recovery: no prior rows found")
    return []


def row_score(row) -> int:
    return len(str(row.get("body") or "")) + (500 if row.get("imageUrl") else 0) + (300 if row.get("imageUrls") else 0)


def merge_rows(current, additions):
    merged = {}
    for row in current + additions:
        if not isinstance(row, dict):
            continue
        url = str(row.get("sourceUrl") or "").strip()
        if not url:
            continue
        row = dict(row)
        row["id"] = stable_id(url)
        previous = merged.get(url)
        if previous and row_score(previous) > row_score(row):
            continue
        merged[url] = row
    return sorted(merged.values(), key=lambda row: int(row.get("publishedAtEpoch") or 0), reverse=True)[:220]


def main():
    current = load_current()
    additions = []

    # X: try both the conservative no-replies/no-retweets route and the plain
    # timeline route. Public RSSHub deployments vary in which route parameters
    # they currently support.
    for region, handle in X_ACCOUNTS:
        quoted = urllib.parse.quote(handle)
        additions.extend(fetch_best(region, "公式X", [
            f"/twitter/user/{quoted}/exclude_rts_replies",
            f"/twitter/user/{quoted}",
        ], hosts=X_RSSHUB_HOSTS))

    # Bilibili: dynamic posts carry most announcements; article/video routes are
    # additional coverage. If every live endpoint is down, Git history below
    # prevents a temporary outage from deleting the source from the app.
    additions.extend(fetch_best("CHINA", "公式Bilibili · 動態", [
        f"/bilibili/user/dynamic/{BILIBILI_UID}",
    ]))
    additions.extend(fetch_best("CHINA", "公式Bilibili · 記事", [
        f"/bilibili/user/article/{BILIBILI_UID}",
    ]))
    additions.extend(fetch_best("CHINA", "公式Bilibili · 動画", [
        f"/bilibili/user/video/{BILIBILI_UID}",
    ]))

    historical_bilibili = recent_historical_bilibili()
    additions.extend(historical_bilibili)

    rows = merge_rows(current, additions)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    x_count = sum(1 for row in rows if row.get("platform") == "公式X")
    bili_count = sum(1 for row in rows if is_bilibili(row))
    print(f"social repair merged: current={len(current)} additions={len(additions)} total={len(rows)} X={x_count} Bilibili={bili_count}")


if __name__ == "__main__":
    main()
