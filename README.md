# Kirapara News ✨

日本版「きらめきパラダイス」、中国版「以闪亮之名」、グローバル版「Life Makeover」、韓国版「Stylight」の公式ニュースを1つのタイムラインで追うための**非公式Androidファンアプリ**です。

> [!IMPORTANT]
> 本アプリは非公式ファンアプリです。Archosaur Games、VVANNA GIRLS、各地域の運営会社・SNS事業者とは関係ありません。

## ✨ v0.2.0

v0.2では、外部の有料SNS APIや翻訳APIを使わずに動かす方向へ変更しました。

- 🇯🇵 日本公式YouTubeの公開RSSを取得
- 🌎 Global公式YouTube `@LifeMakeover` の公開ページからchannel IDを解決してRSSを取得
- 🇰🇷 Stylight公式YouTube `@stylight_official` を同様に取得
- 🇨🇳 中国公式WeiboをRSSHub経由で取得
- 複数ソースを同時取得し、1つ落ちても他のニュースは表示
- URL単位の簡易重複除去
- 公開日時順に統合
- 中国語 / 英語 / 韓国語 → 日本語を **ML Kitのオンデバイス翻訳** で処理
- 翻訳本文を外部の翻訳APIへ送信しない
- 原文はそのまま保持し、従来通りカードから日本語 / 原文を切替可能
- `versionCode 2` / `versionName 0.2.0`

### ローカル翻訳について

翻訳には `com.google.mlkit:translate:17.0.3` を使用しています。

初めて中国語・英語・韓国語の記事を翻訳するときは、対応する翻訳モデルを端末へダウンロードするため通信が必要です。モデル取得後の翻訳処理は端末内で行われ、ニュース本文を外部の翻訳APIへ送る構成ではありません。

翻訳モデルの取得に失敗した場合は、ニュース自体を消さず原文を表示するフォールバック動作にしています。

> ML Kit On-Device Translationを使用するため、Googleの適用される帰属・利用ガイドラインに従います。

### API不要ニュース取得の考え方

```text
公式公開ページ / 公開RSS
        ↓
YouTube RSS / RSSHub
        ↓
ApiFreeNewsRepository
        ↓
重複除去・日時順ソート
        ↓
ML Kit On-Device Translation
        ↓
Kirapara News タイムライン
```

SNSの非公開APIキー、X APIキー、YouTube Data APIキー、翻訳APIキーは使用しません。

公開HTML・RSSの仕様変更やRSSHub側の障害で一部ソースが取得できなくなる可能性はあります。そのため取得処理はソースごとに分離し、1ソースの失敗でアプリ全体が止まらない構成です。

## v0.1から継続している機能

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

## 📰 v0.2で接続しているニュースソース

| 地域 | ソース | 方法 | APIキー |
| --- | --- | --- | --- |
| 🇯🇵 日本 | きらめきパラダイス公式YouTube | YouTube公開RSS | 不要 |
| 🇨🇳 中国 | 以闪亮之名 公式Weibo | RSSHub | 不要 |
| 🌎 Global | Life Makeover公式YouTube | 公開ページ + YouTube RSS | 不要 |
| 🇰🇷 韓国 | Stylight公式YouTube | 公開ページ + YouTube RSS | 不要 |

今後、公式Webサイト、Bilibili、Naverなども同じ `PublicNewsSource` 境界へ追加していきます。

## 🎨 デザイン

ライトモードはパールホワイト、淡いピンク、ラベンダー、水色。ダークモードは黒一色ではなく、ダークパープル、ネイビー、ピンクを基調にしています。

公式ゲームUIや公式素材をそのまま複製せず、「きらめきパラダイス」の華やかさを意識した独自デザインです。

## 🧱 技術構成

- Kotlin
- Jetpack Compose / Material 3
- Coroutines
- Android XmlPullParser
- HttpURLConnection
- ML Kit On-Device Translation
- SharedPreferences（テーマ・更新設定）
- Android DownloadManager
- GitHub REST API
- Coil

## 🗂️ 構成

```text
app/src/main/java/com/ikegami99/krprnews/
├ MainActivity.kt
├ data/
│  ├ News.kt
│  ├ DemoNewsRepository.kt
│  └ ApiFreeNewsRepository.kt
├ translation/
│  └ LocalTranslationManager.kt
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

その後、`v0.2.0` のようなタグをpushすると `.github/workflows/release.yml` が以下を生成します。

```text
Kirapara-News-v0.2.0.apk
Kirapara-News-v0.2.0.apk.sha256
```

署名鍵は絶対にリポジトリへコミットしないでください。全バージョンで同じ署名鍵を使わないとAndroidの上書きアップデートができなくなります。

## 🛡️ プライバシー

ユーザー登録、位置情報、連絡先、写真ライブラリ等を必要としません。ネットワーク通信は公開ニュース取得、翻訳モデルの初回取得、GitHub Releasesの更新確認に使用します。

## ⚖️ コンテンツと免責

ニュースでは投稿元と公式URLを明示し、原文へ戻れる設計です。公開RSS・公開ページ・各サービスの規約や仕様変更に応じて取得方法を調整します。

## Version

Current development version: **v0.2.0**
