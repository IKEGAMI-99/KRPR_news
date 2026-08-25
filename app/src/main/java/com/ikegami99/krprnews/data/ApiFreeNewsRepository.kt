package com.ikegami99.krprnews.data

import android.util.Xml
import com.ikegami99.krprnews.translation.LocalTranslationManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import org.xmlpull.v1.XmlPullParser
import java.net.HttpURLConnection
import java.net.URL
import java.time.Duration
import java.time.Instant
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/**
 * APIキーを使わず公開RSS/公開HTMLのみからニュースを集める repository。
 * 取得失敗はソース単位で無視し、複数の取得経路をフォールバックとして使う。
 */
object ApiFreeNewsRepository : NewsRepository {
    private val rssHubHosts = listOf(
        "https://rsshub.yfi.moe",
        "https://rsshub.rssforever.com",
        "https://rsshub.app"
    )

    private fun hubRoutes(path: String) = rssHubHosts.map { "$it$path" }

    private val sources: List<PublicNewsSource> = listOf(
        // 日本版。公式チャンネルIDが分かっているのでYouTube公式RSSを直接利用。
        YouTubeChannelSource(
            region = Region.JAPAN,
            channelId = "UC9MO21fNvt0F4-UK28kc_VQ",
            label = "公式YouTube"
        ),

        // Global。公式の /c/LifeMakeover と handle の両方から channel ID を解決する。
        YouTubePageSource(
            region = Region.GLOBAL,
            pageUrls = listOf(
                "https://www.youtube.com/c/LifeMakeover/",
                "https://www.youtube.com/@LifeMakeover"
            ),
            label = "公式YouTube"
        ),
        RssSource(
            region = Region.GLOBAL,
            urls = hubRoutes("/youtube/c/LifeMakeover"),
            label = "公式YouTube · RSSHub"
        ),

        // 韓国版 Stylight。handle直読みとRSSHubを併用。
        YouTubePageSource(
            region = Region.KOREA,
            pageUrls = listOf("https://www.youtube.com/@stylight_official"),
            label = "公式YouTube"
        ),
        RssSource(
            region = Region.KOREA,
            urls = hubRoutes("/youtube/user/@stylight_official"),
            label = "公式YouTube · RSSHub"
        ),

        // 中国版。Weiboだけに依存せず、公式Bilibili投稿も取得する。
        RssSource(
            region = Region.CHINA,
            urls = hubRoutes("/weibo/user/7521830234"),
            label = "公式Weibo · RSSHub"
        ),
        RssSource(
            region = Region.CHINA,
            urls = hubRoutes("/bilibili/user/video/676200579"),
            label = "公式Bilibili · RSSHub"
        )
    )

    override suspend fun loadNews(): List<NewsItem> = coroutineScope {
        val raw = sources.map { source ->
            async(Dispatchers.IO) {
                runCatching { source.fetch() }.getOrDefault(emptyList())
            }
        }.awaitAll()
            .flatten()
            .distinctBy { it.sourceUrl }
            .sortedByDescending { it.publishedAtEpoch }
            .take(40)

        if (raw.isEmpty()) return@coroutineScope DemoNewsRepository.loadNews()

        raw.map { item ->
            val translatedTitle = LocalTranslationManager.translate(item.region, item.title)
            val originalBody = item.body.ifBlank { item.title }
            val translatedBody = if (originalBody == item.title) {
                translatedTitle
            } else {
                LocalTranslationManager.translate(item.region, originalBody)
            }
            NewsItem(
                id = item.id,
                region = item.region,
                platform = item.platform,
                publishedLabel = item.publishedLabel,
                translatedTitle = translatedTitle,
                originalTitle = item.title,
                translatedText = translatedBody,
                originalText = originalBody,
                sourceUrl = item.sourceUrl,
                category = categoryFor(item.title, item.region),
                imageUrl = item.imageUrl
            )
        }
    }

    private fun categoryFor(text: String, region: Region): String {
        val t = text.lowercase()
        return when {
            listOf("6星", "星6", "outfit", "set", "세트", "衣装", "套装", "五星", "六星").any(t::contains) -> "👗 新衣装"
            listOf("event", "イベント", "活动", "이벤트").any(t::contains) -> "🎉 イベント"
            listOf("update", "アップデート", "版本", "업데이트").any(t::contains) -> "📢 アップデート"
            listOf("maintenance", "メンテ", "维护", "점검").any(t::contains) -> "🔧 メンテナンス"
            else -> when (region) {
                Region.JAPAN -> "🌸 日本版"
                Region.CHINA -> "👗 中国版"
                Region.GLOBAL -> "✨ Global"
                Region.KOREA -> "💎 韓国版"
            }
        }
    }
}

private data class RawNews(
    val id: String,
    val region: Region,
    val platform: String,
    val title: String,
    val body: String,
    val sourceUrl: String,
    val publishedLabel: String,
    val publishedAtEpoch: Long,
    val imageUrl: String? = null
)

private interface PublicNewsSource {
    suspend fun fetch(): List<RawNews>
}

private class YouTubeChannelSource(
    private val region: Region,
    private val channelId: String,
    private val label: String
) : PublicNewsSource {
    override suspend fun fetch(): List<RawNews> = withContext(Dispatchers.IO) {
        parseFeed(
            xml = httpGet("https://www.youtube.com/feeds/videos.xml?channel_id=$channelId"),
            region = region,
            platform = label
        )
    }
}

/**
 * YouTubeの公開チャンネルページから channel ID を解決する。
 * YouTube側のHTML差分に備え、複数の既知パターンを順番に試す。
 */
private class YouTubePageSource(
    private val region: Region,
    private val pageUrls: List<String>,
    private val label: String
) : PublicNewsSource {
    override suspend fun fetch(): List<RawNews> = withContext(Dispatchers.IO) {
        for (pageUrl in pageUrls) {
            val html = runCatching { httpGet(pageUrl) }.getOrNull() ?: continue
            val channelId = resolveChannelId(html) ?: continue
            val feed = runCatching {
                httpGet("https://www.youtube.com/feeds/videos.xml?channel_id=$channelId")
            }.getOrNull() ?: continue
            val parsed = runCatching { parseFeed(feed, region, label) }.getOrNull()
            if (!parsed.isNullOrEmpty()) return@withContext parsed
        }
        emptyList()
    }
}

private fun resolveChannelId(html: String): String? {
    val patterns = listOf(
        Regex("\\\"channelId\\\"\\s*:\\s*\\\"(UC[a-zA-Z0-9_-]{22})\\\""),
        Regex("\\\"browseId\\\"\\s*:\\s*\\\"(UC[a-zA-Z0-9_-]{22})\\\""),
        Regex("\\\"externalId\\\"\\s*:\\s*\\\"(UC[a-zA-Z0-9_-]{22})\\\""),
        Regex("itemprop=[\\\"'](?:channelId|identifier)[\\\"'][^>]*content=[\\\"'](UC[a-zA-Z0-9_-]{22})[\\\"']", RegexOption.IGNORE_CASE),
        Regex("youtube\\.com/channel/(UC[a-zA-Z0-9_-]{22})", RegexOption.IGNORE_CASE),
        Regex("channelId[^A-Za-z0-9_-]+(UC[a-zA-Z0-9_-]{22})")
    )
    return patterns.firstNotNullOfOrNull { it.find(html)?.groupValues?.getOrNull(1) }
}

private class RssSource(
    private val region: Region,
    private val urls: List<String>,
    private val label: String
) : PublicNewsSource {
    override suspend fun fetch(): List<RawNews> = withContext(Dispatchers.IO) {
        for (url in urls) {
            val result = runCatching { parseFeed(httpGet(url), region, label) }.getOrNull()
            if (!result.isNullOrEmpty()) return@withContext result
        }
        emptyList()
    }
}

private fun parseFeed(xml: String, region: Region, platform: String): List<RawNews> {
    val parser = Xml.newPullParser().apply { setInput(xml.reader()) }
    val out = mutableListOf<RawNews>()

    var inside = false
    var title = ""
    var body = ""
    var link = ""
    var published = ""
    var videoId = ""
    var image: String? = null
    var activeTag = ""

    fun reset() {
        title = ""
        body = ""
        link = ""
        published = ""
        videoId = ""
        image = null
        activeTag = ""
    }

    var event = parser.eventType
    while (event != XmlPullParser.END_DOCUMENT) {
        when (event) {
            XmlPullParser.START_TAG -> {
                val name = parser.name.substringAfter(':')
                if (name == "entry" || name == "item") {
                    inside = true
                    reset()
                }
                if (inside) {
                    activeTag = name
                    if (name == "link") {
                        parser.getAttributeValue(null, "href")?.let { link = it }
                    }
                    if (name == "thumbnail") {
                        image = parser.getAttributeValue(null, "url") ?: image
                    }
                    if (name == "enclosure" || name == "content") {
                        val url = parser.getAttributeValue(null, "url")
                        val type = parser.getAttributeValue(null, "type").orEmpty()
                        val medium = parser.getAttributeValue(null, "medium").orEmpty()
                        if (!url.isNullOrBlank() && (type.startsWith("image") || medium == "image" || looksLikeImage(url))) {
                            image = url
                        }
                    }
                }
            }
            XmlPullParser.TEXT -> if (inside) {
                val text = parser.text.orEmpty().trim()
                if (text.isNotEmpty()) when (activeTag) {
                    "title" -> title += text
                    "description", "content", "encoded", "summary" -> if (body.length < 3000) body += text
                    "link" -> if (link.isBlank() && text.startsWith("http")) link = text
                    "published", "updated", "pubDate" -> if (published.isBlank()) published = text
                    "videoId" -> videoId = text
                    "guid" -> if (link.isBlank() && text.startsWith("http")) link = text
                }
            }
            XmlPullParser.END_TAG -> {
                val name = parser.name.substringAfter(':')
                if (name == activeTag) activeTag = ""
                if (name == "entry" || name == "item") {
                    if (link.isBlank() && videoId.isNotBlank()) link = "https://www.youtube.com/watch?v=$videoId"
                    if (image == null && videoId.isNotBlank()) image = "https://i.ytimg.com/vi/$videoId/hqdefault.jpg"
                    if (image == null) image = extractImageFromHtml(body)
                    if (title.isNotBlank() && link.isNotBlank()) {
                        val cleanedBody = stripHtml(body).ifBlank { title }
                        val epoch = parseEpoch(published)
                        out += RawNews(
                            id = (videoId.ifBlank { link }).hashCode().toString(),
                            region = region,
                            platform = platform,
                            title = stripHtml(title),
                            body = cleanedBody.take(1800),
                            sourceUrl = link,
                            publishedLabel = friendlyDate(epoch, published),
                            publishedAtEpoch = epoch,
                            imageUrl = image
                        )
                    }
                    inside = false
                    reset()
                }
            }
        }
        event = parser.next()
    }
    return out.take(16)
}

private fun looksLikeImage(url: String): Boolean =
    Regex("\\.(?:jpg|jpeg|png|webp)(?:\\?|$)", RegexOption.IGNORE_CASE).containsMatchIn(url)

private fun extractImageFromHtml(value: String): String? {
    val imgTag = Regex("<img[^>]+src=[\\\"']([^\\\"']+)[\\\"']", RegexOption.IGNORE_CASE)
        .find(value)?.groupValues?.getOrNull(1)
    if (!imgTag.isNullOrBlank()) return decodeEntities(imgTag)
    return Regex("https?://[^\\s\\\"'<>]+\\.(?:jpg|jpeg|png|webp)(?:\\?[^\\s\\\"'<>]*)?", RegexOption.IGNORE_CASE)
        .find(value)?.value
        ?.let(::decodeEntities)
}

private fun httpGet(url: String): String {
    val connection = URL(url).openConnection() as HttpURLConnection
    return try {
        connection.connectTimeout = 12_000
        connection.readTimeout = 12_000
        connection.instanceFollowRedirects = true
        connection.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/139 Mobile Safari/537.36 KiraparaNews/0.2.1")
        connection.setRequestProperty("Accept-Language", "ja,en-US;q=0.9,en;q=0.8,ko;q=0.7,zh-CN;q=0.6")
        connection.setRequestProperty("Accept", "application/rss+xml, application/atom+xml, text/xml, text/html;q=0.9, */*;q=0.8")
        val code = connection.responseCode
        if (code !in 200..299) error("HTTP $code for $url")
        connection.inputStream.bufferedReader().use { it.readText() }
    } finally {
        connection.disconnect()
    }
}

private fun decodeEntities(value: String): String = value
    .replace("&amp;", "&")
    .replace("&quot;", "\"")
    .replace("&#39;", "'")

private fun stripHtml(value: String): String = decodeEntities(value)
    .replace(Regex("<br\\s*/?>", RegexOption.IGNORE_CASE), "\n")
    .replace(Regex("<[^>]+>"), " ")
    .replace("&lt;", "<")
    .replace("&gt;", ">")
    .replace(Regex("[ \\t]+"), " ")
    .replace(Regex("\\n{3,}"), "\n\n")
    .trim()

private fun parseEpoch(value: String): Long {
    if (value.isBlank()) return 0L
    return runCatching { Instant.parse(value).epochSecond }.getOrElse {
        runCatching {
            ZonedDateTime.parse(value, DateTimeFormatter.RFC_1123_DATE_TIME).toInstant().epochSecond
        }.getOrDefault(0L)
    }
}

private fun friendlyDate(epoch: Long, raw: String): String {
    if (epoch <= 0L) return raw.take(10).ifBlank { "新着" }
    val age = Duration.between(Instant.ofEpochSecond(epoch), Instant.now())
    return when {
        age.isNegative -> "新着"
        age.toMinutes() < 60 -> "${age.toMinutes().coerceAtLeast(1)}分前"
        age.toHours() < 24 -> "${age.toHours()}時間前"
        age.toDays() < 7 -> "${age.toDays()}日前"
        else -> Instant.ofEpochSecond(epoch).atZone(java.time.ZoneId.systemDefault()).toLocalDate().toString()
    }
}
