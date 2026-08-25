package com.ikegami99.krprnews.data

object DemoNewsRepository : NewsRepository {
    override suspend fun loadNews(): List<NewsItem> = listOf(
        NewsItem(
            id = "cn-demo",
            region = Region.CHINA,
            platform = "Weibo · DEMO",
            publishedLabel = "サンプル",
            translatedTitle = "中国版ニュースの表示サンプル",
            originalTitle = "中国版新闻显示示例",
            translatedText = "中国版の公式投稿を取得した場合、この位置に日本語訳を表示します。カード内のボタンで原文へ切り替えられます。",
            originalText = "获取中国版官方消息后，这里会显示原文。可以使用卡片内的按钮切换语言。",
            sourceUrl = "https://weibo.com/",
            category = "👗 中国版"
        ),
        NewsItem(
            id = "global-demo",
            region = Region.GLOBAL,
            platform = "Official SNS · DEMO",
            publishedLabel = "サンプル",
            translatedTitle = "Global版ニュースの表示サンプル",
            originalTitle = "Global news display sample",
            translatedText = "英語の公式投稿は日本語へ翻訳した本文を標準表示し、必要なときだけ原文へ戻せます。",
            originalText = "Official English posts are shown in Japanese by default, while the original text stays one tap away.",
            sourceUrl = "https://lifemakeover.archosaur.com/",
            category = "✨ Global"
        ),
        NewsItem(
            id = "jp-demo",
            region = Region.JAPAN,
            platform = "公式サイト · DEMO",
            publishedLabel = "サンプル",
            translatedTitle = "日本版ニュースの表示サンプル",
            originalTitle = "日本版ニュースの表示サンプル",
            translatedText = "日本版の情報はそのまま読みやすいカードとして表示します。画像や動画リンクにも対応できるデータ構造です。",
            originalText = "日本版の情報はそのまま読みやすいカードとして表示します。画像や動画リンクにも対応できるデータ構造です。",
            sourceUrl = "https://kirapara.archosaur.com/",
            category = "🌸 日本版"
        ),
        NewsItem(
            id = "kr-demo",
            region = Region.KOREA,
            platform = "Official SNS · DEMO",
            publishedLabel = "サンプル",
            translatedTitle = "韓国版ニュースの表示サンプル",
            originalTitle = "한국판 뉴스 표시 예시",
            translatedText = "Stylightの韓国語投稿も同じタイムラインへ統合し、日本語と韓国語を切り替えられる想定です。",
            originalText = "스타일라잇의 한국어 소식도 같은 타임라인에 통합하여 원문과 번역문을 전환할 수 있습니다.",
            sourceUrl = "https://game.naver.com/",
            category = "💎 韓国版"
        )
    )
}
