#!/usr/bin/env python3
import concurrent.futures
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
MIRROR_DIR = ROOT / "docs" / "media" / "weibo"
RAW_BASE = "https://ikegami-99.github.io/KRPR_news/media/weibo/"
UA = "Mozilla/5.0 (Linux; Android 16; 24122RKC7G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36"
SINA_SUFFIXES = ("sinaimg.cn", "sinaimg.com")
MAX_BYTES = 18 * 1024 * 1024
MIN_BYTES = 1024
HOST_SHARD = re.compile(r"(?:tvax|tva|wx|ww)(\d+)", re.I)


def read_rows():
    try:
        value = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    return value if isinstance(value, list) else []


def write_rows(rows):
    NEWS_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_weibo_row(row: dict) -> bool:
    platform = str(row.get("platform") or "").lower()
    source = str(row.get("sourceUrl") or "").lower()
    return "weibo" in platform or "weibo.com/" in source or "m.weibo.cn/" in source


def is_sina(url: str) -> bool:
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
        return any(host == suffix or host.endswith("." + suffix) for suffix in SINA_SUFFIXES)
    except Exception:
        return False


def source_images(row: dict) -> list[str]:
    values = []
    if isinstance(row.get("imageUrls"), list):
        values.extend(row.get("imageUrls") or [])
    if row.get("imageUrl"):
        values.append(row.get("imageUrl"))
    result = []
    for value in values:
        if isinstance(value, str) and is_sina(value) and value not in result:
            result.append(value)
    return result[:20]


def image_kind(data: bytes, content_type: str = "") -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    ctype = (content_type or "").lower().split(";", 1)[0].strip()
    return {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
    }.get(ctype)


def existing_mirror(digest: str) -> tuple[Path, str] | None:
    for ext in ("jpg", "png", "webp", "gif"):
        path = MIRROR_DIR / f"{digest}.{ext}"
        try:
            data = path.read_bytes()[:32]
        except Exception:
            continue
        if path.stat().st_size >= MIN_BYTES and image_kind(data):
            return path, ext
    return None


def variants(url: str) -> list[str]:
    try:
        parsed = urllib.parse.urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            return [url]
        filename = parts[-1]
        match = HOST_SHARD.search(parsed.netloc)
        shard = match.group(1) if match else "1"
        result = []
        # mw2000 is large enough for the app while keeping repository growth sane.
        for host in (f"wx{shard}.sinaimg.cn", f"ww{shard}.sinaimg.cn", f"tvax{shard}.sinaimg.cn", f"tva{shard}.sinaimg.cn"):
            for size in ("mw2000", "large"):
                candidate = f"https://{host}/{size}/{filename}"
                if candidate not in result:
                    result.append(candidate)
        normalized = urllib.parse.urlunparse(parsed._replace(scheme="https"))
        if normalized not in result:
            result.append(normalized)
        return result
    except Exception:
        return [url]


def fetch_bytes(url: str, source_url: str) -> tuple[bytes, str, str] | None:
    referers = [source_url, "https://weibo.com/", "https://m.weibo.cn/"]
    accept = "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
    for candidate in variants(url):
        for referer in referers:
            try:
                headers = {
                    "User-Agent": UA,
                    "Accept": accept,
                    "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8",
                    "Referer": referer,
                    "Cache-Control": "no-cache",
                }
                req = urllib.request.Request(candidate, headers=headers)
                with urllib.request.urlopen(req, timeout=12) as response:
                    ctype = response.headers.get("Content-Type") or ""
                    length = int(response.headers.get("Content-Length") or 0)
                    if length > MAX_BYTES:
                        continue
                    data = response.read(MAX_BYTES + 1)
                if len(data) < MIN_BYTES or len(data) > MAX_BYTES:
                    continue
                ext = image_kind(data, ctype)
                if not ext:
                    continue
                return data, ext, candidate
            except Exception:
                continue
    return None


def mirror_one(row: dict, index: int, url: str):
    source_url = str(row.get("sourceUrl") or "https://weibo.com/")
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    cached = existing_mirror(digest)
    if cached:
        path, _ext = cached
        return index, url, RAW_BASE + path.name, path, True, "cache"

    fetched = fetch_bytes(url, source_url)
    if not fetched:
        return index, url, "", None, False, "download-failed"
    data, ext, used_url = fetched
    path = MIRROR_DIR / f"{digest}.{ext}"
    path.write_bytes(data)
    return index, url, RAW_BASE + path.name, path, True, used_url


def main():
    rows = read_rows()
    MIRROR_DIR.mkdir(parents=True, exist_ok=True)
    targets = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, dict) or not is_weibo_row(row):
            continue
        for image_index, url in enumerate(source_images(row)):
            targets.append((row_index, image_index, row, url))

    results = {}
    reused = 0
    downloaded = 0
    failed = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(targets)))) as pool:
        future_map = {
            pool.submit(mirror_one, row, image_index, url): (row_index, image_index, url)
            for row_index, image_index, row, url in targets
        }
        for future in concurrent.futures.as_completed(future_map):
            row_index, image_index, url = future_map[future]
            try:
                _index, _url, mirror_url, path, ok, method = future.result()
            except Exception as exc:
                mirror_url, path, ok, method = "", None, False, f"error:{exc}"
            results[(row_index, image_index)] = (mirror_url, path, ok, method)
            if ok and method == "cache":
                reused += 1
            elif ok:
                downloaded += 1
            else:
                failed.append(url)

    active_files = set()
    complete_rows = 0
    partial_rows = 0
    changed_rows = 0
    for row_index, row in enumerate(rows):
        if not isinstance(row, dict) or not is_weibo_row(row):
            continue
        sources = source_images(row)
        if not sources:
            row.pop("imageMirrorUrls", None)
            continue
        mirrors = []
        complete = True
        for image_index, _source in enumerate(sources):
            mirror_url, path, ok, _method = results.get((row_index, image_index), ("", None, False, "missing"))
            if ok and mirror_url and path:
                mirrors.append(mirror_url)
                active_files.add(path.name)
            else:
                mirrors.append("")
                complete = False
        before = row.get("imageMirrorUrls")
        # Only activate mirrors when every source image has a local copy. This
        # preserves one logical gallery item per source and avoids duplicates.
        if complete and len(mirrors) == len(sources):
            row["imageMirrorUrls"] = mirrors
            complete_rows += 1
        else:
            row.pop("imageMirrorUrls", None)
            partial_rows += 1
        if row.get("imageMirrorUrls") != before:
            changed_rows += 1

    pruned = 0
    for path in MIRROR_DIR.iterdir():
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.name not in active_files:
            try:
                path.unlink()
                pruned += 1
            except Exception:
                pass

    write_rows(rows)
    print(
        f"Weibo mirror: sources={len(targets)} downloaded={downloaded} reused={reused} "
        f"failed={len(failed)} complete_posts={complete_rows} partial_posts={partial_rows} "
        f"changed_rows={changed_rows} pruned={pruned}"
    )
    if failed:
        print(f"::warning::Weibo mirror failed for {len(failed)}/{len(targets)} source images")
        for url in failed[:12]:
            print(f"Weibo mirror failed: {url}")


if __name__ == "__main__":
    main()
