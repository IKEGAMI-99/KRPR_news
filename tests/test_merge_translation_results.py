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

    def test_newer_failure_cooldown_survives_parallel_writer_merge(self):
        current = {
            "items": {},
            "failures": {
                "article": {
                    "lastFailureAtEpoch": 10,
                    "retryAfterEpoch": 20,
                }
            },
        }
        incoming = {
            "items": {},
            "failures": {
                "article": {
                    "lastFailureAtEpoch": 30,
                    "retryAfterEpoch": 40,
                }
            },
        }

        merged, stats = merge_caches(current, incoming)

        self.assertEqual(40, merged["failures"]["article"]["retryAfterEpoch"])
        self.assertEqual(1, stats["failure_replaced"])

    def test_new_translation_clears_older_failure_cooldown(self):
        current = {
            "items": {"article": entry(10, "old")},
            "failures": {
                "article": {
                    "lastFailureAtEpoch": 20,
                    "retryAfterEpoch": 99,
                }
            },
        }
        incoming = {
            "items": {"article": entry(30, "translated")},
            "failures": {},
        }

        merged, stats = merge_caches(current, incoming)

        self.assertNotIn("article", merged["failures"])
        self.assertEqual(1, stats["failure_cleared"])

    def test_failure_newer_than_old_translation_is_kept(self):
        current = {
            "items": {"article": entry(10, "old")},
            "failures": {
                "article": {
                    "lastFailureAtEpoch": 20,
                    "retryAfterEpoch": 99,
                }
            },
        }

        merged, _stats = merge_caches(current, {"items": {}})

        self.assertIn("article", merged["failures"])


if __name__ == "__main__":
    unittest.main()
