#!/usr/bin/env python3
"""Run the strict Japanese translation pipeline with Gemma 4 E4B on LiteRT-LM."""

import argparse
import os
import sys
import time
from pathlib import Path

import translate_news_llm as engine
import strict_qwen_translate as strict

MODEL_ID = "litert-community/gemma-4-E4B-it-litert-lm"
MODEL_VARIANT = "LiteRT-LM"
MODEL_REVISION = "gemma-4-e4b-it-litertlm-summary-facts-region-titles-strict-ja-v1"
SUMMARY_FORMAT_VERSION = 4


def configure_gemma() -> None:
    engine.MODEL_ID = MODEL_ID
    engine.MODEL_VARIANT = MODEL_VARIANT
    engine.MODEL_REVISION = MODEL_REVISION
    engine.SUMMARY_FORMAT_VERSION = SUMMARY_FORMAT_VERSION
    strict.STRICT_MODEL_REVISION = MODEL_REVISION


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
            max_num_tokens=4096,
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
        max_tokens=1000,
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
    pending = engine.pending_rows(rows, cache)
    limit = max(1, int(args.max_items or os.getenv("LLM_MAX_ITEMS", "10")))
    selected = pending[:limit]

    if not selected:
        engine.write_json(engine.NEWS_PATH, rows)
        engine.write_json(engine.CACHE_PATH, cache)
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
                print(f"  failed: {key}", file=sys.stderr)
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
    print(f"Gemma4/LiteRT processed: success={successes} failed={failures} remaining={remaining}")
    return 0 if successes or not selected else 1


def run_regenerate_litert(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Regenerate one article with Gemma 4 E4B LiteRT-LM.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--article-id", required=True)
    args = parser.parse_args(argv)

    strict.patch_qwen_module()
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
