package com.ikegami99.krprnews.update

import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import com.ikegami99.krprnews.diagnostics.AppLog
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

private const val API_URL = "https://api.github.com/repos/IKEGAMI-99/KRPR_news/releases/latest"
private const val APK_MIME = "application/vnd.android.package-archive"

data class ReleaseInfo(
    val tagName: String,
    val notes: String,
    val apkUrl: String,
    val apkName: String,
    val checksumUrl: String?
)

class UpdateCheckException(message: String) : Exception(message)
class UpdateInstallPermissionException : Exception("このアプリからのインストール許可が必要です")

object GitHubUpdateManager {
    suspend fun checkLatest(): ReleaseInfo? = withContext(Dispatchers.IO) {
        val connection = URL(API_URL).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 10_000
            connection.readTimeout = 10_000
            connection.setRequestProperty("Accept", "application/vnd.github+json")
            connection.setRequestProperty("User-Agent", "Kirapara-News-Android")

            val responseCode = connection.responseCode
            if (responseCode == 404) throw UpdateCheckException("GitHub Releaseがまだ公開されていません")
            if (responseCode !in 200..299) throw UpdateCheckException("GitHubの更新確認に失敗しました (HTTP $responseCode)")

            val json = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            val assets = json.getJSONArray("assets")
            var apkUrl: String? = null
            var apkName: String? = null
            var checksumUrl: String? = null
            for (i in 0 until assets.length()) {
                val asset = assets.getJSONObject(i)
                val name = asset.optString("name")
                val url = asset.optString("browser_download_url")
                when {
                    name.endsWith(".apk", ignoreCase = true) && apkUrl == null -> {
                        apkUrl = url
                        apkName = name
                    }
                    name.endsWith(".sha256", ignoreCase = true) -> checksumUrl = url
                }
            }
            if (apkUrl.isNullOrBlank() || apkName.isNullOrBlank()) throw UpdateCheckException("最新ReleaseにAPKがありません")

            ReleaseInfo(
                tagName = json.optString("tag_name"),
                notes = json.optString("body", "更新内容はGitHub Releasesで確認できます。"),
                apkUrl = apkUrl,
                apkName = apkName,
                checksumUrl = checksumUrl
            )
        } finally {
            connection.disconnect()
        }
    }

    fun isNewer(current: String, remoteTag: String): Boolean {
        fun parts(value: String) = value.removePrefix("v").split('.').map { it.toIntOrNull() ?: 0 }
        val a = parts(current)
        val b = parts(remoteTag)
        val max = maxOf(a.size, b.size)
        for (i in 0 until max) {
            val left = a.getOrElse(i) { 0 }
            val right = b.getOrElse(i) { 0 }
            if (right != left) return right > left
        }
        return false
    }

    suspend fun fetchChecksum(url: String?): String? = withContext(Dispatchers.IO) {
        if (url.isNullOrBlank()) return@withContext null
        val connection = URL(url).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 10_000
            connection.readTimeout = 10_000
            connection.setRequestProperty("User-Agent", "Kirapara-News-Android")
            if (connection.responseCode !in 200..299) return@withContext null
            connection.inputStream.bufferedReader().use { it.readText() }.trim().split(Regex("\\s+")).firstOrNull()
        } finally {
            connection.disconnect()
        }
    }

    suspend fun downloadAndVerify(
        context: Context,
        release: ReleaseInfo,
        wifiOnly: Boolean,
        onProgress: (Int) -> Unit = {}
    ): File = withContext(Dispatchers.IO) {
        val app = context.applicationContext
        if (wifiOnly && !isOnWifi(app)) {
            throw IllegalStateException("Wi-Fi接続時のみダウンロードする設定です")
        }
        val expected = fetchChecksum(release.checksumUrl)
            ?: throw IllegalStateException("SHA-256チェックサムを取得できませんでした")

        val dir = File(app.cacheDir, "updates").apply { mkdirs() }
        val part = File(dir, release.apkName + ".part")
        val target = File(dir, release.apkName)
        part.delete()
        target.delete()

        AppLog.i(app, "Updater", "download start ${release.tagName} ${release.apkUrl}")
        val connection = URL(release.apkUrl).openConnection() as HttpURLConnection
        try {
            connection.instanceFollowRedirects = true
            connection.connectTimeout = 15_000
            connection.readTimeout = 30_000
            connection.setRequestProperty("User-Agent", "Kirapara-News-Android")
            if (connection.responseCode !in 200..299) {
                throw IllegalStateException("APKダウンロードに失敗しました (HTTP ${connection.responseCode})")
            }
            val total = connection.contentLengthLong
            val digest = MessageDigest.getInstance("SHA-256")
            var done = 0L
            connection.inputStream.buffered().use { input ->
                part.outputStream().buffered().use { output ->
                    val buffer = ByteArray(128 * 1024)
                    while (true) {
                        val read = input.read(buffer)
                        if (read <= 0) break
                        output.write(buffer, 0, read)
                        digest.update(buffer, 0, read)
                        done += read
                        if (total > 0) onProgress(((done * 100L) / total).toInt().coerceIn(0, 100))
                    }
                }
            }
            val actual = digest.digest().joinToString("") { "%02x".format(it) }
            if (!actual.equals(expected, ignoreCase = true)) {
                part.delete()
                AppLog.e(app, "Updater", "checksum mismatch expected=$expected actual=$actual")
                throw SecurityException("APKのSHA-256が一致しません。更新を中止しました")
            }
            if (!part.renameTo(target)) {
                part.copyTo(target, overwrite = true)
                part.delete()
            }
            onProgress(100)
            AppLog.i(app, "Updater", "download verified ${target.name} sha256=$actual")
            target
        } catch (t: Throwable) {
            AppLog.e(app, "Updater", "download failed ${release.tagName}", t)
            throw t
        } finally {
            connection.disconnect()
        }
    }

    fun canInstallPackages(context: Context): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.O || context.packageManager.canRequestPackageInstalls()

    fun unknownSourcesIntent(context: Context): Intent =
        Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}"))

    fun installVerifiedApk(context: Context, apk: File) {
        val app = context.applicationContext
        if (!canInstallPackages(app)) throw UpdateInstallPermissionException()
        val uri = FileProvider.getUriForFile(app, "${app.packageName}.fileprovider", apk)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, APK_MIME)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        AppLog.i(app, "Updater", "launch Android installer ${apk.name}")
        app.startActivity(intent)
    }

    private fun isOnWifi(context: Context): Boolean {
        val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = manager.activeNetwork ?: return false
        val caps = manager.getNetworkCapabilities(network) ?: return false
        return caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
    }
}
