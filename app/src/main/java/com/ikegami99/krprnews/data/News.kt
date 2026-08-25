package com.ikegami99.krprnews.data

enum class Region(val flag: String, val label: String, val originalLabel: String) {
    JAPAN("🇯🇵", "日本", "原文"),
    CHINA("🇨🇳", "中国", "中文"),
    GLOBAL("🌎", "Global", "English"),
    KOREA("🇰🇷", "韓国", "한국어")
}

data class NewsItem(
    val id: String,
    val region: Region,
    val platform: String,
    val publishedLabel: String,
    val translatedTitle: String,
    val originalTitle: String,
    val translatedText: String,
    val originalText: String,
    val sourceUrl: String,
    val category: String,
    val imageUrl: String? = null
)

interface NewsRepository {
    suspend fun loadNews(): List<NewsItem>
}
