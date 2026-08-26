package com.ikegami99.krprnews.ai

import android.content.Context
import android.database.Cursor
import android.net.Uri
import android.os.Debug
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
import java.io.File
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
 * 重いllama.cpp処理は :ai サービスへ隔離する。
 * v0.3.11ではGemma 4のThinkingを使わず、system/userを分離して
 * 翻訳・要約の最終結果だけをタグで受け取る。
 */
object LocalGemmaManager {
    // v5 invalidates v0.3.10 caches which may contain prompt placeholders.
    private const val CACHE_PREFS = "krpr_local_ai_cache_v5"
    private const val CONTEXT_LENGTH = 2048
    private const val BATCH_SIZE = 64
    private const val THREADS = 4
    private const val LOAD_TIMEOUT_MS = 300_000L
    private const val SYSTEM_PROMPT_TIMEOUT_MS = 60_000L
    private const val GENERATE_TIMEOUT_MS = 180_000L
    private const val TRANSLATION_MAX_PREDICT_TOKENS = 640
    private const val SUMMARY_MAX_PREDICT_TOKENS = 192

    private val inferenceMutex = Mutex()
    private var loadedUri: String? = null
    private var engine: InferenceEngine? = null

    private val translationSystemPrompt = """
        あなたはゲーム公式ニュース専用の高精度翻訳エンジンです。
        Thinkingや内部推論を回答に出さず、分析、説明、前置き、Markdownも出力しません。
        入力されたタイトルと本文を、省略せず自然な日本語へ翻訳してください。
        固有名詞、キャラクター名、衣装名、アイテム名、日付、時刻、数値、価格、絵文字、イベント条件は正確に保持してください。
        入力にない内容を追加せず、説明用の仮文字列や例示文を回答として使わないでください。
        最終回答ではJP_TITLEタグの内側に実際のタイトル翻訳、JP_BODYタグの内側に実際の本文翻訳を入れてください。
        JP_TITLEとJP_BODYの2組のタグ以外は出力しないでください。
    """.trimIndent()

    private val summarySystemPrompt = """
        あなたはゲーム公式ニュース専用の日本語要約エンジンです。
        Thinkingや内部推論を回答に出さず、分析、説明、前置き、Markdownも出力しません。
        入力されたニュースを自然な日本語2〜5文で簡潔に要約してください。
        日付、時刻、イベント期間、報酬、衣装名、アイテム名、価格、参加条件など重要情報は残し、入力にない情報を追加しないでください。
        説明用の仮文字列や例示文を回答として使わないでください。
        最終回答ではJP_SUMMARYタグの内側に実際の日本語要約を入れてください。
        JP_SUMMARYタグ以外は出力しないでください。
    """.trimIndent()

    private fun isAiProcess(): Boolean = runCatching {
        File("/proc/self/cmdline").inputStream().bufferedReader().use { reader ->
            reader.readText().trim('\u0000', ' ', '\n', '\r', '\t').endsWith(":ai")
        }
    }.getOrDefault(false)

    suspend fun warmUp(context: Context, modelUri: String) {
        if (!isAiProcess()) {
            LocalAiProcessClient.warmUp(context.applicationContext, modelUri)
            return
        }
        inferenceMutex.withLock { ensureModelLocked(context.applicationContext, modelUri) }
    }

    suspend fun translate(context: Context, modelUri: String, news: NewsItem): LocalAiTranslation {
        if (news.region == Region.JAPAN) return LocalAiTranslation(news.originalTitle, news.originalText)
        if (!isAiProcess()) return LocalAiProcessClient.translate(context.applicationContext, modelUri, news)

        return inferenceMutex.withLock {
            readTranslationCache(context, modelUri, news)?.let { return@withLock it }
            val llama = ensureModelLocked(context.applicationContext, modelUri)
            val sourceLanguage = when (news.region) {
                Region.CHINA -> "中国語"
                Region.GLOBAL -> "英語"
                Region.KOREA -> "韓国語"
                Region.JAPAN -> "日本語"
            }
            val userPrompt = buildString {
                appendLine("SOURCE_LANGUAGE=$sourceLanguage")
                appendLine("<SOURCE_TITLE>")
                appendLine(news.originalTitle)
                appendLine("</SOURCE_TITLE>")
                appendLine("<SOURCE_BODY>")
                appendLine(news.originalText)
                appendLine("</SOURCE_BODY>")
            }

            AppLog.i(context, "LocalGemma", "translation start region=${news.region} id=${news.id}")
            val result = completeLocked(
                context = context,
                llama = llama,
                systemPrompt = translationSystemPrompt,
                userPrompt = userPrompt,
                maxPredictTokens = TRANSLATION_MAX_PREDICT_TOKENS,
                mode = "translation"
            )
            val translation = parseTranslation(result.text).copy(tokensPerSecond = result.tokensPerSecond)
            writeTranslationCache(context, modelUri, news, translation)
            AppLog.i(context, "LocalGemma", "translation done id=${news.id} tps=${result.tokensPerSecond}")
            translation
        }
    }

    suspend fun summarize(context: Context, modelUri: String, news: NewsItem): LocalAiSummary {
        if (!isAiProcess()) return LocalAiProcessClient.summarize(context.applicationContext, modelUri, news)

        return inferenceMutex.withLock {
            readSummaryCache(context, modelUri, news)?.let { return@withLock it }
            val llama = ensureModelLocked(context.applicationContext, modelUri)
            val userPrompt = buildString {
                appendLine("<SOURCE_TITLE>")
                appendLine(news.originalTitle)
                appendLine("</SOURCE_TITLE>")
                appendLine("<SOURCE_BODY>")
                appendLine(news.originalText)
                appendLine("</SOURCE_BODY>")
            }

            AppLog.i(context, "LocalGemma", "summary start region=${news.region} id=${news.id}")
            val result = completeLocked(
                context = context,
                llama = llama,
                systemPrompt = summarySystemPrompt,
                userPrompt = userPrompt,
                maxPredictTokens = SUMMARY_MAX_PREDICT_TOKENS,
                mode = "summary"
            )
            val summary = LocalAiSummary(parseSummary(result.text), result.tokensPerSecond)
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
        if (!isAiProcess()) return
        inferenceMutex.withLock { releaseLocked() }
    }

    suspend fun clearPreparedModels(context: Context) {
        if (!isAiProcess()) {
            LocalAiProcessClient.release(context.applicationContext)
            PreparedModelStore.clear(context.applicationContext)
            return
        }
        inferenceMutex.withLock {
            releaseLocked()
            PreparedModelStore.clear(context.applicationContext)
        }
    }

    fun preparedModelBytes(context: Context): Long = PreparedModelStore.preparedBytes(context.applicationContext)

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
        engine?.takeIf { loadedUri == modelUri && it.state.value is InferenceEngine.State.ModelReady }?.let { return it }
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

        val name = displayName(context, modelUri) ?: "selected.gguf"
        val sourceSize = modelSizeBytes(context, modelUri)
        val preparedFile = runCatching { PreparedModelStore.prepare(context, modelUri) }.getOrElse { cause ->
            AppLog.e(context, "LocalGemma", "model prepare failed name=$name", cause)
            throw IllegalStateException("GGUFの準備に失敗しました。空き容量を確認して、もう一度モデル読み込みテストを実行してください。", cause)
        }

        val llama = AiChat.getInferenceEngine(context)
        var state = withTimeout(60_000L) {
            llama.state.first {
                it is InferenceEngine.State.Initialized || it is InferenceEngine.State.ModelReady || it is InferenceEngine.State.Error
            }
        }
        if (state is InferenceEngine.State.ModelReady || state is InferenceEngine.State.Error) {
            runCatching { llama.cleanUp() }.onFailure { AppLog.e(context, "LocalGemma", "engine reset failed", it) }
            state = llama.state.value
        }
        if (state !is InferenceEngine.State.Initialized) {
            val cause = (state as? InferenceEngine.State.Error)?.exception
            throw IllegalStateException("llama.cppエンジンを初期化できませんでした。", cause)
        }

        AppLog.i(context, "LocalGemma", "model load start name=$name sourceSize=${sourceSize ?: -1} preparedSize=${preparedFile.length()} backend=official-llama-generic-cpu context=$CONTEXT_LENGTH batch=$BATCH_SIZE threads=$THREADS flashAttn=off q4Repack=on pssMb=${Debug.getPss() / 1024}")
        try {
            AppLog.i(context, "LocalGemma", "opening prepared model path=${preparedFile.absolutePath}")
            withTimeout(LOAD_TIMEOUT_MS) { llama.loadModel(preparedFile.absolutePath) }
        } catch (t: Throwable) {
            runCatching {
                if (llama.state.value is InferenceEngine.State.Error || llama.state.value is InferenceEngine.State.ModelReady) llama.cleanUp()
            }
            AppLog.e(context, "LocalGemma", "model load failed name=$name state=${llama.state.value.javaClass.simpleName}", t)
            throw IllegalStateException("GGUFの読み込みに失敗しました。設定から診断ログを書き出してください。", t)
        }
        if (llama.state.value !is InferenceEngine.State.ModelReady) {
            throw IllegalStateException("GGUFを読み込みましたが推論準備状態になりませんでした。")
        }

        loadedUri = modelUri
        engine = llama
        AppLog.i(context, "LocalGemma", "model load success name=$name context=$CONTEXT_LENGTH backend=generic CPU/NEON batch=$BATCH_SIZE threads=$THREADS flashAttn=off q4Repack=on sampling=gemma4 pssMb=${Debug.getPss() / 1024}")
        return llama
    }

    private suspend fun completeLocked(
        context: Context,
        llama: InferenceEngine,
        systemPrompt: String,
        userPrompt: String,
        maxPredictTokens: Int,
        mode: String
    ): GenerationResult {
        check(llama.state.value is InferenceEngine.State.ModelReady) { "AIモデルが推論可能な状態ではありません。" }

        // Gemma 4 enables Thinking only when the system prompt begins with <|think|>.
        // Our translation/summary system prompts intentionally omit that token.
        withTimeout(SYSTEM_PROMPT_TIMEOUT_MS) {
            llama.setSystemPrompt(systemPrompt)
        }

        val started = SystemClock.elapsedRealtime()
        val output = StringBuilder()
        var emittedPieces = 0
        AppLog.i(context, "LocalGemma", "generation dispatch mode=$mode promptChars=${userPrompt.length} maxPredict=$maxPredictTokens context=$CONTEXT_LENGTH batch=$BATCH_SIZE threads=$THREADS thinking=off flashAttn=off q4Repack=on pssMb=${Debug.getPss() / 1024}")

        withTimeout(GENERATE_TIMEOUT_MS) {
            llama.sendUserPrompt(userPrompt, predictLength = maxPredictTokens).collect { piece ->
                output.append(piece)
                emittedPieces++
                if (emittedPieces == 1 || emittedPieces % 16 == 0) {
                    val elapsedMs = SystemClock.elapsedRealtime() - started
                    AppLog.i(context, "LocalGemma", "generation progress mode=$mode pieces=$emittedPieces elapsedMs=$elapsedMs pssMb=${Debug.getPss() / 1024}")
                }
            }
        }
        val seconds = (SystemClock.elapsedRealtime() - started).coerceAtLeast(1L) / 1000.0
        val tps = (emittedPieces / seconds).toFloat()
        AppLog.i(context, "LocalGemma", "generation complete mode=$mode pieces=$emittedPieces elapsedSec=$seconds pssMb=${Debug.getPss() / 1024}")
        return GenerationResult(output.toString(), tps)
    }

    private fun releaseLocked() {
        engine?.let { current ->
            runCatching {
                when (current.state.value) {
                    is InferenceEngine.State.ModelReady, is InferenceEngine.State.Error -> current.cleanUp()
                    else -> Unit
                }
            }
        }
        engine = null
        loadedUri = null
    }

    private fun extractTag(raw: String, tag: String): String? {
        val open = "<$tag>"
        val close = "</$tag>"
        val start = raw.lastIndexOf(open)
        if (start < 0) return null
        val contentStart = start + open.length
        val end = raw.indexOf(close, contentStart)
        if (end < 0) return null
        return raw.substring(contentStart, end).trim().takeIf { it.isNotBlank() }
    }

    private fun extractFinalJson(raw: String): JSONObject? {
        val text = raw.trim()
        val marker = "<FINAL_JSON>"
        val markerEnd = "</FINAL_JSON>"
        val start = text.lastIndexOf(marker)
        val candidate = if (start >= 0) {
            val contentStart = start + marker.length
            val end = text.indexOf(markerEnd, contentStart).takeIf { it >= 0 } ?: text.length
            text.substring(contentStart, end)
        } else {
            val firstBrace = text.indexOf('{')
            val lastBrace = text.lastIndexOf('}')
            if (firstBrace >= 0 && lastBrace > firstBrace) text.substring(firstBrace, lastBrace + 1) else ""
        }
        if (candidate.isBlank()) return null
        val cleaned = candidate.trim().removePrefix("```json").removePrefix("```").removeSuffix("```").trim()
        return runCatching { JSONObject(cleaned) }.getOrNull()
    }

    private fun isPlaceholder(value: String): Boolean {
        val normalized = value.trim().lowercase()
        return normalized in setOf(
            "日本語タイトル",
            "日本語本文",
            "日本語要約",
            "japanese title",
            "japanese body",
            "japanese summary",
            "title",
            "body",
            "summary"
        )
    }

    private fun parseTranslation(raw: String): LocalAiTranslation {
        var title = extractTag(raw, "JP_TITLE")
        var body = extractTag(raw, "JP_BODY")

        // Keep a compatibility fallback for models that choose JSON despite the tag instruction.
        if (title == null || body == null) {
            extractFinalJson(raw)?.let { json ->
                if (title == null) title = json.optString("title").trim().takeIf { it.isNotBlank() }
                if (body == null) body = json.optString("body").trim().takeIf { it.isNotBlank() }
            }
        }

        val finalTitle = title?.trim().orEmpty()
        val finalBody = body?.trim().orEmpty()
        if (finalTitle.isBlank() || finalBody.isBlank()) {
            throw IllegalStateException("翻訳の最終結果を取得できませんでした。もう一度実行してください。")
        }
        if (isPlaceholder(finalTitle) || isPlaceholder(finalBody)) {
            throw IllegalStateException("翻訳モデルが仮文字列を返しました。もう一度実行してください。")
        }
        return LocalAiTranslation(finalTitle, finalBody)
    }

    private fun parseSummary(raw: String): String {
        var summary = extractTag(raw, "JP_SUMMARY")
        if (summary == null) {
            summary = extractFinalJson(raw)?.optString("summary")?.trim()?.takeIf { it.isNotBlank() }
        }
        val finalSummary = summary?.trim().orEmpty()
        if (finalSummary.isBlank()) {
            throw IllegalStateException("要約の最終結果を取得できませんでした。もう一度実行してください。")
        }
        if (isPlaceholder(finalSummary)) {
            throw IllegalStateException("要約モデルが仮文字列を返しました。もう一度実行してください。")
        }
        return finalSummary
    }

    private fun readTranslationCache(context: Context, modelUri: String, news: NewsItem): LocalAiTranslation? {
        val raw = context.getSharedPreferences(CACHE_PREFS, Context.MODE_PRIVATE)
            .getString(cacheKey(modelUri, news, "translation"), null) ?: return null
        return runCatching {
            val json = JSONObject(raw)
            val title = json.getString("title").trim()
            val body = json.getString("body").trim()
            if (title.isBlank() || body.isBlank() || isPlaceholder(title) || isPlaceholder(body)) return@runCatching null
            LocalAiTranslation(title, body)
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
        if (raw.isBlank() || isPlaceholder(raw)) return null
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
