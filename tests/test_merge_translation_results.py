import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from merge_translation_results import merge_caches  # noqa: E402


def entry(epoch, text, **extra):
    return {
        "titleJa": text,
        "bodyJa": text,
        "summaryJa": text,
        "updatedAtEpoch": epoch,
        **extra,
    }


class TranslationCacheMergeTests(unittest.TestCase):
    def test_newer_incoming_automatic_result_wins(self):
        current = {"items": {"article": entry(10, "old")}}
        incoming = {"items": {"article": entry(20, "new")}}
        merged, stats = merge_caches(current, incoming)
        self.assertEqual("new", merged["items"]["article"]["titleJa"])
        self.assertEqual(1, stats["replaced"])

    def test_newer_current_result_survives_stale_workflow_snapshot(self):
        current = {"items": {"article": entry(30, "published")}}
        incoming = {"items": {"article": entry(20, "stale")}}
        merged, stats = merge_caches(current, incoming)
        self.assertEqual("published", merged["items"]["article"]["titleJa"])
        self.assertEqual(1, stats["kept"])

    def test_reviewed_current_result_beats_newer_automatic_result(self):
        current = {
            "items": {
                "article": entry(10, "reviewed", managedBySol=True, model="GPT-5.6 Sol")
            }
        }
        incoming = {"items": {"article": entry(99, "automatic")}}
        merged, _stats = merge_caches(current, incoming)
        self.assertEqual("reviewed", merged["items"]["article"]["titleJa"])

    def test_reviewed_incoming_result_beats_automatic_current_result(self):
        current = {"items": {"article": entry(99, "automatic")}}
        incoming = {
            "items": {
                "article": entry(10, "reviewed", managedBySol=True, model="GPT-5.6 Sol")
            }
        }
        merged, _stats = merge_caches(current, incoming)
        self.assertEqual("reviewed", merged["items"]["article"]["titleJa"])

    def test_missing_entries_and_metadata_are_added(self):
        current = {"items": {}}
        incoming = {
            "version": 2,
            "model": "gemma",
            "modelRevision": "v2",
            "items": {"article": entry(10, "new")},
        }
        merged, stats = merge_caches(current, incoming)
        self.assertEqual("gemma", merged["model"])
        self.assertIn("article", merged["items"])
        self.assertEqual(1, stats["added"])


if __name__ == "__main__":
    unittest.main()
