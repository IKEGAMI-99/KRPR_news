package com.ikegami99.krprnews.data

object DemoNewsRepository : NewsRepository {
    override suspend fun loadNews(): List<NewsItem> = listOf(
        NewsItem(
            id = "cn-demo",
            region = Region.CHINA,
            platform = "Weibo · DEMO",
            publishedLabel = "サンプル",
            originalTitle = "中国版新闻显示示例",
            originalText = "获取中国版官方消息后，这里会显示原文。需要时可使用本地GGUF模型翻译成日语或生成日语摘要。",
            sourceUrl = "https://weibo.com/",
            category = "👗 中国版"
        ),
        NewsItem(
            id = "global-demo",
            region = Region.GLOBAL,
            platform = "Official SNS · DEMO",
            publishedLabel = "サンプル",
            originalTitle = "Global news display sample",
            originalText = "Official English posts stay in their original language until the user asks the local GGUF model to translate or summarize them.",
            sourceUrl = "https://lifemakeover.archosaur.com/",
            category = "✨ Global"
        ),
        NewsItem(
            id = "jp-demo",
            region = Region.JAPAN,
            platform = "公式サイト · DEMO",
            publishedLabel = "サンプル",
            originalTitle = "日本版ニュースの表示サンプル",
            originalText = "日本版の情報はそのまま読みやすいカードとして表示します。必要に応じてローカルAIで要約できます。",
            sourceUrl = "https://kirapara.archosaur.com/",
            category = "🌸 日本版"
        ),
        NewsItem(
            id = "kr-demo",
            region = Region.KOREA,
            platform = "Official SNS · DEMO",
            publishedLabel = "サンプル",
            originalTitle = "한국판 뉴스 표시 예시",
            originalText = "스타일라잇의 한국어 소식도 원문으로 표시하고 필요할 때 로컬 GGUF 모델로 일본어 번역과 요약을 생성합니다.",
            sourceUrl = "https://game.naver.com/",
            category = "💎 韓国版"
        )
    )
}
