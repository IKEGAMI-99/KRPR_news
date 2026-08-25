package com.ikegami99.krprnews.data

import android.util.Xml
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONArray
import org.xmlpull.v1.XmlPullParser
import java.net.HttpURLConnection
import java.net.URL
import java.time.Duration
import java.time.Instant
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/**
 * 公開RSS/HTML + GitHub Actionsキャッシュを使うニュースRepository。
 * ニュースは各地域の原文のまま読み込み、翻訳や要約はユーザー操作時だけ
 * LocalGemmaManager が端末内GGUFで行う。
 */
object ApiFreeNewsRepository : NewsRepository {
    private const val AGGREGATED_TIMEOUT_MS = 4_000L
    private const val SOURCE_TIMEOUT_MS = 5_500L

    private val rssHubHosts = listOf(
        "https://rsshub.app",
        "https://rsshub.rssforever.com",
        "https://rsshub.yfi.moe"
    )

    private fun hubRoutes(path: String) = rssHubHosts.map { "$it$path" }

    private val directSources: List<PublicNewsSource> = listOf(
        YouTubeChannelSource(
            region = Region.JAPAN,
            channelId = "UC9MO21fNvt0F4-UK28kc_VQ",
            label = "公式YouTube"
        ),
        YouTubePageSource(
            region = Region.GLOBAL,
            pageUrls = listOf(
                "https://www.youtube.com/c/LifeMakeover/",
                "https://www.youtube.com/@LifeMakeover"
            ),
            label = "公式YouTube"
        ),
        YouTubePageSource(
            region = Region.KOREA,
            pageUrls = listOf("https://www.youtube.com/@stylight_official"),
            label = "公式YouTube"
        ),
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

    override suspend fun loadNews(): List<NewsItem> = supervisorScope {
        val aggregated = withTimeoutOrNull(AGGREGATED_TIMEOUT_MS) {
            runCatching { GitHubJsonSource.fetch() }.getOrDefault(emptyList())
        }.orEmpty()

        val raw = if (aggregated.isNotEmpty()) {
            aggregated
        } else {
            directSources.map { source ->
                async(Dispatchers.IO) {
                    withTimeoutOrNull(SOURCE_TIMEOUT_MS) {
                        runCatching { source.fetch() }.getOrDefault(emptyList())
                    }.orEmpty()
                }
            }.awaitAll().flatten()
        }
            .distinctBy { it.sourceUrl }
            .sortedByDescending { it.publishedAtEpoch }
            .take(30)

        if (raw.isEmpty()) return@supervisorScope DemoNewsRepository.loadNews()

        raw.map { item ->
            val originalBody = item.body.ifBlank { item.title }
            NewsItem(
                id = item.id,
                region = item.region,
                platform = item.platform,
                publishedLabel = item.publishedLabel,
                originalTitle = item.title,
                originalText = originalBody,
                sourceUrl = item.sourceUrl,
                category = categoryFor(item.title, item.region),
                imageUrl = normalizeImage(item.imageUrl, item.region)
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

private object GitHubJsonSource : PublicNewsSource {
    override suspend fun fetch(): List<RawNews> = withContext(Dispatchers.IO) {
        val json = httpGet(
            "https://raw.githubusercontent.com/IKEGAMI-99/KRPR_news/main/data/news.json",
            timeoutMs = 3_500
        )
        val array = JSONArray(json)
        buildList {
            for (i in 0 until array.length()) {
                val item = array.optJSONObject(i) ?: continue
                val region = when (item.optString("region").uppercase()) {
                    "JAPAN" -> Region.JAPAN
                    "CHINA" -> Region.CHINA
                    "GLOBAL" -> Region.GLOBAL
                    "KOREA" -> Region.KOREA
                    else -> continue
                }
                val title = item.optString("title").trim()
                val url = item.optString("sourceUrl").trim()
                if (title.isBlank() || url.isBlank()) continue
                val epoch = item.optLong("publishedAtEpoch", 0L)
                add(
                    RawNews(
                        id = item.optString("id").ifBlank { url.hashCode().toString() },
                        region = region,
                        platform = item.optString("platform").ifBlank { "公式情報" },
                        title = title,
                        body = item.optString("body").ifBlank { title },
                        sourceUrl = url,
                        publishedLabel = item.optString("publishedLabel").ifBlank { friendlyDate(epoch, "") },
                        publishedAtEpoch = epoch,
                        imageUrl = item.optString("imageUrl").takeIf { it.isNotBlank() }
                    )
                )
            }
        }
    }
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

private class YouTubePageSource(
    private val region: Region,
    private val pageUrls: List<String>,
    private val label: String
) : PublicNewsSource {
    override suspend fun fetch(): List<RawNews> = withContext(Dispatchers.IO) {
        for (pageUrl in pageUrls) {
            val html = runCatching { httpGet(pageUrl, timeoutMs = 4_000) }.getOrNull() ?: continue
            val channelId = resolveChannelId(html) ?: continue
            val feed = runCatching {
                httpGet("https://www.youtube.com/feeds/videos.xml?channel_id=$channelId", timeoutMs = 4_000)
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
    override suspend fun fetch(): List<RawNews> = coroutineScope {
        urls.map { url ->
            async(Dispatchers.IO) {
                runCatching {
                    parseFeed(httpGet(url, timeoutMs = 4_000), region, label)
                }.getOrDefault(emptyList())
            }
        }.awaitAll().firstOrNull { it.isNotEmpty() }.orEmpty()
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
                        val cleanedTitle = compactTitle(title, region)
                        val cleanedBody = cleanSocialText(stripHtml(body).ifBlank { title }, region)
                        val epoch = parseEpoch(published)
                        out += RawNews(
                            id = (videoId.ifBlank { link }).hashCode().toString(),
                            region = region,
                            platform = platform,
                            title = cleanedTitle,
                            body = cleanedBody.take(1800),
                            sourceUrl = link,
                            publishedLabel = friendlyDate(epoch, published),
                            publishedAtEpoch = epoch,
                            imageUrl = normalizeImage(image, region)
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

private fun cleanSocialText(value: String, region: Region): String {
    var text = stripHtml(value)
    if (region == Region.CHINA) {
        text = text
            .replace(Regex("#[^#\\n]{1,80}#"), " ")
            .replace(Regex("^\\s*(以闪亮之名\\s*)+"), "")
            .replace("网页链接", "")
        text = text.lineSequence()
            .map(String::trim)
            .filter { it.isNotBlank() }
            .filterNot { it.contains("下载传送门") || it.contains("活动传送门") }
            .joinToString("\n")
    }
    return text
        .replace(Regex("[ \\t]{2,}"), " ")
        .replace(Regex("\\n{3,}"), "\n\n")
        .trim()
}

private fun compactTitle(value: String, region: Region): String {
    val cleaned = cleanSocialText(value, region)
    if (cleaned.isBlank()) return "新着ニュース"
    val first = cleaned.split(Regex("[\\n。！？!?]"), limit = 2).firstOrNull().orEmpty().trim()
    val candidate = if (first.length >= 8) first else cleaned.replace("\n", " ")
    return candidate.take(100).trimEnd(' ', ',', '，', '、', '-', '｜', '|')
}

private fun normalizeImage(url: String?, region: Region): String? {
    val low = url.orEmpty().lowercase()
    val invalid = url.isNullOrBlank() || listOf(
        "timeline_card_small_super_default",
        "timeline_card_small_web_default",
        "timeline_card_small_default"
    ).any(low::contains)

    if (!invalid) return url
    return when (region) {
        Region.JAPAN -> "https://kirapara.archosaur.com/new_script/img/pc/top_logo.png"
        Region.CHINA -> "https://mystyle.archosaur.com/assets/260811/pc/images/p3/slider1.jpg"
        Region.KOREA -> "https://stylight.nex2fun.com/assets/pc/img/page1/page1_slogan.png"
        Region.GLOBAL -> null
    }
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

private fun httpGet(url: String, timeoutMs: Int = 4_500): String {
    val connection = URL(url).openConnection() as HttpURLConnection
    return try {
        connection.connectTimeout = timeoutMs
        connection.readTimeout = timeoutMs
        connection.instanceFollowRedirects = true
        connection.setRequestProperty(
            "User-Agent",
            "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/139 Mobile Safari/537.36 KiraparaNews/0.3.0"
        )
        connection.setRequestProperty("Accept-Language", "ja,en-US;q=0.9,en;q=0.8,ko;q=0.7,zh-CN;q=0.6")
        connection.setRequestProperty("Accept", "application/rss+xml, application/atom+xml, application/json, text/xml, text/html;q=0.9, */*;q=0.8")
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
