# Kirapara News ✨

日本版「きらめきパラダイス」、中国版「以闪亮之名」、グローバル版「Life Makeover」、韓国版「Stylight」の公式ニュースを1つのタイムラインで追うための**非公式Androidファンアプリ**です。

> [!IMPORTANT]
> 本アプリは非公式ファンアプリです。Archosaur Games、VVANNA GIRLS、各地域の運営会社・SNS事業者とは関係ありません。

## ✨ v0.2.1

v0.2.1では実機確認をもとにニュース取得と表示を改善しました。

- 🇯🇵 日本公式YouTubeは公式RSSを直接取得
- 🇨🇳 中国は公式Weiboに加え、公式Bilibili（UID `676200579`）を追加
- 🌎 Global公式YouTubeは `/c/LifeMakeover` と `@LifeMakeover` の複数URLからchannel IDを解決
- 🇰🇷 Stylight公式YouTubeは `@stylight_official` の公開ページとRSSHubをフォールバック利用
- RSSHubは複数の公開ホストを順番に試し、1サービス障害で地域全体が消えにくい構成へ変更
- YouTube HTMLからのchannel ID抽出パターンを複数用意
- ニュースカード上部に取得できた画像・YouTubeサムネイルを表示
- RSS/RSSHub本文中の画像URLも可能な範囲で抽出
- ダークモード時のカード本文・見出し・設定画面文字色を明示的に白系へ修正
- `versionCode 3` / `versionName 0.2.1`

## 🌐 APIキー不要 + ローカル翻訳

外部の有料SNS APIや翻訳APIを使わずに動かす方向で開発しています。

中国語 / 英語 / 韓国語 → 日本語は **ML Kit On-Device Translation** を利用します。初回だけ対応言語モデルを端末へダウンロードするため通信が必要ですが、モデル取得後の翻訳処理は端末内で行われます。

翻訳モデルの取得に失敗した場合もニュース自体を消さず、原文を表示します。

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

X APIキー、YouTube Data APIキー、翻訳APIキーは使用していません。

## 📰 接続しているニュースソース

| 地域 | ソース | 方法 | APIキー |
| --- | --- | --- | --- |
| 🇯🇵 日本 | きらめきパラダイス公式YouTube | YouTube公開RSS | 不要 |
| 🇨🇳 中国 | 以闪亮之名 公式Weibo | RSSHub 複数ホスト | 不要 |
| 🇨🇳 中国 | 以闪亮之名 公式Bilibili | RSSHub `/bilibili/user/video/676200579` | 不要 |
| 🌎 Global | Life Makeover公式YouTube | 公開ページ + YouTube RSS + RSSHub | 不要 |
| 🇰🇷 韓国 | Stylight公式YouTube | 公開ページ + YouTube RSS + RSSHub | 不要 |

公開HTML・RSS・RSSHubの仕様変更で一部ソースが取得できなくなる可能性があります。そのためソース単位でエラーを分離し、一つ失敗しても他のニュース取得を続けます。

## 📱 主な機能

- 🇯🇵 日本 / 🇨🇳 中国 / 🌎 Global / 🇰🇷 韓国の統合タイムライン
- 日本語 / 原文のワンタップ切替
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

1. このリポジトリの **Releases** を開く
2. 最新版の `Kirapara-News-vX.X.X.apk` をダウンロード
3. APKを開く
4. Androidから求められた場合は、利用中のブラウザまたはファイルアプリについて「この提供元からのアプリを許可」を有効にする
5. Androidの確認画面でインストールする

GitHub Actionsの `Kirapara-News-debug` は開発確認用です。継続利用・上書き更新には同じ署名鍵で作られたReleasesのAPKを使ってください。

## ⚠️ セキュリティ警告

Google Play以外からAPKをインストールするため、Androidから「提供元不明のアプリ」等の警告が表示される場合があります。これはサイドロードAPKに対するAndroidの標準的な保護機能です。

- APKは `IKEGAMI-99/KRPR_news` のGitHub Releasesからのみ取得してください
- 第三者サイト、SNS、ファイル共有サービス等で再配布されたAPKをインストールしないでください
- 各正式ReleaseにはAPKと `.sha256` を掲載します
- アプリ内更新もSHA-256が確認できないReleaseはインストールしません
- Androidが署名不一致を警告した場合はインストールを中止してください

## 🔄 アプリ内アップデート

設定 → アップデートから `releases/latest` を確認します。

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

## 🎨 デザイン

ライトモードはパールホワイト、淡いピンク、ラベンダー、水色。ダークモードはダークパープル、ネイビー、ピンクを基調にしています。

記事に画像がある場合はカード上部へ大きく表示し、下側にカテゴリを重ねます。画像がない場合は従来のグラデーション表示へフォールバックします。

## 🧱 技術構成

- Kotlin
- Jetpack Compose / Material 3
- Coroutines
- Android XmlPullParser
- HttpURLConnection
- ML Kit On-Device Translation
- Coil
- SharedPreferences
- Android DownloadManager
- GitHub REST API

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

`v0.2.1` のようなタグをpushすると、署名済みAPKとSHA-256ファイルをGitHub Releaseへ公開するワークフローを用意しています。

署名鍵は絶対にリポジトリへコミットしないでください。全バージョンで同じ署名鍵を使わないとAndroidの上書きアップデートができなくなります。

## 🛡️ プライバシー

ユーザー登録、位置情報、連絡先、写真ライブラリ等を必要としません。ネットワーク通信は公開ニュース取得、翻訳モデルの初回取得、GitHub Releasesの更新確認に使用します。

## ⚖️ コンテンツと免責

ニュースでは投稿元と公式URLを明示し、原文へ戻れる設計です。公開RSS・公開ページ・各サービスの規約や仕様変更に応じて取得方法を調整します。

## Version

Current development version: **v0.2.1**
