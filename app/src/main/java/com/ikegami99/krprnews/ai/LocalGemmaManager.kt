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
 *
 * v0.3.7以降、重いllama.cpp処理は :ai サービスへ隔離する。
 * v0.3.10ではJinjaクラッシュの原因が解消したため、診断用の超低速設定から
 * context 2048 / batch 64 / 4 threadsへ戻し、最終回答だけをUIへ返す。
 *
 * SAFのcontent:// URIは初回だけアプリ専用モデル領域へコピーし、
 * llama.cppには通常ファイルパスを渡す。
 */
object LocalGemmaManager {
    // v4 intentionally invalidates v0.3.9 caches that may contain raw analysis text.
    private const val CACHE_PREFS = "krpr_local_ai_cache_v4"
    private const val CONTEXT_LENGTH = 2048
    private const val BATCH_SIZE = 64
    private const val THREADS = 4
    private const val LOAD_TIMEOUT_MS = 300_000L
    private const val GENERATE_TIMEOUT_MS = 180_000L
    private const val TRANSLATION_MAX_PREDICT_TOKENS = 320
    private const val SUMMARY_MAX_PREDICT_TOKENS = 128

    private val inferenceMutex = Mutex()
    private var loadedUri: String? = null
    private var engine: InferenceEngine? = null

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
        inferenceMutex.withLock {
            ensureModelLocked(context.applicationContext, modelUri)
        }
    }

    suspend fun translate(context: Context, modelUri: String, news: NewsItem): LocalAiTranslation {
        if (news.region == Region.JAPAN) return LocalAiTranslation(news.originalTitle, news.originalText)
        if (!isAiProcess()) {
            return LocalAiProcessClient.translate(context.applicationContext, modelUri, news)
        }

        return inferenceMutex.withLock {
            readTranslationCache(context, modelUri, news)?.let { return@withLock it }
            val llama = ensureModelLocked(context.applicationContext, modelUri)
            val sourceLanguage = when (news.region) {
                Region.CHINA -> "中国語"
                Region.GLOBAL -> "英語"
                Region.KOREA -> "韓国語"
                Region.JAPAN -> "日本語"
            }
            AppLog.i(context, "LocalGemma", "translation start region=${news.region} id=${news.id}")
            val result = completeLocked(
                context = context,
                llama = llama,
                prompt = """
                これは翻訳だけを行うタスクです。以下の$sourceLanguageの公式ゲームニュースを、情報を省略せず自然な日本語へ翻訳してください。
                内部の思考、分析、手順、説明、前置き、原文の解説は回答に書かないでください。
                固有名詞、衣装名、アイテム名、日付、時刻、数値、絵文字、価格、イベント条件は正確に保持してください。
                Markdownは使わず、最後の回答は必ず次の形式だけにしてください。
                <FINAL_JSON>{"title":"日本語タイトル","body":"日本語本文"}</FINAL_JSON>

                原文タイトル:
                ${news.originalTitle}

                原文本文:
                ${news.originalText}
                """.trimIndent(),
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
        if (!isAiProcess()) {
            return LocalAiProcessClient.summarize(context.applicationContext, modelUri, news)
        }

        return inferenceMutex.withLock {
            readSummaryCache(context, modelUri, news)?.let { return@withLock it }
            val llama = ensureModelLocked(context.applicationContext, modelUri)
            AppLog.i(context, "LocalGemma", "summary start region=${news.region} id=${news.id}")
            val result = completeLocked(
                context = context,
                llama = llama,
                prompt = """
                これは日本語要約だけを行うタスクです。以下の公式ゲームニュースを自然な日本語2〜5文で簡潔に要約してください。
                内部の思考、分析、手順、説明、前置きは回答に書かないでください。
                日付、時刻、イベント期間、報酬、衣装名、アイテム名、価格、参加条件など重要情報は残し、原文にない情報は追加しないでください。
                Markdownや見出しは使わず、最後の回答は必ず次の形式だけにしてください。
                <FINAL_JSON>{"summary":"日本語要約"}</FINAL_JSON>

                原文タイトル:
                ${news.originalTitle}

                原文本文:
                ${news.originalText}
                """.trimIndent(),
                maxPredictTokens = SUMMARY_MAX_PREDICT_TOKENS,
                mode = "summary"
            )
            val summary = LocalAiSummary(
                text = parseSummary(result.text),
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

        val name = displayName(context, modelUri) ?: "selected.gguf"
        val sourceSize = modelSizeBytes(context, modelUri)
        val preparedFile = runCatching {
            PreparedModelStore.prepare(context, modelUri)
        }.getOrElse { cause ->
            AppLog.e(context, "LocalGemma", "model prepare failed name=$name", cause)
            throw IllegalStateException(
                "GGUFの準備に失敗しました。空き容量を確認して、もう一度モデル読み込みテストを実行してください。",
                cause
            )
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

        AppLog.i(
            context,
            "LocalGemma",
            "model load start name=$name sourceSize=${sourceSize ?: -1} preparedSize=${preparedFile.length()} backend=official-llama-generic-cpu context=$CONTEXT_LENGTH batch=$BATCH_SIZE threads=$THREADS flashAttn=off q4Repack=on pssMb=${Debug.getPss() / 1024}"
        )

        try {
            AppLog.i(context, "LocalGemma", "opening prepared model path=${preparedFile.absolutePath}")
            withTimeout(LOAD_TIMEOUT_MS) {
                llama.loadModel(preparedFile.absolutePath)
            }
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
            "model load success name=$name context=$CONTEXT_LENGTH backend=generic CPU/NEON batch=$BATCH_SIZE threads=$THREADS flashAttn=off q4Repack=on pssMb=${Debug.getPss() / 1024}"
        )
        return llama
    }

    private suspend fun completeLocked(
        context: Context,
        llama: InferenceEngine,
        prompt: String,
        maxPredictTokens: Int,
        mode: String
    ): GenerationResult {
        check(llama.state.value is InferenceEngine.State.ModelReady) { "AIモデルが推論可能な状態ではありません。" }
        val started = SystemClock.elapsedRealtime()
        val output = StringBuilder()
        var emittedPieces = 0

        AppLog.i(
            context,
            "LocalGemma",
            "generation dispatch mode=$mode promptChars=${prompt.length} maxPredict=$maxPredictTokens context=$CONTEXT_LENGTH batch=$BATCH_SIZE threads=$THREADS flashAttn=off q4Repack=on pssMb=${Debug.getPss() / 1024}"
        )

        withTimeout(GENERATE_TIMEOUT_MS) {
            llama.sendUserPrompt(prompt, predictLength = maxPredictTokens).collect { piece ->
                output.append(piece)
                emittedPieces++
                if (emittedPieces == 1 || emittedPieces % 16 == 0) {
                    val elapsedMs = SystemClock.elapsedRealtime() - started
                    AppLog.i(
                        context,
                        "LocalGemma",
                        "generation progress mode=$mode pieces=$emittedPieces elapsedMs=$elapsedMs pssMb=${Debug.getPss() / 1024}"
                    )
                }
            }
        }

        val seconds = ((SystemClock.elapsedRealtime() - started).coerceAtLeast(1L) / 1000.0)
        val tps = (emittedPieces / seconds).toFloat()
        AppLog.i(
            context,
            "LocalGemma",
            "generation complete mode=$mode pieces=$emittedPieces elapsedSec=$seconds pssMb=${Debug.getPss() / 1024}"
        )
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
        val cleaned = candidate.trim()
            .removePrefix("```json")
            .removePrefix("```")
            .removeSuffix("```")
            .trim()
        return runCatching { JSONObject(cleaned) }.getOrNull()
    }

    private fun parseTranslation(raw: String): LocalAiTranslation {
        val json = extractFinalJson(raw)
            ?: throw IllegalStateException("翻訳の最終結果を取得できませんでした。もう一度実行してください。")
        val title = json.optString("title").trim()
        val body = json.optString("body").trim()
        if (title.isBlank() || body.isBlank()) {
            throw IllegalStateException("翻訳結果の形式が不完全でした。もう一度実行してください。")
        }
        return LocalAiTranslation(title = title, body = body)
    }

    private fun parseSummary(raw: String): String {
        val json = extractFinalJson(raw)
            ?: throw IllegalStateException("要約の最終結果を取得できませんでした。もう一度実行してください。")
        return json.optString("summary").trim().ifBlank {
            throw IllegalStateException("要約結果の形式が不完全でした。もう一度実行してください。")
        }
    }

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
