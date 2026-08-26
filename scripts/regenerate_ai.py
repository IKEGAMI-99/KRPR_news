#!/usr/bin/env python3
import argparse
import os
import time
from pathlib import Path

from translate_news_llm import (
    NEWS_PATH,
    CACHE_PATH,
    MODEL_ID,
    MODEL_VARIANT,
    MODEL_REVISION,
    apply_cache,
    cache_key,
    infer_one,
    normalized_cache,
    prune_cache,
    read_json,
    source_hash,
    write_json,
)


def main():
    parser = argparse.ArgumentParser(description="Regenerate one article translation/summary.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--article-id", required=True)
    args = parser.parse_args()

    rows = read_json(NEWS_PATH, [])
    if not isinstance(rows, list):
        rows = []
    row = next((r for r in rows if str(r.get("id") or "") == args.article_id), None)
    if not row:
        raise SystemExit(f"article not found: {args.article_id}")

    cache = normalized_cache(read_json(CACHE_PATH, {}))
    key = cache_key(row)
    previous = cache.get("items", {}).get(key)
    cache["items"].pop(key, None)

    model_path = Path(args.model).expanduser()
    if not model_path.is_file():
        raise SystemExit(f"model not found: {model_path}")

    from llama_cpp import Llama
    threads = max(2, min(4, os.cpu_count() or 4))
    llm = Llama(
        model_path=str(model_path),
        n_ctx=4096,
        n_batch=128,
        n_threads=threads,
        n_threads_batch=threads,
        verbose=False,
    )
    result = infer_one(llm, row)
    if not result:
        if previous:
            cache["items"][key] = previous
        write_json(CACHE_PATH, cache)
        raise SystemExit("LLM regeneration failed; previous result restored")

    cache["items"][key] = {
        "contentHash": source_hash(row),
        **result,
        "model": f"{MODEL_ID}:{MODEL_VARIANT}",
        "modelRevision": MODEL_REVISION,
        "updatedAtEpoch": int(time.time()),
        "regenerated": True,
    }
    prune_cache(cache)
    apply_cache(rows, cache)
    write_json(CACHE_PATH, cache)
    write_json(NEWS_PATH, rows)
    print(f"regenerated AI result: {args.article_id}")


if __name__ == "__main__":
    main()
