# Kirapara News ✨

日本版「きらめきパラダイス」、中国版「以闪亮之名」、グローバル版「Life Makeover」、韓国版「Stylight」の公式ニュースを1つのタイムラインで追うための**非公式Androidファンアプリ**です。

> [!IMPORTANT]
> 本アプリは非公式ファンアプリです。Archosaur Games、VVANNA GIRLS、各地域の運営会社・SNS事業者とは関係ありません。

## ✨ v0.1.0で入っているもの

- 🇯🇵 日本 / 🇨🇳 中国 / 🌎 Global / 🇰🇷 韓国 の統合タイムラインUI
- 各記事の **日本語 / 原文** ワンタップ切替
- 地域フィルター
- Android標準共有シート
- 公式投稿を開くボタン
- パール・ピンク・ラベンダーを基調にした独自UI
- ライト / ダーク / 端末設定連動テーマ
- GitHub Releasesの最新版チェック
- アプリ内APKダウンロード
- SHA-256検証後にAndroid標準インストーラーへ引き渡す更新フロー
- GitHub ActionsによるDebug APKビルド
- タグpushによる署名済みRelease APK + SHA-256公開ワークフロー

現在のニュース本文はUIと機能確認用の**デモデータ**です。`NewsRepository` を境界にしているため、次段階でSupabase / Cloudflare Workers等の収集APIへ差し替えられます。

## 📱 対応環境

- Android 8.0 (API 26) 以上
- Google Playでは配布しません
- 正式APKはこのリポジトリのGitHub Releasesから配布します

## 📥 APKのインストール

1. このリポジトリの **Releases** を開く
2. 最新版の `Kirapara-News-vX.X.X.apk` をダウンロード
3. APKを開く
4. Androidから求められた場合は、利用中のブラウザまたはファイルアプリについて「この提供元からのアプリを許可」を有効にする
5. Androidの確認画面でインストールする

GitHub Actionsの `Kirapara-News-debug` は開発確認用です。継続利用・上書き更新には同じ署名鍵で作られたReleasesのAPKを使ってください。

## ⚠️ セキュリティ警告

Google Play以外からAPKをインストールするため、Androidから「提供元不明のアプリ」等の警告が表示される場合があります。これはサイドロードAPKに対するAndroidの標準的な保護機能です。

**必ず守ってください。**

- APKは `IKEGAMI-99/KRPR_news` のGitHub Releasesからのみ取得する
- 第三者サイト、SNS、ファイル共有サービス等で再配布されたAPKをインストールしない
- 各ReleaseにはAPKと `.sha256` を掲載する
- アプリ内更新もSHA-256が確認できないReleaseはインストールしない
- Androidが署名不一致を警告した場合はインストールを中止する

## 🔄 アプリ内アップデート

設定 → アップデートから `releases/latest` を確認します。新しいバージョンがある場合、Release Notesを表示し、APKをAndroidのDownloadManagerで取得します。

```text
GitHub Releases
      ↓
最新版を確認
      ↓
versionNameを比較
      ↓
APK + SHA-256を取得
      ↓
SHA-256検証
      ↓
Android標準インストーラー
```

Androidの仕様上、ユーザー確認なしに勝手にAPKをインストールすることはありません。

## 🔐 初回だけ必要な設定

アプリ自身からアップデートAPKをインストールする場合、Android 8以降ではKirapara Newsに対して「この提供元からのアプリを許可」を有効にする必要があります。アプリは必要なときだけAndroidの該当設定画面を開きます。

## 📰 想定ニュースソース

| 地域 | タイトル | 主な候補 |
| --- | --- | --- |
| 🇯🇵 日本 | きらめきパラダイス | 公式サイト / X / YouTube / Instagram / TikTok |
| 🇨🇳 中国 | 以闪亮之名 | Weibo / Bilibili / 小紅書 / 公式サイト等 |
| 🌎 Global | Life Makeover | X / Instagram / YouTube / TikTok / Facebook / Discord |
| 🇰🇷 韓国 | Stylight | Naver Cafe / Naver Lounge / X / Instagram / YouTube等 |

SNSごとにAPI・利用規約・取得方法が異なるため、Androidアプリから各SNSを直接スクレイピングする構造にはしていません。バックエンド側で統一フォーマットへ変換し、アプリは1つのニュースAPIだけを読む構成を想定しています。

## 🎨 デザイン

ライトモードはパールホワイト、淡いピンク、ラベンダー、水色。ダークモードは黒一色ではなく、ダークパープル、ネイビー、ピンクを基調にしています。

公式ゲームUIや公式素材をそのまま複製せず、「きらめきパラダイス」の華やかさを意識した独自デザインです。

## 🧱 技術構成

- Kotlin
- Jetpack Compose / Material 3
- Coroutines
- SharedPreferences（テーマ・更新設定）
- Android DownloadManager
- GitHub REST API
- Coil導入済み（実ニュース画像接続用）

## 🗂️ 構成

```text
app/src/main/java/com/ikegami99/krprnews/
├ MainActivity.kt
├ data/
│  ├ News.kt
│  └ DemoNewsRepository.kt
├ prefs/
│  └ AppPreferences.kt
├ ui/
│  ├ KiraparaApp.kt
│  └ theme/KiraparaTheme.kt
└ update/
   └ GitHubUpdateManager.kt
```

## 🛠️ ビルド

JDK 17とGradle 8.9を使用します。

```bash
gradle assembleDebug
```

生成先:

```text
app/build/outputs/apk/debug/app-debug.apk
```

mainへのpushではGitHub ActionsもDebug APKをビルドし、Workflow Artifactとして保存します。

## 🚀 署名済みReleaseの作り方

GitHub Repository Secretsへ以下を登録します。

- `KEYSTORE_BASE64` : release keystoreをBase64化した文字列
- `KEYSTORE_PASSWORD`
- `KEY_ALIAS`
- `KEY_PASSWORD`

その後、`v0.1.0` のようなタグをpushすると `.github/workflows/release.yml` が以下を生成します。

```text
Kirapara-News-v0.1.0.apk
Kirapara-News-v0.1.0.apk.sha256
```

署名鍵は絶対にリポジトリへコミットしないでください。全バージョンで同じ署名鍵を使わないとAndroidの上書きアップデートができなくなります。

## 🛡️ プライバシー

初期版ではユーザー登録、位置情報、連絡先、写真ライブラリ等を必要としません。ネットワーク通信はニュース取得とGitHub Releasesの更新確認に使用します。

## ⚖️ コンテンツと免責

ニュースでは投稿元と公式URLを明示し、原文へ戻れる設計にします。各SNS・公式サイトのAPI、利用規約、著作権に応じて取得・表示方法を調整します。

## Version

Current development version: **v0.1.0**
