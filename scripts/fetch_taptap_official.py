#!/usr/bin/env python3
import concurrent.futures
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
TOPIC_URLS = [
    "https://www.taptap.cn/app/218210/topic?type=official",
    "https://www.taptap.cn/app/218210/topic?type=official&page=2",
]
DETAIL_API = "https://www.taptap.cn/webapiv2/moment/v3/detail"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36 KiraparaNews-TapTap/1.0"
X_UA = "V=1&PN=WebApp&LANG=zh_CN&VN_CODE=102&LOC=CN&PLT=PC&DS=Android&UID={uuid}&OS=Windows&OSV=10&DT=PC"
OFFICIAL_AUTHOR_TOKENS = ("vvanna", "以闪亮之名")
MAX_DISCOVERED = 30
MAX_ARTICLE_IMAGES = 12

ARTICLE_IMAGE_PATH_TOKENS = {
    "images",
    "image_list",
    "image_urls",
    "pictures",
    "photos",
    "attachments",
    "attachment",
    "media",
    "cover",
}
ARTICLE_IMAGE_URL_KEYS = {
    "original_url",
    "large_url",
    "full_url",
    "image_url",
}
BLOCKED_IMAGE_PATH_TOKENS = {
    "author",
    "user",
    "avatar",
    "app",
    "game",
    "group",
    "icon",
    "logo",
    "emoji",
    "qrcode",
    "qr_code",
    "badge",
    "medal",
    "recommend",
    "recommended",
    "related",
    "share",
    "follow",
    "user_card",
    "usercard",
    "topic_group",
}
BLOCKED_IMAGE_URL_TOKENS = (
    "/avatar/",
    "/user/avatar",
    "/icon/",
    "/logo/",
    "/emoji/",
    "/qrcode/",
    "/qr_code/",
)


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def request_text(url: str, timeout: int = 10, accept: str = "text/html,*/*;q=0.8") -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": accept,
            "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.7,en;q=0.5",
            "Referer": "https://www.taptap.cn/",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(5_000_000)
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def clean_text(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</(?:p|div|section|li|h\d)\s*>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value).replace("\xa0", " ")
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s*\n\s*\n+", "\n\n", value)
    return value.strip()


def discover_moment_ids(page: str) -> list[str]:
    page = html.unescape(page or "").replace("\\/", "/")
    patterns = (
        r'https?://www\.taptap\.cn/moment/(\d+)',
        r'href=["\']/moment/(\d+)(?:[?"\'])',
        r'["\']/moment/(\d+)(?:\?[^"\']*)?["\']',
    )
    found = []
    for pattern in patterns:
        for moment_id in re.findall(pattern, page, flags=re.I):
            if moment_id not in found:
                found.append(moment_id)
    return found


def discover(limit: int = MAX_DISCOVERED) -> list[str]:
    found = []
    for url in TOPIC_URLS:
        try:
            page = request_text(url, timeout=10)
        except Exception as exc:
            print(f"TapTap official list failed {url}: {exc}")
            continue
        for moment_id in discover_moment_ids(page):
            if moment_id not in found:
                found.append(moment_id)
            if len(found) >= limit:
                break
        if len(found) >= limit:
            break
    print(f"TapTap official candidates: {len(found)}")
    return found


def api_payload(moment_id: str) -> dict:
    params = urllib.parse.urlencode(
        {
            "id": moment_id,
            "X-UA": X_UA.format(uuid=uuid.uuid4()),
        }
    )
    text = request_text(
        DETAIL_API + "?" + params,
        timeout=10,
        accept="application/json,text/plain,*/*",
    )
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("TapTap detail response is not an object")
    return payload


def nested(data, *keys):
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def normalize_epoch(value) -> int:
    try:
        epoch = int(value or 0)
    except (TypeError, ValueError):
        return 0
    if epoch > 10_000_000_000:
        epoch //= 1000
    return epoch if epoch > 1_500_000_000 else 0


def normalize_image_url(value: str) -> str:
    candidate = html.unescape(value or "").replace("\\/", "/").strip()
    if not candidate.startswith(("http://", "https://")):
        return ""
    candidate = re.sub(r"/_tap_[^/?#]+(?=$|[?#])", "", candidate, flags=re.I)
    try:
        parsed = urllib.parse.urlparse(candidate)
    except Exception:
        return ""
    host = parsed.netloc.lower()
    if "tapimg.com" not in host and "tapimg.cn" not in host:
        return ""
    low_url = (parsed.path + "?" + parsed.query).lower()
    if any(token in low_url for token in BLOCKED_IMAGE_URL_TOKENS):
        return ""
    return candidate


def image_path_score(path: tuple[str, ...]) -> int:
    segments = {segment.casefold() for segment in path if segment}
    if segments & BLOCKED_IMAGE_PATH_TOKENS:
        return -100

    score = 0
    if segments & ARTICLE_IMAGE_PATH_TOKENS:
        score += 8
    if segments & ARTICLE_IMAGE_URL_KEYS:
        score += 5
    if path and path[-1].casefold() == "url":
        score += 1
    return score


def collect_image_urls(value) -> list[str]:
    ranked: dict[str, int] = {}

    def walk(node, path=()):
        if isinstance(node, dict):
            for key, child in node.items():
                walk(child, path + (str(key).casefold(),))
            return
        if isinstance(node, list):
            for child in node:
                walk(child, path)
            return
        if not isinstance(node, str):
            return

        score = image_path_score(path)
        if score < 8:
            return
        candidate = normalize_image_url(node)
        if not candidate:
            return
        ranked[candidate] = max(score, ranked.get(candidate, -100))

    walk(value)
    return [url for url, _ in sorted(ranked.items(), key=lambda item: -item[1])][:MAX_ARTICLE_IMAGES]


def article_from_api(payload: dict, moment_id: str):
    data = payload.get("data") if isinstance(payload, dict) else None
    moment = data.get("moment") if isinstance(data, dict) else None
    if not isinstance(moment, dict):
        return None

    topic = moment.get("topic") if isinstance(moment.get("topic"), dict) else {}
    author = clean_text(nested(moment, "author", "user", "name") or "")
    if author and not any(token in author.casefold() for token in OFFICIAL_AUTHOR_TOKENS):
        return None

    title = clean_text(topic.get("title") or "")
    body = clean_text(topic.get("summary") or topic.get("content") or topic.get("text") or "")
    if not title:
        title = re.split(r"[\n。！？!?]", body, maxsplit=1)[0][:120].strip()
    if not body:
        body = title
    if not title:
        return None

    epoch = normalize_epoch(moment.get("created_time"))
    images = collect_image_urls(topic)
    source_url = f"https://www.taptap.cn/moment/{moment_id}"
    return {
        "id": stable_id("taptap:" + moment_id),
        "region": "CHINA",
        "platform": "公式TapTap",
        "title": title[:180],
        "body": body[:5000],
        "sourceUrl": source_url,
        "publishedLabel": time.strftime("%Y-%m-%d", time.localtime(epoch)) if epoch else "TapTap",
        "publishedAtEpoch": epoch,
        "imageUrl": images[0] if images else None,
        "imageUrls": images,
    }


def meta_value(page: str, name: str) -> str:
    for pattern in (
        rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(name)}["\']',
    ):
        match = re.search(pattern, page, re.I)
        if match:
            return clean_text(match.group(1))
    return ""


def collect_html_article_images(page: str) -> list[str]:
    images = []

    def add(value: str):
        candidate = normalize_image_url(value)
        if candidate and candidate not in images:
            images.append(candidate)

    add(meta_value(page, "og:image"))

    normalized_page = html.unescape(page or "").replace("\\/", "/")
    pattern = re.compile(
        r'["\'](?P<key>original_url|large_url|full_url|image_url)["\']\s*:\s*["\'](?P<url>https?://[^"\'<>\s]+)["\']',
        re.I,
    )
    for match in pattern.finditer(normalized_page):
        context = normalized_page[max(0, match.start() - 260): match.start()].casefold()
        article_pos = max(
            (max(context.rfind(f'"{token}"'), context.rfind(f"'{token}'")) for token in ARTICLE_IMAGE_PATH_TOKENS),
            default=-1,
        )
        blocked_pos = max(
            (max(context.rfind(f'"{token}"'), context.rfind(f"'{token}'")) for token in BLOCKED_IMAGE_PATH_TOKENS),
            default=-1,
        )
        if article_pos < 0 or blocked_pos > article_pos:
            continue
        add(match.group("url"))
        if len(images) >= MAX_ARTICLE_IMAGES:
            break

    return images[:MAX_ARTICLE_IMAGES]


def article_from_html(page: str, moment_id: str):
    title = meta_value(page, "og:title")
    if " - " in title:
        title = title.split(" - ", 1)[0].strip()
    body = meta_value(page, "og:description") or meta_value(page, "description")
    if not title:
        match = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.I | re.S)
        title = clean_text(match.group(1)) if match else ""
    if not body:
        body = title
    if not title:
        return None

    epoch = 0
    for pattern in (
        r'["\']created_time["\']\s*:\s*(\d{10,13})',
        r'["\']published_time["\']\s*:\s*(\d{10,13})',
    ):
        match = re.search(pattern, page, re.I)
        if match:
            epoch = normalize_epoch(match.group(1))
            break

    images = collect_html_article_images(page)

    source_url = f"https://www.taptap.cn/moment/{moment_id}"
    return {
        "id": stable_id("taptap:" + moment_id),
        "region": "CHINA",
        "platform": "公式TapTap",
        "title": title[:180],
        "body": body[:5000],
        "sourceUrl": source_url,
        "publishedLabel": time.strftime("%Y-%m-%d", time.localtime(epoch)) if epoch else "TapTap",
        "publishedAtEpoch": epoch,
        "imageUrl": images[0] if images else None,
        "imageUrls": images,
    }


def fetch_article(moment_id: str):
    try:
        row = article_from_api(api_payload(moment_id), moment_id)
        if row:
            return row
    except Exception as exc:
        print(f"TapTap API failed {moment_id}: {exc}")

    url = f"https://www.taptap.cn/moment/{moment_id}"
    try:
        return article_from_html(request_text(url, timeout=10), moment_id)
    except Exception as exc:
        print(f"TapTap page failed {moment_id}: {exc}")
        return None


def merge_rows(existing: list[dict], incoming: list[dict]) -> list[dict]:
    merged = {str(row.get("sourceUrl")): row for row in existing if isinstance(row, dict) and row.get("sourceUrl")}
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

    moment_ids = discover()
    added = []
    if moment_ids:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(moment_ids))) as pool:
            for row in pool.map(fetch_article, moment_ids):
                if row:
                    added.append(row)

    final = merge_rows(rows, added)
    NEWS_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"official TapTap articles merged: {len(added)}; total={len(final)}")


if __name__ == "__main__":
    main()
