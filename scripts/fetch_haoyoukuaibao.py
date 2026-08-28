#!/usr/bin/env python3
import concurrent.futures
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
GAME_PAGE = "https://m.3839.com/a/137078.htm"
UA = "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/140 Mobile Safari/537.36 KiraparaNews-Haoyoukuaibao/1.0"
MAX_POSTS = 18


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def request_text(url: str, timeout: int = 10) -> tuple[str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.7,en;q=0.5",
            "Referer": "https://m.3839.com/",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(5_000_000)
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace"), response.geturl()


def clean_text(value: str) -> str:
    value = value or ""
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</(?:p|div|section|li|h\d|article)\s*>", "\n", value, flags=re.I)
    value = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value).replace("\xa0", " ")
    value = "".join(ch for ch in value if ch in "\n\t" or ord(ch) >= 32)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s*\n\s*\n+", "\n\n", value)
    return value.strip()


def normalize_url(base: str, value: str | None) -> str | None:
    if not value:
        return None
    value = html.unescape(value.strip()).replace("\\/", "/")
    if value.startswith("//"):
        value = "https:" + value
    try:
        url = urllib.parse.urljoin(base, value)
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        return url
    except Exception:
        return None


def meta_value(page: str, name: str) -> str:
    for pattern in (
        rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(name)}["\']',
    ):
        match = re.search(pattern, page or "", re.I)
        if match:
            return clean_text(match.group(1))
    return ""


def parse_epoch(value: str) -> int:
    value = clean_text(value)
    if not value:
        return 0
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
        try:
            return int(datetime.strptime(value, fmt).timestamp())
        except ValueError:
            pass
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except Exception:
        return 0


def article_epoch(page: str) -> int:
    candidates = []
    for pattern in (
        r'<meta[^>]+(?:property|name)=["\'](?:article:published_time|datePublished|pubdate|publishdate)["\'][^>]+content=["\']([^"\']+)',
        r'["\'](?:datePublished|publish_time|created_at|create_time)["\']\s*[:=]\s*["\']([^"\']+)["\']',
        r'<time[^>]+datetime=["\']([^"\']+)["\']',
        r'(20\d{2}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)',
    ):
        candidates.extend(re.findall(pattern, page or "", flags=re.I))
    now = int(time.time())
    for value in candidates:
        epoch = parse_epoch(value)
        if 1_500_000_000 < epoch <= now + 86400:
            return epoch
    return 0


def image_urls(page: str, base: str) -> list[str]:
    found = []
    for name in ("og:image", "twitter:image"):
        value = meta_value(page, name)
        url = normalize_url(base, value)
        if url:
            found.append(url)

    for match in re.finditer(r'<img[^>]+(?:data-original|data-src|src)=["\']([^"\']+)', page or "", re.I):
        url = normalize_url(base, match.group(1))
        if not url:
            continue
        low = urllib.parse.unquote(url).lower()
        if any(token in low for token in ("avatar", "headimg", "logo", "icon", "qrcode", "qr_", "emoji", "blank", "spacer")):
            continue
        if url not in found:
            found.append(url)
        if len(found) >= 12:
            break
    return found[:12]


def discover_official_posts(page: str, limit: int = MAX_POSTS) -> list[dict]:
    normalized = html.unescape((page or "").replace("\\/", "/"))
    marker = re.search(r"官方帖子", normalized, re.I)
    if not marker:
        return []

    start = marker.start()
    end = len(normalized)
    for token in ("相关游戏", "开发者其他游戏", "快爆独家", "每日新发现", "友情链接"):
        pos = normalized.find(token, marker.end())
        if pos != -1:
            end = min(end, pos)
    fragment = normalized[start:end]

    found = []
    for match in re.finditer(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        fragment,
        re.I | re.S,
    ):
        url = normalize_url(GAME_PAGE, match.group(1))
        title = clean_text(match.group(2))
        if not url or not title or len(title) < 5:
            continue
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc.lower() not in {"m.bbs.3839.com", "bbs.3839.com"}:
            continue
        if not re.search(r"/thread-\d+\.htm", parsed.path, re.I):
            continue
        if title in {"查看全部", "官方帖子", "论坛"}:
            continue
        if any(item["url"] == url for item in found):
            continue
        found.append({"url": url, "title": title[:180]})
        if len(found) >= limit:
            break
    return found


def extract_body(page: str, fallback_title: str) -> str:
    for name in ("og:description", "description"):
        value = meta_value(page, name)
        if value and "不支持 JavaScript" not in value and len(value) >= 20:
            return value[:5000]

    for pattern in (
        r'<(?:div|article|section)[^>]+class=["\'][^"\']*(?:thread|post|article|message)[^"\']*(?:content|body|text)[^"\']*["\'][^>]*>(.*?)</(?:div|article|section)>',
        r'<(?:div|article|section)[^>]+class=["\'][^"\']*(?:content|article|post)[^"\']*["\'][^>]*>(.*?)</(?:div|article|section)>',
    ):
        match = re.search(pattern, page or "", re.I | re.S)
        if not match:
            continue
        value = clean_text(match.group(1))
        if len(value) >= 30 and "不支持 JavaScript" not in value:
            return value[:5000]
    return fallback_title


def fetch_article(candidate: dict):
    url = candidate["url"]
    fallback_title = candidate["title"]
    page = ""
    final_url = url
    try:
        page, final_url = request_text(url, timeout=10)
    except Exception as exc:
        print(f"Haoyoukuaibao article failed {url}: {exc}")

    title = meta_value(page, "og:title") if page else ""
    if not title and page:
        match = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.I | re.S)
        if match:
            title = clean_text(match.group(1))
    if not title or title in {"好游快爆论坛", "好游快爆"} or len(title) < 5:
        title = fallback_title

    body = extract_body(page, title) if page else title
    epoch = article_epoch(page) if page else 0
    images = image_urls(page, final_url) if page else []

    return {
        "id": stable_id("haoyoukuaibao:" + final_url),
        "region": "CHINA",
        "platform": "官方好游快爆",
        "title": title[:180],
        "body": body[:5000],
        "sourceUrl": final_url,
        "publishedLabel": time.strftime("%Y-%m-%d", time.localtime(epoch)) if epoch else "好游快爆",
        "publishedAtEpoch": epoch,
        "imageUrl": images[0] if images else None,
        "imageUrls": images,
    }


def merge_rows(existing: list[dict], incoming: list[dict]) -> list[dict]:
    merged = {
        str(row.get("sourceUrl")): row
        for row in existing
        if isinstance(row, dict) and row.get("sourceUrl")
    }
    for row in incoming:
        old = merged.get(row["sourceUrl"])
        if old:
            for key in (
                "titleJa",
                "bodyJa",
                "summaryJa",
                "aiProcessed",
                "aiModel",
                "aiSummaryFormat",
                "managedBySol",
                "solLocked",
            ):
                if old.get(key) and not row.get(key):
                    row[key] = old[key]
            if not row.get("publishedAtEpoch") and old.get("publishedAtEpoch"):
                row["publishedAtEpoch"] = old["publishedAtEpoch"]
                row["publishedLabel"] = old.get("publishedLabel") or row["publishedLabel"]
        merged[row["sourceUrl"]] = row

    return sorted(
        merged.values(),
        key=lambda item: int(item.get("publishedAtEpoch") or 0),
        reverse=True,
    )[:260]


def main():
    try:
        rows = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
    except Exception:
        rows = []
    if not isinstance(rows, list):
        rows = []

    try:
        page, _ = request_text(GAME_PAGE, timeout=12)
        candidates = discover_official_posts(page)
    except Exception as exc:
        print(f"Haoyoukuaibao official page failed: {exc}")
        candidates = []

    print(f"Haoyoukuaibao official candidates: {len(candidates)}")
    added = []
    if candidates:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(candidates))) as pool:
            for row in pool.map(fetch_article, candidates):
                if row:
                    added.append(row)

    final = merge_rows(rows, added)
    NEWS_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"official Haoyoukuaibao articles merged: {len(added)}; total={len(final)}")


if __name__ == "__main__":
    main()
