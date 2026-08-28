import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
WORKFLOW = ROOT / ".github" / "workflows" / "news-refresh.yml"


class CrawlStatusTests(unittest.TestCase):
    def test_crawl_status_data_shape(self):
        payload = json.loads((ROOT / "data" / "crawl_status.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("source"), "news-refresh.yml")
        self.assertRegex(
            str(payload.get("lastCrawlAt") or ""),
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
        )

    def test_header_uses_crawl_status_ui(self):
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        script = (DOCS / "crawl-status.js").read_text(encoding="utf-8")
        sw = (DOCS / "sw.js").read_text(encoding="utf-8")

        self.assertIn('id="statusText">最終更新 取得中…</p>', html)
        self.assertIn('./crawl-status.js', html)
        self.assertIn('./crawl-status.js', sw)
        self.assertIn('lastCrawlAt', script)
        self.assertIn('最終更新 ${formatter.format', script)

    def test_news_refresh_records_completion_at_hour_zero(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        menu = (DOCS / "menu-install.js").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("cron: '0 * * * *'", workflow)
        self.assertIn('Record completed crawl time', workflow)
        self.assertIn('data/crawl_status.json', workflow)
        self.assertIn('毎時 :00', menu)
        self.assertIn('毎時 :00  news-refresh.yml', readme)
        self.assertNotIn('毎時 :17', menu)
        self.assertNotIn('毎時 :17  news-refresh.yml', readme)


if __name__ == "__main__":
    unittest.main()
