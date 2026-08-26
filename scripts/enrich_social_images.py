#!/usr/bin/env python3
import concurrent.futures
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "news.json"
UA = "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/140 Safari/537.36 KiraparaNews-SocialImages/0.1"

GENERAL_HOSTS = [
    "https://rsshub.pseudoyu.com",
    "https://rsshub.umzzz.com",
    "https://rsshub.yfi.moe",
    "https://rsshub.isrss.com",
    "https://rsshub.rssforever.com",
    "https://rsshub.rss.tips",
    "https://hub.slarker.me",
    "https://rsshub.stsecurity.moe",
    "https://rsshub.moonagic.com",
    "https://rsshub.app",
]
X_HOSTS = ["https://rss.xxu.do", "https://rsshub.ethanliunyaa.com"] + GENERAL_HOSTS

SOURCES = [
    ("JAPAN", "公式X", "/twitter/user/kirapara_JP", X_HOSTS),
    ("GLOBAL", "公式X", "/twitter/user/LifeMakeover510", X_HOSTS),
    ("KOREA", "公式X", "/twitter/user/stylight_kr", X_HOSTS),
    ("JAPAN", "公式Instagram", "/instagram/2/user/kiramekiparadise_jp", GENERAL_HOSTS),
    ("GLOBAL", "公式Instagram", "/instagram/2/user/lifemakeover_global", GENERAL_HOSTS),
    ("KOREA", "公式Instagram", "/instagram/2/user/stylight_kr", GENERAL_HOSTS),
    ("JAPAN", "公式TikTok", "/tiktok/user/@kiramekiparadise_jp", GENERAL_HOSTS),
    ("GLOBAL", "公式TikTok", "/tiktok/user/@lifemakeoverofficial", GENERAL_HOSTS),
    ("KOREA", "公式TikTok", "/tiktok/user/@stylightofficial", GENERAL_HOSTS),
    ("CHINA", "公式Weibo", "/weibo/user/7521830234", GENERAL_HOSTS),
    ("CHINA", "公式Bilibili · 記事", "/bilibili/user/article/676200579", GENERAL_HOSTS),
    ("CHINA", "公式Bilibili · 動態", "/bilibili/user/dynamic/676200579", GENERAL_HOSTS),
]

BAD = (
    "favicon", "logo", "avatar", "profile", "qrcode", "qr-code", "qr_code",
    "emoji", "emoticon", "icon_", "/icon/", "/icons/", "badge", "sprite",
    "placeholder", "spinner", "loading", "tracking", "pixel.", "blank.",
)


def request_text(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.7",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8,ko;q=0.7,zh-CN;q=0.6",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(5_000_000)
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, errors="replace")
        except LookupError:
            return raw.decode("utf-8", errors="replace")


def normalize(base: str, value: str | None) -> str | None:
    if not value:
        return None
    value = html.unescape(str(value).strip()).replace("\\/", "/")
    if value.startswith("//"):
        value = "https:" + value
    if value.startswith(("data:", "blob:")):
        return None
    try:
        url = urllib.parse.urljoin(base, value)
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        low = urllib.parse.unquote(url).lower()
        if parsed.path.lower().endswith((".svg", ".ico")) or any(token in low for token in BAD):
            return None
        return url
    except Exception:
        return None


def local_name(tag: str) -> str:
    return tag.split("}")[-1].lower()


def first_text(entry, names: set[str]) -> str:
    for child in entry.iter():
        if local_name(child.tag) in names and child.text:
            return child.text.strip()
    return ""


def entry_link(entry) -> str:
    for child in entry.iter():
        if local_name(child.tag) == "link":
            value = child.attrib.get("href") or (child.text or "").strip()
            if value:
                return value
    value = first_text(entry, {"guid", "id"})
    return value if value.startswith("http") else ""


def link_key(url: str) -> str:
    try:
        decoded = html.unescape(url)
        status = re.search(r"/(?:status|statuses)/(\d+)", decoded)
        if status:
            return "x-status:" + status.group(1)
        parsed = urllib.parse.urlparse(decoded)
        host = parsed.netloc.lower().removeprefix("www.")
        if host == "twitter.com":
            host = "x.com"
        path = re.sub(r"/+$", "", parsed.path)
        return f"{host}{path}"
    except Exception:
        return url


def html_images(markup: str, base: str) -> list[str]:
    markup = html.unescape(markup or "")
    found = []
    patterns = [
        r'<img[^>]+(?:src|data-src|data-original|data-lazy-src)=["\']([^"\']+)',
        r'<source[^>]+srcset=["\']([^"\']+)',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, markup, re.I):
            raw = match.group(1).split(",")[0].strip().split()[0]
            url = normalize(base, raw)
            if url and url not in found:
                found.append(url)
    return found


def entry_images(entry, link: str) -> list[str]:
    found = []
    for child in entry.iter():
        name = local_name(child.tag)
        mime = (child.attrib.get("type") or "").lower()
        medium = (child.attrib.get("medium") or "").lower()
        candidate = child.attrib.get("url") or child.attrib.get("href")
        if candidate and (name in {"thumbnail", "content", "enclosure", "image"} or medium == "image" or mime.startswith("image/")):
            url = normalize(link, candidate)
            if url and url not in found:
                found.append(url)

    for name in ({"description", "summary", "content", "encoded"},):
        markup = first_text(entry, name)
        for url in html_images(markup, link):
            if url not in found:
                found.append(url)
    return found[:20]


def parse_feed(xml_text: str) -> dict[str, list[str]]:
    root = ET.fromstring(xml_text)
    entries = [e for e in root if local_name(e.tag) == "entry"] if local_name(root.tag) == "feed" else root.findall(".//item")
    out = {}
    for entry in entries[:30]:
        link = entry_link(entry)
        if not link:
            continue
        images = entry_images(entry, link)
        if images:
            out[link_key(link)] = images
    return out


def fetch_source(region: str, platform: str, route: str, hosts: list[str]):
    last_error = None
    for host in hosts:
        try:
            data = parse_feed(request_text(host.rstrip("/") + route))
            if data:
                print(f"social images {region} {platform}: {len(data)} posts via {host}")
                return region, platform, data
        except Exception as exc:
            last_error = exc
    if last_error:
        print(f"social images unavailable {region} {platform}: {last_error}")
    return region, platform, {}


def main():
    try:
        rows = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        rows = []
    if not isinstance(rows, list):
        rows = []

    maps = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(fetch_source, *source) for source in SOURCES]
        for future in futures:
            region, platform, mapping = future.result()
            maps[(region, platform)] = mapping

    changed = 0
    multi = 0
    for row in rows:
        mapping = maps.get((str(row.get("region") or ""), str(row.get("platform") or "")), {})
        extras = mapping.get(link_key(str(row.get("sourceUrl") or "")), [])
        if not extras:
            continue
        merged = []
        for raw in extras + (row.get("imageUrls") if isinstance(row.get("imageUrls"), list) else []) + ([row.get("imageUrl")] if row.get("imageUrl") else []):
            url = normalize(str(row.get("sourceUrl") or ""), raw)
            if url and url not in merged:
                merged.append(url)
        merged = merged[:20]
        old = row.get("imageUrls") if isinstance(row.get("imageUrls"), list) else []
        if merged != old:
            row["imageUrls"] = merged
            row["imageUrl"] = merged[0] if merged else None
            changed += 1
        if len(merged) > 1:
            multi += 1

    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"social image enrichment changed: {changed}")
    print(f"social multi-image posts: {multi}")


if __name__ == "__main__":
    main()
