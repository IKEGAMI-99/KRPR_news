package com.ikegami99.krprnews.ai

import android.content.Context
import android.net.Uri
import android.os.StatFs
import com.ikegami99.krprnews.diagnostics.AppLog
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest

/**
 * Android Storage Access Framework の content:// URI をネイティブ llama.cpp に直接渡すと、
 * Java では読めるのに native fopen/mmap で再オープンできない端末がある。
 * そのため初回だけアプリ専用領域へGGUFをコピーし、以後は通常ファイルパスを使う。
 */
object PreparedModelStore {
    private const val BUFFER_SIZE = 8 * 1024 * 1024
    private const val EXTRA_FREE_SPACE = 256L * 1024L * 1024L

    suspend fun prepare(context: Context, sourceUriString: String): File = withContext(Dispatchers.IO) {
        val appContext = context.applicationContext
        val uri = Uri.parse(sourceUriString)
        val sourceSize = querySize(appContext, uri)
            ?: throw IllegalStateException("GGUFのファイルサイズを取得できません。")
        if (sourceSize <= 0L) throw IllegalStateException("GGUFファイルが空です。")

        val dir = modelDir(appContext)
        if (!dir.exists() && !dir.mkdirs()) {
            throw IllegalStateException("アプリ用モデル保存先を作成できません。")
        }

        val target = File(dir, "${stableId(sourceUriString, sourceSize)}.gguf")
        if (target.isFile && target.length() == sourceSize) {
            AppLog.i(appContext, "LocalGemma", "prepared model reuse path=${target.absolutePath} size=$sourceSize")
            return@withContext target
        }

        val part = File(dir, target.name + ".part")
        if (target.exists()) target.delete()
        if (part.exists()) part.delete()

        val available = runCatching { StatFs(dir.absolutePath).availableBytes }.getOrDefault(0L)
        val required = sourceSize + EXTRA_FREE_SPACE
        if (available in 1 until required) {
            val needGb = required / 1024.0 / 1024.0 / 1024.0
            val freeGb = available / 1024.0 / 1024.0 / 1024.0
            throw IllegalStateException(
                "モデル準備用の空き容量が不足しています。必要 約%.2f GB / 空き 約%.2f GB".format(needGb, freeGb)
            )
        }

        AppLog.i(
            appContext,
            "LocalGemma",
            "model import start sourceSize=$sourceSize target=${target.absolutePath}"
        )

        try {
            val input = appContext.contentResolver.openInputStream(uri)
                ?: throw IllegalStateException("選択したGGUFを開けません。")
            input.use { source ->
                FileOutputStream(part).use { output ->
                    val buffer = ByteArray(BUFFER_SIZE)
                    var copied = 0L
                    var lastLogged = -10
                    while (true) {
                        val read = source.read(buffer)
                        if (read < 0) break
                        if (read == 0) continue
                        output.write(buffer, 0, read)
                        copied += read
                        val progress = ((copied * 100L) / sourceSize).toInt().coerceIn(0, 100)
                        if (progress >= lastLogged + 10) {
                            lastLogged = progress
                            AppLog.i(appContext, "LocalGemma", "model import progress=$progress% copied=$copied/$sourceSize")
                        }
                    }
                    output.fd.sync()
                }
            }

            if (part.length() != sourceSize) {
                throw IllegalStateException(
                    "GGUFのコピーサイズが一致しません。expected=$sourceSize actual=${part.length()}"
                )
            }
            if (!part.renameTo(target)) {
                throw IllegalStateException("準備したGGUFを確定できませんでした。")
            }

            AppLog.i(appContext, "LocalGemma", "model import complete path=${target.absolutePath} size=${target.length()}")
            target
        } catch (t: Throwable) {
            part.delete()
            AppLog.e(appContext, "LocalGemma", "model import failed", t)
            throw t
        }
    }

    fun preparedBytes(context: Context): Long {
        val dir = modelDir(context.applicationContext)
        return dir.listFiles()?.filter { it.isFile && it.extension == "gguf" }?.sumOf { it.length() } ?: 0L
    }

    fun clear(context: Context) {
        val dir = modelDir(context.applicationContext)
        dir.listFiles()?.forEach { it.delete() }
        AppLog.i(context, "LocalGemma", "prepared models cleared")
    }

    private fun modelDir(context: Context): File {
        return context.getExternalFilesDir("models") ?: File(context.filesDir, "models")
    }

    private fun querySize(context: Context, uri: Uri): Long? {
        return runCatching {
            context.contentResolver.openFileDescriptor(uri, "r")?.use { pfd ->
                pfd.statSize.takeIf { it > 0L }
            }
        }.getOrNull()
    }

    private fun stableId(uri: String, size: Long): String {
        val digest = MessageDigest.getInstance("SHA-256")
            .digest("$uri|$size".toByteArray())
        return digest.take(12).joinToString("") { "%02x".format(it) }
    }
}
