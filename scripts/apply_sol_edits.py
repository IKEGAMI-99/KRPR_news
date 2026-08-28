#!/usr/bin/env python3
import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
TRANSLATIONS_PATH = ROOT / "data" / "translations.json"
SOL_NEWS_PATH = ROOT / "data" / "sol_news.json"
SOL_OVERRIDES_PATH = ROOT / "data" / "sol_overrides.json"

TRANSLATION_FIELDS = ("titleJa", "bodyJa", "summaryJa")
SOL_MODEL = "GPT-5.6 Sol"
SOL_REVISION = "sol-reviewed-v1"
SUMMARY_FORMAT_VERSION = 2


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def read_json_required(path: Path, expected_type):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"required JSON is unreadable or malformed: {path}: {exc}") from exc
    if not isinstance(value, expected_type):
        raise RuntimeError(f"required JSON has the wrong type: {path}")
    return value


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def source_hash(row: dict) -> str:
    payload = "\n".join([
        str(row.get("region") or ""),
        str(row.get("title") or ""),
        str(row.get("body") or ""),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def cache_key(row: dict) -> str:
    return str(row.get("sourceUrl") or row.get("id") or source_hash(row))


def stable_id(row: dict) -> str:
    key = cache_key(row)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def normalize_translation_cache(raw) -> dict:
    if not isinstance(raw, dict):
        raw = {}
    items = raw.get("items")
    if not isinstance(items, dict):
        items = {}
    raw["items"] = items
    failures = raw.get("failures")
    if not isinstance(failures, dict):
        failures = {}
    raw["failures"] = failures
    raw.setdefault("version", 2)
    return raw


def complete_translation(row: dict) -> bool:
    region = str(row.get("region") or "")
    if region == "JAPAN":
        if not str(row.get("titleJa") or "").strip():
            row["titleJa"] = str(row.get("title") or "").strip()
        if not str(row.get("bodyJa") or "").strip():
            row["bodyJa"] = str(row.get("body") or row.get("title") or "").strip()
    return all(isinstance(row.get(field), str) and row.get(field).strip() for field in TRANSLATION_FIELDS)


def merge_sol_news(rows: list, sol_items: list) -> int:
    index = {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        for key in (row.get("sourceUrl"), row.get("id")):
            if key:
                index[str(key)] = i

    merged_count = 0
    for item in sol_items:
        if not isinstance(item, dict):
            continue
        incoming = dict(item)
        if not incoming.get("sourceUrl") and not incoming.get("id"):
            continue
        incoming.setdefault("id", stable_id(incoming))
        incoming["solAdded"] = True

        hit = None
        for key in (incoming.get("sourceUrl"), incoming.get("id")):
            if key and str(key) in index:
                hit = index[str(key)]
                break

        if hit is None:
            rows.append(incoming)
            hit = len(rows) - 1
        else:
            existing = rows[hit]
            rows[hit] = {**existing, **incoming, "solAdded": True}

        row = rows[hit]
        for key in (row.get("sourceUrl"), row.get("id")):
            if key:
                index[str(key)] = hit
        merged_count += 1

    return merged_count


def find_override(row: dict, overrides: dict):
    for key in (row.get("sourceUrl"), row.get("id"), cache_key(row)):
        if key and isinstance(overrides.get(str(key)), dict):
            return overrides[str(key)]
    return None


def main() -> int:
    rows = read_json_required(NEWS_PATH, list)

    sol_news_raw = read_json(SOL_NEWS_PATH, {"version": 1, "items": []})
    sol_items = sol_news_raw.get("items", []) if isinstance(sol_news_raw, dict) else []
    if not isinstance(sol_items, list):
        sol_items = []

    overrides_raw = read_json(SOL_OVERRIDES_PATH, {"version": 1, "items": {}})
    overrides = overrides_raw.get("items", {}) if isinstance(overrides_raw, dict) else {}
    if not isinstance(overrides, dict):
        overrides = {}

    cache = normalize_translation_cache(read_json_required(TRANSLATIONS_PATH, dict))
    cache_items = cache["items"]
    cache_failures = cache["failures"]

    merged = merge_sol_news(rows, sol_items)
    now = int(time.time())
    locked_keys = set()
    applied = 0

    for row in rows:
        if not isinstance(row, dict):
            continue

        override = find_override(row, overrides)
        if override:
            for field in TRANSLATION_FIELDS:
                value = override.get(field)
                if isinstance(value, str) and value.strip():
                    row[field] = value.strip()
            reason = override.get("reason")
            if isinstance(reason, str) and reason.strip():
                row["solEditReason"] = reason.strip()
            row["solReviewed"] = True

        wants_lock = bool(override) or bool(row.get("solAdded"))
        if not wants_lock or not complete_translation(row):
            row.pop("solLocked", None)
            continue

        key = cache_key(row)
        if not key:
            continue

        updated = now
        for source in (override, row):
            if not isinstance(source, dict):
                continue
            for field in ("updatedAtEpoch", "solUpdatedAtEpoch", "reviewedAtEpoch"):
                try:
                    candidate = int(source.get(field) or 0)
                except Exception:
                    candidate = 0
                if candidate > 0:
                    updated = candidate
                    break
            if updated != now:
                break

        entry = {
            "contentHash": source_hash(row),
            "titleJa": row["titleJa"],
            "bodyJa": row["bodyJa"],
            "summaryJa": row["summaryJa"],
            "model": SOL_MODEL,
            "modelRevision": SOL_REVISION,
            "summaryFormatVersion": SUMMARY_FORMAT_VERSION,
            "updatedAtEpoch": updated,
            "managedBySol": True,
        }
        cache_items[key] = entry
        cache_failures.pop(key, None)
        locked_keys.add(key)

        row["solLocked"] = True
        row["aiProcessed"] = True
        row["aiModel"] = SOL_MODEL
        row["aiSummaryFormat"] = "facts-v2"
        applied += 1

    stale = [
        key for key, entry in cache_items.items()
        if isinstance(entry, dict) and entry.get("managedBySol") and key not in locked_keys
    ]
    for key in stale:
        cache_items.pop(key, None)

    rows.sort(key=lambda row: int((row or {}).get("publishedAtEpoch") or 0), reverse=True)
    write_json(NEWS_PATH, rows)
    write_json(TRANSLATIONS_PATH, cache)

    print(f"Sol supplemental news merged: {merged}")
    print(f"Sol translation locks applied: {applied}")
    print(f"Stale Sol cache locks removed: {len(stale)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
