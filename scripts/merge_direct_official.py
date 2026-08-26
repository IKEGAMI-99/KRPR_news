#!/usr/bin/env python3
"""Merge a small set of known-good official CMS articles into data/news.json.

Archosaur's JEECMS list endpoints intermittently return HTTP 500 while the
individual article pages remain public and healthy. The main collector keeps
trying the live indexes; this fallback prevents the timeline from collapsing
back to social/video-only when those indexes are down.
"""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "news.json"
UA = "Mozilla/5.0 KiraparaNews-GitHubCollector/0.3.12"

# Known-good official pages. These are deliberately few: they are a resilient
# fallback, not a replacement for the live index scraper in fetch_news.py.
DIRECT_ARTICLES = [
    ("JAPAN", "https://cms.archosaur.com/jeecms/smhwjpevent/5903.jhtml"),
    ("JAPAN", "https://cms.archosaur.com/jeecms/smhwjpnews/5875.jhtml"),
    ("JAPAN", "https://cms.archosaur.com/jeecms/smhwjpevent/5876.jhtml"),
    ("JAPAN", "https://cms.archosaur.com/jeecms/smhwjpevent/5852.jhtml"),
    ("GLOBAL", "https://cms.archosaur.com/jeecms/smhwpcinhd/5860.jhtml"),
    ("GLOBAL", "https://cms.archosaur.com/jeecms/smhwpcinhd/5802.jhtml"),
]


def get(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, errors="replace")
        except LookupError:
            return raw.decode("utf-8", errors="replace")


def stable_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]


def strip_tags(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def clean_text(value: str) -> str:
    value = strip_tags(value)
    value = re.sub(r"https?://\S+", "", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def normalize_url(base: str, value: str | None) -> str | None:
    if not value:
        return None
    value = html.unescape(value.strip())
    if value.startswith("//"):
        return "https:" + value
    return urllib.parse.urljoin(base, value)


def bad_image(url: str | None) -> bool:
    if not url:
        return True
    low = url.lower()
    return any(
        marker in low
        for marker in (
            "qrcode", "qr_", "qr-", "ewm", "favicon", "icon", "logo",
            "avatar", "download", "appstore", "googleplay", "blank.gif",
            "spacer.gif", "default.png",
        )
    )


def image_from_page(page: str, article_url: str) -> str | None:
    meta_patterns = [
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']',
    ]
    for pattern in meta_patterns:
        match = re.search(pattern, page, re.I)
        if match:
            candidate = normalize_url(article_url, match.group(1))
            if not bad_image(candidate):
                return candidate

    for match in re.finditer(
        r'<img[^>]+(?:data-original|data-src|src)=["\']([^"\']+)["\']',
        page,
        re.I,
    ):
        candidate = normalize_url(article_url, match.group(1))
        if candidate and not candidate.startswith("data:") and not bad_image(candidate):
            return candidate
    return None


def title_from_page(page: str) -> str:
    for pattern in (
        r'<h1[^>]*>(.*?)</h1>',
        r'<meta[^>]+(?:property|name)=["\']og:title["\'][^>]+content=["\']([^"\']+)',
        r'<title[^>]*>(.*?)</title>',
    ):
        match = re.search(pattern, page, re.I | re.S)
        if match:
            title = clean_text(match.group(1))
            if title:
                return title[:140]
    return "公式ニュース"


def parse_epoch(value: str) -> int:
    if not value:
        return 0
    try:
        return int(parsedate_to_datetime(value).timestamp())
    except Exception:
        pass
    normalized = value.replace("/", "-").replace("年", "-").replace("月", "-").replace("日", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    try:
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", normalized):
            normalized += " 00:00:00"
        return int(datetime.fromisoformat(normalized.replace("Z", "+00:00")).timestamp())
    except Exception:
        return 0


def epoch_from_page(page: str) -> int:
    for pattern in (
        r'(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}(?:日)?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)',
        r'content=["\'](20\d{2}-\d{2}-\d{2}T[^"\']+)["\']',
    ):
        match = re.search(pattern, page, re.I)
        if match:
            epoch = parse_epoch(match.group(1))
            if epoch:
                return epoch
    return 0


def rel_label(epoch: int) -> str:
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


def body_from_page(page: str) -> str:
    cleaned = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", page, flags=re.I | re.S)
    chunks: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(r"<(?:p|li)[^>]*>(.*?)</(?:p|li)>", cleaned, flags=re.I | re.S):
        text = clean_text(raw)
        if len(text) < 4 or text in seen:
            continue
        low = text.lower()
        if any(marker in low for marker in ("copyright", "all rights reserved", "follow us", "app store", "google play")):
            continue
        seen.add(text)
        chunks.append(text)
        if sum(len(chunk) for chunk in chunks) >= 2200:
            break
    return "\n".join(chunks)[:1800].strip()


def fetch_article(region: str, url: str) -> dict | None:
    try:
        page = get(url)
        title = title_from_page(page)
        body = body_from_page(page) or title
        epoch = epoch_from_page(page)
        return {
            "id": stable_id(url),
            "region": region,
            "platform": "公式サイト",
            "title": title,
            "body": body,
            "sourceUrl": url,
            "publishedLabel": rel_label(epoch),
            "publishedAtEpoch": epoch,
            "imageUrl": image_from_page(page, url),
        }
    except Exception as exc:
        print(f"direct official failed {url}: {exc}")
        return None


def main() -> None:
    try:
        existing = json.loads(OUT.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            existing = []
    except Exception:
        existing = []

    merged = {row.get("sourceUrl"): row for row in existing if row.get("sourceUrl")}
    added = 0
    for region, url in DIRECT_ARTICLES:
        row = fetch_article(region, url)
        if row:
            merged[url] = row
            added += 1

    rows = sorted(
        merged.values(),
        key=lambda row: int(row.get("publishedAtEpoch") or 0),
        reverse=True,
    )[:80]
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"merged {added} resilient official-site articles; total={len(rows)}")


if __name__ == "__main__":
    main()
