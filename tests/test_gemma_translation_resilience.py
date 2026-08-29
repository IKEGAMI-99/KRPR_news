import json
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import strict_gemma_translate as gemma  # noqa: E402
import translation_engine as engine  # noqa: E402
import translation_quality as quality  # noqa: E402


def article(url: str, epoch: int, body: str = "中国語の原文") -> dict:
    return {
        "id": url.rsplit("/", 1)[-1],
        "sourceUrl": url,
        "region": "CHINA",
        "platform": "公式Bilibili · 記事",
        "title": "更新公告",
        "body": body,
        "publishedAtEpoch": epoch,
    }


class FailureCooldownTests(unittest.TestCase):
    def setUp(self):
        gemma.configure_gemma()

    def test_normalized_cache_preserves_failure_state(self):
        raw = {
            "items": {},
            "failures": {"article": {"lastFailureAtEpoch": 123}},
        }
        cache = engine.normalized_cache(raw)
        self.assertEqual(123, cache["failures"]["article"]["lastFailureAtEpoch"])

    def test_exhausted_article_is_deferred_while_next_article_runs(self):
        first = article("https://example.com/first", 20)
        second = article("https://example.com/second", 10)
        cache = engine.normalized_cache({"items": {}})

        record = gemma.defer_failed_row(cache, first, 1_000)
        runnable, deferred = gemma.partition_pending_rows(
            [first, second], cache, 1_001
        )

        self.assertEqual(gemma.FAILED_ATTEMPTS_PER_ARTICLE, record["failedAttempts"])
        self.assertEqual(1_000 + gemma.FAILURE_COOLDOWN_SECONDS, record["retryAfterEpoch"])
        self.assertEqual([second], runnable)
        self.assertEqual([first], deferred)

    def test_deferred_article_becomes_runnable_after_cooldown(self):
        row = article("https://example.com/retry", 20)
        cache = engine.normalized_cache({"items": {}})
        record = gemma.defer_failed_row(cache, row, 1_000)

        runnable, deferred = gemma.partition_pending_rows(
            [row], cache, record["retryAfterEpoch"]
        )

        self.assertEqual([row], runnable)
        self.assertEqual([], deferred)

    def test_source_change_discards_stale_cooldown(self):
        row = article("https://example.com/changed", 20, body="古い原文")
        cache = engine.normalized_cache({"items": {}})
        gemma.defer_failed_row(cache, row, 1_000)
        row["body"] = "更新された原文"

        runnable, deferred = gemma.partition_pending_rows([row], cache, 1_001)

        self.assertEqual([row], runnable)
        self.assertEqual([], deferred)
        self.assertNotIn(row["sourceUrl"], cache["failures"])

    def test_success_clears_previous_cooldown(self):
        row = article("https://example.com/success", 20)
        cache = engine.normalized_cache({"items": {}})
        gemma.defer_failed_row(cache, row, 1_000)

        gemma.clear_failure_record(cache, row)

        self.assertNotIn(row["sourceUrl"], cache["failures"])


class LiteRTBudgetTests(unittest.TestCase):
    def test_adapter_allocates_8192_context_and_3000_output_tokens(self):
        state = {}

        class FakeConversation:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def send_message(self, text, **kwargs):
                state["message"] = text
                state["send_kwargs"] = kwargs
                return {"content": [{"type": "text", "text": "ok"}]}

        class FakeRuntime:
            def __init__(self, model_path, **kwargs):
                state["model_path"] = model_path
                state["engine_kwargs"] = kwargs

            def create_conversation(self, **kwargs):
                state["conversation_kwargs"] = kwargs
                return FakeConversation()

            def close(self):
                state["closed"] = True

        fake_module = types.SimpleNamespace(
            Engine=FakeRuntime,
            Backend=types.SimpleNamespace(CPU=lambda **kwargs: ("cpu", kwargs)),
            SamplerConfig=lambda **kwargs: kwargs,
        )
        previous = sys.modules.get("litert_lm")
        sys.modules["litert_lm"] = fake_module
        try:
            adapter = gemma.LiteRTChatAdapter("model.litertlm")
            result = adapter.create_chat_completion(
                messages=[
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "user"},
                ]
            )
            adapter.close()
        finally:
            if previous is None:
                sys.modules.pop("litert_lm", None)
            else:
                sys.modules["litert_lm"] = previous

        self.assertEqual(gemma.CONTEXT_TOKEN_LIMIT, state["engine_kwargs"]["max_num_tokens"])
        self.assertEqual(gemma.OUTPUT_TOKEN_LIMIT, state["conversation_kwargs"]["max_output_tokens"])
        self.assertEqual(gemma.OUTPUT_TOKEN_LIMIT, state["send_kwargs"]["max_output_tokens"])
        self.assertEqual("ok", result["choices"][0]["message"]["content"])
        self.assertTrue(state["closed"])

    def test_strict_inference_requests_3000_output_tokens(self):
        calls = []

        class FakeLlm:
            def create_chat_completion(self, **kwargs):
                calls.append(kwargs)
                return {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "titleJa": "アップデートのお知らせ",
                                        "bodyJa": "新しいイベントが開催され、限定衣装と報酬を獲得できます。",
                                        "summaryJa": "・追加: 新しいイベントが開催\n・報酬: 限定衣装を獲得可能",
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ]
                }

        row = article(
            "https://example.com/quality",
            20,
            body="全新活动开启，完成任务后可以获得限定服装和奖励。",
        )
        result = quality.strict_infer_one(FakeLlm(), row)

        self.assertIsNotNone(result)
        self.assertEqual(gemma.OUTPUT_TOKEN_LIMIT, calls[0]["max_tokens"])


if __name__ == "__main__":
    unittest.main()
