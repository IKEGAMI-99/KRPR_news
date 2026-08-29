import importlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


class BilibiliImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.urls = importlib.import_module("bilibili_image_urls")
        cls.normalizer = importlib.import_module("normalize_news")

    def test_resize_and_crop_suffix_is_replaced_by_original_url(self):
        thumbnail = (
            "https://i0.hdslb.com/bfs/new_dyn/"
            "788e446472623052817c84f2ccb2896d676200579.jpg@316w_560h_1e_1c"
        )
        original = thumbnail.split("@", 1)[0]
        self.assertEqual(original, self.urls.canonicalize_bilibili_image_url(thumbnail))

    def test_output_format_suffix_is_removed_and_https_is_enforced(self):
        thumbnail = "http://i0.hdslb.com/bfs/new_dyn/example.jpg@672w_378h_1c.webp"
        self.assertEqual(
            "https://i0.hdslb.com/bfs/new_dyn/example.jpg",
            self.urls.canonicalize_bilibili_image_url(thumbnail),
        )

    def test_unrelated_cdn_url_is_untouched(self):
        url = "https://example.com/photo.jpg@316w_560h_1e_1c"
        self.assertEqual(url, self.urls.canonicalize_bilibili_image_url(url))

    def test_numbered_hdslb_aliases_share_one_canonical_url(self):
        first = "https://i0.hdslb.com/bfs/new_dyn/example.jpg@316w_560h_1e_1c"
        second = "https://i2.hdslb.com/bfs/new_dyn/example.jpg"
        self.assertEqual(
            ["https://i0.hdslb.com/bfs/new_dyn/example.jpg"],
            self.urls.unique_canonical_image_urls([first, second]),
        )

    def test_final_normalizer_deduplicates_derivatives_but_keeps_real_gallery(self):
        first = "https://i0.hdslb.com/bfs/new_dyn/first.jpg"
        second = "https://i0.hdslb.com/bfs/new_dyn/second.png"
        row = {
            "imageUrl": first + "@316w_560h_1e_1c",
            "imageUrls": [
                first + "@316w_560h_1e_1c",
                first,
                second + "@1192w",
                second,
            ],
        }

        self.assertTrue(self.normalizer.normalize_image_fields(row))
        self.assertEqual([first, second], row["imageUrls"])
        self.assertEqual(first, row["imageUrl"])

    def test_committed_news_has_no_bilibili_resize_derivatives(self):
        rows = json.loads((ROOT / "data" / "news.json").read_text(encoding="utf-8"))
        for row in rows:
            values = list(row.get("imageUrls") or [])
            if row.get("imageUrl"):
                values.append(row["imageUrl"])
            for url in values:
                with self.subTest(source=row.get("sourceUrl"), image=url):
                    self.assertEqual(url, self.urls.canonicalize_bilibili_image_url(url))


if __name__ == "__main__":
    unittest.main()
