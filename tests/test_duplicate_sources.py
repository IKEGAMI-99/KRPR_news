import unittest

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import merge_duplicate_sources as merger


class DuplicateSourceMergeTests(unittest.TestCase):
    def test_same_china_story_merges_weibo_taptap_and_bilibili(self):
        rows = [
            {
                "id": "w",
                "region": "CHINA",
                "platform": "公式Weibo",
                "title": "以闪亮之名 #以闪亮之名# VME | 爆料早班机：首发艺人即将启程",
                "body": "Weibo body",
                "sourceUrl": "https://weibo.com/example/1",
                "publishedAtEpoch": 1787889600,
                "imageUrl": "https://example.com/weibo.jpg",
            },
            {
                "id": "t",
                "region": "CHINA",
                "platform": "公式TapTap",
                "title": "VME | 爆料早班机：首发艺人即将启程",
                "body": "TapTap body with more useful detail than the short Weibo body.",
                "sourceUrl": "https://www.taptap.cn/moment/1",
                "publishedAtEpoch": 1787889660,
                "imageUrl": "https://example.com/taptap.jpg",
            },
            {
                "id": "b",
                "region": "CHINA",
                "platform": "公式Bilibili · 記事",
                "title": "VME | 爆料早班机：首发艺人即将启程 💘超级新星降临音乐宇宙",
                "body": "Bilibili body",
                "sourceUrl": "https://www.bilibili.com/opus/1",
                "publishedAtEpoch": 1787889630,
                "imageUrl": "https://example.com/bili.jpg",
            },
        ]
        merged = merger.merge_rows(rows)
        self.assertEqual(1, len(merged))
        self.assertEqual(3, merged[0]["sourceCount"])
        self.assertEqual(
            {"Weibo", "TapTap", "Bilibili"},
            {source["label"] for source in merged[0]["sources"]},
        )
        self.assertEqual("https://www.taptap.cn/moment/1", merged[0]["sourceUrl"])
        self.assertEqual("https://example.com/taptap.jpg", merged[0]["imageUrl"])

    def test_short_taptap_title_merges_with_long_bilibili_title(self):
        rows = [
            {
                "id": "t",
                "region": "CHINA",
                "platform": "公式TapTap",
                "title": "歌声点亮璀璨舞台",
                "body": "乐符旋律与心跳共振，与你循声共赴绚烂花路！",
                "sourceUrl": "https://www.taptap.cn/moment/843802325314178463",
                "publishedAtEpoch": 1788231600,
            },
            {
                "id": "b",
                "region": "CHINA",
                "platform": "公式Bilibili · 記事",
                "title": "歌声点亮璀璨舞台 ✨乐符旋律与心跳共振， ✨与你循声共赴绚烂花路",
                "body": "歌声点亮璀璨舞台 乐符旋律与心跳共振，与你循声共赴绚烂花路！",
                "sourceUrl": "https://www.bilibili.com/opus/example",
                "publishedAtEpoch": 1788231660,
            },
        ]
        merged = merger.merge_rows(rows)
        self.assertEqual(1, len(merged))
        self.assertEqual(2, merged[0]["sourceCount"])

    def test_taptap_body_fallback_merges_when_titles_are_not_similar_enough(self):
        rows = [
            {
                "id": "t",
                "region": "CHINA",
                "platform": "公式TapTap",
                "title": "你的今日份幸运已到货",
                "body": "让幸运蛋为你开启专属好运磁场，如果要有期限，我希望是一万年！",
                "sourceUrl": "https://www.taptap.cn/moment/843553470001709843",
                "publishedAtEpoch": 1788171619,
            },
            {
                "id": "b",
                "region": "CHINA",
                "platform": "公式Bilibili · 記事",
                "title": "今日好运开启 🍅让幸运蛋为你开启专属好运磁场， 🥜如果要有期限，我希望是一万年",
                "body": "让幸运蛋为你开启专属好运磁场，如果要有期限，我希望是一万年！",
                "sourceUrl": "https://www.bilibili.com/opus/example-2",
                "publishedAtEpoch": 1788171670,
            },
        ]
        merged = merger.merge_rows(rows)
        self.assertEqual(1, len(merged))
        self.assertEqual(2, merged[0]["sourceCount"])

    def test_nearby_but_different_titles_do_not_merge(self):
        rows = [
            {
                "id": "1",
                "region": "CHINA",
                "platform": "公式Weibo",
                "title": "星夜神谕礼包限时开启",
                "body": "a",
                "sourceUrl": "https://weibo.com/example/2",
                "publishedAtEpoch": 1787889600,
            },
            {
                "id": "2",
                "region": "CHINA",
                "platform": "公式TapTap",
                "title": "全新主线章节正式开放",
                "body": "b",
                "sourceUrl": "https://www.taptap.cn/moment/2",
                "publishedAtEpoch": 1787889660,
            },
        ]
        self.assertEqual(2, len(merger.merge_rows(rows)))

    def test_same_title_across_regions_does_not_merge(self):
        base = {
            "title": "Summer Event Starts Now",
            "body": "body",
            "publishedAtEpoch": 1787889600,
        }
        rows = [
            {**base, "id": "g", "region": "GLOBAL", "platform": "公式X", "sourceUrl": "https://x.com/example/1"},
            {**base, "id": "j", "region": "JAPAN", "platform": "公式X", "sourceUrl": "https://x.com/example/2"},
        ]
        self.assertEqual(2, len(merger.merge_rows(rows)))

    def test_official_site_label_stays_natural(self):
        self.assertEqual("公式サイト", merger.platform_label("公式サイト"))


if __name__ == "__main__":
    unittest.main()
