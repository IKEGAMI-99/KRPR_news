#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

from glossary_schema import read_glossary, runtime_flat_map


ROOT = Path(__file__).resolve().parents[1]
GLOSSARY_PATH = ROOT / "data" / "translation_glossary.json"
SCRIPTS_DIR = ROOT / "scripts"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: run_with_runtime_glossary.py SCRIPT [ARGS...]", file=sys.stderr)
        return 2

    script = (ROOT / sys.argv[1]).resolve()
    if SCRIPTS_DIR not in script.parents or not script.is_file():
        print(f"refusing to run non-project script: {script}", file=sys.stderr)
        return 2

    original = GLOSSARY_PATH.read_text(encoding="utf-8")
    doc = read_glossary(GLOSSARY_PATH)
    runtime = runtime_flat_map(doc)

    try:
        # translate_news_llm.py currently consumes a simple mapping. Provide that
        # view only inside this isolated Actions workspace, while keeping the
        # repository's authoritative glossary rich enough for future LoRA use.
        GLOSSARY_PATH.write_text(
            json.dumps(runtime, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        completed = subprocess.run(
            [sys.executable, "-u", str(script), *sys.argv[2:]],
            cwd=ROOT,
            env=env,
            check=False,
        )
        return int(completed.returncode)
    finally:
        GLOSSARY_PATH.write_text(original, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
