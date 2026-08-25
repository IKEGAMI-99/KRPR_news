package com.ikegami99.krprnews.ai

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.Bundle
import android.os.DeadObjectException
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Message
import android.os.Messenger
import com.ikegami99.krprnews.data.NewsItem
import com.ikegami99.krprnews.diagnostics.AppLog
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.withTimeout
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong

/**
 * Main-process facade for [LocalAiService].
 *
 * The Messenger boundary is deliberate: if llama.cpp aborts or Android kills the
 * heavy AI process, the UI process survives and receives a normal error instead.
 */
object LocalAiProcessClient {
    private const val CONNECT_TIMEOUT_MS = 15_000L
    private const val REQUEST_TIMEOUT_MS = 300_000L

    private val lock = Any()
    private val nextRequestId = AtomicLong(1L)
    private val pending = ConcurrentHashMap<Long, CompletableDeferred<Bundle>>()

    @Volatile
    private var service: Messenger? = null
    private var connecting: CompletableDeferred<Messenger>? = null
    private var bound = false
    private var applicationContext: Context? = null

    private val replies = Messenger(
        Handler(Looper.getMainLooper()) { message ->
            if (message.what != LocalAiService.MSG_RESULT) return@Handler false
            val data = message.data
            val requestId = data.getLong(LocalAiService.KEY_REQUEST_ID, -1L)
            pending.remove(requestId)?.complete(data)
            true
        }
    )

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
            if (binder == null) {
                failConnection("AIサービスへ接続できませんでした。")
                return
            }

            val messenger = Messenger(binder)
            synchronized(lock) {
                service = messenger
                connecting?.complete(messenger)
                connecting = null
            }

            runCatching {
                binder.linkToDeath(
                    { handleProcessDeath("AI推論プロセスが異常終了しました。もう一度実行してください。") },
                    0
                )
            }

            applicationContext?.let {
                AppLog.i(it, "LocalAiClient", "AI process connected")
            }
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            handleProcessDeath("AI推論プロセスとの接続が切れました。もう一度実行してください。")
        }

        override fun onBindingDied(name: ComponentName?) {
            handleProcessDeath("AI推論プロセスが終了しました。もう一度実行してください。")
        }

        override fun onNullBinding(name: ComponentName?) {
            failConnection("AIサービスを開始できませんでした。")
        }
    }

    suspend fun warmUp(context: Context, modelUri: String) {
        request(
            context,
            LocalAiService.CMD_WARM_UP,
            Bundle().apply { putString(LocalAiService.KEY_MODEL_URI, modelUri) }
        )
    }

    suspend fun translate(context: Context, modelUri: String, news: NewsItem): LocalAiTranslation {
        val result = request(
            context,
            LocalAiService.CMD_TRANSLATE,
            newsBundle(modelUri, news)
        )
        return LocalAiTranslation(
            title = result.getString(LocalAiService.KEY_TITLE).orEmpty(),
            body = result.getString(LocalAiService.KEY_BODY).orEmpty(),
            tokensPerSecond = result.getFloat(LocalAiService.KEY_TPS, 0f)
        )
    }

    suspend fun summarize(context: Context, modelUri: String, news: NewsItem): LocalAiSummary {
        val result = request(
            context,
            LocalAiService.CMD_SUMMARIZE,
            newsBundle(modelUri, news)
        )
        return LocalAiSummary(
            text = result.getString(LocalAiService.KEY_TEXT).orEmpty(),
            tokensPerSecond = result.getFloat(LocalAiService.KEY_TPS, 0f)
        )
    }

    suspend fun release(context: Context) {
        runCatching {
            request(context, LocalAiService.CMD_RELEASE, Bundle())
        }
    }

    private suspend fun request(context: Context, command: Int, payload: Bundle): Bundle {
        val target = ensureConnected(context.applicationContext)
        val requestId = nextRequestId.getAndIncrement()
        val deferred = CompletableDeferred<Bundle>()
        pending[requestId] = deferred
        payload.putLong(LocalAiService.KEY_REQUEST_ID, requestId)

        try {
            target.send(
                Message.obtain(null, command).apply {
                    data = payload
                    replyTo = replies
                }
            )
        } catch (dead: DeadObjectException) {
            pending.remove(requestId)
            handleProcessDeath("AI推論プロセスが異常終了しました。もう一度実行してください。")
            throw IllegalStateException("AI推論プロセスが異常終了しました。", dead)
        } catch (t: Throwable) {
            pending.remove(requestId)
            throw t
        }

        val result = try {
            withTimeout(REQUEST_TIMEOUT_MS) { deferred.await() }
        } finally {
            pending.remove(requestId)
        }

        if (!result.getBoolean(LocalAiService.KEY_OK, false)) {
            throw IllegalStateException(
                result.getString(LocalAiService.KEY_ERROR)
                    ?: "AI推論に失敗しました。"
            )
        }
        return result
    }

    private suspend fun ensureConnected(context: Context): Messenger {
        service?.let { return it }

        val deferred = synchronized(lock) {
            service?.let { return it }
            applicationContext = context
            connecting ?: CompletableDeferred<Messenger>().also { waiter ->
                connecting = waiter
                if (!bound) {
                    val ok = context.bindService(
                        Intent(context, LocalAiService::class.java),
                        connection,
                        Context.BIND_AUTO_CREATE
                    )
                    bound = ok
                    if (!ok) {
                        connecting = null
                        waiter.completeExceptionally(
                            IllegalStateException("AIサービスを開始できませんでした。")
                        )
                    }
                }
            }
        }

        return withTimeout(CONNECT_TIMEOUT_MS) { deferred.await() }
    }

    private fun failConnection(message: String) {
        val error = IllegalStateException(message)
        synchronized(lock) {
            service = null
            connecting?.completeExceptionally(error)
            connecting = null
        }
        failPending(error)
    }

    private fun handleProcessDeath(message: String) {
        val error = IllegalStateException(message)
        val context = applicationContext

        synchronized(lock) {
            service = null
            connecting?.completeExceptionally(error)
            connecting = null

            if (bound && context != null) {
                runCatching { context.unbindService(connection) }
            }
            bound = false
        }

        failPending(error)
        context?.let {
            AppLog.e(it, "LocalAiClient", "AI process died; UI process kept alive", error)
        }
    }

    private fun failPending(error: Throwable) {
        val requests = pending.values.toList()
        pending.clear()
        requests.forEach { it.completeExceptionally(error) }
    }

    private fun newsBundle(modelUri: String, news: NewsItem) = Bundle().apply {
        putString(LocalAiService.KEY_MODEL_URI, modelUri)
        putString(LocalAiService.KEY_NEWS_ID, news.id)
        putString(LocalAiService.KEY_REGION, news.region.name)
        putString(LocalAiService.KEY_PLATFORM, news.platform)
        putString(LocalAiService.KEY_PUBLISHED_LABEL, news.publishedLabel)
        putString(LocalAiService.KEY_ORIGINAL_TITLE, news.originalTitle)
        putString(LocalAiService.KEY_ORIGINAL_TEXT, news.originalText)
        putString(LocalAiService.KEY_SOURCE_URL, news.sourceUrl)
        putString(LocalAiService.KEY_CATEGORY, news.category)
        putString(LocalAiService.KEY_IMAGE_URL, news.imageUrl)
    }
}
