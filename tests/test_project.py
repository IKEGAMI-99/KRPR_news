import ast
import importlib
import json
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
DOCS = ROOT / "docs"
sys.path.insert(0, str(SCRIPTS))


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "script" and values.get("src"):
            self.assets.append(values["src"])
        if tag == "link" and values.get("href"):
            self.assets.append(values["href"])


class CollectorTests(unittest.TestCase):
    def test_youtube_resolver_prefers_canonical_owner(self):
        collector = importlib.import_module("fetch_news")
        expected = collector.YOUTUBE_CHANNEL_IDS["GLOBAL"]
        unrelated = "UCsbOnjTbwKMVC_t_kD-sAGg"
        page = (
            f'<script>{{"channelId":"{unrelated}"}}</script>'
            f'<link rel="canonical" href="https://www.youtube.com/channel/{expected}">'
        )
        original_get = collector.get
        collector.get = lambda _url: page
        try:
            self.assertEqual(expected, collector.resolve_youtube_channel_id("https://www.youtube.com/@LifeMakeover"))
        finally:
            collector.get = original_get

    def test_official_youtube_ids_are_explicit(self):
        collector = importlib.import_module("fetch_news")
        self.assertEqual(
            {"JAPAN", "GLOBAL", "KOREA"},
            set(collector.YOUTUBE_CHANNEL_IDS),
        )
        for channel_id in collector.YOUTUBE_CHANNEL_IDS.values():
            self.assertRegex(channel_id, r"^UC[A-Za-z0-9_-]{22}$")


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((ROOT / "data" / "news.json").read_text(encoding="utf-8"))

    def test_news_data_shape_and_order(self):
        self.assertIsInstance(self.rows, list)
        self.assertTrue(self.rows)
        epochs = []
        for row in self.rows:
            self.assertIsInstance(row, dict)
            self.assertIn(row.get("region"), {"JAPAN", "CHINA", "KOREA", "GLOBAL"})
            self.assertTrue(row.get("id"))
            self.assertRegex(str(row.get("sourceUrl")), r"^https?://")
            self.assertTrue(row.get("title"))
            epochs.append(int(row.get("publishedAtEpoch") or 0))
        self.assertEqual(epochs, sorted(epochs, reverse=True))

    def test_news_ids_and_urls_are_unique(self):
        ids = [row["id"] for row in self.rows]
        urls = [row["sourceUrl"] for row in self.rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(urls), len(set(urls)))

    def test_unrelated_archosaur_games_are_absent(self):
        blocked = ("dragon raja", "noah's heart", "noah’s heart", "archosaur games’ ue5 teaser")
        titles = "\n".join(str(row.get("title") or "").casefold() for row in self.rows)
        for token in blocked:
            self.assertNotIn(token, titles)


class ProjectStructureTests(unittest.TestCase):
    def test_python_sources_parse(self):
        for path in sorted(SCRIPTS.glob("*.py")):
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_index_local_assets_exist(self):
        parser = AssetParser()
        parser.feed((DOCS / "index.html").read_text(encoding="utf-8"))
        for asset in parser.assets:
            if not asset.startswith("./"):
                continue
            path = DOCS / asset[2:].split("?", 1)[0]
            with self.subTest(asset=asset):
                self.assertTrue(path.exists(), f"missing index asset: {asset}")

    def test_service_worker_shell_assets_exist(self):
        source = (DOCS / "sw.js").read_text(encoding="utf-8")
        assets = re.findall(r"'\./([^']*)'", source)
        for asset in assets:
            path = DOCS / (asset or "index.html")
            with self.subTest(asset=asset):
                self.assertTrue(path.exists(), f"missing service-worker asset: {asset}")

    def test_search_is_connected(self):
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        app = (DOCS / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="searchInput"', html)
        self.assertIn("els.search.addEventListener('input'", app)

    def test_mobile_layout_does_not_force_viewport_width(self):
        topics_css = (DOCS / "topics.css").read_text(encoding="utf-8")
        self.assertNotIn("width:100vw", topics_css)
        self.assertNotIn("min-width:100vw", topics_css)

    def test_active_translation_cache_metadata(self):
        gemma = importlib.import_module("strict_gemma_translate")
        engine = importlib.import_module("translation_engine")
        gemma.configure_gemma()
        cache = engine.normalized_cache({"model": "old", "items": {}})
        self.assertEqual(f"{gemma.MODEL_ID}:{gemma.MODEL_VARIANT}", cache["model"])
        self.assertEqual(gemma.MODEL_REVISION, cache["modelRevision"])

    def test_removed_legacy_layers_are_not_referenced(self):
        combined = "\n".join(
            (DOCS / name).read_text(encoding="utf-8")
            for name in ("index.html", "sw.js")
        )
        for name in (
            "feed-status.js", "x-image-fix.js", "ui_fixes.js", "gallery-strip.js",
            "month-sections.js", "early-info.js", "dev-release.js", "theme-kawaii.js",
        ):
            self.assertNotIn(name, combined)
        self.assertFalse((ROOT / ".github" / "workflows" / "reset-lfm-state.yml").exists())

    def test_documentation_matches_active_model_and_schedule(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "ai-translate.yml").read_text(encoding="utf-8")
        self.assertNotIn("Qwen", readme)
        self.assertIn("Gemma 4 E4B", readme)
        self.assertIn("cron: '7-59/15 * * * *'", workflow)
        self.assertIn("LLM_MAX_ITEMS: '3'", workflow)


if __name__ == "__main__":
    unittest.main()
