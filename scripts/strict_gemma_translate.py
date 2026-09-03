#!/usr/bin/env python3
"""Run the strict Japanese translation pipeline with Gemma 4 E4B on LiteRT-LM."""

import argparse
import os
import sys
import time
from pathlib import Path

import translation_engine as engine
import translation_quality as strict

MODEL_ID = "litert-community/gemma-4-E4B-it-litert-lm"
MODEL_VARIANT = "LiteRT-LM"
MODEL_REVISION = "gemma-4-e4b-it-litertlm-summary-facts-region-titles-strict-ja-v2"
SUMMARY_FORMAT_VERSION = 4
CONTEXT_TOKEN_LIMIT = 8192
OUTPUT_TOKEN_LIMIT = 3000
FAILED_ATTEMPTS_PER_ARTICLE = 3
FAILURE_COOLDOWN_SECONDS = 3 * 60 * 60

_BASE_VALID_ENTRY = engine.valid_entry


def gemma_entry_valid(row: dict, entry) -> bool:
    """Only current Gemma results (or explicit Sol-reviewed locks) count as complete.

    Older model revisions remain visible until their turn comes, but stay in the
    pending queue so the active batched worker replaces them. Newer articles win
    because engine.pending_rows sorts newest first.
    """
    if not engine.content_entry_valid(row, entry):
        return False
    if not isinstance(entry, dict):
        return False

    model = str(entry.get("model") or "")
    if entry.get("managedBySol") or "GPT-5.6 Sol" in model:
        return True

    return (
        model == f"{MODEL_ID}:{MODEL_VARIANT}"
        and str(entry.get("modelRevision") or "") == MODEL_REVISION
        and int(entry.get("summaryFormatVersion") or 0) == SUMMARY_FORMAT_VERSION
    )


def configure_gemma() -> None:
    engine.MODEL_ID = MODEL_ID
    engine.MODEL_VARIANT = MODEL_VARIANT
    engine.MODEL_REVISION = MODEL_REVISION
    engine.SUMMARY_FORMAT_VERSION = SUMMARY_FORMAT_VERSION
    engine.valid_entry = gemma_entry_valid
    strict.STRICT_MODEL_REVISION = MODEL_REVISION
    strict.STRICT_MAX_OUTPUT_TOKENS = OUTPUT_TOKEN_LIMIT


def failure_records(cache: dict) -> dict:
    records = cache.get("failures")
    if not isinstance(records, dict):
        records = {}
        cache["failures"] = records
    return records


def prune_failure_records(rows: list, cache: dict) -> int:
    """Remove stale cooldowns after source changes or a valid result arrives."""
    records = failure_records(cache)
    items = cache.get("items", {})
    row_by_key = {
        engine.cache_key(row): row
        for row in rows
        if isinstance(row, dict) and engine.cache_key(row)
    }
    stale = []
    for key, record in records.items():
        row = row_by_key.get(key)
        if not row or not isinstance(record, dict):
            stale.append(key)
            continue
        if record.get("contentHash") != engine.source_hash(row):
            stale.append(key)
            continue
        if engine.valid_entry(row, items.get(key)):
            stale.append(key)
    for key in stale:
        records.pop(key, None)
    return len(stale)


def partition_pending_rows(pending: list, cache: dict, now_epoch: int) -> tuple[list, list]:
    """Keep cooling articles behind runnable work without changing base priority."""
    records = failure_records(cache)
    runnable = []
    deferred = []
    for row in pending:
        key = engine.cache_key(row)
        record = records.get(key)
        if not isinstance(record, dict):
            runnable.append(row)
            continue
        if record.get("contentHash") != engine.source_hash(row):
            records.pop(key, None)
            runnable.append(row)
            continue
        try:
            retry_after = int(record.get("retryAfterEpoch") or 0)
        except (TypeError, ValueError):
            retry_after = 0
        try:
            last_failure = int(record.get("lastFailureAtEpoch") or 0)
        except (TypeError, ValueError):
            last_failure = 0
        if last_failure > 0:
            current_policy_retry = last_failure + FAILURE_COOLDOWN_SECONDS
            retry_after = min(retry_after, current_policy_retry) if retry_after else current_policy_retry
            record["retryAfterEpoch"] = retry_after
        if retry_after > now_epoch:
            deferred.append(row)
        else:
            runnable.append(row)
    return runnable, deferred


def defer_failed_row(cache: dict, row: dict, now_epoch: int) -> dict:
    """Record one exhausted three-attempt inference cycle for an article."""
    records = failure_records(cache)
    key = engine.cache_key(row)
    content_hash = engine.source_hash(row)
    previous = records.get(key)
    if not isinstance(previous, dict) or previous.get("contentHash") != content_hash:
        previous = {}
    try:
        failed_attempts = int(previous.get("failedAttempts") or 0)
    except (TypeError, ValueError):
        failed_attempts = 0
    try:
        failed_runs = int(previous.get("failedRuns") or 0)
    except (TypeError, ValueError):
        failed_runs = 0
    record = {
        "contentHash": content_hash,
        "failedAttempts": failed_attempts + FAILED_ATTEMPTS_PER_ARTICLE,
        "failedRuns": failed_runs + 1,
        "lastFailureAtEpoch": int(now_epoch),
        "retryAfterEpoch": int(now_epoch) + FAILURE_COOLDOWN_SECONDS,
    }
    records[key] = record
    return record


def clear_failure_record(cache: dict, row: dict) -> None:
    failure_records(cache).pop(engine.cache_key(row), None)


class LiteRTChatAdapter:
    """OpenAI-style adapter so the existing strict inference code can stay intact."""

    def __init__(self, model_path: str):
        import litert_lm

        self.litert_lm = litert_lm
        threads = max(2, min(4, os.cpu_count() or 4))
        cache_dir = str(Path.home() / ".cache" / "kirapara-litert-runtime")
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        self.runtime = litert_lm.Engine(
            model_path,
            backend=litert_lm.Backend.CPU(thread_count=threads),
            max_num_tokens=CONTEXT_TOKEN_LIMIT,
            cache_dir=cache_dir,
        )

    def close(self) -> None:
        self.runtime.close()

    def create_chat_completion(
        self,
        *,
        messages,
        temperature=0.0,
        top_p=0.9,
        max_tokens=OUTPUT_TOKEN_LIMIT,
        seed=42,
        **_kwargs,
    ):
        system_text = "\n\n".join(
            str(item.get("content") or "")
            for item in messages
            if item.get("role") == "system"
        ).strip()
        user_text = "\n\n".join(
            str(item.get("content") or "")
            for item in messages
            if item.get("role") != "system"
        ).strip()

        sampler = self.litert_lm.SamplerConfig(
            top_k=40,
            top_p=float(top_p),
            temperature=float(temperature),
            seed=int(seed),
        )

        with self.runtime.create_conversation(
            system_message=system_text or None,
            sampler_config=sampler,
            max_output_tokens=int(max_tokens),
            automatic_tool_calling=False,
        ) as conversation:
            response = conversation.send_message(
                user_text,
                max_output_tokens=int(max_tokens),
            )

        parts = response.get("content", []) if isinstance(response, dict) else []
        text_parts = []
        for part in parts if isinstance(parts, list) else [parts]:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(str(part.get("text") or ""))
            elif isinstance(part, str):
                text_parts.append(part)
        text = "".join(text_parts).strip()
        return {"choices": [{"message": {"content": text}}]}


def cmd_translate_litert(args) -> int:
    model_path = Path(args.model or os.getenv("LLM_MODEL_PATH", "")).expanduser()
    if not model_path.is_file():
        print(f"model not found: {model_path}", file=sys.stderr)
        return 2

    rows = engine.read_json(engine.NEWS_PATH, [])
    if not isinstance(rows, list):
        rows = []
    cache = engine.normalized_cache(engine.read_json(engine.CACHE_PATH, {}))
    engine.apply_cache(rows, cache)
    prune_failure_records(rows, cache)
    pending = engine.pending_rows(rows, cache)
    now_epoch = int(time.time())
    runnable, deferred = partition_pending_rows(pending, cache, now_epoch)
    limit = max(1, int(args.max_items or os.getenv("LLM_MAX_ITEMS", "10")))
    selected = runnable[:limit]

    if not selected:
        engine.write_json(engine.NEWS_PATH, rows)
        engine.write_json(engine.CACHE_PATH, cache)
        if deferred:
            retry_times = []
            records = failure_records(cache)
            for row in deferred:
                try:
                    retry_times.append(int((records.get(engine.cache_key(row)) or {}).get("retryAfterEpoch") or 0))
                except (TypeError, ValueError):
                    continue
            next_retry = min((value for value in retry_times if value > now_epoch), default=0)
            print(
                "no runnable items; "
                f"deferred={len(deferred)} nextRetryAtEpoch={next_retry}"
            )
        else:
            print("no new items need LLM processing")
        return 0

    llm = LiteRTChatAdapter(str(model_path))
    successes = 0
    failures = 0
    try:
        for index, row in enumerate(selected, 1):
            key = engine.cache_key(row)
            print(
                f"[{index}/{len(selected)}] Gemma4/LiteRT "
                f"{row.get('region')} {row.get('platform')}: "
                f"{str(row.get('title') or '')[:70]}"
            )
            result = engine.infer_one(llm, row)
            if not result:
                failures += 1
                failure = defer_failed_row(cache, row, int(time.time()))
                print(
                    f"  failed and deferred: {key} "
                    f"attempts={failure['failedAttempts']} "
                    f"retryAfterEpoch={failure['retryAfterEpoch']}",
                    file=sys.stderr,
                )
                engine.write_json(engine.CACHE_PATH, cache)
                continue

            entry = {
                "contentHash": engine.source_hash(row),
                **result,
                "model": f"{MODEL_ID}:{MODEL_VARIANT}",
                "modelRevision": MODEL_REVISION,
                "summaryFormatVersion": SUMMARY_FORMAT_VERSION,
                "updatedAtEpoch": int(time.time()),
            }
            cache["items"][key] = entry
            clear_failure_record(cache, row)
            successes += 1

            engine.apply_cache(rows, cache)
            engine.prune_cache(cache)
            engine.write_json(engine.CACHE_PATH, cache)
            engine.write_json(engine.NEWS_PATH, rows)
    finally:
        llm.close()

    engine.apply_cache(rows, cache)
    engine.prune_cache(cache)
    engine.write_json(engine.CACHE_PATH, cache)
    engine.write_json(engine.NEWS_PATH, rows)
    remaining = len(engine.pending_rows(rows, cache))
    _runnable, deferred = partition_pending_rows(
        engine.pending_rows(rows, cache), cache, int(time.time())
    )
    print(
        f"Gemma4/LiteRT processed: success={successes} failed={failures} "
        f"deferred={len(deferred)} remaining={remaining}"
    )
    return 0 if successes or not selected else 1


def run_regenerate_litert(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Regenerate one article with Gemma 4 E4B LiteRT-LM.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--article-id", required=True)
    args = parser.parse_args(argv)

    strict.patch_engine()
    rows = engine.read_json(engine.NEWS_PATH, [])
    if not isinstance(rows, list):
        rows = []
    row = next((r for r in rows if str(r.get("id") or "") == args.article_id), None)
    if not row:
        print(f"article not found: {args.article_id}", file=sys.stderr)
        return 2

    cache = engine.normalized_cache(engine.read_json(engine.CACHE_PATH, {}))
    key = engine.cache_key(row)
    previous = cache.get("items", {}).get(key)
    cache["items"].pop(key, None)

    model_path = Path(args.model).expanduser()
    if not model_path.is_file():
        print(f"model not found: {model_path}", file=sys.stderr)
        return 2

    llm = LiteRTChatAdapter(str(model_path))
    try:
        result = engine.infer_one(llm, row)
    finally:
        llm.close()

    if not result:
        if previous:
            cache["items"][key] = previous
        engine.write_json(engine.CACHE_PATH, cache)
        print("LLM regeneration failed; previous result restored", file=sys.stderr)
        return 1

    cache["items"][key] = {
        "contentHash": engine.source_hash(row),
        **result,
        "model": f"{MODEL_ID}:{MODEL_VARIANT}",
        "modelRevision": MODEL_REVISION,
        "summaryFormatVersion": SUMMARY_FORMAT_VERSION,
        "updatedAtEpoch": int(time.time()),
        "regenerated": True,
    }
    clear_failure_record(cache, row)
    engine.prune_cache(cache)
    engine.apply_cache(rows, cache)
    engine.write_json(engine.CACHE_PATH, cache)
    engine.write_json(engine.NEWS_PATH, rows)
    print(f"regenerated AI result with Gemma4/LiteRT: {args.article_id}")
    return 0


def main() -> int:
    configure_gemma()
    if len(sys.argv) >= 2 and sys.argv[1] == "regenerate":
        return run_regenerate_litert(sys.argv[2:])
    engine.cmd_translate = cmd_translate_litert
    return strict.main()


if __name__ == "__main__":
    raise SystemExit(main())
