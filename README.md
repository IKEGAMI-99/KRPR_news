# Kirapara News ✨

日本版「きらめきパラダイス」、中国版「以闪亮之名」、グローバル版「Life Makeover」、韓国版「Stylight」の公式ニュースを1つのタイムラインで追うための**非公式Androidファンアプリ**です。

> [!IMPORTANT]
> 本アプリは非公式ファンアプリです。Archosaur Games、VVANNA GIRLS、各地域の運営会社・SNS事業者とは関係ありません。

## 📥 最新版APK

**現在の正式版: v0.3.0**

### [⬇️ Kirapara News v0.3.0 APKをダウンロード](https://github.com/IKEGAMI-99/KRPR_news/releases/download/v0.3.0/Kirapara-News-v0.3.0.apk)

- [最新のGitHub Releaseを開く](https://github.com/IKEGAMI-99/KRPR_news/releases/latest)
- [すべてのReleasesを見る](https://github.com/IKEGAMI-99/KRPR_news/releases)
- SHA-256: `056d2e6513ebd80dd17320dc6e0064efbdcdc75783e05e0cdb23f2ae641fb968`

> [!WARNING]
> APKは必ずこのリポジトリのGitHub Releasesから取得してください。第三者が再配布したAPKは使用しないでください。

## ✨ v0.3.0

翻訳方式を全面的に変更しました。

- ニュースは**各国の原文を標準表示**
- サーバー翻訳を廃止
- Google Cloud Translationを廃止
- ML Kit翻訳を廃止
- 設定から端末内の **GGUFモデルを選択**
- llama.cppでGemma 4などのGGUFを端末内実行
- 海外記事に「日本語に翻訳」ボタンを追加
- 全記事に「日本語要約」ボタンを追加
- 翻訳後は「原文に戻す」で即切り替え
- 翻訳・要約はユーザーが押した記事だけ実行
- モデルは一度ロードしたらメモリ上で再利用
- 翻訳・要約結果を記事単位で端末キャッシュ
- GGUF自体はアプリ領域へコピーせず、Androidのファイル選択権限から直接読み込み
- `versionCode 7` / `versionName 0.3.0`

## 🧠 ローカルGemma 4

設定 → **ローカルGemma 4** → **GGUFを選択** から、端末に保存済みのGGUFを指定します。

```text
端末内の model.gguf
        ↓
Android ファイル選択
        ↓
永続読み取り権限
        ↓
llama.cpp
        ↓
翻訳 / 日本語要約
        ↓
端末内キャッシュ
```

モデルやニュース本文を翻訳APIへ送信しません。ニュースを見るだけならモデルはロードされず、「日本語に翻訳」または「日本語要約」を押した時に初めてロードします。

### 推論設定

- GGUF / llama.cpp
- Context: 4096 tokens
- CPU/NEON
- Threads: 端末CPU数に応じて4〜8
- arm64-v8a
- Gemma 4対応llama.cppを使用

v0.3.0で使用するAARは `dev.ffmpegkit-maintained:llama-android:0.1.1` で、llama.cpp b9878を内包しています。

> [!NOTE]
> モデルサイズと量子化によって必要RAM・生成速度は大きく変わります。大きなGemma 4では初回ロードや生成に時間がかかる場合があります。

## 🌐 ニュース取得

GitHub Actionsは**原文ニュースを集めるだけ**です。翻訳処理は行いません。

```text
公式公開ページ / 公開RSS / RSSHub
        ↓
GitHub Actions 定期収集
        ↓
SNS本文の不要部分を整理
        ↓
data/news.json（原文）
        ↓
Androidアプリ
```

GitHub Actionsが1時間ごとにニュースを取得し、`data/news.json` を更新します。アプリはまずこの軽量キャッシュを読み、利用できない場合のみ公開RSS / RSSHub等へ直接アクセスします。

## 📰 接続しているニュースソース

| 地域 | ソース | 方法 | SNS APIキー |
| --- | --- | --- | --- |
| 🇯🇵 日本 | きらめきパラダイス公式YouTube | YouTube公開RSS | 不要 |
| 🇨🇳 中国 | 以闪亮之名 公式Weibo | RSSHub 複数ホスト | 不要 |
| 🇨🇳 中国 | 以闪亮之名 公式Bilibili | RSSHub | 不要 |
| 🌎 Global | Life Makeover公式YouTube | 公開ページ + YouTube RSS | 不要 |
| 🇰🇷 韓国 | Stylight公式YouTube | 公開ページ + YouTube RSS | 不要 |

公開HTML・RSS・RSSHubは提供側の仕様変更で取得できなくなる場合があります。一つの取得先が失敗しても他の地域は表示できるようにしています。

## 🖼️ サムネイル

優先順位:

1. 記事または動画固有の画像
2. YouTube動画サムネイル
3. 各地域公式サイトの画像
4. アプリ内グラデーション背景

Weiboの `timeline_card_small_*_default` などの汎用プレースホルダー画像は記事画像として使用しません。

## 📱 主な機能

- 🇯🇵 日本 / 🇨🇳 中国 / 🌎 Global / 🇰🇷 韓国の統合タイムライン
- 各国原文を標準表示
- ローカルGGUFによるオンデマンド日本語翻訳
- ローカルGGUFによる日本語要約
- 翻訳 / 要約キャッシュ
- 折りたたみ式ニュースカード
- 地域フィルター
- 記事画像・YouTubeサムネイル表示
- Android標準共有シート
- 公式投稿を開くボタン
- ライト / ダーク / 端末設定連動テーマ
- GitHub Releasesの最新版チェック
- アプリ内APKダウンロード
- SHA-256検証後にAndroid標準インストーラーへ引き渡す更新フロー

## 📱 対応環境

- Android 8.0 (API 26) 以上
- arm64-v8a
- GGUFファイルはユーザーが用意
- Google Playでは配布しません

## 🔒 プライバシー

- 翻訳・要約は端末内
- GGUFを外部へ送信しない
- ニュース本文を翻訳APIへ送信しない
- ユーザー登録不要
- 位置情報、連絡先、写真ライブラリ不要
- 選択したGGUFへの読み取り権限のみ保持

ネットワーク通信は公開ニュース取得、ニュースキャッシュ取得、GitHub Releasesの更新確認に使用します。

## 🔄 アプリ内アップデート

設定 → アップデートからGitHub Releasesの最新版を確認できます。

```text
GitHub Releases
      ↓
versionNameを比較
      ↓
APK + SHA-256を取得
      ↓
SHA-256検証
      ↓
Android標準インストーラー
```

## 🧱 技術構成

- Kotlin
- Jetpack Compose / Material 3
- Coroutines
- llama.cpp / GGUF
- `dev.ffmpegkit-maintained:llama-android:0.1.1`
- Android Storage Access Framework
- Coil
- SharedPreferences
- Android DownloadManager
- GitHub Actions

## 🛠️ ビルド

JDK 17とGradle 8.9を使用します。

```bash
gradle assembleDebug
```

生成先:

```text
app/build/outputs/apk/debug/app-debug.apk
```

## 🚀 署名済みRelease

GitHub Repository Secretsへ以下を登録します。

- `KEYSTORE_BASE64`
- `KEYSTORE_PASSWORD`
- `KEY_ALIAS`
- `KEY_PASSWORD`

翻訳API用Secretは不要です。

`versionName` を更新してmainへpushすると、固定署名済みAPKとSHA-256ファイルをGitHub Releaseへ自動公開します。

## ⚖️ コンテンツと免責

ニュースでは投稿元と公式URLを明示し、原文へ戻れる設計です。公開RSS・公開ページ・各サービスの規約や仕様変更に応じて取得方法を調整します。

## Version

Current version: **v0.3.0**
