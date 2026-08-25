package com.ikegami99.krprnews.ai

import android.app.Service
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Message
import android.os.Messenger
import android.os.Process
import com.ikegami99.krprnews.data.NewsItem
import com.ikegami99.krprnews.data.Region
import com.ikegami99.krprnews.diagnostics.AppLog
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * Runs llama.cpp outside the UI process.
 *
 * Native inference can be terminated by Android or abort inside ggml/llama.cpp.
 * Keeping it in :ai prevents that failure from taking Kirapara News itself down.
 */
class LocalAiService : Service() {
    companion object {
        const val CMD_WARM_UP = 1
        const val CMD_TRANSLATE = 2
        const val CMD_SUMMARIZE = 3
        const val CMD_RELEASE = 4
        const val MSG_RESULT = 100

        const val KEY_REQUEST_ID = "request_id"
        const val KEY_MODEL_URI = "model_uri"
        const val KEY_OK = "ok"
        const val KEY_ERROR = "error"
        const val KEY_TITLE = "title"
        const val KEY_BODY = "body"
        const val KEY_TEXT = "text"
        const val KEY_TPS = "tps"

        const val KEY_NEWS_ID = "news_id"
        const val KEY_REGION = "region"
        const val KEY_PLATFORM = "platform"
        const val KEY_PUBLISHED_LABEL = "published_label"
        const val KEY_ORIGINAL_TITLE = "original_title"
        const val KEY_ORIGINAL_TEXT = "original_text"
        const val KEY_SOURCE_URL = "source_url"
        const val KEY_CATEGORY = "category"
        const val KEY_IMAGE_URL = "image_url"
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val incoming = Messenger(
        Handler(Looper.getMainLooper()) { message ->
            val replyTo = message.replyTo
            val request = Bundle(message.data)
            val requestId = request.getLong(KEY_REQUEST_ID, -1L)
            val command = message.what

            if (replyTo == null || requestId < 0L) return@Handler true

            scope.launch {
                AppLog.i(
                    applicationContext,
                    "LocalAiService",
                    "request start cmd=$command requestId=$requestId pid=${Process.myPid()}"
                )

                val result = Bundle().apply {
                    putLong(KEY_REQUEST_ID, requestId)
                }

                try {
                    when (command) {
                        CMD_WARM_UP -> {
                            val modelUri = request.requireString(KEY_MODEL_URI)
                            LocalGemmaManager.warmUp(applicationContext, modelUri)
                        }

                        CMD_TRANSLATE -> {
                            val modelUri = request.requireString(KEY_MODEL_URI)
                            val translated = LocalGemmaManager.translate(
                                applicationContext,
                                modelUri,
                                request.toNewsItem()
                            )
                            result.putString(KEY_TITLE, translated.title)
                            result.putString(KEY_BODY, translated.body)
                            result.putFloat(KEY_TPS, translated.tokensPerSecond)
                        }

                        CMD_SUMMARIZE -> {
                            val modelUri = request.requireString(KEY_MODEL_URI)
                            val summary = LocalGemmaManager.summarize(
                                applicationContext,
                                modelUri,
                                request.toNewsItem()
                            )
                            result.putString(KEY_TEXT, summary.text)
                            result.putFloat(KEY_TPS, summary.tokensPerSecond)
                        }

                        CMD_RELEASE -> LocalGemmaManager.release()
                        else -> error("Unknown AI command: $command")
                    }
                    result.putBoolean(KEY_OK, true)
                    AppLog.i(
                        applicationContext,
                        "LocalAiService",
                        "request done cmd=$command requestId=$requestId pid=${Process.myPid()}"
                    )
                } catch (t: Throwable) {
                    result.putBoolean(KEY_OK, false)
                    result.putString(KEY_ERROR, t.message ?: t.javaClass.simpleName)
                    AppLog.e(
                        applicationContext,
                        "LocalAiService",
                        "request failed cmd=$command requestId=$requestId pid=${Process.myPid()}",
                        t
                    )
                }

                runCatching {
                    replyTo.send(Message.obtain(null, MSG_RESULT).apply { data = result })
                }
            }
            true
        }
    )

    override fun onBind(intent: Intent?): IBinder = incoming.binder

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    private fun Bundle.requireString(key: String): String =
        getString(key)?.takeIf { it.isNotBlank() } ?: error("Missing $key")

    private fun Bundle.toNewsItem(): NewsItem = NewsItem(
        id = requireString(KEY_NEWS_ID),
        region = Region.valueOf(requireString(KEY_REGION)),
        platform = getString(KEY_PLATFORM).orEmpty(),
        publishedLabel = getString(KEY_PUBLISHED_LABEL).orEmpty(),
        originalTitle = getString(KEY_ORIGINAL_TITLE).orEmpty(),
        originalText = getString(KEY_ORIGINAL_TEXT).orEmpty(),
        sourceUrl = getString(KEY_SOURCE_URL).orEmpty(),
        category = getString(KEY_CATEGORY).orEmpty(),
        imageUrl = getString(KEY_IMAGE_URL)
    )
}
