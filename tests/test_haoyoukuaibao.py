import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


class HaoyoukuaibaoCollectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.collector = importlib.import_module("fetch_haoyoukuaibao")

    def test_discovers_only_official_thread_links(self):
        page = '''
        <div>普通论坛 <a href="https://m.bbs.3839.com/thread-111.htm">不要拾取</a></div>
        <h3>官方帖子</h3>
        <a href="https://m.bbs.3839.com/thread-7759267.htm">参与谜城夺宝，获取五星限定套装「失落城市」！</a>
        <a href="//m.bbs.3839.com/thread-7759268.htm">全新限时萌宠时装礼包上架！</a>
        <a href="https://m.bbs.3839.com/forum-26453.htm">查看全部</a>
        <h3>相关游戏</h3>
        <a href="https://m.bbs.3839.com/thread-9999999.htm">不要越界拾取</a>
        '''
        rows = self.collector.discover_official_posts(page)
        self.assertEqual(2, len(rows))
        self.assertEqual("https://m.bbs.3839.com/thread-7759267.htm", rows[0]["url"])
        self.assertIn("萌宠时装", rows[1]["title"])

    def test_article_helpers_read_metadata_and_date(self):
        page = '''
        <meta property="og:title" content="全新4.3版本正式上线">
        <meta property="og:description" content="五星套装与全新玩法现已开放，欢迎合伙人进入游戏体验。">
        <meta property="article:published_time" content="2026-08-28 10:30:00">
        <meta property="og:image" content="https://img.3839.com/yslzm/news.jpg">
        '''
        self.assertEqual("全新4.3版本正式上线", self.collector.meta_value(page, "og:title"))
        self.assertGreater(self.collector.article_epoch(page), 0)
        images = self.collector.image_urls(page, "https://m.bbs.3839.com/thread-1.htm")
        self.assertEqual(["https://img.3839.com/yslzm/news.jpg"], images)

    def test_merge_preserves_existing_ai_fields(self):
        existing = [{
            "sourceUrl": "https://m.bbs.3839.com/thread-1.htm",
            "publishedAtEpoch": 1787889600,
            "publishedLabel": "1時間前",
            "titleJa": "既存翻訳",
            "summaryJa": "既存要約",
            "aiProcessed": True,
        }]
        incoming = [{
            "sourceUrl": "https://m.bbs.3839.com/thread-1.htm",
            "publishedAtEpoch": 0,
            "publishedLabel": "好游快爆",
            "title": "原文",
        }]
        row = self.collector.merge_rows(existing, incoming)[0]
        self.assertEqual("既存翻訳", row["titleJa"])
        self.assertEqual("既存要約", row["summaryJa"])
        self.assertEqual(1787889600, row["publishedAtEpoch"])


if __name__ == "__main__":
    unittest.main()
