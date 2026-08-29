import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from glossary_schema import active_entries, lora_seed_records, read_glossary, validate_glossary


class GlossaryLoRATests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / "data" / "translation_glossary.json"
        self.doc = read_glossary(self.path)

    def test_glossary_schema_is_valid(self):
        validate_glossary(self.doc)

    def test_lora_records_only_use_verified_training_entries(self):
        records = lora_seed_records(self.doc)
        expected_ids = {
            entry["id"]
            for entry in active_entries(self.doc)
            if entry.get("trainingEligible") and entry.get("verified")
        }
        actual_ids = {record["metadata"]["glossaryId"] for record in records}
        self.assertEqual(actual_ids, expected_ids)

    def test_lora_records_have_valid_chat_shape(self):
        for record in lora_seed_records(self.doc):
            self.assertEqual([m["role"] for m in record["messages"]], ["system", "user", "assistant"])
            self.assertTrue(record["messages"][2]["content"].strip())
            self.assertTrue(record["metadata"]["glossaryId"])

    def test_jsonl_serialization_is_deterministic(self):
        records = lora_seed_records(self.doc)
        first = "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + ("\n" if records else "")
        second = "\n".join(json.dumps(r, ensure_ascii=False) for r in lora_seed_records(self.doc)) + ("\n" if records else "")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
