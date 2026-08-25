package com.ikegami99.krprnews.translation

import com.google.android.gms.tasks.Task
import com.google.mlkit.common.model.DownloadConditions
import com.google.mlkit.nl.translate.TranslateLanguage
import com.google.mlkit.nl.translate.Translation
import com.google.mlkit.nl.translate.Translator
import com.google.mlkit.nl.translate.TranslatorOptions
import com.ikegami99.krprnews.data.Region
import java.util.concurrent.ConcurrentHashMap
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.coroutines.suspendCoroutine

/**
 * Google ML Kit のオンデバイス翻訳。
 * 翻訳本文は外部の翻訳APIへ送信しない。言語モデルだけ初回に端末へ取得する。
 */
object LocalTranslationManager {
    private val clients = ConcurrentHashMap<Region, Translator>()
    private val ready = ConcurrentHashMap<Region, Boolean>()

    suspend fun translate(region: Region, text: String): String {
        if (text.isBlank() || region == Region.JAPAN) return text
        return runCatching {
            val translator = clients.getOrPut(region) { createTranslator(region) }
            if (ready[region] != true) {
                translator.downloadModelIfNeeded(
                    DownloadConditions.Builder().build()
                ).awaitTask()
                ready[region] = true
            }
            translator.translate(text).awaitTask()
        }.getOrDefault(text)
    }

    suspend fun warmUp(region: Region): Boolean {
        if (region == Region.JAPAN) return true
        return runCatching {
            val translator = clients.getOrPut(region) { createTranslator(region) }
            translator.downloadModelIfNeeded(DownloadConditions.Builder().build()).awaitTask()
            ready[region] = true
            true
        }.getOrDefault(false)
    }

    fun isReady(region: Region): Boolean = region == Region.JAPAN || ready[region] == true

    private fun createTranslator(region: Region): Translator {
        val source = when (region) {
            Region.CHINA -> TranslateLanguage.CHINESE
            Region.GLOBAL -> TranslateLanguage.ENGLISH
            Region.KOREA -> TranslateLanguage.KOREAN
            Region.JAPAN -> TranslateLanguage.JAPANESE
        }
        val options = TranslatorOptions.Builder()
            .setSourceLanguage(source)
            .setTargetLanguage(TranslateLanguage.JAPANESE)
            .build()
        return Translation.getClient(options)
    }
}

private suspend fun <T> Task<T>.awaitTask(): T = suspendCoroutine { continuation ->
    addOnSuccessListener { continuation.resume(it) }
    addOnFailureListener { continuation.resumeWithException(it) }
}
