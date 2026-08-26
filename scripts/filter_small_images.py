#!/usr/bin/env python3
import concurrent.futures
import json
import struct
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
UA = "Mozilla/5.0 KiraparaNews-ImageQuality/1.0"
MIN_SHORT_SIDE = 260
MIN_AREA = 150_000
MAX_READ = 512_000


def dimensions(data: bytes):
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if len(data) >= 10 and data[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", data[6:10])
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if len(data) >= 30 and data[12:16] == b"VP8X":
            w = 1 + int.from_bytes(data[24:27], "little")
            h = 1 + int.from_bytes(data[27:30], "little")
            return w, h
        if len(data) >= 30 and data[12:16] == b"VP8L":
            b0, b1, b2, b3 = data[21:25]
            w = 1 + (((b2 & 0x3F) << 8) | b1)
            h = 1 + ((b3 << 6) | (b2 >> 6))
            return w, h
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
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                if i + 7 <= len(data):
                    h = int.from_bytes(data[i + 3:i + 5], "big")
                    w = int.from_bytes(data[i + 5:i + 7], "big")
                    return w, h
            i += length
    return None


def probe(url: str):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Range": f"bytes=0-{MAX_READ - 1}",
            "Referer": "",
        })
        with urllib.request.urlopen(req, timeout=8) as response:
            ctype = (response.headers.get("Content-Type") or "").lower()
            if ctype and not ctype.startswith("image/"):
                return False, None
            data = response.read(MAX_READ)
        size = dimensions(data)
        if not size:
            return None, None
        w, h = size
        good = min(w, h) >= MIN_SHORT_SIDE and w * h >= MIN_AREA
        return good, (w, h)
    except Exception:
        return None, None


def main():
    try:
        rows = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
    except Exception:
        rows = []
    if not isinstance(rows, list):
        rows = []

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

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
        future_map = {pool.submit(probe, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_map):
            url = future_map[future]
            try:
                results[url] = future.result()
            except Exception:
                results[url] = (None, None)

    removed = 0
    known = 0
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

    NEWS_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"image quality probe: {known}/{len(urls)} dimensions known")
    print(f"small/non-image candidates removed: {removed}")


if __name__ == "__main__":
    main()
