package com.ikegami99.krprnews.ai

import android.app.ActivityManager
import android.app.ApplicationExitInfo
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.Build
import android.os.Bundle
import android.os.DeadObjectException
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Message
import android.os.Messenger
import android.os.SystemClock
import com.ikegami99.krprnews.data.NewsItem
import com.ikegami99.krprnews.diagnostics.AppLog
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.withTimeout
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong

/**
 * Main-process facade for [LocalAiService].
 *
 * llama.cpp runs in a dedicated :ai process. If native inference aborts or Android
 * kills the heavy process, Kirapara News itself survives. v0.3.8 also asks Android
 * for ApplicationExitInfo so the next diagnostic log records WHY the AI process died.
 */
object LocalAiProcessClient {
    private const val CONNECT_TIMEOUT_MS = 15_000L
    private const val REQUEST_TIMEOUT_MS = 300_000L
    private const val EXIT_LOOKBACK_MS = 90_000L
    private const val MAX_TRACE_BYTES = 2 * 1024 * 1024

    private val lock = Any()
    private val nextRequestId = AtomicLong(1L)
    private val pending = ConcurrentHashMap<Long, CompletableDeferred<Bundle>>()
    private val mainHandler = Handler(Looper.getMainLooper())

    @Volatile
    private var service: Messenger? = null
    private var connecting: CompletableDeferred<Messenger>? = null
    private var bound = false
    private var applicationContext: Context? = null
    private var lastDeathDiagnosticScheduleMs = 0L
    private var lastLoggedExitTimestamp = 0L

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
                        Context.BIND_AUTO_CREATE or Context.BIND_IMPORTANT
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
            scheduleExitDiagnostics(it)
        }
    }

    /**
     * Binder death can arrive a little before ActivityManager publishes the exit record,
     * so retry a few times. Duplicate binder/service callbacks are de-duplicated here.
     */
    private fun scheduleExitDiagnostics(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return

        val now = SystemClock.elapsedRealtime()
        synchronized(lock) {
            if (now - lastDeathDiagnosticScheduleMs < 2_000L) return
            lastDeathDiagnosticScheduleMs = now
        }

        val app = context.applicationContext
        val delays = longArrayOf(350L, 1_500L, 4_000L)
        delays.forEachIndexed { index, delay ->
            mainHandler.postDelayed({
                val found = runCatching { captureLatestAiExit(app) }
                    .onFailure { AppLog.e(app, "ExitInfo", "failed to read AI process exit info", it) }
                    .getOrDefault(false)
                if (!found && index == delays.lastIndex) {
                    AppLog.w(app, "ExitInfo", "no recent :ai ApplicationExitInfo record was available")
                }
            }, delay)
        }
    }

    private fun captureLatestAiExit(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return false

        val activityManager = context.getSystemService(ActivityManager::class.java) ?: return false
        val aiProcessName = "${context.packageName}:ai"
        val nowWall = System.currentTimeMillis()
        val exit = activityManager
            .getHistoricalProcessExitReasons(context.packageName, 0, 16)
            .asSequence()
            .filter { it.processName == aiProcessName }
            .filter { nowWall - it.timestamp in 0..EXIT_LOOKBACK_MS }
            .filter { it.timestamp > lastLoggedExitTimestamp }
            .maxByOrNull { it.timestamp }
            ?: return false

        lastLoggedExitTimestamp = exit.timestamp
        val summary = buildString {
            append("process=")
            append(exit.processName)
            append(" reason=")
            append(exitReasonName(exit.reason))
            append('(')
            append(exit.reason)
            append(')')
            append(" status=")
            append(exit.status)
            append(" importance=")
            append(exit.importance)
            append(" pssMb=")
            append(exit.pss / 1024)
            append(" rssMb=")
            append(exit.rss / 1024)
            append(" timestamp=")
            append(exit.timestamp)
            val description = exit.description
            if (!description.isNullOrBlank()) {
                append(" description=")
                append(description.replace('\n', ' '))
            }
        }
        AppLog.e(context, "ExitInfo", "AI process exit captured: $summary")

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && exit.reason == ApplicationExitInfo.REASON_CRASH_NATIVE) {
            runCatching {
                exit.traceInputStream?.use { input ->
                    val bytes = readAtMost(input, MAX_TRACE_BYTES)
                    if (bytes.isNotEmpty()) AppLog.saveAiExitTrace(context, bytes)
                }
            }.onFailure {
                AppLog.e(context, "ExitInfo", "failed to read native tombstone trace", it)
            }
        }
        return true
    }

    private fun exitReasonName(reason: Int): String = when (reason) {
        0 -> "UNKNOWN"
        1 -> "EXIT_SELF"
        2 -> "SIGNALED"
        3 -> "LOW_MEMORY"
        4 -> "CRASH_JAVA"
        5 -> "CRASH_NATIVE"
        6 -> "ANR"
        7 -> "INITIALIZATION_FAILURE"
        8 -> "PERMISSION_CHANGE"
        9 -> "EXCESSIVE_RESOURCE_USAGE"
        10 -> "USER_REQUESTED"
        11 -> "USER_STOPPED"
        12 -> "DEPENDENCY_DIED"
        13 -> "OTHER"
        14 -> "FREEZER"
        15 -> "PACKAGE_STATE_CHANGE"
        16 -> "PACKAGE_UPDATED"
        17 -> "MEMORY_LIMITER"
        18 -> "ANOMALY"
        else -> "REASON_$reason"
    }

    private fun readAtMost(input: InputStream, maxBytes: Int): ByteArray {
        val out = ByteArrayOutputStream(minOf(maxBytes, 64 * 1024))
        val buffer = ByteArray(16 * 1024)
        var remaining = maxBytes
        while (remaining > 0) {
            val count = input.read(buffer, 0, minOf(buffer.size, remaining))
            if (count <= 0) break
            out.write(buffer, 0, count)
            remaining -= count
        }
        return out.toByteArray()
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
