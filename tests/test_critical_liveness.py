import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import translation_engine as engine
import strict_gemma_translate as gemma
import validate_pipeline_state as validator


class WorkflowSerializationTests(unittest.TestCase):
    def test_every_production_data_writer_uses_one_lock(self):
        workflow_dir = ROOT / ".github" / "workflows"
        for name in ("news-refresh.yml", "ai-translate.yml", "regenerate-ai.yml"):
            with self.subTest(workflow=name):
                source = (workflow_dir / name).read_text(encoding="utf-8")
                self.assertIn("group: kirapara-data-writer", source)
                self.assertIn("cancel-in-progress: false", source)

    def test_successful_refresh_triggers_translation_and_watchdog_marker_can_kick_it(self):
        source = (ROOT / ".github" / "workflows" / "ai-translate.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_run:", source)
        self.assertIn("- 'Refresh News Cache'", source)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", source)
        self.assertIn("data/ai_kick.json", source)
        self.assertIn("branches:\n      - main\n    paths:", source)

    def test_refresh_validates_before_recording_or_committing(self):
        source = (ROOT / ".github" / "workflows" / "news-refresh.yml").read_text(encoding="utf-8")
        validation = source.index("Reject destructive or malformed refresh output")
        completion = source.index("Record completed crawl time")
        commit = source.index("Commit refreshed news and crawl status")
        self.assertLess(validation, completion)
        self.assertLess(completion, commit)
        self.assertIn('--baseline-news "$RUNNER_TEMP/news-before-refresh.json"', source)


class PipelineDataGuardTests(unittest.TestCase):
    def test_current_production_data_is_valid(self):
        validator.validate(
            ROOT / "data" / "news.json",
            ROOT / "data" / "translations.json",
        )

    def test_malformed_required_json_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "news.json"
            path.write_text("{not-json", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                engine.read_json_required(path, list)

    def test_catastrophic_refresh_shrink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = []
            for index in range(80):
                baseline.append(
                    {
                        "region": validator.REGIONS[index % len(validator.REGIONS)],
                        "sourceUrl": f"https://example.test/baseline/{index}",
                    }
                )
            current = [
                {
                    "region": validator.REGIONS[index],
                    "sourceUrl": f"https://example.test/current/{index}",
                }
                for index in range(len(validator.REGIONS))
            ]
            news_path = root / "news.json"
            baseline_path = root / "baseline.json"
            translations_path = root / "translations.json"
            news_path.write_text(json.dumps(current), encoding="utf-8")
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            translations_path.write_text(json.dumps({"items": {}}), encoding="utf-8")

            with self.assertRaisesRegex(validator.ValidationError, "row count collapsed"):
                validator.validate(news_path, translations_path, baseline_path)


class TranslationFailureQuarantineTests(unittest.TestCase):
    @staticmethod
    def rows():
        return [
            {
                "region": "CHINA",
                "sourceUrl": f"https://example.test/article/{index}",
                "title": f"article {index}",
                "body": "body",
                "publishedAtEpoch": index,
            }
            for index in range(4, 0, -1)
        ]

    def test_three_bad_articles_do_not_block_the_next_article(self):
        rows = self.rows()
        cache = engine.normalized_cache({})
        for row in rows[:3]:
            engine.record_failure(cache, row, now_epoch=1_000)

        eligible = engine.pending_rows(rows, cache, now_epoch=1_001)
        all_pending = engine.pending_rows(rows, cache, include_deferred=True, now_epoch=1_001)

        self.assertEqual([rows[3]["sourceUrl"]], [row["sourceUrl"] for row in eligible])
        self.assertEqual(4, len(all_pending))
        self.assertEqual(4, len(engine.pending_rows(rows, cache, now_epoch=4_600)))

    def test_failure_backoff_increases_and_success_clears_it(self):
        row = self.rows()[0]
        cache = engine.normalized_cache({})
        first = engine.record_failure(cache, row, now_epoch=1_000)
        second = engine.record_failure(cache, row, now_epoch=first["retryAfterEpoch"])

        self.assertEqual(1, first["attempts"])
        self.assertEqual(2, second["attempts"])
        self.assertGreater(
            second["retryAfterEpoch"] - second["lastFailedAtEpoch"],
            first["retryAfterEpoch"] - first["lastFailedAtEpoch"],
        )
        engine.clear_failure(cache, row)
        self.assertIsNone(engine.failure_state(row, cache))

    def test_failure_cache_is_pruned_even_when_translation_cache_is_small(self):
        cache = engine.normalized_cache({})
        cache["failures"] = {
            "old": {"lastFailedAtEpoch": 1},
            "middle": {"lastFailedAtEpoch": 2},
            "new": {"lastFailedAtEpoch": 3},
        }
        engine.prune_cache(cache, max_entries=2)
        self.assertEqual({"middle", "new"}, set(cache["failures"]))

    def test_worker_commits_failures_as_queue_state_and_returns_success(self):
        class AlwaysInvalidAdapter:
            def __init__(self, _model_path):
                pass

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            news_path = root / "news.json"
            cache_path = root / "translations.json"
            model_path = root / "model.litertlm"
            news_path.write_text(json.dumps(self.rows()), encoding="utf-8")
            cache_path.write_text(json.dumps({"items": {}}), encoding="utf-8")
            model_path.write_bytes(b"test")

            original_news = engine.NEWS_PATH
            original_cache = engine.CACHE_PATH
            original_adapter = gemma.LiteRTChatAdapter
            original_infer = engine.infer_one
            engine.NEWS_PATH = news_path
            engine.CACHE_PATH = cache_path
            gemma.LiteRTChatAdapter = AlwaysInvalidAdapter
            engine.infer_one = lambda _llm, _row: None
            try:
                result = gemma.cmd_translate_litert(
                    SimpleNamespace(model=str(model_path), max_items=3)
                )
            finally:
                engine.NEWS_PATH = original_news
                engine.CACHE_PATH = original_cache
                gemma.LiteRTChatAdapter = original_adapter
                engine.infer_one = original_infer

            written_rows = json.loads(news_path.read_text(encoding="utf-8"))
            written_cache = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(0, result)
            self.assertEqual(3, len(written_cache["failures"]))
            self.assertEqual(1, len(engine.pending_rows(written_rows, written_cache)))


if __name__ == "__main__":
    unittest.main()
