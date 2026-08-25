package com.ikegami99.krprnews.ui

import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.OpenInNew
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import coil.compose.AsyncImage
import com.ikegami99.krprnews.BuildConfig
import com.ikegami99.krprnews.ai.LocalAiSummary
import com.ikegami99.krprnews.ai.LocalAiTranslation
import com.ikegami99.krprnews.ai.LocalGemmaManager
import com.ikegami99.krprnews.data.*
import com.ikegami99.krprnews.prefs.AppPreferences
import com.ikegami99.krprnews.prefs.ThemeMode
import com.ikegami99.krprnews.ui.theme.KiraparaTheme
import com.ikegami99.krprnews.update.GitHubUpdateManager
import com.ikegami99.krprnews.update.ReleaseInfo
import kotlinx.coroutines.launch

enum class AppPage { HOME, SETTINGS }
private enum class AiTask { TRANSLATE, SUMMARY }

@Composable
fun KiraparaApp(repository: NewsRepository = ApiFreeNewsRepository) {
    val context = LocalContext.current
    val prefs = remember { AppPreferences(context) }
    var themeMode by remember { mutableStateOf(prefs.themeMode) }
    var page by remember { mutableStateOf(AppPage.HOME) }
    var autoUpdate by remember { mutableStateOf(prefs.autoUpdateCheck) }
    var wifiOnly by remember { mutableStateOf(prefs.wifiOnly) }
    var releaseInfo by remember { mutableStateOf<ReleaseInfo?>(null) }
    var updateMessage by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun checkUpdates() {
        updateMessage = "最新版を確認しています…"
        scope.launch {
            runCatching { GitHubUpdateManager.checkLatest() }
                .onSuccess { release ->
                    if (release != null && GitHubUpdateManager.isNewer(BuildConfig.VERSION_NAME, release.tagName)) {
                        releaseInfo = release
                        updateMessage = "${release.tagName} が利用できます"
                    } else {
                        releaseInfo = null
                        updateMessage = "最新版です"
                    }
                }
                .onFailure { updateMessage = "更新確認に失敗しました" }
        }
    }

    LaunchedEffect(autoUpdate) {
        if (autoUpdate) checkUpdates()
    }

    KiraparaTheme(themeMode) {
        Box(
            Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        listOf(
                            MaterialTheme.colorScheme.background,
                            MaterialTheme.colorScheme.primary.copy(alpha = 0.08f),
                            MaterialTheme.colorScheme.secondary.copy(alpha = 0.07f)
                        )
                    )
                )
        ) {
            when (page) {
                AppPage.HOME -> HomeScreen(
                    repository = repository,
                    releaseInfo = releaseInfo,
                    onOpenSettings = { page = AppPage.SETTINGS },
                    onRefreshUpdate = ::checkUpdates
                )

                AppPage.SETTINGS -> SettingsScreen(
                    themeMode = themeMode,
                    autoUpdate = autoUpdate,
                    wifiOnly = wifiOnly,
                    releaseInfo = releaseInfo,
                    updateMessage = updateMessage,
                    onBack = { page = AppPage.HOME },
                    onThemeChanged = {
                        themeMode = it
                        prefs.themeMode = it
                    },
                    onAutoUpdateChanged = {
                        autoUpdate = it
                        prefs.autoUpdateCheck = it
                    },
                    onWifiOnlyChanged = {
                        wifiOnly = it
                        prefs.wifiOnly = it
                    },
                    onCheckUpdate = ::checkUpdates
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HomeScreen(
    repository: NewsRepository,
    releaseInfo: ReleaseInfo?,
    onOpenSettings: () -> Unit,
    onRefreshUpdate: () -> Unit
) {
    var newsItems by remember { mutableStateOf<List<NewsItem>>(emptyList()) }
    var region by remember { mutableStateOf<Region?>(null) }
    var refreshing by remember { mutableStateOf(false) }
    var loadError by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    fun reload() {
        refreshing = true
        loadError = false
        scope.launch {
            runCatching { repository.loadNews() }
                .onSuccess { newsItems = it }
                .onFailure { loadError = true }
            refreshing = false
        }
    }

    LaunchedEffect(Unit) { reload() }

    Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Kirapara News ✨", fontWeight = FontWeight.Bold)
                        Text("原文で追って、必要な時だけローカルAI", fontSize = 11.sp)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Transparent),
                actions = {
                    IconButton(onClick = { reload(); onRefreshUpdate() }) {
                        Icon(Icons.Default.Refresh, if (refreshing) "更新中" else "更新")
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, "設定")
                    }
                }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(bottom = 28.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            if (releaseInfo != null) {
                item {
                    Surface(
                        modifier = Modifier.padding(horizontal = 16.dp).fillMaxWidth(),
                        shape = RoundedCornerShape(22.dp),
                        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.78f),
                        contentColor = MaterialTheme.colorScheme.onPrimaryContainer
                    ) {
                        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.AutoAwesome, null)
                            Spacer(Modifier.width(10.dp))
                            Column(Modifier.weight(1f)) {
                                Text("${releaseInfo.tagName} が利用できます", fontWeight = FontWeight.Bold)
                                Text("設定 → アップデートから更新できます", fontSize = 12.sp)
                            }
                        }
                    }
                }
            }

            item {
                LazyRow(
                    contentPadding = PaddingValues(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    item {
                        FilterChip(
                            selected = region == null,
                            onClick = { region = null },
                            label = { Text("✨ すべて") }
                        )
                    }
                    items(Region.entries) { r ->
                        FilterChip(
                            selected = region == r,
                            onClick = { region = r },
                            label = { Text("${r.flag} ${r.label}") }
                        )
                    }
                }
            }

            if (refreshing && newsItems.isEmpty()) {
                item { LoadingNewsState() }
            } else if ((loadError || newsItems.isEmpty()) && !refreshing) {
                item { EmptyNewsState(onRetry = ::reload) }
            }

            items(
                newsItems.filter { region == null || it.region == region },
                key = { it.id }
            ) { news ->
                NewsCard(news, Modifier.padding(horizontal = 16.dp))
            }

            item {
                Text(
                    "v${BuildConfig.VERSION_NAME} · 原文タイムライン + ローカルGGUF翻訳 / 日本語要約",
                    modifier = Modifier.padding(horizontal = 22.dp, vertical = 8.dp),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.65f)
                )
            }
        }
    }
}

@Composable
private fun LoadingNewsState() {
    Column(
        modifier = Modifier.fillMaxWidth().padding(vertical = 64.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        CircularProgressIndicator()
        Text("ニュースを読み込んでいます…", color = MaterialTheme.colorScheme.onSurface)
    }
}

@Composable
private fun EmptyNewsState(onRetry: () -> Unit) {
    Card(
        modifier = Modifier.padding(horizontal = 16.dp).fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f),
            contentColor = MaterialTheme.colorScheme.onSurface
        )
    ) {
        Column(
            Modifier.fillMaxWidth().padding(22.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text("ニュースを取得できませんでした", fontWeight = FontWeight.Bold)
            Text(
                "通信または取得元が一時的に利用できない可能性があります。",
                style = MaterialTheme.typography.bodySmall
            )
            Button(onClick = onRetry) {
                Icon(Icons.Default.Refresh, null)
                Spacer(Modifier.width(8.dp))
                Text("再読み込み")
            }
        }
    }
}

@Composable
private fun NewsCard(news: NewsItem, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val prefs = remember { AppPreferences(context) }
    val modelUri = prefs.ggufModelUri
    val scope = rememberCoroutineScope()

    var expanded by remember(news.id) { mutableStateOf(false) }
    var translation by remember(news.id, modelUri) {
        mutableStateOf<LocalAiTranslation?>(LocalGemmaManager.cachedTranslation(context, modelUri, news))
    }
    var showTranslation by remember(news.id, modelUri) { mutableStateOf(false) }
    var summary by remember(news.id, modelUri) {
        mutableStateOf<LocalAiSummary?>(LocalGemmaManager.cachedSummary(context, modelUri, news))
    }
    var showSummary by remember(news.id, modelUri) { mutableStateOf(false) }
    var aiTask by remember(news.id) { mutableStateOf<AiTask?>(null) }
    var aiError by remember(news.id) { mutableStateOf<String?>(null) }

    val textColor = MaterialTheme.colorScheme.onSurface
    val visibleTranslation = translation.takeIf { showTranslation }
    val title = visibleTranslation?.title ?: news.originalTitle
    val body = visibleTranslation?.body ?: news.originalText
    val busy = aiTask != null

    fun requireModel(): String? {
        if (modelUri.isNullOrBlank()) {
            aiError = "設定 → ローカルGemma 4 からGGUFを選択してください。"
            expanded = true
            return null
        }
        return modelUri
    }

    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f),
            contentColor = textColor
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 5.dp)
    ) {
        Column {
            NewsThumbnail(news)
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "${news.region.flag} ${news.region.label} · ${news.platform}",
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.weight(1f),
                        color = textColor
                    )
                    Text(
                        news.publishedLabel,
                        style = MaterialTheme.typography.labelSmall,
                        color = textColor.copy(alpha = 0.72f)
                    )
                }

                AssistChip(
                    onClick = { },
                    enabled = false,
                    label = {
                        Text(if (visibleTranslation != null) "🇯🇵 Gemma 4 翻訳" else "${news.region.flag} ${news.region.originalLabel} 原文")
                    }
                )

                Text(
                    title,
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = textColor,
                    maxLines = if (expanded) Int.MAX_VALUE else 2,
                    overflow = TextOverflow.Ellipsis
                )

                Text(
                    body,
                    style = MaterialTheme.typography.bodyMedium,
                    color = textColor,
                    maxLines = if (expanded) Int.MAX_VALUE else 3,
                    overflow = TextOverflow.Ellipsis
                )

                if (showSummary && summary != null) {
                    Surface(
                        shape = RoundedCornerShape(18.dp),
                        color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.72f),
                        contentColor = MaterialTheme.colorScheme.onSecondaryContainer
                    ) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("✨ Gemma 4 日本語要約", fontWeight = FontWeight.Bold)
                            Text(summary!!.text, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }

                aiError?.let {
                    Text(
                        it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    if (news.region != Region.JAPAN) {
                        FilledTonalButton(
                            onClick = {
                                aiError = null
                                if (showTranslation) {
                                    showTranslation = false
                                } else if (translation != null) {
                                    showTranslation = true
                                    expanded = true
                                } else {
                                    val uri = requireModel() ?: return@FilledTonalButton
                                    aiTask = AiTask.TRANSLATE
                                    scope.launch {
                                        runCatching { LocalGemmaManager.translate(context, uri, news) }
                                            .onSuccess {
                                                translation = it
                                                showTranslation = true
                                                expanded = true
                                            }
                                            .onFailure { aiError = it.message ?: "翻訳に失敗しました。" }
                                        aiTask = null
                                    }
                                }
                            },
                            enabled = !busy,
                            modifier = Modifier.weight(1f)
                        ) {
                            if (aiTask == AiTask.TRANSLATE) {
                                CircularProgressIndicator(Modifier.size(17.dp), strokeWidth = 2.dp)
                                Spacer(Modifier.width(7.dp))
                                Text("翻訳中")
                            } else {
                                Icon(Icons.Default.Language, null, Modifier.size(18.dp))
                                Spacer(Modifier.width(6.dp))
                                Text(if (showTranslation) "原文に戻す" else "日本語に翻訳")
                            }
                        }
                    }

                    FilledTonalButton(
                        onClick = {
                            aiError = null
                            if (showSummary) {
                                showSummary = false
                            } else if (summary != null) {
                                showSummary = true
                                expanded = true
                            } else {
                                val uri = requireModel() ?: return@FilledTonalButton
                                aiTask = AiTask.SUMMARY
                                scope.launch {
                                    runCatching { LocalGemmaManager.summarize(context, uri, news) }
                                        .onSuccess {
                                            summary = it
                                            showSummary = true
                                            expanded = true
                                        }
                                        .onFailure { aiError = it.message ?: "要約に失敗しました。" }
                                    aiTask = null
                                }
                            }
                        },
                        enabled = !busy,
                        modifier = Modifier.weight(1f)
                    ) {
                        if (aiTask == AiTask.SUMMARY) {
                            CircularProgressIndicator(Modifier.size(17.dp), strokeWidth = 2.dp)
                            Spacer(Modifier.width(7.dp))
                            Text("要約中")
                        } else {
                            Icon(Icons.Default.AutoAwesome, null, Modifier.size(18.dp))
                            Spacer(Modifier.width(6.dp))
                            Text(if (showSummary) "要約を閉じる" else "日本語要約")
                        }
                    }
                }

                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    if (translation?.tokensPerSecond?.let { it > 0f } == true && showTranslation) {
                        Text(
                            String.format("%.1f tok/s", translation!!.tokensPerSecond),
                            style = MaterialTheme.typography.labelSmall,
                            color = textColor.copy(alpha = 0.58f)
                        )
                    } else if (summary?.tokensPerSecond?.let { it > 0f } == true && showSummary) {
                        Text(
                            String.format("%.1f tok/s", summary!!.tokensPerSecond),
                            style = MaterialTheme.typography.labelSmall,
                            color = textColor.copy(alpha = 0.58f)
                        )
                    }
                    Spacer(Modifier.weight(1f))
                    TextButton(onClick = { expanded = !expanded }) {
                        Icon(
                            if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(Modifier.width(3.dp))
                        Text(if (expanded) "閉じる" else "続きを読む")
                    }
                }

                if (expanded) {
                    HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.25f))
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        TextButton(onClick = {
                            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(news.sourceUrl)))
                        }) {
                            Icon(Icons.Default.OpenInNew, null, Modifier.size(18.dp))
                            Spacer(Modifier.width(5.dp))
                            Text("公式投稿")
                        }
                        TextButton(onClick = {
                            val shareBody = buildString {
                                appendLine("【${news.region.label}版】$title")
                                appendLine()
                                appendLine(body)
                                if (showSummary && summary != null) {
                                    appendLine()
                                    appendLine("【日本語要約】")
                                    appendLine(summary!!.text)
                                }
                                appendLine()
                                append(news.sourceUrl)
                            }
                            context.startActivity(
                                Intent.createChooser(
                                    Intent(Intent.ACTION_SEND).apply {
                                        type = "text/plain"
                                        putExtra(Intent.EXTRA_TEXT, shareBody)
                                    },
                                    "ニュースを共有"
                                )
                            )
                        }) {
                            Icon(Icons.Default.Share, null, Modifier.size(18.dp))
                            Spacer(Modifier.width(5.dp))
                            Text("共有")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun NewsThumbnail(news: NewsItem) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(180.dp)
            .background(
                Brush.linearGradient(
                    listOf(
                        MaterialTheme.colorScheme.primary.copy(alpha = 0.72f),
                        MaterialTheme.colorScheme.secondary.copy(alpha = 0.58f),
                        MaterialTheme.colorScheme.tertiary.copy(alpha = 0.62f)
                    )
                )
            )
    ) {
        if (!news.imageUrl.isNullOrBlank()) {
            AsyncImage(
                model = news.imageUrl,
                contentDescription = news.originalTitle,
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Crop
            )
            Box(
                Modifier
                    .fillMaxSize()
                    .background(
                        Brush.verticalGradient(
                            listOf(
                                Color.Transparent,
                                Color.Black.copy(alpha = 0.06f),
                                Color.Black.copy(alpha = 0.65f)
                            )
                        )
                    )
            )
        }

        Column(
            modifier = Modifier.align(Alignment.BottomStart).padding(16.dp)
        ) {
            Text(
                "${news.region.flag} ${news.category}",
                color = Color.White,
                fontWeight = FontWeight.Bold,
                fontSize = 17.sp
            )
            Text("✦ ･ﾟ: *✧･ﾟ:*", color = Color.White.copy(alpha = 0.82f))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SettingsScreen(
    themeMode: ThemeMode,
    autoUpdate: Boolean,
    wifiOnly: Boolean,
    releaseInfo: ReleaseInfo?,
    updateMessage: String?,
    onBack: () -> Unit,
    onThemeChanged: (ThemeMode) -> Unit,
    onAutoUpdateChanged: (Boolean) -> Unit,
    onWifiOnlyChanged: (Boolean) -> Unit,
    onCheckUpdate: () -> Unit
) {
    val context = LocalContext.current
    val prefs = remember { AppPreferences(context) }
    val scope = rememberCoroutineScope()
    var downloadId by remember { mutableStateOf<Long?>(null) }
    var installStatus by remember { mutableStateOf<String?>(null) }
    var modelStatus by remember { mutableStateOf<String?>(null) }
    var modelUri by remember { mutableStateOf(prefs.ggufModelUri) }
    var modelName by remember {
        mutableStateOf(prefs.ggufModelName ?: LocalGemmaManager.displayName(context, prefs.ggufModelUri))
    }

    val modelPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            runCatching {
                context.contentResolver.takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION
                )
            }
            val name = LocalGemmaManager.displayName(context, uri.toString())
                ?: uri.lastPathSegment
                ?: "選択したGGUF"
            modelUri = uri.toString()
            modelName = name
            prefs.ggufModelUri = modelUri
            prefs.ggufModelName = modelName
            modelStatus = "モデルを選択しました。最初の翻訳 / 要約時に読み込みます。"
            scope.launch { LocalGemmaManager.release() }
        }
    }

    DisposableEffect(downloadId, releaseInfo) {
        val id = downloadId
        val release = releaseInfo
        if (id == null || release == null) return@DisposableEffect onDispose { }
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(receiverContext: Context?, intent: Intent?) {
                if (intent?.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L) != id) return
                scope.launch {
                    installStatus = "SHA-256を検証しています…"
                    val expected = runCatching {
                        GitHubUpdateManager.fetchChecksum(release.checksumUrl)
                    }.getOrNull()
                    if (expected.isNullOrBlank()) {
                        installStatus = "チェックサムが見つからないためインストールを中止しました"
                        return@launch
                    }
                    val verified = runCatching {
                        GitHubUpdateManager.verifyDownloadedApk(context, id, expected)
                    }.getOrDefault(false)
                    if (!verified) {
                        installStatus = "APKの検証に失敗しました。インストールしません"
                        return@launch
                    }
                    installStatus = if (GitHubUpdateManager.installDownloadedApk(context, id)) {
                        "Androidのインストール画面を開きました"
                    } else {
                        "「この提供元を許可」を有効にしてから、もう一度アップデートしてください"
                    }
                }
            }
        }
        ContextCompat.registerReceiver(
            context,
            receiver,
            IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE),
            ContextCompat.RECEIVER_NOT_EXPORTED
        )
        onDispose { runCatching { context.unregisterReceiver(receiver) } }
    }

    Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            TopAppBar(
                title = { Text("設定", fontWeight = FontWeight.Bold) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Transparent),
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, "戻る")
                    }
                }
            )
        }
    ) { padding ->
        LazyColumn(
            Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                SettingsCard("🎨 外観", "ライト、ダーク、端末設定に合わせて切り替えます") {
                    ThemeMode.entries.forEach { mode ->
                        Row(
                            Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).padding(vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            RadioButton(selected = themeMode == mode, onClick = { onThemeChanged(mode) })
                            Text(
                                when (mode) {
                                    ThemeMode.SYSTEM -> "端末設定に合わせる"
                                    ThemeMode.LIGHT -> "ライト"
                                    ThemeMode.DARK -> "ダーク"
                                }
                            )
                        }
                    }
                }
            }

            item {
                SettingsCard("🧠 ローカルGemma 4", "端末内のGGUFを翻訳と日本語要約に使います") {
                    Text(
                        "ニュースは通常は各国の原文で表示します。記事の「日本語に翻訳」または「日本語要約」を押した時だけ選択したGGUFを実行します。本文は外部へ送信しません。",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Spacer(Modifier.height(12.dp))

                    Surface(
                        shape = RoundedCornerShape(16.dp),
                        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.72f)
                    ) {
                        Column(Modifier.fillMaxWidth().padding(14.dp)) {
                            Text("選択中のモデル", style = MaterialTheme.typography.labelMedium)
                            Text(
                                modelName ?: "未選択",
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(top = 3.dp)
                            )
                            Text(
                                "GGUF / llama.cpp · Context 4096 · CPU/NEON",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.72f),
                                modifier = Modifier.padding(top = 4.dp)
                            )
                        }
                    }

                    Button(
                        onClick = { modelPicker.launch(arrayOf("application/octet-stream", "*/*")) },
                        modifier = Modifier.fillMaxWidth().padding(top = 12.dp)
                    ) {
                        Icon(Icons.Default.FolderOpen, null)
                        Spacer(Modifier.width(8.dp))
                        Text("GGUFを選択")
                    }

                    OutlinedButton(
                        onClick = {
                            val uri = modelUri
                            if (uri.isNullOrBlank()) {
                                modelStatus = "先にGGUFを選択してください。"
                            } else {
                                modelStatus = "GGUFを読み込んでいます…"
                                scope.launch {
                                    runCatching { LocalGemmaManager.warmUp(context, uri) }
                                        .onSuccess { modelStatus = "モデルを読み込みました。翻訳 / 要約できます。" }
                                        .onFailure { modelStatus = it.message ?: "モデル読み込みに失敗しました。" }
                                }
                            }
                        },
                        enabled = !modelUri.isNullOrBlank(),
                        modifier = Modifier.fillMaxWidth().padding(top = 8.dp)
                    ) {
                        Icon(Icons.Default.AutoAwesome, null)
                        Spacer(Modifier.width(8.dp))
                        Text("モデル読み込みテスト")
                    }

                    modelStatus?.let {
                        Text(it, Modifier.padding(top = 8.dp), style = MaterialTheme.typography.bodySmall)
                    }
                }
            }

            item {
                SettingsCard("🔄 アップデート", "GitHub Releasesから安全に更新します") {
                    Text("現在のバージョン  v${BuildConfig.VERSION_NAME}", fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(8.dp))
                    SettingSwitch("起動時に更新を確認", autoUpdate, onAutoUpdateChanged)
                    SettingSwitch("Wi-Fi時のみAPKをダウンロード", wifiOnly, onWifiOnlyChanged)
                    Spacer(Modifier.height(8.dp))
                    Button(onClick = onCheckUpdate, modifier = Modifier.fillMaxWidth()) {
                        Icon(Icons.Default.Refresh, null)
                        Spacer(Modifier.width(8.dp))
                        Text("アップデートを確認")
                    }
                    updateMessage?.let {
                        Text(it, Modifier.padding(top = 8.dp), style = MaterialTheme.typography.bodySmall)
                    }
                    releaseInfo?.let { release ->
                        Spacer(Modifier.height(12.dp))
                        Surface(
                            shape = RoundedCornerShape(18.dp),
                            color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.7f),
                            contentColor = MaterialTheme.colorScheme.onPrimaryContainer
                        ) {
                            Column(Modifier.padding(14.dp)) {
                                Text("最新版 ${release.tagName}", fontWeight = FontWeight.Bold)
                                Text(
                                    release.notes.ifBlank { "更新内容はGitHub Releasesで確認できます。" },
                                    maxLines = 6,
                                    style = MaterialTheme.typography.bodySmall
                                )
                            }
                        }
                        Button(
                            onClick = {
                                if (release.checksumUrl == null) {
                                    installStatus = "ReleaseにSHA-256ファイルがありません。安全のため更新を中止しました"
                                } else {
                                    downloadId = GitHubUpdateManager.enqueueDownload(context, release, wifiOnly)
                                    installStatus = "APKをダウンロードしています…"
                                }
                            },
                            modifier = Modifier.fillMaxWidth().padding(top = 10.dp)
                        ) {
                            Text("${release.tagName} にアップデート")
                        }
                    }
                    installStatus?.let {
                        Text(it, Modifier.padding(top = 8.dp), style = MaterialTheme.typography.bodySmall)
                    }
                }
            }

            item {
                SettingsCard("🛡️ このアプリについて", "非公式ファンアプリ") {
                    Text(
                        "Google Playでは配布しません。APKは必ず IKEGAMI-99/KRPR_news のGitHub Releasesから取得してください。",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Spacer(Modifier.height(8.dp))
                    TextButton(onClick = {
                        context.startActivity(
                            Intent(Intent.ACTION_VIEW, Uri.parse("https://github.com/IKEGAMI-99/KRPR_news"))
                        )
                    }) {
                        Icon(Icons.Default.OpenInNew, null)
                        Spacer(Modifier.width(6.dp))
                        Text("GitHubを開く")
                    }
                }
            }
        }
    }
}

@Composable
private fun SettingsCard(
    title: String,
    subtitle: String,
    content: @Composable ColumnScope.() -> Unit
) {
    Card(
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.94f),
            contentColor = MaterialTheme.colorScheme.onSurface
        )
    ) {
        Column(Modifier.fillMaxWidth().padding(18.dp)) {
            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface
            )
            Text(
                subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.68f)
            )
            Spacer(Modifier.height(12.dp))
            content()
        }
    }
}

@Composable
private fun SettingSwitch(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(label, Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurface)
        Switch(checked = checked, onCheckedChange = onChange)
    }
}
