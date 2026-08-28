import importlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


class TapTapCollectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.collector = importlib.import_module("fetch_taptap_official")

    def test_discover_moment_ids_handles_relative_absolute_and_escaped_links(self):
        page = """
        <a href="/moment/839107099152615643?group_id=303113">A</a>
        <a href="https://www.taptap.cn/moment/839106831950283339">B</a>
        <script>{"url":"https:\/\/www.taptap.cn\/moment\/839000000000000001"}</script>
        """
        found = self.collector.discover_moment_ids(page)
        self.assertEqual(
            {"839107099152615643", "839106831950283339", "839000000000000001"},
            set(found),
        )

    def test_api_payload_maps_to_kirapara_news_shape(self):
        payload = {
            "data": {
                "moment": {
                    "created_time": 1787824800,
                    "author": {"user": {"name": "VVANNA GIRLS"}},
                    "topic": {
                        "title": "测试公告",
                        "summary": "这是官方测试公告正文。",
                        "images": [
                            {"original_url": "https://img2-tc.tapimg.com/test-image.jpg"}
                        ],
                    },
                }
            }
        }
        row = self.collector.article_from_api(payload, "839107099152615643")
        self.assertIsNotNone(row)
        self.assertEqual("CHINA", row["region"])
        self.assertEqual("公式TapTap", row["platform"])
        self.assertEqual("测试公告", row["title"])
        self.assertEqual(1787824800, row["publishedAtEpoch"])
        self.assertEqual(
            "https://www.taptap.cn/moment/839107099152615643",
            row["sourceUrl"],
        )
        self.assertEqual(
            ["https://img2-tc.tapimg.com/test-image.jpg"],
            row["imageUrls"],
        )

    def test_image_collection_keeps_article_media_and_rejects_page_assets(self):
        topic = {
            "images": [
                {"original_url": "https://img2-tc.tapimg.com/article-main.jpg"},
                {"url": "https://img2-tc.tapimg.com/article-second.jpg"},
            ],
            "author": {
                "avatar": {"url": "https://img2-tc.tapimg.com/avatar/author.jpg"}
            },
            "app": {
                "icon": {"url": "https://img2-tc.tapimg.com/app-icon.jpg"},
                "cover": {"url": "https://img2-tc.tapimg.com/game-cover.jpg"},
            },
            "related": {
                "images": [
                    {"original_url": "https://img2-tc.tapimg.com/related-post.jpg"}
                ]
            },
            "share": {"image_url": "https://img2-tc.tapimg.com/share-card.jpg"},
        }
        found = self.collector.collect_image_urls(topic)
        self.assertEqual(
            [
                "https://img2-tc.tapimg.com/article-main.jpg",
                "https://img2-tc.tapimg.com/article-second.jpg",
            ],
            found,
        )

    def test_html_fallback_does_not_scan_every_tapimg_asset(self):
        page = """
        <meta property="og:image" content="https://img2-tc.tapimg.com/moment-cover.jpg">
        <script>
        {"app":{"icon":{"image_url":"https://img2-tc.tapimg.com/app-icon.jpg"}},
         "images":[{"original_url":"https://img2-tc.tapimg.com/article-main.jpg"}]}
        </script>
        <img src="https://img2-tc.tapimg.com/unrelated-footer.jpg">
        """
        found = self.collector.collect_html_article_images(page)
        self.assertEqual(
            [
                "https://img2-tc.tapimg.com/moment-cover.jpg",
                "https://img2-tc.tapimg.com/article-main.jpg",
            ],
            found,
        )

    def test_non_official_author_is_rejected(self):
        payload = {
            "data": {
                "moment": {
                    "created_time": 1787824800,
                    "author": {"user": {"name": "普通玩家"}},
                    "topic": {"title": "玩家帖子", "summary": "should not enter the feed"},
                }
            }
        }
        self.assertIsNone(self.collector.article_from_api(payload, "1"))


if __name__ == "__main__":
    unittest.main()
