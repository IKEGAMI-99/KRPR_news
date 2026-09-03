#!/usr/bin/env python3
"""Generate deploy-time SEO assets for Kirapara News.

The public app stays a lightweight JavaScript timeline, while this script creates
crawlable, stable HTML article URLs plus sitemap.xml and robots.txt from the
same normalized news cache.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "news.json"
DOCS_DIR = ROOT / "docs"
ARTICLES_DIR = DOCS_DIR / "articles"
SITE_BASE = "https://ikegami-99.github.io/KRPR_news/"
SITE_NAME = "Kirapara News"
MAX_ARTICLES = max(1, int(os.getenv("SEO_MAX_ARTICLES", "800")))


def clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def truncate(value: str, limit: int) -> str:
    value = clean_text(value)
    if len(value) <= limit:
        return value
    return value[: max(1, limit - 1)].rstrip() + "…"


def article_id(item: dict) -> str:
    raw = clean_text(item.get("id"))
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", raw)
    if safe:
        return safe
    # Normalized news normally always has an id. This fallback keeps the
    # generator deterministic if malformed supplemental data slips through.
    import hashlib

    basis = clean_text(item.get("sourceUrl")) or clean_text(item.get("title"))
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def display_title(item: dict) -> str:
    return clean_text(item.get("titleJa")) or clean_text(item.get("title")) or "Kirapara News"


def display_summary(item: dict) -> str:
    return (
        clean_text(item.get("summaryJa"))
        or clean_text(item.get("bodyJa"))
        or clean_text(item.get("body"))
        or display_title(item)
    )


def iso_datetime(epoch: object) -> str:
    try:
        ts = int(epoch)
    except (TypeError, ValueError):
        ts = 0
    if ts <= 0:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def absolute_image(item: dict) -> str:
    candidates = []
    if isinstance(item.get("imageUrls"), list):
        candidates.extend(item["imageUrls"])
    if item.get("imageUrl"):
        candidates.append(item["imageUrl"])
    for candidate in candidates:
        candidate = clean_text(candidate)
        if candidate:
            return urljoin(SITE_BASE, candidate)
    return urljoin(SITE_BASE, "icon.svg")


def region_label(region: object) -> str:
    return {
        "JAPAN": "日本",
        "CHINA": "中国",
        "KOREA": "韓国",
        "GLOBAL": "Global",
    }.get(clean_text(region).upper(), clean_text(region) or "ニュース")


def json_ld(item: dict, canonical: str, title: str, summary: str, image: str, published: str) -> str:
    payload = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": truncate(title, 110),
        "description": truncate(summary, 220),
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "url": canonical,
        "image": [image],
        "isAccessibleForFree": True,
        "inLanguage": "ja",
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": SITE_BASE,
            "logo": {
                "@type": "ImageObject",
                "url": urljoin(SITE_BASE, "icon.svg"),
            },
        },
    }
    if published:
        payload["datePublished"] = published
        payload["dateModified"] = published
    source_url = clean_text(item.get("sourceUrl"))
    if source_url:
        payload["sameAs"] = [source_url]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def render_article(item: dict) -> tuple[str, str]:
    aid = article_id(item)
    canonical = urljoin(SITE_BASE, f"articles/{aid}.html")
    title = display_title(item)
    summary = display_summary(item)
    description = truncate(summary, 160)
    image = absolute_image(item)
    published = iso_datetime(item.get("publishedAtEpoch"))
    platform = clean_text(item.get("platform")) or "公開ニュース"
    source_url = clean_text(item.get("sourceUrl"))
    region = region_label(item.get("region"))
    seo_title = truncate(title, 72) + " | Kirapara News"

    source_link = ""
    if source_url:
        source_link = (
            f'<p class="source"><a href="{html.escape(source_url, quote=True)}" '
            'target="_blank" rel="noopener noreferrer nofollow">元記事を開く ↗</a></p>'
        )

    published_markup = ""
    if published:
        human_date = datetime.fromisoformat(published.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
        published_markup = f'<time datetime="{html.escape(published)}">{human_date}</time>'

    body = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(seo_title)}</title>
  <meta name="description" content="{html.escape(description, quote=True)}">
  <meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">
  <link rel="canonical" href="{html.escape(canonical, quote=True)}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="Kirapara News">
  <meta property="og:locale" content="ja_JP">
  <meta property="og:title" content="{html.escape(title, quote=True)}">
  <meta property="og:description" content="{html.escape(description, quote=True)}">
  <meta property="og:url" content="{html.escape(canonical, quote=True)}">
  <meta property="og:image" content="{html.escape(image, quote=True)}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{html.escape(title, quote=True)}">
  <meta name="twitter:description" content="{html.escape(description, quote=True)}">
  <meta name="twitter:image" content="{html.escape(image, quote=True)}">
  <script type="application/ld+json">{json_ld(item, canonical, title, summary, image, published)}</script>
  <style>
    :root{{color-scheme:light dark;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
    body{{margin:0;background:#111018;color:#f7f3fb;line-height:1.7}}
    main{{width:min(760px,calc(100% - 32px));margin:0 auto;padding:32px 0 64px}}
    a{{color:#e4b6ff}} .back{{display:inline-block;margin-bottom:24px}}
    article{{background:#1b1824;border:1px solid #352b45;border-radius:20px;overflow:hidden}}
    .hero{{width:100%;max-height:520px;object-fit:cover;background:#24202d}}
    .content{{padding:24px}} .meta{{font-size:.88rem;color:#bfb5ca;margin-bottom:12px}}
    h1{{font-size:clamp(1.55rem,5vw,2.3rem);line-height:1.35;margin:.2em 0 .8em}}
    .summary{{white-space:pre-wrap;font-size:1.03rem}}
    .source a{{display:inline-block;margin-top:18px;padding:10px 15px;border-radius:999px;background:#2b2138;text-decoration:none}}
    footer{{margin-top:24px;color:#9e95a8;font-size:.86rem}}
  </style>
</head>
<body>
  <main>
    <a class="back" href="{SITE_BASE}">← Kirapara Newsへ戻る</a>
    <article>
      <img class="hero" src="{html.escape(image, quote=True)}" alt="" loading="eager">
      <div class="content">
        <div class="meta">{html.escape(region)} · {html.escape(platform)} {published_markup}</div>
        <h1>{html.escape(title)}</h1>
        <p class="summary">{html.escape(summary)}</p>
        {source_link}
      </div>
    </article>
    <footer>非公式ファンツール。AI翻訳・要約には誤りが含まれる場合があります。</footer>
  </main>
</body>
</html>
"""
    return aid, body


def build_sitemap(items: list[dict]) -> str:
    entries = [(SITE_BASE, "")]
    for item in items:
        aid = article_id(item)
        entries.append((urljoin(SITE_BASE, f"articles/{aid}.html"), iso_datetime(item.get("publishedAtEpoch"))))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, lastmod in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{html.escape(url)}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{html.escape(lastmod)}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def main() -> int:
    data = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("data/news.json must contain a JSON array")

    items = [item for item in data if isinstance(item, dict)]
    items.sort(key=lambda row: int(row.get("publishedAtEpoch") or 0), reverse=True)
    items = items[:MAX_ARTICLES]

    if ARTICLES_DIR.exists():
        shutil.rmtree(ARTICLES_DIR)
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    for item in items:
        aid, markup = render_article(item)
        (ARTICLES_DIR / f"{aid}.html").write_text(markup, encoding="utf-8")

    (DOCS_DIR / "sitemap.xml").write_text(build_sitemap(items), encoding="utf-8")
    (DOCS_DIR / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: " + urljoin(SITE_BASE, "sitemap.xml") + "\n",
        encoding="utf-8",
    )

    print(f"Generated {len(items)} SEO article pages, sitemap.xml and robots.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
