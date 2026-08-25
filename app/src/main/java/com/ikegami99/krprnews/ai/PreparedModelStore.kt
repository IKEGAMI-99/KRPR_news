package com.ikegami99.krprnews.ai

import android.content.Context
import android.net.Uri
import android.os.StatFs
import android.provider.OpenableColumns
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
 *
 * Google が初期配布した Gemma 4 E4B Q4_0 GGUF には vocabulary 不整合版が存在する。
 * 既知の旧版は llama.cpp の vocab load で process abort するため、native に渡す前に拒否する。
 * 現行公式修正版はコピーと同時に SHA-256 を検証する。
 */
object PreparedModelStore {
    private const val BUFFER_SIZE = 8 * 1024 * 1024
    private const val EXTRA_FREE_SPACE = 256L * 1024L * 1024L

    private const val GEMMA4_E4B_Q40_NAME = "gemma-4-E4B_q4_0-it.gguf"
    private const val GEMMA4_E4B_Q40_BROKEN_SIZE = 5_154_940_864L
    private const val GEMMA4_E4B_Q40_FIXED_SIZE = 5_154_941_280L
    private const val GEMMA4_E4B_Q40_FIXED_SHA256 =
        "676c35070db6dbe52f93e9c864ee0fba4eddea94b9c875d9cb10daff453fbaee"

    suspend fun prepare(context: Context, sourceUriString: String): File = withContext(Dispatchers.IO) {
        val appContext = context.applicationContext
        val uri = Uri.parse(sourceUriString)
        val sourceSize = querySize(appContext, uri)
            ?: throw IllegalStateException("GGUFのファイルサイズを取得できません。")
        if (sourceSize <= 0L) throw IllegalStateException("GGUFファイルが空です。")

        val sourceName = queryName(appContext, uri) ?: uri.lastPathSegment.orEmpty()
        validateKnownBrokenModel(sourceName, sourceSize)

        val dir = modelDir(appContext)
        if (!dir.exists() && !dir.mkdirs()) {
            throw IllegalStateException("アプリ用モデル保存先を作成できません。")
        }

        val target = File(dir, "${stableId(sourceUriString, sourceSize)}.gguf")
        val checksumMarker = File(dir, target.name + ".sha256")
        val verifyOfficialE4B = isCurrentOfficialE4B(sourceName, sourceSize)

        if (target.isFile && target.length() == sourceSize) {
            if (!verifyOfficialE4B) {
                AppLog.i(appContext, "LocalGemma", "prepared model reuse path=${target.absolutePath} size=$sourceSize")
                return@withContext target
            }

            val stored = checksumMarker.takeIf { it.isFile }?.readText()?.trim().orEmpty()
            if (stored.equals(GEMMA4_E4B_Q40_FIXED_SHA256, ignoreCase = true)) {
                AppLog.i(appContext, "LocalGemma", "prepared official Gemma 4 checksum reuse verified")
                return@withContext target
            }

            AppLog.i(appContext, "LocalGemma", "verifying existing prepared official Gemma 4 checksum")
            val existingSha = sha256(target)
            if (existingSha.equals(GEMMA4_E4B_Q40_FIXED_SHA256, ignoreCase = true)) {
                checksumMarker.writeText(existingSha)
                return@withContext target
            }

            AppLog.w(appContext, "LocalGemma", "prepared official Gemma 4 checksum mismatch; rebuilding")
            target.delete()
            checksumMarker.delete()
        }

        val part = File(dir, target.name + ".part")
        if (target.exists()) target.delete()
        if (part.exists()) part.delete()
        if (checksumMarker.exists()) checksumMarker.delete()

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
            "model import start name=$sourceName sourceSize=$sourceSize target=${target.absolutePath} verifyOfficialE4B=$verifyOfficialE4B"
        )

        try {
            val digest = MessageDigest.getInstance("SHA-256")
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
                        digest.update(buffer, 0, read)
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

            val copiedSha = digest.digest().joinToString("") { "%02x".format(it) }
            AppLog.i(appContext, "LocalGemma", "model import sha256=$copiedSha")

            if (verifyOfficialE4B && !copiedSha.equals(GEMMA4_E4B_Q40_FIXED_SHA256, ignoreCase = true)) {
                throw IllegalStateException(
                    "Gemma 4 E4B Q4_0 のSHA-256がGoogle公式修正版と一致しません。ファイルを削除して公式版を再ダウンロードしてください。"
                )
            }

            if (!part.renameTo(target)) {
                throw IllegalStateException("準備したGGUFを確定できませんでした。")
            }
            if (verifyOfficialE4B) checksumMarker.writeText(copiedSha)

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

    private fun validateKnownBrokenModel(name: String, size: Long) {
        if (name.equals(GEMMA4_E4B_Q40_NAME, ignoreCase = true) && size == GEMMA4_E4B_Q40_BROKEN_SIZE) {
            throw IllegalStateException(
                "このGemma 4 E4B Q4_0はGoogle初期配布の旧版です。vocabulary不整合でllama.cppが強制終了します。" +
                    "Google公式のcorrected vocabulary版を再ダウンロードしてください。" +
                    "修正版サイズ: $GEMMA4_E4B_Q40_FIXED_SIZE bytes"
            )
        }
    }

    private fun isCurrentOfficialE4B(name: String, size: Long): Boolean =
        name.equals(GEMMA4_E4B_Q40_NAME, ignoreCase = true) && size == GEMMA4_E4B_Q40_FIXED_SIZE

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

    private fun queryName(context: Context, uri: Uri): String? {
        return runCatching {
            context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                if (!cursor.moveToFirst()) return@use null
                val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (index >= 0 && !cursor.isNull(index)) cursor.getString(index) else null
            }
        }.getOrNull()
    }

    private fun stableId(uri: String, size: Long): String {
        val digest = MessageDigest.getInstance("SHA-256")
            .digest("$uri|$size".toByteArray())
        return digest.take(12).joinToString("") { "%02x".format(it) }
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().buffered(BUFFER_SIZE).use { input ->
            val buffer = ByteArray(BUFFER_SIZE)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                if (read > 0) digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
