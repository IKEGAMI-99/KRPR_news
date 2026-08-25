package com.ikegami99.krprnews.ai

import android.content.Context
import android.database.Cursor
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import com.ikegami99.krprnews.data.NewsItem
import com.ikegami99.krprnews.data.Region
import dev.ffmpegkit.llama.Llama
import dev.ffmpegkit.llama.LlamaConfig
import dev.ffmpegkit.llama.LlamaModel
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONObject
import java.security.MessageDigest

data class LocalAiTranslation(
    val title: String,
    val body: String,
    val tokensPerSecond: Float = 0f
)

data class LocalAiSummary(
    val text: String,
    val tokensPerSecond: Float = 0f
)

/**
 * ユーザーが選択したGGUFをllama.cppで直接実行するローカルAI。
 * モデルも記事本文も外部へ送信しない。
 *
 * SAFのcontent:// URIをParcelFileDescriptorで開き、/proc/self/fd/<fd> を
 * llama.cppへ渡すことで巨大なGGUFをアプリ領域へ複製せず利用する。
 */
object LocalGemmaManager {
    private const val CACHE_PREFS = "krpr_local_ai_cache_v1"

    private val inferenceMutex = Mutex()
    private var loadedUri: String? = null
    private var loadedModel: LlamaModel? = null
    private var modelDescriptor: ParcelFileDescriptor? = null

    suspend fun warmUp(context: Context, modelUri: String) {
        inferenceMutex.withLock {
            ensureModelLocked(context.applicationContext, modelUri)
        }
    }

    suspend fun translate(context: Context, modelUri: String, news: NewsItem): LocalAiTranslation {
        if (news.region == Region.JAPAN) {
            return LocalAiTranslation(news.originalTitle, news.originalText)
        }

        return inferenceMutex.withLock {
            readTranslationCache(context, modelUri, news)?.let { return@withLock it }
            val model = ensureModelLocked(context.applicationContext, modelUri)
            val sourceLanguage = when (news.region) {
                Region.CHINA -> "Chinese"
                Region.GLOBAL -> "English"
                Region.KOREA -> "Korean"
                Region.JAPAN -> "Japanese"
            }

            val result = Llama.complete(
                model = model,
                systemPrompt = """
                    You are a professional Japanese game-localization translator.
                    Translate the supplied $sourceLanguage game news into natural Japanese.
                    Preserve proper nouns, outfit/item names, dates, times, numbers, emoji and event conditions accurately.
                    Do not summarize, omit details, explain, add commentary, or invent information.
                    Return ONLY a valid JSON object with exactly two string keys: \"title\" and \"body\".
                """.trimIndent(),
                prompt = """
                    TITLE:
                    ${news.originalTitle}

                    BODY:
                    ${news.originalText}
                """.trimIndent(),
                maxTokens = 1200
            )

            val translation = parseTranslation(result.text, news).copy(tokensPerSecond = result.tokensPerSecond)
            writeTranslationCache(context, modelUri, news, translation)
            translation
        }
    }

    suspend fun summarize(context: Context, modelUri: String, news: NewsItem): LocalAiSummary {
        return inferenceMutex.withLock {
            readSummaryCache(context, modelUri, news)?.let { return@withLock it }
            val model = ensureModelLocked(context.applicationContext, modelUri)
            val result = Llama.complete(
                model = model,
                systemPrompt = """
                    You summarize official game news for Japanese players.
                    Write concise, natural Japanese only.
                    Keep important dates, times, rewards, outfit/item names, prices, event periods and requirements.
                    Do not invent information. Do not add a heading. Use 2 to 5 short sentences.
                """.trimIndent(),
                prompt = """
                    以下の公式ニュースを日本語で要約してください。

                    タイトル:
                    ${news.originalTitle}

                    本文:
                    ${news.originalText}
                """.trimIndent(),
                maxTokens = 360
            )
            val summary = LocalAiSummary(
                text = cleanModelText(result.text).ifBlank { "要約を生成できませんでした。" },
                tokensPerSecond = result.tokensPerSecond
            )
            writeSummaryCache(context, modelUri, news, summary)
            summary
        }
    }

    fun cachedTranslation(context: Context, modelUri: String?, news: NewsItem): LocalAiTranslation? {
        if (modelUri.isNullOrBlank()) return null
        return readTranslationCache(context, modelUri, news)
    }

    fun cachedSummary(context: Context, modelUri: String?, news: NewsItem): LocalAiSummary? {
        if (modelUri.isNullOrBlank()) return null
        return readSummaryCache(context, modelUri, news)
    }

    suspend fun release() {
        inferenceMutex.withLock {
            loadedModel?.let { runCatching { Llama.releaseModel(it) } }
            loadedModel = null
            loadedUri = null
            runCatching { modelDescriptor?.close() }
            modelDescriptor = null
        }
    }

    fun displayName(context: Context, uriString: String?): String? {
        if (uriString.isNullOrBlank()) return null
        val uri = runCatching { Uri.parse(uriString) }.getOrNull() ?: return null
        var cursor: Cursor? = null
        return try {
            cursor = context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
            if (cursor != null && cursor.moveToFirst()) {
                val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (index >= 0) cursor.getString(index) else null
            } else null
        } catch (_: Exception) {
            null
        } finally {
            cursor?.close()
        }
    }

    private suspend fun ensureModelLocked(context: Context, modelUri: String): LlamaModel {
        loadedModel?.takeIf { loadedUri == modelUri }?.let { return it }

        loadedModel?.let { runCatching { Llama.releaseModel(it) } }
        loadedModel = null
        loadedUri = null
        runCatching { modelDescriptor?.close() }
        modelDescriptor = null

        val uri = Uri.parse(modelUri)
        val descriptor = context.contentResolver.openFileDescriptor(uri, "r")
            ?: error("GGUFファイルを開けませんでした")
        modelDescriptor = descriptor

        val procPath = "/proc/self/fd/${descriptor.fd}"
        val threads = Runtime.getRuntime().availableProcessors().coerceIn(4, 8)
        val model = try {
            Llama.loadModel(
                modelPath = procPath,
                config = LlamaConfig(
                    contextSize = 4096,
                    threads = threads,
                    gpuLayers = 0,
                    temperature = 0.12f,
                    topP = 0.9f,
                    topK = 40,
                    seed = 1
                )
            )
        } catch (t: Throwable) {
            runCatching { descriptor.close() }
            modelDescriptor = null
            throw IllegalStateException(
                "GGUFの読み込みに失敗しました。Gemma 4対応GGUFか、空きRAMを確認してください。",
                t
            )
        }

        loadedUri = modelUri
        loadedModel = model
        return model
    }

    private fun parseTranslation(raw: String, news: NewsItem): LocalAiTranslation {
        val cleaned = cleanModelText(raw)
        val jsonPart = cleaned.substringAfter('{', "").let { inner ->
            if (inner.isBlank()) null else "{" + inner.substringBeforeLast('}', inner) + "}"
        }
        if (!jsonPart.isNullOrBlank()) {
            runCatching {
                val json = JSONObject(jsonPart)
                val title = json.optString("title").trim()
                val body = json.optString("body").trim()
                if (title.isNotBlank() || body.isNotBlank()) {
                    return LocalAiTranslation(
                        title = title.ifBlank { news.originalTitle },
                        body = body.ifBlank { cleaned }
                    )
                }
            }
        }
        return LocalAiTranslation(news.originalTitle, cleaned.ifBlank { news.originalText })
    }

    private fun cleanModelText(value: String): String = value
        .trim()
        .removePrefix("```json")
        .removePrefix("```")
        .removeSuffix("```")
        .trim()

    private fun readTranslationCache(
        context: Context,
        modelUri: String,
        news: NewsItem
    ): LocalAiTranslation? {
        val raw = context.getSharedPreferences(CACHE_PREFS, Context.MODE_PRIVATE)
            .getString(cacheKey(modelUri, news, "translation"), null) ?: return null
        return runCatching {
            val json = JSONObject(raw)
            LocalAiTranslation(
                title = json.getString("title"),
                body = json.getString("body")
            )
        }.getOrNull()
    }

    private fun writeTranslationCache(
        context: Context,
        modelUri: String,
        news: NewsItem,
        value: LocalAiTranslation
    ) {
        val json = JSONObject()
            .put("title", value.title)
            .put("body", value.body)
            .toString()
        context.getSharedPreferences(CACHE_PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(cacheKey(modelUri, news, "translation"), json)
            .apply()
    }

    private fun readSummaryCache(context: Context, modelUri: String, news: NewsItem): LocalAiSummary? {
        val raw = context.getSharedPreferences(CACHE_PREFS, Context.MODE_PRIVATE)
            .getString(cacheKey(modelUri, news, "summary"), null) ?: return null
        return LocalAiSummary(raw)
    }

    private fun writeSummaryCache(
        context: Context,
        modelUri: String,
        news: NewsItem,
        value: LocalAiSummary
    ) {
        context.getSharedPreferences(CACHE_PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(cacheKey(modelUri, news, "summary"), value.text)
            .apply()
    }

    private fun cacheKey(modelUri: String, news: NewsItem, mode: String): String {
        val source = "$modelUri|${news.id}|${news.originalTitle}|${news.originalText}|$mode"
        val bytes = MessageDigest.getInstance("SHA-256").digest(source.toByteArray())
        return bytes.joinToString("") { "%02x".format(it) }
    }
}
