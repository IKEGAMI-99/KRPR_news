#!/usr/bin/env python3
import html
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "news.json"
UA = "Mozilla/5.0 KiraparaNews-GitHubCollector/0.2.3"

RSSHUB_HOSTS = [
    "https://rsshub.app",
    "https://rsshub.rssforever.com",
    "https://rsshub.yfi.moe",
]


def get(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def strip_tags(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def image_from_html(s: str):
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', s or "", re.I)
    return html.unescape(m.group(1)) if m else None


def parse_date_epoch(value: str) -> int:
    if not value:
        return 0
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(value)
        return int(dt.timestamp())
    except Exception:
        pass
    try:
        from datetime import datetime
        v = value.replace("Z", "+00:00")
        return int(datetime.fromisoformat(v).timestamp())
    except Exception:
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


def parse_feed(xml_text: str, region: str, platform: str, limit: int = 12):
    root = ET.fromstring(xml_text)
    items = []

    entries = []
    if root.tag.endswith("feed"):
        entries = [e for e in root if e.tag.endswith("entry")]
    else:
        entries = root.findall(".//item")

    for e in entries[:limit]:
        def first_text(names):
            for child in e.iter():
                local = child.tag.split("}")[-1]
                if local in names and child.text:
                    return child.text.strip()
            return ""

        title = first_text({"title"})
        body_raw = first_text({"description", "summary", "content", "encoded"})
        published = first_text({"published", "updated", "pubDate"})
        video_id = first_text({"videoId"})

        link = ""
        for child in e.iter():
            local = child.tag.split("}")[-1]
            if local == "link":
                link = child.attrib.get("href") or (child.text or "").strip()
                if link:
                    break
        if not link:
            guid = first_text({"guid"})
            if guid.startswith("http"):
                link = guid
        if not link and video_id:
            link = f"https://www.youtube.com/watch?v={video_id}"

        image = None
        for child in e.iter():
            local = child.tag.split("}")[-1]
            if local == "thumbnail" and child.attrib.get("url"):
                image = child.attrib["url"]
                break
        if not image and video_id:
            image = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        if not image:
            image = image_from_html(body_raw)

        if not title or not link:
            continue

        epoch = parse_date_epoch(published)
        items.append({
            "id": str(hash(link)),
            "region": region,
            "platform": platform,
            "title": strip_tags(title),
            "body": strip_tags(body_raw) or strip_tags(title),
            "sourceUrl": link,
            "publishedLabel": rel_label(epoch),
            "publishedAtEpoch": epoch,
            "imageUrl": image,
        })
    return items


def resolve_youtube_channel_id(page_url: str):
    text = get(page_url)
    patterns = [
        r'"channelId"\s*:\s*"(UC[a-zA-Z0-9_-]{22})"',
        r'"browseId"\s*:\s*"(UC[a-zA-Z0-9_-]{22})"',
        r'"externalId"\s*:\s*"(UC[a-zA-Z0-9_-]{22})"',
        r'youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return None


def youtube_channel(region: str, platform: str, channel_id=None, page_urls=None):
    if not channel_id:
        for page in page_urls or []:
            try:
                channel_id = resolve_youtube_channel_id(page)
                if channel_id:
                    break
            except Exception as e:
                print(f"youtube page failed {page}: {e}")
    if not channel_id:
        return []
    return parse_feed(get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"), region, platform)


def rsshub(region: str, platform: str, path: str):
    for host in RSSHUB_HOSTS:
        try:
            rows = parse_feed(get(host + path), region, platform)
            if rows:
                return rows
        except Exception as e:
            print(f"rsshub failed {host}{path}: {e}")
    return []


def load_existing():
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def main():
    existing = load_existing()
    fresh = []

    sources = [
        lambda: youtube_channel("JAPAN", "公式YouTube", channel_id="UC9MO21fNvt0F4-UK28kc_VQ"),
        lambda: youtube_channel("GLOBAL", "公式YouTube", page_urls=["https://www.youtube.com/c/LifeMakeover/", "https://www.youtube.com/@LifeMakeover"]),
        lambda: youtube_channel("KOREA", "公式YouTube", page_urls=["https://www.youtube.com/@stylight_official"]),
        lambda: rsshub("CHINA", "公式Weibo · RSSHub", "/weibo/user/7521830234"),
        lambda: rsshub("CHINA", "公式Bilibili · RSSHub", "/bilibili/user/video/676200579"),
    ]

    for fn in sources:
        try:
            fresh.extend(fn())
        except Exception as e:
            print(f"source failed: {e}")

    # その地域の新規取得が0件なら、前回キャッシュを残す。
    fresh_regions = {x.get("region") for x in fresh}
    for region in {"JAPAN", "CHINA", "GLOBAL", "KOREA"}:
        if region not in fresh_regions:
            fresh.extend([x for x in existing if x.get("region") == region])

    dedup = {}
    for row in fresh:
        url = row.get("sourceUrl")
        if url:
            dedup[url] = row

    rows = sorted(dedup.values(), key=lambda x: int(x.get("publishedAtEpoch") or 0), reverse=True)[:60]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} items")


if __name__ == "__main__":
    main()
