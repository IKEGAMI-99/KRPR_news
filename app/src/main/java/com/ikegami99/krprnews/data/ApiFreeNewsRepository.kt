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
 * APIキーを使わず公開RSS/公開HTMLのみからニュースを集める v0.2 repository。
 * 取得失敗はソース単位で握りつぶし、全ソースが落ちた場合だけデモデータへ戻す。
 */
object ApiFreeNewsRepository : NewsRepository {
    private val sources: List<PublicNewsSource> = listOf(
        YouTubeChannelSource(
            region = Region.JAPAN,
            channelId = "UC9MO21fNvt0F4-UK28kc_VQ",
            label = "公式YouTube"
        ),
        YouTubeHandleSource(
            region = Region.GLOBAL,
            handle = "LifeMakeover",
            label = "公式YouTube"
        ),
        YouTubeHandleSource(
            region = Region.KOREA,
            handle = "stylight_official",
            label = "公式YouTube"
        ),
        RssSource(
            region = Region.CHINA,
            urls = listOf(
                "https://rsshub.app/weibo/user/7521830234",
                "https://rsshub.rssforever.com/weibo/user/7521830234"
            ),
            label = "公式Weibo · RSSHub"
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
            .take(20)

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
            listOf("6星", "星6", "outfit", "set", "세트", "衣装", "套装").any(t::contains) -> "👗 新衣装"
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

private class YouTubeHandleSource(
    private val region: Region,
    private val handle: String,
    private val label: String
) : PublicNewsSource {
    override suspend fun fetch(): List<RawNews> = withContext(Dispatchers.IO) {
        val html = httpGet("https://www.youtube.com/@$handle")
        val channelId = Regex("\\\"channelId\\\":\\\"(UC[a-zA-Z0-9_-]{22})\\\"")
            .find(html)?.groupValues?.getOrNull(1)
            ?: Regex("channelId[^A-Za-z0-9_-]+(UC[a-zA-Z0-9_-]{22})")
                .find(html)?.groupValues?.getOrNull(1)
            ?: return@withContext emptyList()
        parseFeed(
            xml = httpGet("https://www.youtube.com/feeds/videos.xml?channel_id=$channelId"),
            region = region,
            platform = label
        )
    }
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
                }
            }
            XmlPullParser.TEXT -> if (inside) {
                val text = parser.text.orEmpty().trim()
                if (text.isNotEmpty()) when (activeTag) {
                    "title" -> title += text
                    "description", "content", "encoded" -> if (body.length < 2400) body += text
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
    return out.take(12)
}

private fun httpGet(url: String): String {
    val connection = URL(url).openConnection() as HttpURLConnection
    return try {
        connection.connectTimeout = 12_000
        connection.readTimeout = 12_000
        connection.instanceFollowRedirects = true
        connection.setRequestProperty("User-Agent", "Mozilla/5.0 (Android) KiraparaNews/0.2")
        connection.setRequestProperty("Accept", "application/rss+xml, application/atom+xml, text/xml, text/html;q=0.9, */*;q=0.8")
        connection.inputStream.bufferedReader().use { it.readText() }
    } finally {
        connection.disconnect()
    }
}

private fun stripHtml(value: String): String = value
    .replace(Regex("<br\\s*/?>", RegexOption.IGNORE_CASE), "\n")
    .replace(Regex("<[^>]+>"), " ")
    .replace("&amp;", "&")
    .replace("&lt;", "<")
    .replace("&gt;", ">")
    .replace("&quot;", "\"")
    .replace("&#39;", "'")
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
