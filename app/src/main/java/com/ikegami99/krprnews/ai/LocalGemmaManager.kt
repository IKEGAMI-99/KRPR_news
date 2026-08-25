package com.ikegami99.krprnews.ai

import android.content.Context
import android.database.Cursor
import android.net.Uri
import android.os.SystemClock
import android.provider.OpenableColumns
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import com.ikegami99.krprnews.data.NewsItem
import com.ikegami99.krprnews.data.Region
import com.ikegami99.krprnews.diagnostics.AppLog
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout
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

private data class GenerationResult(val text: String, val tokensPerSecond: Float)

/**
 * ユーザーが選択したGGUFをAndroid端末内で直接実行する。
 *
 * v0.3.2では第三者rnllama AARを廃止し、Gemma 4のwide/MoE graph crash修正を含む
 * 公式llama.cpp Android実装を固定コミットでビルドする。
 * SAFのcontent:// URIは開いたFDを /proc/self/fd/<fd> として公式llama.cppへ渡すため、
 * 数GBのGGUFをアプリ領域へ複製しない。
 */
object LocalGemmaManager {
    private const val CACHE_PREFS = "krpr_local_ai_cache_v3"
    private const val CONTEXT_LENGTH = 4096
    private const val LOAD_TIMEOUT_MS = 300_000L
    private const val GENERATE_TIMEOUT_MS = 300_000L
    private const val MAX_PREDICT_TOKENS = 1024

    private val inferenceMutex = Mutex()
    private var loadedUri: String? = null
    private var engine: InferenceEngine? = null

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

    private suspend fun ensureModelLocked(context: Context, modelUri: String): InferenceEngine {
        engine?.takeIf {
            loadedUri == modelUri && it.state.value is InferenceEngine.State.ModelReady
        }?.let { return it }

        releaseLocked()

        val uri = Uri.parse(modelUri)
        runCatching {
            context.contentResolver.openFileDescriptor(uri, "r")?.use { pfd ->
                if (pfd.statSize == 0L) error("GGUFファイルが空です")
            } ?: error("GGUFファイルを開けません")
        }.getOrElse { cause ->
            AppLog.e(context, "LocalGemma", "selected GGUF is not readable", cause)
            throw IllegalStateException("選択したGGUFを読み取れません。もう一度GGUFを選択してください。", cause)
        }

        val llama = AiChat.getInferenceEngine(context)
        var state = withTimeout(60_000L) {
            llama.state.first {
                it is InferenceEngine.State.Initialized ||
                    it is InferenceEngine.State.ModelReady ||
                    it is InferenceEngine.State.Error
            }
        }

        if (state is InferenceEngine.State.ModelReady || state is InferenceEngine.State.Error) {
            runCatching { llama.cleanUp() }
                .onFailure { AppLog.e(context, "LocalGemma", "engine reset failed", it) }
            state = llama.state.value
        }
        if (state !is InferenceEngine.State.Initialized) {
            val cause = (state as? InferenceEngine.State.Error)?.exception
            throw IllegalStateException("llama.cppエンジンを初期化できませんでした。", cause)
        }

        val name = displayName(context, modelUri) ?: "selected.gguf"
        val size = modelSizeBytes(context, modelUri)
        AppLog.i(
            context,
            "LocalGemma",
            "model load start name=$name size=${size ?: -1} backend=official-llama-cpu context=$CONTEXT_LENGTH"
        )

        try {
            context.contentResolver.openFileDescriptor(uri, "r")?.use { pfd ->
                if (pfd.fd < 0) error("GGUFのFile Descriptorを取得できません")
                val procPath = "/proc/self/fd/${pfd.fd}"
                AppLog.i(context, "LocalGemma", "opening model through SAF fd=${pfd.fd}")
                withTimeout(LOAD_TIMEOUT_MS) {
                    llama.loadModel(procPath)
                }
            } ?: error("GGUFファイルを開けません")
        } catch (t: Throwable) {
            runCatching {
                if (llama.state.value is InferenceEngine.State.Error ||
                    llama.state.value is InferenceEngine.State.ModelReady
                ) {
                    llama.cleanUp()
                }
            }
            AppLog.e(context, "LocalGemma", "model load failed name=$name state=${llama.state.value.javaClass.simpleName}", t)
            throw IllegalStateException(
                "GGUFの読み込みに失敗しました。設定から診断ログを書き出してください。",
                t
            )
        }

        if (llama.state.value !is InferenceEngine.State.ModelReady) {
            throw IllegalStateException("GGUFを読み込みましたが推論準備状態になりませんでした。")
        }

        loadedUri = modelUri
        engine = llama
        AppLog.i(
            context,
            "LocalGemma",
            "model load success name=$name context=$CONTEXT_LENGTH backend=official llama.cpp CPU variants"
        )
        return llama
    }

    private suspend fun completeLocked(llama: InferenceEngine, prompt: String): GenerationResult {
        check(llama.state.value is InferenceEngine.State.ModelReady) { "AIモデルが推論可能な状態ではありません。" }
        val started = SystemClock.elapsedRealtime()
        val output = StringBuilder()
        var emittedPieces = 0

        withTimeout(GENERATE_TIMEOUT_MS) {
            llama.sendUserPrompt(prompt, predictLength = MAX_PREDICT_TOKENS).collect { piece ->
                output.append(piece)
                emittedPieces++
            }
        }

        val seconds = ((SystemClock.elapsedRealtime() - started).coerceAtLeast(1L) / 1000.0)
        val tps = (emittedPieces / seconds).toFloat()
        return GenerationResult(output.toString(), tps)
    }

    private fun releaseLocked() {
        val current = engine
        if (current != null) {
            runCatching {
                when (current.state.value) {
                    is InferenceEngine.State.ModelReady,
                    is InferenceEngine.State.Error -> current.cleanUp()
                    else -> Unit
                }
            }
        }
        engine = null
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
