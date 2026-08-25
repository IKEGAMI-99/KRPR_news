# Kirapara News ✨

日本版「きらめきパラダイス」、中国版「以闪亮之名」、グローバル版「Life Makeover」、韓国版「Stylight」の公式ニュースを1つのタイムラインで追うための**非公式Androidファンアプリ**です。

> [!IMPORTANT]
> 本アプリは非公式ファンアプリです。Archosaur Games、VVANNA GIRLS、各地域の運営会社・SNS事業者とは関係ありません。

## 📥 最新版APKをダウンロード

**現在の正式版: v0.2.4**

### [⬇️ Kirapara News v0.2.4 APKをダウンロード](https://github.com/IKEGAMI-99/KRPR_news/releases/download/v0.2.4/Kirapara-News-v0.2.4.apk)

- [最新のGitHub Releaseを開く](https://github.com/IKEGAMI-99/KRPR_news/releases/latest)
- [すべてのReleasesを見る](https://github.com/IKEGAMI-99/KRPR_news/releases)
- SHA-256: `695e435cd99aaccc31dc3fe771299e51bee03325aeadac685a76e882e4d876b2`

> [!WARNING]
> APKは必ずこのリポジトリのGitHub Releasesから取得してください。第三者が再配布したAPKは使用しないでください。

## ✨ v0.2.4

v0.2.4では翻訳、サムネイル、ニュースカードの読みやすさを改善しました。

- ニュースカードを折りたたみ式へ変更
- 閉じた状態ではタイトル最大2行 + 本文最大3行を表示
- 「続きを読む」で全文を展開し、「閉じる」で元に戻せる
- 日本語 / 原文の切り替えは折りたたみ時でも利用可能
- Weiboのハッシュタグ、定型ダウンロード文などを翻訳前に除去
- Google Cloud Translationによるサーバー側日本語翻訳に対応
- Google翻訳済みキャッシュが無い記事だけML Kit On-Device Translationへフォールバック
- Weibo等の汎用プレースホルダー画像を記事サムネイルとして扱わないよう修正
- 記事画像を取得できない場合、日本・中国・韓国は各地域の公式サイト画像をフォールバック表示
- YouTubeは実際の動画サムネイルを優先
- 読み込み中インジケータと取得失敗時の再読み込み画面を追加
- 画面下のバージョン表記を自動取得へ変更
- `versionCode 6` / `versionName 0.2.4`

## 🌐 ニュース取得と翻訳

ニュース取得そのものは、X APIやYouTube Data APIなどの有料・認証APIに依存しない構成です。

```text
公式公開ページ / 公開RSS / RSSHub
        ↓
GitHub Actions 定期収集
        ↓
SNS本文の不要部分を整理
        ↓
Google Cloud Translation（設定時）
        ↓
data/news.json
        ↓
Androidアプリ
        ↓
未翻訳記事のみML Kitで端末内翻訳
```

GitHub Actionsが1時間ごとにニュースを取得し、`data/news.json` を更新します。アプリはまずこの軽量キャッシュを読み、キャッシュが利用できない場合のみ公開RSS / RSSHub等へ直接アクセスします。

### Google Cloud Translationを使う場合

Google Cloud TranslationのAPIキーは**APKやソースコードへ直接書きません**。GitHub Repository Secretとして保存します。

Secret名:

```text
GOOGLE_TRANSLATE_API_KEY
```

設定場所:

```text
Repository
→ Settings
→ Secrets and variables
→ Actions
→ New repository secret
```

設定後、GitHub Actionsの **Refresh News Cache** を実行すると、新規・変更された海外記事をGoogle Cloud Translationで日本語化してキャッシュへ保存します。

APIキーが設定されていない場合でもアプリは動作します。その場合は中国語 / 英語 / 韓国語をML Kit On-Device Translationで端末内翻訳します。

> [!CAUTION]
> `GOOGLE_TRANSLATE_API_KEY` をREADME、ソースコード、Issue、スクリーンショット等へ掲載しないでください。

## 📰 接続しているニュースソース

| 地域 | ソース | 方法 | SNS APIキー |
| --- | --- | --- | --- |
| 🇯🇵 日本 | きらめきパラダイス公式YouTube | YouTube公開RSS | 不要 |
| 🇨🇳 中国 | 以闪亮之名 公式Weibo | RSSHub 複数ホスト | 不要 |
| 🇨🇳 中国 | 以闪亮之名 公式Bilibili | RSSHub | 不要 |
| 🌎 Global | Life Makeover公式YouTube | 公開ページ + YouTube RSS | 不要 |
| 🇰🇷 韓国 | Stylight公式YouTube | 公開ページ + YouTube RSS | 不要 |

公開HTML・RSS・RSSHubは提供側の仕様変更で取得できなくなる場合があります。ソース単位でエラーを分離し、一つの取得先が失敗しても他の地域を表示できる構成にしています。

## 🖼️ サムネイル

優先順位は以下です。

1. 記事または動画固有の画像
2. YouTube動画サムネイル
3. 地域公式サイトのフォールバック画像
4. アプリ内グラデーション背景

Weiboが返す `timeline_card_small_*_default` 等の汎用画像は記事画像として使用しません。

## 📱 主な機能

- 🇯🇵 日本 / 🇨🇳 中国 / 🌎 Global / 🇰🇷 韓国の統合タイムライン
- 日本語 / 原文のワンタップ切替
- 折りたたみ式ニュースカード
- 地域フィルター
- 記事画像・YouTubeサムネイル表示
- Android標準共有シート
- 公式投稿を開くボタン
- パール・ピンク・ラベンダーを基調にした独自UI
- ライト / ダーク / 端末設定連動テーマ
- GitHub Releasesの最新版チェック
- アプリ内APKダウンロード
- SHA-256検証後にAndroid標準インストーラーへ引き渡す更新フロー

## 📱 対応環境

- Android 8.0 (API 26) 以上
- Google Playでは配布しません
- 正式APKはこのリポジトリのGitHub Releasesから配布します

## 📥 APKのインストール

1. README上部の **「Kirapara News v0.2.4 APKをダウンロード」** または **Releases** を開く
2. `Kirapara-News-vX.X.X.apk` をダウンロード
3. APKを開く
4. Androidから求められた場合は、利用中のブラウザまたはファイルアプリについて「この提供元からのアプリを許可」を有効にする
5. Androidの確認画面でインストールする

GitHub ActionsのDebug APKは開発確認用です。継続利用・アプリ内アップデートにはReleasesの正式署名APKを使用してください。

## ⚠️ セキュリティ警告

Google Play以外からAPKをインストールするため、Androidから「提供元不明のアプリ」等の警告が表示される場合があります。これはサイドロードAPKに対するAndroidの標準的な保護機能です。

- APKは `IKEGAMI-99/KRPR_news` のGitHub Releasesからのみ取得してください
- 第三者サイト、SNS、ファイル共有サービス等で再配布されたAPKをインストールしないでください
- 各正式ReleaseにはAPKと `.sha256` を掲載します
- アプリ内更新もSHA-256が確認できないReleaseはインストールしません
- Androidが署名不一致を警告した場合はインストールを中止してください

## 🔄 アプリ内アップデート

設定 → アップデートからGitHub Releasesの最新版を確認できます。

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

Androidの仕様上、ユーザー確認なしにAPKを自動インストールすることはありません。

## 🎨 デザイン

ライトモードはパールホワイト、淡いピンク、ラベンダー、水色。ダークモードはダークパープル、ネイビー、ピンクを基調にしています。

記事はコンパクトなカードとして一覧表示し、必要な記事だけ展開して全文を確認できます。

## 🧱 技術構成

- Kotlin
- Jetpack Compose / Material 3
- Coroutines
- Android XmlPullParser
- HttpURLConnection
- ML Kit On-Device Translation
- Google Cloud Translation（任意）
- Coil
- SharedPreferences
- Android DownloadManager
- GitHub REST API
- GitHub Actionsによる定期ニュース収集

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

## 🚀 署名済みRelease

GitHub Repository Secretsへ以下を登録します。

- `KEYSTORE_BASE64`
- `KEYSTORE_PASSWORD`
- `KEY_ALIAS`
- `KEY_PASSWORD`

翻訳をGoogle Cloud Translationで行う場合は追加で:

- `GOOGLE_TRANSLATE_API_KEY`

`versionName` を更新してmainへpushすると、固定署名済みAPKとSHA-256ファイルをGitHub Releaseへ自動公開します。

署名鍵は絶対にリポジトリへコミットしないでください。全バージョンで同じ署名鍵を使わないとAndroidの上書きアップデートができなくなります。

## 🛡️ プライバシー

ユーザー登録、位置情報、連絡先、写真ライブラリ等を必要としません。ネットワーク通信は公開ニュース取得、必要時の翻訳モデル取得、ニュースキャッシュ取得、GitHub Releasesの更新確認に使用します。

Google Cloud Translationを有効にした場合、GitHub Actions上で海外ニュース本文をGoogle Cloud Translationへ送信して日本語訳を生成します。ユーザーがアプリへ入力した個人情報を送信する機能はありません。

## ⚖️ コンテンツと免責

ニュースでは投稿元と公式URLを明示し、原文へ戻れる設計です。公開RSS・公開ページ・各サービスの規約や仕様変更に応じて取得方法を調整します。

## Version

Current development version: **v0.2.4**
