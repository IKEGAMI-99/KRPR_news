#!/usr/bin/env python3
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "news.json"
UA = "Mozilla/5.0 KiraparaNews-GitHubCollector/0.2.4"
GOOGLE_TRANSLATE_API_KEY = os.environ.get("GOOGLE_TRANSLATE_API_KEY", "").strip()

RSSHUB_HOSTS = [
    "https://rsshub.app",
    "https://rsshub.rssforever.com",
    "https://rsshub.yfi.moe",
]

REGION_HOME_PAGES = {
    "JAPAN": "https://kirapara.archosaur.com/",
    "CHINA": "https://mystyle.archosaur.com/",
    "GLOBAL": "https://lifemakeover.archosaur.com/",
    "KOREA": "https://stylight.nex2fun.com/",
}

STATIC_FALLBACK_IMAGES = {
    "JAPAN": "https://kirapara.archosaur.com/new_script/img/pc/top_logo.png",
    "CHINA": "https://mystyle.archosaur.com/assets/260721/pc/images/p3/slider1.jpg",
    "KOREA": "https://stylight.nex2fun.com/assets/pc/img/page1/page1_slogan.png",
}

LANGUAGE_BY_REGION = {
    "CHINA": "zh-CN",
    "GLOBAL": "en",
    "KOREA": "ko",
}

_official_image_cache = {}


def get(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def strip_tags(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def clean_social_text(s: str, region: str) -> str:
    s = strip_tags(s)
    if region == "CHINA":
        s = re.sub(r"#[^#\n]{1,100}#", " ", s)
        s = re.sub(r"^\s*(?:以闪亮之名\s*)+", "", s)
        s = re.sub(r"@[^\s:：]+", "", s)
        s = s.replace("网页链接", "")
        lines = []
        for line in s.splitlines():
            line = line.strip()
            if not line:
                continue
            if any(marker in line for marker in ("下载传送门", "活动传送门", "转发微博")):
                continue
            lines.append(line)
        s = "\n".join(lines)

    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def compact_title(s: str, region: str) -> str:
    s = clean_social_text(s, region)
    if not s:
        return "新着ニュース"
    first = re.split(r"[\n。！？!?]", s, maxsplit=1)[0].strip()
    candidate = first if len(first) >= 6 else s.replace("\n", " ")
    return candidate[:90].rstrip(" ,，、-｜|")


def image_from_html(s: str):
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', s or "", re.I)
    return html.unescape(m.group(1)) if m else None


def is_placeholder_image(url: str | None) -> bool:
    if not url:
        return True
    low = url.lower()
    return any(
        token in low
        for token in (
            "timeline_card_small_super_default",
            "timeline_card_small_web_default",
            "timeline_card_small_default",
            "default_avatar",
            "default.png",
        )
    )


def official_fallback_image(region: str):
    if region in _official_image_cache:
        return _official_image_cache[region]

    home = REGION_HOME_PAGES.get(region)
    discovered = None
    if home:
        try:
            page = get(home, timeout=10)
            patterns = [
                r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']',
            ]
            for pattern in patterns:
                m = re.search(pattern, page, re.I)
                if m:
                    candidate = urllib.parse.urljoin(home, html.unescape(m.group(1)))
                    low = candidate.lower()
                    if not any(x in low for x in ("qrcode", "qr_", "ewm", "favicon", "icon", "logo")):
                        discovered = candidate
                        break

            if not discovered:
                candidates = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', page, re.I)
                scored = []
                for src in candidates:
                    full = urllib.parse.urljoin(home, html.unescape(src))
                    low = full.lower()
                    if full.startswith("data:"):
                        continue
                    if any(token in low for token in ("ewm", "qrcode", "qr_", "qr-", "favicon", "icon", "logo", "download", "store")):
                        continue
                    score = sum(
                        token in low
                        for token in (
                            "keyvisual", "mainvisual", "visual", "banner", "slider", "slide", "kv", "hero", "top_bg", "top-bg"
                        )
                    )
                    if score > 0:
                        scored.append((score, full))
                if scored:
                    scored.sort(key=lambda x: x[0], reverse=True)
                    discovered = scored[0][1]
        except Exception as e:
            print(f"official image discovery failed {region}: {e}")

    result = discovered or STATIC_FALLBACK_IMAGES.get(region)
    _official_image_cache[region] = result
    return result


def parse_date_epoch(value: str) -> int:
    if not value:
        return 0
    try:
        from email.utils import parsedate_to_datetime
        return int(parsedate_to_datetime(value).timestamp())
    except Exception:
        pass
    try:
        from datetime import datetime
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
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
    entries = [e for e in root if e.tag.endswith("entry")] if root.tag.endswith("feed") else root.findall(".//item")
    items = []

    for e in entries[:limit]:
        def first_text(names):
            for child in e.iter():
                local = child.tag.split("}")[-1]
                if local in names and child.text:
                    return child.text.strip()
            return ""

        raw_title = first_text({"title"})
        body_raw = first_text({"description", "summary", "content", "encoded"})
        published = first_text({"published", "updated", "pubDate"})
        video_id = first_text({"videoId"})

        link = ""
        for child in e.iter():
            if child.tag.split("}")[-1] == "link":
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
            if child.tag.split("}")[-1] == "thumbnail" and child.attrib.get("url"):
                image = child.attrib["url"]
                break
        if not image and video_id:
            image = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        if not image:
            image = image_from_html(body_raw)

        if not raw_title or not link:
            continue

        title = compact_title(raw_title, region)
        body = clean_social_text(body_raw, region) or clean_social_text(raw_title, region)
        epoch = parse_date_epoch(published)
        if is_placeholder_image(image):
            image = official_fallback_image(region)

        items.append({
            "id": str(hash(link)),
            "region": region,
            "platform": platform,
            "title": title,
            "body": body[:1800],
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


def google_translate(texts: list[str], source: str) -> list[str]:
    if not texts or not GOOGLE_TRANSLATE_API_KEY:
        return texts
    endpoint = "https://translation.googleapis.com/language/translate/v2?" + urllib.parse.urlencode(
        {"key": GOOGLE_TRANSLATE_API_KEY}
    )
    payload = json.dumps({"q": texts, "source": source, "target": "ja", "format": "text"}).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    translations = data.get("data", {}).get("translations", [])
    if len(translations) != len(texts):
        raise RuntimeError("Google Translation response size mismatch")
    return [html.unescape(x.get("translatedText", "")) for x in translations]


def apply_translations(rows: list[dict], existing: list[dict]):
    existing_by_url = {x.get("sourceUrl"): x for x in existing if x.get("sourceUrl")}
    pending_by_lang: dict[str, list[tuple[dict, str, str]]] = {}

    for row in rows:
        if row.get("region") == "JAPAN":
            row["translatedTitle"] = row.get("title", "")
            row["translatedBody"] = row.get("body", "")
            continue

        previous = existing_by_url.get(row.get("sourceUrl"))
        if (
            previous
            and previous.get("title") == row.get("title")
            and previous.get("body") == row.get("body")
            and previous.get("translatedTitle")
            and previous.get("translatedBody")
        ):
            row["translatedTitle"] = previous["translatedTitle"]
            row["translatedBody"] = previous["translatedBody"]
            continue

        lang = LANGUAGE_BY_REGION.get(row.get("region"))
        if not lang:
            continue
        pending_by_lang.setdefault(lang, []).extend([
            (row, "translatedTitle", row.get("title", "")),
            (row, "translatedBody", row.get("body", "")),
        ])

    if not GOOGLE_TRANSLATE_API_KEY:
        print("GOOGLE_TRANSLATE_API_KEY is not set; app will use on-device ML Kit fallback")
        return

    for lang, pending in pending_by_lang.items():
        for start in range(0, len(pending), 40):
            chunk = pending[start:start + 40]
            texts = [x[2] for x in chunk]
            try:
                translated = google_translate(texts, lang)
                for (row, field, _), value in zip(chunk, translated):
                    row[field] = value
            except Exception as e:
                print(f"google translate failed ({lang}): {e}")


def main():
    existing = load_existing()
    fresh = []

    sources = [
        lambda: youtube_channel("JAPAN", "公式YouTube", channel_id="UC9MO21fNvt0F4-UK28kc_VQ"),
        lambda: youtube_channel(
            "GLOBAL",
            "公式YouTube",
            page_urls=["https://www.youtube.com/c/LifeMakeover/", "https://www.youtube.com/@LifeMakeover"],
        ),
        lambda: youtube_channel("KOREA", "公式YouTube", page_urls=["https://www.youtube.com/@stylight_official"]),
        lambda: rsshub("CHINA", "公式Weibo · RSSHub", "/weibo/user/7521830234"),
        lambda: rsshub("CHINA", "公式Bilibili · RSSHub", "/bilibili/user/video/676200579"),
    ]

    for fn in sources:
        try:
            fresh.extend(fn())
        except Exception as e:
            print(f"source failed: {e}")

    fresh_regions = {x.get("region") for x in fresh}
    for region in {"JAPAN", "CHINA", "GLOBAL", "KOREA"}:
        if region not in fresh_regions:
            fresh.extend([x for x in existing if x.get("region") == region])

    dedup = {}
    for row in fresh:
        url = row.get("sourceUrl")
        if not url:
            continue
        if is_placeholder_image(row.get("imageUrl")):
            row["imageUrl"] = official_fallback_image(row.get("region"))
        dedup[url] = row

    rows = sorted(
        dedup.values(),
        key=lambda x: int(x.get("publishedAtEpoch") or 0),
        reverse=True,
    )[:60]
    apply_translations(rows, existing)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} items")


if __name__ == "__main__":
    main()
