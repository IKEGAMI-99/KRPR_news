package com.ikegami99.krprnews.diagnostics

import android.content.Context
import android.net.Uri
import android.os.Build
import android.util.Base64
import com.ikegami99.krprnews.BuildConfig
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object AppLog {
    private const val MAX_BYTES = 1024 * 1024L
    private const val KEEP_BYTES = 640 * 1024L
    private const val MAX_EXIT_TRACE_BYTES = 2 * 1024 * 1024
    private val lock = Any()
    private val timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US)

    private fun file(context: Context): File {
        val dir = File(context.filesDir, "logs").apply { mkdirs() }
        return File(dir, "krpr-news.log")
    }

    private fun aiExitTraceFile(context: Context): File {
        val dir = File(context.filesDir, "logs").apply { mkdirs() }
        return File(dir, "last-ai-exit-trace.pb")
    }

    fun i(context: Context, tag: String, message: String) = write(context, "I", tag, message, null)
    fun w(context: Context, tag: String, message: String) = write(context, "W", tag, message, null)
    fun e(context: Context, tag: String, message: String, throwable: Throwable? = null) =
        write(context, "E", tag, message, throwable)

    private fun write(context: Context, level: String, tag: String, message: String, throwable: Throwable?) {
        runCatching {
            synchronized(lock) {
                val target = file(context.applicationContext)
                if (target.length() > MAX_BYTES) {
                    val bytes = target.readBytes()
                    val start = (bytes.size - KEEP_BYTES.toInt()).coerceAtLeast(0)
                    target.writeBytes(bytes.copyOfRange(start, bytes.size))
                }
                target.appendText(buildString {
                    append(timestamp.format(Date()))
                    append(' ')
                    append(level)
                    append('/')
                    append(tag)
                    append(": ")
                    append(message.replace('\n', ' '))
                    append('\n')
                    if (throwable != null) {
                        append(throwable.stackTraceToString())
                        if (!endsWith("\n")) append('\n')
                    }
                })
            }
        }
    }

    /** Store the newest native tombstone/trace returned by ApplicationExitInfo. */
    fun saveAiExitTrace(context: Context, bytes: ByteArray) {
        if (bytes.isEmpty()) return
        var savedBytes = 0
        var truncated = false
        runCatching {
            synchronized(lock) {
                val target = aiExitTraceFile(context.applicationContext)
                val capped = if (bytes.size <= MAX_EXIT_TRACE_BYTES) bytes else bytes.copyOf(MAX_EXIT_TRACE_BYTES)
                target.writeBytes(capped)
                savedBytes = capped.size
                truncated = bytes.size > capped.size
            }
            i(context, "ExitInfo", "saved AI native exit trace bytes=$savedBytes truncated=$truncated")
        }
    }

    fun clear(context: Context) {
        runCatching {
            synchronized(lock) {
                file(context.applicationContext).writeText("")
                aiExitTraceFile(context.applicationContext).delete()
            }
        }
    }

    fun sizeBytes(context: Context): Long = runCatching { file(context.applicationContext).length() }.getOrDefault(0L)

    fun export(context: Context, destination: Uri, modelName: String?) {
        val app = context.applicationContext
        val trace: ByteArray? = runCatching {
            aiExitTraceFile(app).takeIf { it.isFile }?.readBytes()
        }.getOrNull()
        val body = buildString {
            appendLine("Kirapara News diagnostics")
            appendLine("========================")
            appendLine("App: ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})")
            appendLine("Device: ${Build.MANUFACTURER} ${Build.MODEL}")
            appendLine("Android: ${Build.VERSION.RELEASE} / API ${Build.VERSION.SDK_INT}")
            appendLine("ABI: ${Build.SUPPORTED_ABIS.joinToString()}")
            appendLine("Model: ${modelName ?: "not selected"}")
            appendLine("AI backend: llama.cpp generic CPU/NEON · ctx=2048 · batch/ubatch=64 · threads=4 · temp=1.0 · top-p=0.95 · top-k=64 · thinking=off · flash-attn=off · q4-repack=on")
            appendLine()
            appendLine("Log")
            appendLine("---")
            append(runCatching { file(app).readText() }.getOrDefault("(no log entries)"))

            if (trace != null && trace.isNotEmpty()) {
                appendLine()
                appendLine("AI native exit trace")
                appendLine("---")
                appendLine("Format: Android tombstone protobuf, base64 encoded")
                appendLine("Bytes: ${trace.size}")
                appendLine(Base64.encodeToString(trace, Base64.NO_WRAP))
            }
        }
        app.contentResolver.openOutputStream(destination, "wt")?.bufferedWriter()?.use { it.write(body) }
            ?: error("ログの保存先を開けませんでした")
    }
}
