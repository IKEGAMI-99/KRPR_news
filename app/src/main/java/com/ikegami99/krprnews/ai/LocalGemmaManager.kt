package com.ikegami99.krprnews.ai

import android.content.Context
import android.database.Cursor
import android.net.Uri
import android.provider.OpenableColumns
import com.ikegami99.krprnews.data.NewsItem
import com.ikegami99.krprnews.data.Region
import com.ikegami99.krprnews.diagnostics.AppLog
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.channels.BufferOverflow
import org.json.JSONObject
import org.nehuatl.llamacpp.LlamaHelper
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

private data class GenerationResult(val text: String, val tokensPerSecond: Float)

/**
 * ユーザーが選択したGGUFをAndroid端末内で直接実行する。
 *
 * v0.3.1からScoped Storage対応のFile Descriptor経路を使う。
 * content:// URIを実ファイルパスへ偽装せずContentResolverから直接開くため、
 * Download等に置いた巨大GGUFをアプリ領域へ複製しない。
 */
object LocalGemmaManager {
    private const val CACHE_PREFS = "krpr_local_ai_cache_v2"
    private const val CONTEXT_LENGTH = 4096
    private const val LOAD_TIMEOUT_MS = 300_000L
    private const val GENERATE_TIMEOUT_MS = 300_000L

    private val inferenceMutex = Mutex()
    private var loadedUri: String? = null
    private var helper: LlamaHelper? = null
    private var eventFlow: MutableSharedFlow<LlamaHelper.LLMEvent>? = null
    private var engineScope: CoroutineScope? = null

    suspend fun warmUp(context: Context, modelUri: String) {
        inferenceMutex.withLock {
            ensureModelLocked(context.applicationContext, modelUri)
        }
    }

    suspend fun translate(context: Context, modelUri: String, news: NewsItem): LocalAiTranslation {
        if (news.region == Region.JAPAN) return LocalAiTranslation(news.originalTitle, news.originalText)

        return inferenceMutex.withLock {
            readTranslationCache(context, modelUri, news)?.let { return@withLock it }
            val llama = ensureModelLocked(context.applicationContext, modelUri)
            val sourceLanguage = when (news.region) {
                Region.CHINA -> "Chinese"
                Region.GLOBAL -> "English"
                Region.KOREA -> "Korean"
                Region.JAPAN -> "Japanese"
            }
            AppLog.i(context, "LocalGemma", "translation start region=${news.region} id=${news.id}")
            val result = completeLocked(
                llama,
                """
                You are a professional Japanese game-localization translator.
                Translate the following $sourceLanguage official game news into natural Japanese.
                Preserve proper nouns, outfit/item names, dates, times, numbers, emoji, prices and event conditions accurately.
                Do not summarize, omit details, explain, add commentary, or invent information.
                Return ONLY a valid JSON object with exactly two string keys: "title" and "body".

                TITLE:
                ${news.originalTitle}

                BODY:
                ${news.originalText}
                """.trimIndent()
            )
            val translation = parseTranslation(result.text, news).copy(tokensPerSecond = result.tokensPerSecond)
            writeTranslationCache(context, modelUri, news, translation)
            AppLog.i(context, "LocalGemma", "translation done id=${news.id} tps=${result.tokensPerSecond}")
            translation
        }
    }

    suspend fun summarize(context: Context, modelUri: String, news: NewsItem): LocalAiSummary {
        return inferenceMutex.withLock {
            readSummaryCache(context, modelUri, news)?.let { return@withLock it }
            val llama = ensureModelLocked(context.applicationContext, modelUri)
            AppLog.i(context, "LocalGemma", "summary start region=${news.region} id=${news.id}")
            val result = completeLocked(
                llama,
                """
                以下の公式ゲームニュースを日本語で簡潔に要約してください。
                日付、時間、イベント期間、報酬、衣装名、アイテム名、価格、参加条件など重要情報は落とさないでください。
                原文にない情報を推測・追加しないでください。
                見出しは付けず、自然な日本語2〜5文だけを返してください。

                タイトル:
                ${news.originalTitle}

                本文:
                ${news.originalText}
                """.trimIndent()
            )
            val summary = LocalAiSummary(
                text = cleanModelText(result.text).ifBlank { "要約を生成できませんでした。" },
                tokensPerSecond = result.tokensPerSecond
            )
            writeSummaryCache(context, modelUri, news, summary)
            AppLog.i(context, "LocalGemma", "summary done id=${news.id} tps=${result.tokensPerSecond}")
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
        inferenceMutex.withLock { releaseLocked() }
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

    fun modelSizeBytes(context: Context, uriString: String?): Long? {
        if (uriString.isNullOrBlank()) return null
        val uri = runCatching { Uri.parse(uriString) }.getOrNull() ?: return null
        return runCatching {
            context.contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { cursor ->
                if (!cursor.moveToFirst()) return@use null
                val index = cursor.getColumnIndex(OpenableColumns.SIZE)
                if (index >= 0 && !cursor.isNull(index)) cursor.getLong(index) else null
            }
        }.getOrNull()
    }

    private suspend fun ensureModelLocked(context: Context, modelUri: String): LlamaHelper {
        helper?.takeIf { loadedUri == modelUri }?.let { return it }
        releaseLocked()

        val uri = Uri.parse(modelUri)
        runCatching {
            context.contentResolver.openFileDescriptor(uri, "r")?.use { pfd ->
                if (pfd.statSize == 0L) error("GGUFファイルが空です")
            } ?: error("GGUFファイルを開けません")
        }.getOrElse { cause ->
            AppLog.e(context, "LocalGemma", "selected GGUF is not readable uri=$modelUri", cause)
            throw IllegalStateException("選択したGGUFを読み取れません。もう一度GGUFを選択してください。", cause)
        }

        val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        val flow = MutableSharedFlow<LlamaHelper.LLMEvent>(
            extraBufferCapacity = 512,
            onBufferOverflow = BufferOverflow.DROP_OLDEST
        )
        val newHelper = LlamaHelper(context.contentResolver, scope, flow)
        val ready = CompletableDeferred<Unit>()
        val collector = scope.launch(start = CoroutineStart.UNDISPATCHED) {
            flow.collect { event ->
                when (event) {
                    is LlamaHelper.LLMEvent.Loaded -> if (!ready.isCompleted) ready.complete(Unit)
                    is LlamaHelper.LLMEvent.Error -> if (!ready.isCompleted) {
                        ready.completeExceptionally(IllegalStateException(event.message))
                    }
                    else -> Unit
                }
            }
        }

        val name = displayName(context, modelUri) ?: modelUri
        val size = modelSizeBytes(context, modelUri)
        AppLog.i(context, "LocalGemma", "model load start name=$name size=${size ?: -1} uri=$modelUri")
        try {
            newHelper.load(path = modelUri, contextLength = CONTEXT_LENGTH) {
                if (!ready.isCompleted) ready.complete(Unit)
            }
            withTimeout(LOAD_TIMEOUT_MS) { ready.await() }
        } catch (t: Throwable) {
            collector.cancel()
            runCatching { newHelper.abort() }
            runCatching { newHelper.release() }
            scope.cancel()
            AppLog.e(context, "LocalGemma", "model load failed name=$name", t)
            throw IllegalStateException(
                "GGUFの読み込みに失敗しました。ログを書き出して確認できます。モデル形式と空きRAMも確認してください。",
                t
            )
        }
        collector.cancel()

        loadedUri = modelUri
        helper = newHelper
        eventFlow = flow
        engineScope = scope
        AppLog.i(context, "LocalGemma", "model load success name=$name context=$CONTEXT_LENGTH backend=CPU/NEON")
        return newHelper
    }

    private suspend fun completeLocked(llama: LlamaHelper, prompt: String): GenerationResult {
        val flow = eventFlow ?: error("AIイベントストリームがありません")
        val scope = engineScope ?: error("AIエンジンがありません")
        val done = CompletableDeferred<GenerationResult>()
        val collector = scope.launch(start = CoroutineStart.UNDISPATCHED) {
            flow.collect { event ->
                when (event) {
                    is LlamaHelper.LLMEvent.Done -> {
                        val seconds = (event.duration.coerceAtLeast(1L) / 1000.0)
                        val tps = (event.tokenCount / seconds).toFloat()
                        if (!done.isCompleted) done.complete(GenerationResult(event.fullText, tps))
                    }
                    is LlamaHelper.LLMEvent.Error -> if (!done.isCompleted) {
                        done.completeExceptionally(IllegalStateException(event.message))
                    }
                    else -> Unit
                }
            }
        }
        try {
            llama.predict(prompt, partialCompletion = true)
            return withTimeout(GENERATE_TIMEOUT_MS) { done.await() }
        } finally {
            collector.cancel()
        }
    }

    private fun releaseLocked() {
        runCatching { helper?.abort() }
        runCatching { helper?.release() }
        runCatching { engineScope?.cancel() }
        helper = null
        eventFlow = null
        engineScope = null
        loadedUri = null
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

    private fun readTranslationCache(context: Context, modelUri: String, news: NewsItem): LocalAiTranslation? {
        val raw = context.getSharedPreferences(CACHE_PREFS, Context.MODE_PRIVATE)
            .getString(cacheKey(modelUri, news, "translation"), null) ?: return null
        return runCatching {
            val json = JSONObject(raw)
            LocalAiTranslation(json.getString("title"), json.getString("body"))
        }.getOrNull()
    }

    private fun writeTranslationCache(context: Context, modelUri: String, news: NewsItem, value: LocalAiTranslation) {
        val json = JSONObject().put("title", value.title).put("body", value.body).toString()
        context.getSharedPreferences(CACHE_PREFS, Context.MODE_PRIVATE)
            .edit().putString(cacheKey(modelUri, news, "translation"), json).apply()
    }

    private fun readSummaryCache(context: Context, modelUri: String, news: NewsItem): LocalAiSummary? {
        val raw = context.getSharedPreferences(CACHE_PREFS, Context.MODE_PRIVATE)
            .getString(cacheKey(modelUri, news, "summary"), null) ?: return null
        return LocalAiSummary(raw)
    }

    private fun writeSummaryCache(context: Context, modelUri: String, news: NewsItem, value: LocalAiSummary) {
        context.getSharedPreferences(CACHE_PREFS, Context.MODE_PRIVATE)
            .edit().putString(cacheKey(modelUri, news, "summary"), value.text).apply()
    }

    private fun cacheKey(modelUri: String, news: NewsItem, mode: String): String {
        val source = "$modelUri|${news.id}|${news.originalTitle}|${news.originalText}|$mode"
        val bytes = MessageDigest.getInstance("SHA-256").digest(source.toByteArray())
        return bytes.joinToString("") { "%02x".format(it) }
    }
}
