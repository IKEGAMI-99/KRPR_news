import ast
import importlib
import json
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


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

    def test_official_x_and_bilibili_sources_are_retained(self):
        platforms = [str(row.get("platform") or "") for row in self.rows]
        urls = [str(row.get("sourceUrl") or "").lower() for row in self.rows]
        self.assertIn("公式X", platforms)
        self.assertTrue(
            any("bilibili" in platform.lower() for platform in platforms)
            or any("bilibili.com" in url for url in urls),
            "Bilibili disappeared from the normalized news cache",
        )

    def test_complete_weibo_mirrors_are_backed_by_deployed_files(self):
        mirror_dir = DOCS / "media" / "weibo"
        for row in self.rows:
            mirrors = row.get("imageMirrorUrls")
            if not isinstance(mirrors, list) or not mirrors:
                continue
            sources = []
            if isinstance(row.get("imageUrls"), list):
                sources.extend(value for value in row.get("imageUrls") or [] if isinstance(value, str))
            if row.get("imageUrl") and row.get("imageUrl") not in sources:
                sources.append(row.get("imageUrl"))
            self.assertEqual(len(sources), len(mirrors), row.get("sourceUrl"))
            for mirror in mirrors:
                parsed = urlparse(mirror)
                self.assertIn(parsed.hostname, {"ikegami-99.github.io", "raw.githubusercontent.com"})
                filename = Path(parsed.path).name
                self.assertTrue(filename)
                self.assertTrue((mirror_dir / filename).exists(), f"missing Weibo mirror: {filename}")


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

    def test_legal_pages_are_linked_and_cached(self):
        index = (DOCS / "index.html").read_text(encoding="utf-8")
        menu = (DOCS / "menu-install.js").read_text(encoding="utf-8")
        sw = (DOCS / "sw.js").read_text(encoding="utf-8")
        terms = (DOCS / "terms.html").read_text(encoding="utf-8")
        privacy = (DOCS / "privacy.html").read_text(encoding="utf-8")

        for name in ("terms.html", "privacy.html", "legal.css"):
            self.assertTrue((DOCS / name).exists(), f"missing legal asset: {name}")
            self.assertIn(f"./{name}", sw)

        self.assertIn("./terms.html", index)
        self.assertIn("./privacy.html", index)
        self.assertIn("./terms.html", menu)
        self.assertIn("./privacy.html", menu)
        self.assertIn("@ikegami_krpr", terms)
        self.assertIn("Google Analytics 4", privacy)
        self.assertIn("@ikegami_krpr", privacy)

    def test_weibo_image_delivery_is_self_hosted_and_wired(self):
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        sw = (DOCS / "sw.js").read_text(encoding="utf-8")
        fallback = (DOCS / "weibo-image-fallback.js").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "news-refresh.yml").read_text(encoding="utf-8")
        mirror = (SCRIPTS / "mirror_weibo_images.py").read_text(encoding="utf-8")

        self.assertIn("./weibo-image-fallback.js", html)
        self.assertIn("./weibo-image-fallback.js", sw)
        self.assertIn("python scripts/mirror_weibo_images.py", workflow)
        self.assertIn("docs/media/weibo", workflow)
        self.assertIn("ikegami-99.github.io/KRPR_news/media/weibo/", mirror)
        self.assertNotIn("weserv.nl", fallback)
        self.assertNotIn("weserv.nl", mirror)

    def test_search_and_advance_info_features_are_removed(self):
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        app = (DOCS / "app.js").read_text(encoding="utf-8")
        sw = (DOCS / "sw.js").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        news_workflow = (ROOT / ".github" / "workflows" / "news-refresh.yml").read_text(encoding="utf-8")
        ai_workflow = (ROOT / ".github" / "workflows" / "ai-translate.yml").read_text(encoding="utf-8")
        gap_html = (DOCS / "gap.html").read_text(encoding="utf-8")
        gap_js = (DOCS / "gap.js").read_text(encoding="utf-8")

        self.assertNotIn('id="searchInput"', html)
        self.assertNotIn("search-wrap", html)
        self.assertNotIn("weeklyTopics", html)
        self.assertNotIn("state.query", app)
        self.assertNotIn("early-info-badge", app)
        self.assertNotIn("topics.js", sw)
        self.assertNotIn("early-info.css", sw)
        self.assertNotIn("tag_early_info.py", news_workflow)
        self.assertNotIn("tag_early_info.py", ai_workflow)
        self.assertIn("検索バーと旧トップ3予測UIは2026-08-28に完全削除", readme)
        self.assertNotIn("FORECAST", gap_html)
        self.assertNotIn("forecasts", gap_js)

        for path in (
            DOCS / "topics.js",
            DOCS / "topics.css",
            DOCS / "early-info.css",
            SCRIPTS / "tag_early_info.py",
        ):
            self.assertFalse(path.exists(), f"removed feature file still exists: {path}")

    def test_mobile_layout_does_not_force_viewport_width(self):
        combined_css = "\n".join(
            (DOCS / name).read_text(encoding="utf-8")
            for name in ("styles.css", "theme-kawaii.css", "layout-fixes.css")
        )
        self.assertNotIn("width:100vw", combined_css)
        self.assertNotIn("min-width:100vw", combined_css)

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
            "feed-status.js", "ui_fixes.js", "gallery-strip.js",
            "month-sections.js", "early-info.js", "dev-release.js", "theme-kawaii.js",
        ):
            self.assertNotIn(name, combined)
        self.assertIn("x-image-fix.js", combined)
        self.assertTrue((DOCS / "x-image-fix.js").exists())
        self.assertFalse((ROOT / ".github" / "workflows" / "reset-lfm-state.yml").exists())

    def test_documentation_matches_active_model_and_schedule(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "ai-translate.yml").read_text(encoding="utf-8")
        self.assertNotIn("Qwen", readme)
        self.assertIn("Gemma 4 E4B", readme)
        self.assertIn("cron: '7,22,37,52 * * * *'", workflow)
        self.assertIn("LLM_MAX_ITEMS: '3'", workflow)


if __name__ == "__main__":
    unittest.main()
