#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
TRANSLATIONS_PATH = ROOT / "data" / "translations.json"
SOL_OVERRIDES_PATH = ROOT / "data" / "sol_overrides.json"
SOL_AUDIT_STATE_PATH = ROOT / "data" / "sol_audit_state.json"

AI_FIELDS = {
    "titleJa",
    "bodyJa",
    "summaryJa",
    "aiProcessed",
    "aiModel",
    "aiSummaryFormat",
    "solLocked",
    "solReviewed",
    "solEditReason",
    "solUpdatedAtEpoch",
    "reviewedAtEpoch",
}


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    rows = read_json(NEWS_PATH, [])
    if not isinstance(rows, list):
        rows = []

    cleaned = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        touched = False
        for field in AI_FIELDS:
            if field in row:
                row.pop(field, None)
                touched = True
        if touched:
            cleaned += 1

    rows.sort(key=lambda row: int((row or {}).get("publishedAtEpoch") or 0), reverse=True)
    write_json(NEWS_PATH, rows)
    write_json(TRANSLATIONS_PATH, {
        "version": 2,
        "model": "LiquidAI/LFM2.5-8B-A1B-GGUF:Q4_K_M",
        "modelRevision": "lfm2.5-8b-a1b-q4-k-m-summary-facts-region-titles-strict-ja-v1",
        "items": {},
    })
    write_json(SOL_OVERRIDES_PATH, {"version": 1, "items": {}})
    write_json(SOL_AUDIT_STATE_PATH, {
        "version": 1,
        "initialAuditComplete": False,
        "audited": {},
        "lastRunAt": 0,
    })

    print(f"AI state reset: articles={len(rows)} cleaned={cleaned}")
    print("Translation cache cleared")
    print("Sol translation overrides and audit state cleared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
