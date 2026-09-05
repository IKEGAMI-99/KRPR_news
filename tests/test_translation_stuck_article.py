import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import apply_sol_edits as edits
import strict_gemma_translate as gemma
import translation_engine as engine
import translation_quality as quality


class NotationTests(unittest.TestCase):
    def setUp(self):
        self.row = {'region': 'CHINA', 'title': '活动公告',
                    'body': '活动期间5.1折和7.8折优惠，其他商品5折、2.2折、8折。'}
        self.result = {'titleJa': '新しい活动のお知らせ',
                       'bodyJa': '活动期間中は5.1折と7.8折です。ほかに5折、2.2折、8折があります。',
                       'summaryJa': '・期間: イベント開催中\n・価格: 5.1折で購入できます'}

    def test_actual_rejection_is_repaired_before_strict_validation(self):
        result, reason = quality.strict_validate_result_with_reason(self.row, self.result)
        self.assertEqual('', reason)
        self.assertIsNotNone(result)
        for expected in ['49%OFF', '22%OFF', '50%OFF', '78%OFF', '20%OFF']:
            self.assertIn(expected, result['bodyJa'])
        self.assertNotIn('活动', result['titleJa'])
        self.assertNotIn('折', result['summaryJa'])

    def test_unrelated_chinese_still_fails(self):
        self.result['bodyJa'] += '礼包を購入できます。'
        result, reason = quality.strict_validate_result_with_reason(self.row, self.result)
        self.assertIsNone(result)
        self.assertIn('礼包', reason)

    def test_hallucinated_discount_is_not_accepted(self):
        self.result['bodyJa'] += '9折で購入できます。'
        result, reason = quality.strict_validate_result_with_reason(self.row, self.result)
        self.assertIsNone(result)
        self.assertIn('割引表記', reason)

    def test_protected_text_and_non_china_are_unchanged(self):
        value = 'https://example.com/5.1折 #活动5.1折 保持活动 イベント5.1折'
        with patch.object(quality, 'scoped_preserved_terms', return_value=['保持活动']):
            result = quality.normalize_chinese_notation(self.row, {'bodyJa': value})
        self.assertEqual('https://example.com/5.1折 #活动5.1折 保持活动 イベント49%OFF', result['bodyJa'])
        self.assertEqual(self.result, quality.normalize_chinese_notation({'region': 'JAPAN'}, self.result))

    def test_decimal_precision_and_invalid_rates(self):
        row = {**self.row, 'body': '7.85折、0折、10折、12折'}
        result = quality.normalize_chinese_notation(row, {'bodyJa': '7.85折、0折、10折、12折'})
        self.assertEqual('21.5%OFF、0折、10折、12折', result['bodyJa'])


class PrepareAndOverrideTests(unittest.TestCase):
    def test_prepare_distinguishes_cooldown_and_new_work(self):
        gemma.configure_gemma()
        row = {'region': 'CHINA', 'title': '活动公告', 'body': '新活动', 'sourceUrl': 'https://example.com/a'}
        cache = engine.normalized_cache({})
        gemma.defer_failed_row(cache, row, 1000)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            news, translations, output = root / 'news.json', root / 'translations.json', root / 'output'
            news.write_text(json.dumps([row]))
            translations.write_text(json.dumps(cache))
            with patch.object(engine, 'NEWS_PATH', news), patch.object(engine, 'CACHE_PATH', translations), patch.object(gemma.time, 'time', return_value=1001):
                gemma.cmd_prepare_gemma(argparse.Namespace(github_output=str(output)))
            values = dict(line.split('=') for line in output.read_text().splitlines())
            self.assertEqual(('1', '0', '1'), (values['pending'], values['runnable'], values['deferred']))
            self.assertNotIn('aiProcessed', json.loads(news.read_text())[0])
            row['body'] += '更新'
            news.write_text(json.dumps([row]))
            output.unlink()
            with patch.object(engine, 'NEWS_PATH', news), patch.object(engine, 'CACHE_PATH', translations), patch.object(gemma.time, 'time', return_value=1001):
                gemma.cmd_prepare_gemma(argparse.Namespace(github_output=str(output)))
            values = dict(line.split('=') for line in output.read_text().splitlines())
            self.assertEqual(('1', '1', '0'), (values['pending'], values['runnable'], values['deferred']))

    def test_review_is_invalidated_after_source_changes(self):
        row = {'sourceUrl': 'https://example.com/a', 'body': 'original'}
        override = {'contentHash': edits.source_hash(row), 'bodyJa': '翻訳'}
        self.assertEqual(override, edits.find_override(row, {row['sourceUrl']: override}))
        row['body'] = 'changed'
        self.assertIsNone(edits.find_override(row, {row['sourceUrl']: override}))

    def test_review_clears_failure_and_records_reviewer(self):
        row = {'sourceUrl': 'https://example.com/a', 'body': 'original', 'region': 'CHINA'}
        key = row['sourceUrl']
        override = {'contentHash': edits.source_hash(row), 'titleJa': 'お知らせ',
                    'bodyJa': '翻訳しました', 'summaryJa': '・追加: イベント',
                    'reviewerModel': 'ChatGPT (reviewed)', 'updatedAtEpoch': 123}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {name: root / name for name in ('NEWS_PATH', 'TRANSLATIONS_PATH', 'SOL_NEWS_PATH', 'SOL_OVERRIDES_PATH')}
            paths['NEWS_PATH'].write_text(json.dumps([row]))
            paths['TRANSLATIONS_PATH'].write_text(json.dumps({'items': {}, 'failures': {key: {'failedRuns': 2}}}))
            paths['SOL_OVERRIDES_PATH'].write_text(json.dumps({'items': {key: override}}))
            with patch.multiple(edits, **paths):
                edits.main()
            cache = json.loads(paths['TRANSLATIONS_PATH'].read_text())
            self.assertNotIn(key, cache['failures'])
            self.assertEqual('ChatGPT (reviewed)', cache['items'][key]['model'])
            self.assertTrue(cache['items'][key]['managedBySol'])


if __name__ == '__main__':
    unittest.main()
