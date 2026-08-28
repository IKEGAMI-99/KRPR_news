import importlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


class PreserveOfficialXHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = importlib.import_module("preserve_official_x_history")

    def row(self, region, handle, status, epoch, title="item"):
        return {
            "id": str(status),
            "region": region,
            "platform": "公式X",
            "title": title,
            "body": title,
            "sourceUrl": f"https://x.com/{handle}/status/{status}",
            "publishedAtEpoch": epoch,
        }

    def test_missing_global_x_rows_are_restored(self):
        now = 2_000_000_000
        current = [
            {
                "id": "youtube",
                "region": "GLOBAL",
                "platform": "公式YouTube",
                "title": "video",
                "body": "video",
                "sourceUrl": "https://www.youtube.com/watch?v=abc",
                "publishedAtEpoch": now - 100,
            }
        ]
        history = [
            self.row("GLOBAL", "LifeMakeover510", "101", now - 200),
            self.row("GLOBAL", "LifeMakeover510", "102", now - 300),
        ]

        rows, restored = self.mod.merge_rows(current, history, now)

        self.assertEqual(2, restored["GLOBAL"])
        self.assertEqual(3, len(rows))
        self.assertTrue(any(r["sourceUrl"].endswith("/101") for r in rows))
        self.assertTrue(any(r["sourceUrl"].endswith("/102") for r in rows))

    def test_fresh_row_wins_over_history_duplicate(self):
        now = 2_000_000_000
        fresh = self.row("GLOBAL", "LifeMakeover510", "101", now - 50, title="fresh")
        old = self.row("GLOBAL", "LifeMakeover510", "101", now - 500, title="old")

        rows, restored = self.mod.merge_rows([fresh], [old], now)

        self.assertEqual(0, restored["GLOBAL"])
        self.assertEqual("fresh", rows[0]["title"])

    def test_stale_history_is_not_restored(self):
        now = 2_000_000_000
        stale = self.row(
            "GLOBAL",
            "LifeMakeover510",
            "103",
            now - (self.mod.RETENTION_DAYS + 1) * 86400,
        )

        rows, restored = self.mod.merge_rows([], [stale], now)

        self.assertEqual([], rows)
        self.assertEqual(0, restored["GLOBAL"])

    def test_other_x_accounts_are_not_mistaken_for_official(self):
        row = self.row("GLOBAL", "someone_else", "104", 2_000_000_000)
        self.assertIsNone(self.mod.account_key(row))


if __name__ == "__main__":
    unittest.main()
