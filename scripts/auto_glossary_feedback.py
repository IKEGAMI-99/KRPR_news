#!/usr/bin/env python3
"""Learn recurring, validator-driven translation corrections into the glossary.

Automatic quality corrections start as inactive candidates. A candidate is
promoted only after the same source->target mapping is observed in three
independent article-content observations. If competing targets reach the
threshold, automatic promotion is stopped and the candidates remain inactive
for Sol/human review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import translation_engine as engine
from glossary_schema import read_glossary, validate_glossary


PROVENANCE = "auto-quality-correction"
PROMOTION_THRESHOLD = 3
RETRY_RE = re.compile(
    r"error-aware retry \d+/3 (.+?): 中国語の一般語が残っています: (.+)$"
)

# Only terms for which the active quality prompt already prescribes a concrete
# Japanese choice (or a small explicit choice set) are eligible for automatic
# learning. Other residue terms still trigger retry, but are deliberately not
# persisted because inferring a reusable dictionary rule would be unsafe.
TARGET_CHOICES: dict[str, tuple[str, ...]] = {
    "礼包": ("パック", "セット"),
    "活动": ("イベント", "キャンペーン"),
    "任务": ("ミッション", "クエスト"),
    "合伙人": ("プレイヤー",),
    "网页链接": ("Webリンク",),
}


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _regions(entry: dict) -> tuple[str, ...]:
    return tuple(sorted(str(v).upper() for v in (entry.get("regions") or [])))


def _candidate_id(region: str, source: str, target: str) -> str:
    digest = hashlib.sha256(f"{region}\n{source}\n{target}".encode("utf-8")).hexdigest()[:16]
    return f"auto-quality-{digest}"


def _evidence_hash(row: dict, source: str, target: str) -> str:
    raw = "\n".join(
        [
            str(row.get("region") or ""),
            str(row.get("title") or ""),
            str(row.get("body") or ""),
            source,
            target,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _find_candidate(doc: dict, region: str, source: str, target: str) -> dict | None:
    wanted_regions = (region.upper(),)
    for entry in doc.get("entries", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("provenance") or "") != PROVENANCE:
            continue
        if str(entry.get("sourceText") or "") != source:
            continue
        if str(entry.get("targetText") or "") != target:
            continue
        if _regions(entry) != wanted_regions:
            continue
        return entry
    return None


def _authoritative_active_targets(doc: dict, source: str) -> set[str]:
    targets: set[str] = set()
    for entry in doc.get("entries", []):
        if not isinstance(entry, dict) or not entry.get("active", True):
            continue
        if str(entry.get("sourceText") or "") != source:
            continue
        if str(entry.get("provenance") or "") == PROVENANCE:
            continue
        target = str(entry.get("targetText") or "").strip()
        if target:
            targets.add(target)
    return targets


def _auto_candidates_for_source(doc: dict, source: str) -> list[dict]:
    return [
        entry
        for entry in doc.get("entries", [])
        if isinstance(entry, dict)
        and str(entry.get("provenance") or "") == PROVENANCE
        and str(entry.get("sourceText") or "") == source
    ]


def normalize_promotions(doc: dict) -> None:
    """Promote only an uncontested 3-observation mapping per source term."""
    sources = {
        str(entry.get("sourceText") or "")
        for entry in doc.get("entries", [])
        if isinstance(entry, dict) and str(entry.get("provenance") or "") == PROVENANCE
    }

    for source in sorted(s for s in sources if s):
        candidates = _auto_candidates_for_source(doc, source)
        authoritative = _authoritative_active_targets(doc, source)

        for entry in candidates:
            observations = sorted(set(str(v) for v in (entry.get("observedEvidenceHashes") or []) if v))
            entry["observedEvidenceHashes"] = observations
            entry["successCount"] = len(observations)
            entry["promotionThreshold"] = PROMOTION_THRESHOLD
            entry["active"] = False
            entry["verified"] = False
            entry["trainingEligible"] = False
            entry["confidence"] = round(min(0.55 + 0.13 * len(observations), 0.94), 2)

        if authoritative:
            for entry in candidates:
                target = str(entry.get("targetText") or "")
                if target in authoritative:
                    entry["notes"] = (
                        "自動品質チェック由来の候補。既存の監査済み辞書項目と同じ訳語のため、"
                        "候補として履歴のみ保持。"
                    )
                else:
                    entry["notes"] = (
                        "自動品質チェック由来の候補。既存の監査済み辞書項目と競合するため自動昇格しない。"
                    )
            continue

        eligible = [
            entry for entry in candidates if int(entry.get("successCount") or 0) >= PROMOTION_THRESHOLD
        ]
        eligible_targets = {str(entry.get("targetText") or "") for entry in eligible}

        if len(eligible_targets) == 1 and eligible:
            winner = max(eligible, key=lambda item: int(item.get("successCount") or 0))
            winner["active"] = True
            winner["verified"] = True
            winner["trainingEligible"] = True
            winner["confidence"] = 0.95
            winner["notes"] = (
                f"自動品質チェックの再翻訳で同一変換を{winner['successCount']}件確認。"
                "3件以上の独立観測により自動昇格。Sol監査で別の根拠が得られた場合はそちらを優先する。"
            )
        elif len(eligible_targets) > 1:
            for entry in eligible:
                entry["notes"] = (
                    "自動品質チェック由来の候補。同一原語で複数の訳語が昇格条件に達したため、"
                    "自動昇格を停止してSol監査待ち。"
                )


def add_observation(
    doc: dict,
    row: dict,
    source: str,
    target: str,
    *,
    now: int | None = None,
) -> bool:
    region = str(row.get("region") or "").upper()
    if not region or not source or not target:
        return False

    # If a non-auto active rule already teaches the same mapping, there is
    # nothing useful to learn automatically.
    for entry in doc.get("entries", []):
        if not isinstance(entry, dict) or not entry.get("active", True):
            continue
        if str(entry.get("provenance") or "") == PROVENANCE:
            continue
        if str(entry.get("sourceText") or "") == source and str(entry.get("targetText") or "") == target:
            return False

    timestamp = int(now if now is not None else time.time())
    candidate = _find_candidate(doc, region, source, target)
    if candidate is None:
        candidate = {
            "id": _candidate_id(region, source, target),
            "sourceText": source,
            "targetText": target,
            "sourceLanguage": "zh",
            "targetLanguage": "ja",
            "category": "auto_quality_term",
            "behavior": "translate",
            "regions": [region],
            "contextHints": ["自動品質チェックで検出され、再翻訳で解消された一般語"],
            "avoidTranslations": [],
            "active": False,
            "trainingEligible": False,
            "trainingWeight": 1.0,
            "verified": False,
            "confidence": 0.55,
            "provenance": PROVENANCE,
            "evidenceUrls": [],
            "notes": "自動品質チェック由来の候補。3件一致するまでランタイム辞書・LoRA seedには使用しない。",
            "createdAtEpoch": timestamp,
            "updatedAtEpoch": timestamp,
            "successCount": 0,
            "promotionThreshold": PROMOTION_THRESHOLD,
            "observedEvidenceHashes": [],
        }
        doc.setdefault("entries", []).append(candidate)

    evidence = _evidence_hash(row, source, target)
    observed = set(str(v) for v in (candidate.get("observedEvidenceHashes") or []) if v)
    if evidence in observed:
        return False
    observed.add(evidence)
    candidate["observedEvidenceHashes"] = sorted(observed)
    candidate["updatedAtEpoch"] = timestamp

    source_url = str(row.get("sourceUrl") or "").strip()
    urls = [str(v) for v in (candidate.get("evidenceUrls") or []) if str(v).strip()]
    if source_url and source_url not in urls:
        urls.append(source_url)
    candidate["evidenceUrls"] = urls[-8:]

    normalize_promotions(doc)
    validate_glossary(doc)
    return True


def parse_retry_terms(log_text: str) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for raw_line in log_text.splitlines():
        line = raw_line.strip()
        match = RETRY_RE.search(line)
        if not match:
            continue
        key = match.group(1).strip()
        terms = {term.strip() for term in match.group(2).split(",") if term.strip()}
        eligible = {term for term in terms if term in TARGET_CHOICES}
        if eligible:
            result.setdefault(key, set()).update(eligible)
    return result


def _accepted_target(source: str, translated_text: str) -> str | None:
    if source in translated_text:
        return None
    choices = TARGET_CHOICES.get(source, ())
    found = [choice for choice in choices if choice in translated_text]
    if len(found) != 1:
        return None
    return found[0]


def record_from_log(log_path: Path) -> int:
    retries = parse_retry_terms(log_path.read_text(encoding="utf-8", errors="replace"))
    if not retries:
        print("auto glossary feedback: no eligible quality corrections in log")
        return 0

    rows = engine.read_json(engine.NEWS_PATH, [])
    cache = engine.normalized_cache(engine.read_json(engine.CACHE_PATH, {}))
    if not isinstance(rows, list):
        print("auto glossary feedback: news data is not a list")
        return 0

    row_by_key = {engine.cache_key(row): row for row in rows if isinstance(row, dict)}
    items = cache.get("items", {}) if isinstance(cache, dict) else {}
    glossary = read_glossary(engine.GLOSSARY_PATH)
    changed = 0

    for key, terms in retries.items():
        row = row_by_key.get(key)
        entry = items.get(key) if isinstance(items, dict) else None
        if not row or not engine.content_entry_valid(row, entry):
            continue
        if (entry or {}).get("managedBySol") or "GPT-5.6 Sol" in str((entry or {}).get("model") or ""):
            continue
        translated = "\n".join(str((entry or {}).get(field) or "") for field in engine.TRANSLATION_FIELDS)
        for source in sorted(terms):
            target = _accepted_target(source, translated)
            if not target:
                continue
            if add_observation(glossary, row, source, target):
                changed += 1
                print(f"auto glossary feedback: observed {source} -> {target} ({key})")

    if changed:
        normalize_promotions(glossary)
        validate_glossary(glossary)
        _write_json(engine.GLOSSARY_PATH, glossary)
    print(f"auto glossary feedback: observations_added={changed}")
    return changed


def merge_incoming(incoming_path: Path) -> int:
    current = read_glossary(engine.GLOSSARY_PATH)
    incoming = read_glossary(incoming_path)
    changed = 0

    for inc in incoming.get("entries", []):
        if not isinstance(inc, dict) or str(inc.get("provenance") or "") != PROVENANCE:
            continue
        region_values = _regions(inc)
        if len(region_values) != 1:
            continue
        region = region_values[0]
        source = str(inc.get("sourceText") or "")
        target = str(inc.get("targetText") or "")
        cur = _find_candidate(current, region, source, target)
        if cur is None:
            current.setdefault("entries", []).append(dict(inc))
            changed += 1
            continue

        before = json.dumps(cur, ensure_ascii=False, sort_keys=True)
        observed = set(str(v) for v in (cur.get("observedEvidenceHashes") or []) if v)
        observed.update(str(v) for v in (inc.get("observedEvidenceHashes") or []) if v)
        cur["observedEvidenceHashes"] = sorted(observed)

        urls = [str(v) for v in (cur.get("evidenceUrls") or []) if str(v).strip()]
        for value in inc.get("evidenceUrls") or []:
            value = str(value).strip()
            if value and value not in urls:
                urls.append(value)
        cur["evidenceUrls"] = urls[-8:]
        cur["createdAtEpoch"] = min(
            int(cur.get("createdAtEpoch") or 0) or int(inc.get("createdAtEpoch") or 0),
            int(inc.get("createdAtEpoch") or 0) or int(cur.get("createdAtEpoch") or 0),
        )
        cur["updatedAtEpoch"] = max(
            int(cur.get("updatedAtEpoch") or 0), int(inc.get("updatedAtEpoch") or 0)
        )
        after = json.dumps(cur, ensure_ascii=False, sort_keys=True)
        if before != after:
            changed += 1

    if changed:
        normalize_promotions(current)
        validate_glossary(current)
        _write_json(engine.GLOSSARY_PATH, current)
    print(f"auto glossary feedback merge: entries_changed={changed}")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("record")
    record.add_argument("--log", required=True, type=Path)
    merge = sub.add_parser("merge")
    merge.add_argument("--incoming", required=True, type=Path)
    args = parser.parse_args()

    if args.command == "record":
        record_from_log(args.log)
        return 0
    if args.command == "merge":
        merge_incoming(args.incoming)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
