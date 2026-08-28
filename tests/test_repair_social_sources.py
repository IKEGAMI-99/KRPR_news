import importlib
import sys
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


class RepairSocialSourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = importlib.import_module("repair_social_sources")

    def x_row(self, status, epoch, host="x.com", body="post"):
        url = f"https://{host}/kirapara_JP/status/{status}"
        return {
            "id": str(status),
            "region": "JAPAN",
            "platform": "公式X",
            "title": body,
            "body": body,
            "sourceUrl": url,
            "publishedAtEpoch": epoch,
        }

    def rss(self, status, published):
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><item>
  <title>status {status}</title>
  <link>https://x.com/kirapara_JP/status/{status}</link>
  <description>status {status}</description>
  <pubDate>{published}</pubDate>
</item></channel></rss>"""

    def test_feed_merge_uses_freshest_mirror_and_canonicalizes_x_urls(self):
        stale = [
            self.x_row("100", 100, host="twitter.com", body="short"),
            self.x_row("099", 90),
        ]
        fresh = [
            self.x_row("101", 200),
            self.x_row("100", 100, body="a much more complete version of the post"),
        ]

        rows = self.mod.merge_feed_rows("公式X", [stale, fresh])

        self.assertEqual([200, 100, 90], [row["publishedAtEpoch"] for row in rows])
        self.assertEqual("https://x.com/kirapara_JP/status/100", rows[1]["sourceUrl"])
        self.assertEqual("a much more complete version of the post", rows[1]["body"])

    def test_fetch_best_does_not_stop_at_first_stale_success(self):
        stale_host = "https://stale.example"
        fresh_host = "https://fresh.example"

        def fake_request(url, timeout=12):
            if url.startswith(fresh_host):
                time.sleep(0.03)
                return self.rss("201", "Fri, 28 Aug 2026 09:00:03 GMT")
            return self.rss("200", "Thu, 27 Aug 2026 09:00:02 GMT")

        with mock.patch.object(self.mod, "request_text", side_effect=fake_request):
            rows = self.mod.fetch_best(
                "JAPAN",
                "公式X",
                ["/twitter/user/kirapara_JP"],
                hosts=[stale_host, fresh_host],
            )

        self.assertEqual("https://x.com/kirapara_JP/status/201", rows[0]["sourceUrl"])
        self.assertEqual(2, len(rows))

    def test_historical_bilibili_rows_survive_live_feed_outage(self):
        historical = {
            "id": "old",
            "region": "CHINA",
            "platform": "公式Bilibili · 記事",
            "title": "known good",
            "body": "known good",
            "sourceUrl": "https://www.bilibili.com/opus/123",
            "publishedAtEpoch": 100,
        }
        current = [
            {
                "id": "weibo",
                "region": "CHINA",
                "platform": "公式Weibo",
                "title": "another China source",
                "body": "another China source",
                "sourceUrl": "https://weibo.com/example/1",
                "publishedAtEpoch": 200,
            }
        ]

        rows = self.mod.merge_rows(current, [historical])

        self.assertTrue(any(self.mod.is_bilibili(row) for row in rows))
        self.assertEqual(2, len(rows))

    def test_news_refresh_runs_social_repair_before_image_enrichment(self):
        workflow = (ROOT / ".github" / "workflows" / "news-refresh.yml").read_text(encoding="utf-8")
        repair = workflow.index("python scripts/repair_social_sources.py")
        images = workflow.index("python scripts/enrich_social_images.py")
        self.assertLess(repair, images)


if __name__ == "__main__":
    unittest.main()
