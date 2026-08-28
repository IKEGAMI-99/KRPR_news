#!/usr/bin/env python3
"""Run the strict Japanese translation pipeline with Gemma 4 E4B.

The shared translation engine is model-agnostic. This wrapper switches runtime
metadata to Gemma 4 E4B and bumps the summary format so older LFM2.5 cache
entries are gradually regenerated with the new model.
"""

import translate_news_llm as engine
import strict_qwen_translate as strict

MODEL_ID = "unsloth/gemma-4-E4B-it-GGUF"
MODEL_VARIANT = "Q4_K_M"
MODEL_REVISION = "gemma-4-e4b-it-q4-k-m-summary-facts-region-titles-strict-ja-v1"
SUMMARY_FORMAT_VERSION = 4


def configure_gemma() -> None:
    engine.MODEL_ID = MODEL_ID
    engine.MODEL_VARIANT = MODEL_VARIANT
    engine.MODEL_REVISION = MODEL_REVISION
    engine.SUMMARY_FORMAT_VERSION = SUMMARY_FORMAT_VERSION
    strict.STRICT_MODEL_REVISION = MODEL_REVISION


def main() -> int:
    configure_gemma()
    return strict.main()


if __name__ == "__main__":
    raise SystemExit(main())
