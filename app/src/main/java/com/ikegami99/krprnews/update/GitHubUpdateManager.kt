package com.ikegami99.krprnews.update

import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
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

object GitHubUpdateManager {
    suspend fun checkLatest(): ReleaseInfo? = withContext(Dispatchers.IO) {
        val connection = URL(API_URL).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 10_000
            connection.readTimeout = 10_000
            connection.setRequestProperty("Accept", "application/vnd.github+json")
            connection.setRequestProperty("User-Agent", "Kirapara-News-Android")
            if (connection.responseCode != 200) return@withContext null
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
            if (apkUrl.isNullOrBlank() || apkName.isNullOrBlank()) return@withContext null
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

    fun enqueueDownload(context: Context, release: ReleaseInfo, wifiOnly: Boolean): Long {
        val request = DownloadManager.Request(Uri.parse(release.apkUrl))
            .setTitle("Kirapara News ${release.tagName}")
            .setDescription("アップデートAPKをダウンロードしています")
            .setMimeType(APK_MIME)
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalFilesDir(context, Environment.DIRECTORY_DOWNLOADS, release.apkName)
        if (wifiOnly) request.setAllowedNetworkTypes(DownloadManager.Request.NETWORK_WIFI)
        return (context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager).enqueue(request)
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

    suspend fun verifyDownloadedApk(context: Context, downloadId: Long, expected: String): Boolean = withContext(Dispatchers.IO) {
        val manager = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        val uri = manager.getUriForDownloadedFile(downloadId) ?: return@withContext false
        val digest = MessageDigest.getInstance("SHA-256")
        context.contentResolver.openInputStream(uri)?.use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val read = input.read(buffer)
                if (read <= 0) break
                digest.update(buffer, 0, read)
            }
        } ?: return@withContext false
        val actual = digest.digest().joinToString("") { "%02x".format(it) }
        actual.equals(expected, ignoreCase = true)
    }

    fun installDownloadedApk(context: Context, downloadId: Long): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !context.packageManager.canRequestPackageInstalls()) {
            context.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}")))
            return false
        }
        val manager = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        val uri = manager.getUriForDownloadedFile(downloadId) ?: return false
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, APK_MIME)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
        return true
    }
}
