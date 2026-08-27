#!/usr/bin/env python3
import json
from pathlib import Path


SCHEMA = "krpr.translation-glossary.v2"


def read_glossary(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and raw.get("schema") == SCHEMA and isinstance(raw.get("entries"), list):
        return raw
    if isinstance(raw, dict):
        # Legacy v1 flat map. Keep migration compatibility for older branches/tools.
        entries = []
        for index, (source, target) in enumerate(raw.items(), 1):
            if not isinstance(source, str) or not isinstance(target, str):
                continue
            entries.append({
                "id": f"legacy-{index}",
                "sourceText": source,
                "targetText": target,
                "sourceLanguage": "unknown",
                "targetLanguage": "ja",
                "category": "legacy",
                "behavior": "preserve" if source == target else "translate",
                "regions": [],
                "contextHints": [],
                "avoidTranslations": [],
                "active": True,
                "trainingEligible": False,
                "trainingWeight": 1.0,
                "verified": False,
                "confidence": 0.5,
                "provenance": "legacy-v1",
                "evidenceUrls": [],
                "notes": "Migrated in memory from v1 flat glossary.",
            })
        return {
            "version": 2,
            "schema": SCHEMA,
            "defaultTargetLanguage": "ja",
            "entries": entries,
        }
    raise ValueError("translation glossary must be a JSON object")


def active_entries(doc: dict) -> list[dict]:
    entries = doc.get("entries", []) if isinstance(doc, dict) else []
    return [entry for entry in entries if isinstance(entry, dict) and entry.get("active", True)]


def validate_glossary(doc: dict) -> None:
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"unsupported glossary schema: {doc.get('schema')!r}")
    ids = set()
    scoped = {}
    for entry in active_entries(doc):
        entry_id = str(entry.get("id") or "").strip()
        source = str(entry.get("sourceText") or "").strip()
        target = str(entry.get("targetText") or "").strip()
        behavior = str(entry.get("behavior") or "translate")
        regions = tuple(sorted(str(value) for value in (entry.get("regions") or [])))
        if not entry_id or not source or not target:
            raise ValueError("active glossary entries require id, sourceText and targetText")
        if entry_id in ids:
            raise ValueError(f"duplicate glossary id: {entry_id}")
        ids.add(entry_id)
        if behavior not in {"translate", "preserve"}:
            raise ValueError(f"unsupported glossary behavior for {entry_id}: {behavior}")
        key = (source, regions)
        previous = scoped.get(key)
        if previous is not None and previous != target:
            raise ValueError(f"conflicting scoped glossary mapping for {source}: {previous} / {target}")
        scoped[key] = target


def runtime_flat_map(doc: dict) -> dict[str, str]:
    """Build the legacy flat map consumed by the current Qwen prompt code.

    The structured file stays authoritative. If future entries require the same
    sourceText to map differently by region, this function fails loudly instead
    of silently teaching Qwen a wrong global replacement.
    """
    validate_glossary(doc)
    result = {}
    for entry in active_entries(doc):
        source = str(entry.get("sourceText") or "").strip()
        target = str(entry.get("targetText") or "").strip()
        if source in result and result[source] != target:
            raise ValueError(
                f"runtime glossary ambiguity for {source!r}; update translate_news_llm.py to use scoped entries"
            )
        result[source] = target
    return result


def lora_seed_records(doc: dict) -> list[dict]:
    """Convert verified training-eligible terms to future SFT/LoRA seed records."""
    validate_glossary(doc)
    records = []
    for entry in active_entries(doc):
        if not entry.get("trainingEligible") or not entry.get("verified"):
            continue
        source = str(entry.get("sourceText") or "").strip()
        target = str(entry.get("targetText") or "").strip()
        behavior = str(entry.get("behavior") or "translate")
        hints = [str(value) for value in (entry.get("contextHints") or []) if str(value).strip()]
        regions = [str(value) for value in (entry.get("regions") or []) if str(value).strip()]
        context = " / ".join(hints) if hints else "ゲーム公式告知の用語"
        region_text = ", ".join(regions) if regions else "ALL"
        instruction = (
            "次の『きらめきパラダイス / Life Makeover』系公式告知の用語を、"
            "KRPRの日本語表記ルールに従って出力してください。固有名詞を保持する指定なら翻訳しないでください。"
        )
        user = f"region={region_text}\ncontext={context}\nsource={source}"
        records.append({
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": user},
                {"role": "assistant", "content": target},
            ],
            "metadata": {
                "glossaryId": entry.get("id"),
                "task": "term_preservation" if behavior == "preserve" else "term_translation",
                "sourceLanguage": entry.get("sourceLanguage"),
                "targetLanguage": entry.get("targetLanguage", "ja"),
                "category": entry.get("category"),
                "regions": regions,
                "trainingWeight": float(entry.get("trainingWeight") or 1.0),
                "avoidTranslations": entry.get("avoidTranslations") or [],
                "confidence": float(entry.get("confidence") or 0.0),
                "provenance": entry.get("provenance"),
                "evidenceUrls": entry.get("evidenceUrls") or [],
            },
        })
    return records
