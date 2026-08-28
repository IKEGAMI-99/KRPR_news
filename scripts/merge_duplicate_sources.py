#!/usr/bin/env python3
import difflib
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
MAX_TIME_GAP = 12 * 60 * 60


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def normalize_title(value: str) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"#[^#\n]{1,80}#", "", text)
    text = re.sub(r"^(?:以闪亮之名|きらめきパラダイス|life\s*makeover|스타일라잇)\s*", "", text)
    text = re.sub(r"(?:官方|公式)(?:微博|weibo|bilibili|taptap|好游快爆)?", "", text)
    text = re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]+", "", text)
    return text[:240]


def time_close(a: dict, b: dict) -> bool:
    ea = int(a.get("publishedAtEpoch") or 0)
    eb = int(b.get("publishedAtEpoch") or 0)
    if not ea or not eb:
        return True
    return abs(ea - eb) <= MAX_TIME_GAP


def same_story(a: dict, b: dict) -> bool:
    if a.get("region") != b.get("region"):
        return False
    if not time_close(a, b):
        return False
    ta = normalize_title(a.get("title"))
    tb = normalize_title(b.get("title"))
    if min(len(ta), len(tb)) < 10:
        return False
    short, long = sorted((ta, tb), key=len)
    if len(short) >= 14 and short in long:
        return True
    ratio = difflib.SequenceMatcher(None, ta, tb).ratio()
    return ratio >= 0.76


def platform_label(platform: str) -> str:
    value = str(platform or "元記事")
    value = re.sub(r"^(?:公式|官方)", "", value).strip()
    value = re.sub(r"\s*·\s*(?:記事|動態)$", "", value).strip()
    return value or "元記事"


def source_entries(row: dict) -> list[dict]:
    entries = []
    for source in row.get("sources") or []:
        if not isinstance(source, dict):
            continue
        url = str(source.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        entries.append({
            "platform": str(source.get("platform") or source.get("label") or "元記事"),
            "label": str(source.get("label") or platform_label(source.get("platform"))),
            "url": url,
        })
    url = str(row.get("sourceUrl") or "").strip()
    if url.startswith(("http://", "https://")):
        entries.append({
            "platform": str(row.get("platform") or "元記事"),
            "label": platform_label(row.get("platform")),
            "url": url,
        })
    deduped = []
    seen = set()
    for entry in entries:
        if entry["url"] in seen:
            continue
        seen.add(entry["url"])
        deduped.append(entry)
    return deduped


def quality_score(row: dict) -> int:
    body = len(str(row.get("body") or ""))
    images = len(row.get("imageUrls") or []) + (1 if row.get("imageUrl") else 0)
    ai = 2500 if row.get("aiProcessed") and row.get("summaryJa") else 0
    official = 500 if str(row.get("platform") or "").startswith(("公式", "官方")) else 0
    return body + images * 250 + ai + official


def merge_cluster(cluster: list[dict]) -> dict:
    primary = max(cluster, key=quality_score).copy()
    sources = []
    seen_urls = set()
    images = []
    seen_images = set()
    epochs = []

    for row in cluster:
        for source in source_entries(row):
            if source["url"] in seen_urls:
                continue
            seen_urls.add(source["url"])
            sources.append(source)
        for image in list(row.get("imageUrls") or []) + ([row.get("imageUrl")] if row.get("imageUrl") else []):
            if not isinstance(image, str) or not image.startswith(("http://", "https://")) or image in seen_images:
                continue
            seen_images.add(image)
            images.append(image)
        epoch = int(row.get("publishedAtEpoch") or 0)
        if epoch:
            epochs.append(epoch)
        for key in ("titleJa", "bodyJa", "summaryJa", "aiProcessed", "aiModel", "aiSummaryFormat", "managedBySol", "solLocked"):
            if not primary.get(key) and row.get(key):
                primary[key] = row[key]

    primary["sources"] = sources
    primary["sourceCount"] = len(sources)
    if images:
        primary["imageUrls"] = images[:16]
        primary["imageUrl"] = primary.get("imageUrl") or images[0]
    if epochs:
        primary["publishedAtEpoch"] = min(epochs)
    if len(sources) > 1:
        primary["id"] = stable_id("merged:" + "|".join(sorted(seen_urls)))
    return primary


def merge_rows(rows: list[dict]) -> list[dict]:
    clusters: list[list[dict]] = []
    for row in sorted(rows, key=lambda r: int(r.get("publishedAtEpoch") or 0), reverse=True):
        if not isinstance(row, dict) or not row.get("sourceUrl"):
            continue
        matched = None
        for cluster in clusters:
            if same_story(row, cluster[0]):
                matched = cluster
                break
        if matched is None:
            clusters.append([row])
        else:
            matched.append(row)

    merged = [merge_cluster(cluster) for cluster in clusters]
    merged.sort(key=lambda r: int(r.get("publishedAtEpoch") or 0), reverse=True)
    return merged[:260]


def main():
    try:
        rows = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
    except Exception:
        rows = []
    if not isinstance(rows, list):
        rows = []
    merged = merge_rows(rows)
    groups = sum(1 for row in merged if int(row.get("sourceCount") or 0) > 1)
    NEWS_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"duplicate article merge: {len(rows)} -> {len(merged)} rows; multi-source={groups}")


if __name__ == "__main__":
    main()
