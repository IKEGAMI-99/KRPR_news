#!/usr/bin/env python3
import concurrent.futures
import json
import struct
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
CACHE_PATH = ROOT / "data" / "image_quality.json"
UA = "Mozilla/5.0 KiraparaNews-ImageQuality/1.2"
BROWSER_UA = "Mozilla/5.0 (Linux; Android 16; 24122RKC7G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36"
MIN_SHORT_SIDE = 260
MIN_AREA = 150_000
MAX_READ = 512_000
CACHE_TTL = 30 * 86400
SINA_SUFFIXES = ("sinaimg.cn", "sinaimg.com")


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def dimensions(data: bytes):
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if len(data) >= 10 and data[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", data[6:10])
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if len(data) >= 30 and data[12:16] == b"VP8X":
            return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
        if len(data) >= 30 and data[12:16] == b"VP8L":
            b1, b2, b3 = data[22], data[23], data[24]
            return 1 + (((b2 & 0x3F) << 8) | b1), 1 + ((b3 << 6) | (b2 >> 6))
    if len(data) >= 4 and data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            i += 2
            if marker in (0xD8, 0xD9):
                continue
            if i + 2 > len(data):
                break
            length = int.from_bytes(data[i:i + 2], "big")
            if length < 2 or i + length > len(data):
                break
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF) and i + 7 <= len(data):
                h = int.from_bytes(data[i + 3:i + 5], "big")
                w = int.from_bytes(data[i + 5:i + 7], "big")
                return w, h
            i += length
    return None


def is_sina(url: str) -> bool:
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
        return any(host == suffix or host.endswith("." + suffix) for suffix in SINA_SUFFIXES)
    except Exception:
        return False


def request_profiles(url: str):
    image_accept = "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
    if is_sina(url):
        # Sina's CDN can reject generic bot UAs, a missing Weibo referer, or Range
        # requests independently. Try browser-like combinations before declaring
        # the image unverifiable. A hotlink response must never delete a real URL.
        return [
            {
                "User-Agent": BROWSER_UA,
                "Accept": image_accept,
                "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8",
                "Referer": "https://weibo.com/",
                "Range": f"bytes=0-{MAX_READ - 1}",
            },
            {
                "User-Agent": BROWSER_UA,
                "Accept": image_accept,
                "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8",
                "Referer": "https://m.weibo.cn/",
            },
            {
                "User-Agent": BROWSER_UA,
                "Accept": image_accept,
                "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8",
            },
        ]
    return [{
        "User-Agent": UA,
        "Accept": image_accept,
        "Range": f"bytes=0-{MAX_READ - 1}",
    }]


def probe(url: str):
    sina = is_sina(url)
    saw_non_image = False
    for headers in request_profiles(url):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=9) as response:
                ctype = (response.headers.get("Content-Type") or "").lower()
                if ctype and not ctype.startswith("image/"):
                    saw_non_image = True
                    continue
                data = response.read(MAX_READ)
            size = dimensions(data)
            if not size:
                continue
            w, h = size
            return min(w, h) >= MIN_SHORT_SIDE and w * h >= MIN_AREA, (w, h)
        except Exception:
            continue

    # For Sina, an HTML/403/anti-hotlink response is not evidence that the real
    # image is invalid. Keep it and let the browser/proxy fallbacks try it.
    if sina:
        return None, None
    if saw_non_image:
        return False, None
    return None, None


def main():
    rows = read_json(NEWS_PATH, [])
    cache = read_json(CACHE_PATH, {})
    if not isinstance(rows, list):
        rows = []
    if not isinstance(cache, dict):
        cache = {}

    urls = []
    seen = set()
    for row in rows:
        values = list(row.get("imageUrls") or [])
        if row.get("imageUrl"):
            values.append(row["imageUrl"])
        for url in values:
            if isinstance(url, str) and url.startswith("http") and url not in seen:
                seen.add(url)
                urls.append(url)

    now = int(time.time())
    results = {}
    pending = []
    for url in urls:
        entry = cache.get(url)
        if isinstance(entry, dict) and now - int(entry.get("checkedAt") or 0) < CACHE_TTL:
            size = None
            if int(entry.get("width") or 0) and int(entry.get("height") or 0):
                size = (int(entry["width"]), int(entry["height"]))
            results[url] = (entry.get("ok"), size)
        else:
            pending.append(url)

    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
        future_map = {pool.submit(probe, url): url for url in pending}
        for future in concurrent.futures.as_completed(future_map):
            url = future_map[future]
            try:
                verdict, size = future.result()
            except Exception:
                verdict, size = None, None
            results[url] = (verdict, size)
            if verdict is not None:
                cache[url] = {
                    "ok": bool(verdict),
                    "width": size[0] if size else 0,
                    "height": size[1] if size else 0,
                    "checkedAt": now,
                }

    removed = 0
    known = 0
    sina_total = 0
    sina_known = 0
    sina_unknown = []
    for url in urls:
        if not is_sina(url):
            continue
        sina_total += 1
        verdict, size = results.get(url, (None, None))
        if size:
            sina_known += 1
        elif verdict is None:
            sina_unknown.append(url)

    for row in rows:
        values = []
        for url in list(row.get("imageUrls") or []) + ([row.get("imageUrl")] if row.get("imageUrl") else []):
            if not isinstance(url, str) or url in values:
                continue
            verdict, size = results.get(url, (None, None))
            if verdict is False:
                removed += 1
                continue
            if size:
                known += 1
            values.append(url)
        row["imageUrls"] = values[:20]
        row["imageUrl"] = values[0] if values else None

    live = set(urls)
    cache = {url: value for url, value in cache.items() if url in live}
    NEWS_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"image quality: cached={len(urls) - len(pending)} probed={len(pending)} known={known}")
    print(f"small/non-image candidates removed: {removed}")
    print(f"Sina image quality: total={sina_total} verified={sina_known} unresolved={len(sina_unknown)}")
    if sina_unknown:
        print(f"::warning::Sina image verification unresolved for {len(sina_unknown)}/{sina_total} URLs; keeping them for browser fallback")
        for url in sina_unknown[:8]:
            print(f"Sina image unresolved: {url}")


if __name__ == "__main__":
    main()
