#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from glossary_schema import lora_seed_records, read_glossary


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GLOSSARY = ROOT / "data" / "translation_glossary.json"
DEFAULT_OUTPUT = ROOT / "data" / "training" / "glossary_lora_seed.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export verified KRPR glossary entries as SFT/LoRA seed JSONL.")
    parser.add_argument("--glossary", default=str(DEFAULT_GLOSSARY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    glossary_path = Path(args.glossary).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    records = lora_seed_records(read_glossary(glossary_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"LoRA glossary seed exported: {len(records)} records -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
