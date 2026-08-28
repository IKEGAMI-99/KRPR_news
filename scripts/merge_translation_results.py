#!/usr/bin/env python3
"""Merge a translation-cache snapshot without losing newer reviewed results."""

import argparse
import json
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "data" / "translations.json"
TIME_FIELDS = ("updatedAtEpoch", "solUpdatedAtEpoch", "reviewedAtEpoch")


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def is_reviewed(entry) -> bool:
    if not isinstance(entry, dict):
        return False
    model = str(entry.get("model") or "")
    return bool(
        entry.get("managedBySol")
        or entry.get("solLocked")
        or entry.get("solReviewed")
        or "GPT-5.6 Sol" in model
    )


def entry_epoch(entry) -> int:
    if not isinstance(entry, dict):
        return 0
    epochs = []
    for field in TIME_FIELDS:
        try:
            epochs.append(int(entry.get(field) or 0))
        except (TypeError, ValueError):
            continue
    return max(epochs, default=0)


def choose_entry(current, incoming):
    """Prefer reviewed data first, then the newest automatic result.

    Ties intentionally keep the current main-branch value. This makes retries
    idempotent and prevents an older workflow snapshot from replacing an equal-
    timestamp value that has already been published.
    """
    if not isinstance(current, dict):
        return deepcopy(incoming)
    if not isinstance(incoming, dict):
        return deepcopy(current)

    current_reviewed = is_reviewed(current)
    incoming_reviewed = is_reviewed(incoming)
    if current_reviewed != incoming_reviewed:
        return deepcopy(incoming if incoming_reviewed else current)
    if entry_epoch(incoming) > entry_epoch(current):
        return deepcopy(incoming)
    return deepcopy(current)


def merge_caches(current, incoming):
    current_doc = current if isinstance(current, dict) else {}
    incoming_doc = incoming if isinstance(incoming, dict) else {}
    result = deepcopy(current_doc)

    for field in ("version", "model", "modelRevision"):
        if field not in result and field in incoming_doc:
            result[field] = deepcopy(incoming_doc[field])

    current_items = current_doc.get("items")
    incoming_items = incoming_doc.get("items")
    if not isinstance(current_items, dict):
        current_items = {}
    if not isinstance(incoming_items, dict):
        incoming_items = {}

    merged_items = deepcopy(current_items)
    added = 0
    replaced = 0
    kept = 0
    for key, incoming_entry in incoming_items.items():
        if key not in merged_items:
            merged_items[key] = deepcopy(incoming_entry)
            added += 1
            continue
        chosen = choose_entry(merged_items[key], incoming_entry)
        if chosen == merged_items[key]:
            kept += 1
        else:
            merged_items[key] = chosen
            replaced += 1

    result["items"] = merged_items
    return result, {"added": added, "replaced": replaced, "kept": kept}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Semantically merge an incoming Kirapara translation cache."
    )
    parser.add_argument("--incoming", required=True, type=Path)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()

    current = read_json(args.target, {})
    incoming = read_json(args.incoming, {})
    merged, stats = merge_caches(current, incoming)
    write_json(args.target, merged)
    print(
        "translation cache merge: "
        f"added={stats['added']} replaced={stats['replaced']} kept={stats['kept']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
