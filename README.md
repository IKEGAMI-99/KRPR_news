# Kirapara News ✨

日本版「きらめきパラダイス」、中国版「以闪亮之名」、グローバル版「Life Makeover」、韓国版「Stylight」の公式ニュースを1つのタイムラインで追うための**非公式Androidファンアプリ**です。

> [!IMPORTANT]
> 本アプリは非公式ファンアプリです。Archosaur Games、VVANNA GIRLS、各地域の運営会社・SNS事業者とは関係ありません。

## 📥 最新版APK

**現在の正式版: v0.3.1**

### [⬇️ Kirapara News v0.3.1 APKをダウンロード](https://github.com/IKEGAMI-99/KRPR_news/releases/download/v0.3.1/Kirapara-News-v0.3.1.apk)

- [最新のGitHub Release](https://github.com/IKEGAMI-99/KRPR_news/releases/latest)
- [すべてのReleases](https://github.com/IKEGAMI-99/KRPR_news/releases)
- SHA-256: `0aa2473aa2be488c68c4a18725f881c7a7a426d0e77c2259abb9e0b9f5ca3ceb`

> [!WARNING]
> APKは必ずこのリポジトリのGitHub Releasesから取得してください。第三者が再配布したAPKは使用しないでください。

## ✨ v0.3.1

v0.3.1ではローカルGGUFの読み込みとアップデート、診断機能を大きく修正しました。

- Androidの `content://` URIをFile Descriptor経由で直接開く方式へ変更
- 大容量GGUFをアプリ領域へコピーせず、その場で読み込み
- `GGUFを選択` で取得した永続読み取り権限を利用
- モデル読み込み失敗を診断ログへ記録
- 設定に **診断ログを書き出す / クリア** を追加
- アプリ内でAPKを直接ダウンロード
- ダウンロード中の進捗表示
- アプリ内でSHA-256を検証
- 検証成功後にAndroid標準インストーラーを自動で起動
- 「この提供元から許可」が必要な場合は設定画面へ移動し、戻った後にインストールを続行
- llama.cpp Android bindingを `io.github.ljcamargo:llamacpp-kotlin:0.4.0` へ変更
- `compileSdk 36` / `AGP 8.9.1` / `Kotlin 2.3.20` / `Gradle 8.11.1`
- `versionCode 8` / `versionName 0.3.1`

## 🧠 ローカルGemma 4 / GGUF

設定 → **ローカルGemma 4** → **GGUFを選択** から、端末に保存済みのGGUFを指定します。

```text
端末内の model.gguf
        ↓
Android Storage Access Framework
        ↓
content:// URI + File Descriptor
        ↓
llama.cpp
        ↓
翻訳 / 日本語要約
        ↓
端末内キャッシュ
```

ニュースは通常、各地域の**原文**で表示します。海外記事の **「日本語に翻訳」** または全記事の **「日本語要約」** を押した時だけローカルGGUFを実行します。

モデルやニュース本文を翻訳APIへ送信しません。翻訳・要約結果は記事とモデルごとに端末へキャッシュします。

### 現在の推論バックエンド

- GGUF / llama.cpp
- Context: 4096 tokens
- arm64-v8a
- **CPU / NEON**

### Hexagon NPUについて

llama.cpp本家にはSnapdragonのHexagon / HTP NPUバックエンドがありますが、現時点では実験的な実装です。

v0.3.1のAPKにはHexagon用 `libggml-hexagon` / `libggml-htp-vNN` を同梱していないため、現在はCPU/NEONを使用します。UI上だけNPU対応を装うことはせず、専用ネイティブビルドと実機検証ができた段階で追加する方針です。

## 🌐 ニュース取得

GitHub Actionsは**原文ニュースを集めるだけ**で、翻訳は行いません。

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

GitHub Actionsが定期的にニュースを取得します。アプリはまずGitHubの軽量キャッシュを読み、利用できない場合のみ公開RSS / RSSHub等へ直接アクセスします。

## 📰 接続中のニュースソース

| 地域 | ソース | 方法 | APIキー |
| --- | --- | --- | --- |
| 🇯🇵 日本 | きらめきパラダイス公式YouTube | YouTube公開RSS | 不要 |
| 🇨🇳 中国 | 以闪亮之名 公式Weibo | RSSHub 複数ホスト | 不要 |
| 🇨🇳 中国 | 以闪亮之名 公式Bilibili | RSSHub | 不要 |
| 🌎 Global | Life Makeover公式YouTube | 公開ページ + YouTube RSS | 不要 |
| 🇰🇷 韓国 | Stylight公式YouTube | 公開ページ + YouTube RSS | 不要 |

公開HTML・RSS・RSSHubは提供側の仕様変更で取得できなくなる場合があります。一つの取得先が失敗しても他の地域まで巻き込まない構成にしています。

## 📱 主な機能

- 🇯🇵 日本 / 🇨🇳 中国 / 🌎 Global / 🇰🇷 韓国の統合タイムライン
- 各地域の原文を標準表示
- ローカルGGUFによる日本語翻訳
- ローカルGGUFによる日本語要約
- 翻訳 / 要約結果の端末キャッシュ
- 折りたたみ式ニュースカード
- 地域フィルター
- 記事画像 / YouTubeサムネイル
- 公式投稿リンク
- Android共有
- ライト / ダーク / 端末設定連動テーマ
- GitHub Releasesからのアプリ内アップデート
- SHA-256検証
- 診断ログの書き出し

## 🧾 診断ログ

設定 → **診断ログ** から `.txt` ファイルとして書き出せます。

ログには主に以下を記録します。

- アプリバージョン
- Android / 端末 / ABI情報
- 選択中モデル名
- GGUF読み込み開始 / 成功 / 失敗
- AI翻訳 / 要約の開始・完了・エラー
- ニュース取得エラー
- アップデート確認 / ダウンロード / SHA-256検証エラー

ニュース本文そのものを大量に記録する用途にはしていません。ログは約1MBでローテーションします。

## 🔄 アプリ内アップデート

設定 → **アップデート** から最新版を確認できます。

```text
GitHub Releases
      ↓
アプリ内ダウンロード
      ↓
SHA-256検証
      ↓
検証済みAPKをFileProviderで共有
      ↓
Android標準インストーラー
```

APK取得と検証はアプリ内で完結します。

> [!NOTE]
> 通常のAndroidアプリでは、最後のOSによる「インストール」確認そのものを無人化することはできません。これはAndroidのセキュリティ仕様です。

初回など「この提供元からのアプリを許可」が必要な場合は、アプリから該当設定へ移動し、許可後にインストール処理を続行します。

## 📥 初回インストール

1. README上部の **v0.3.1 APKをダウンロード** を開く
2. `Kirapara-News-v0.3.1.apk` をダウンロード
3. APKを開く
4. 必要な場合はAndroidの「この提供元からのアプリを許可」を有効にする
5. インストールする

一度正式署名版を導入した後は、以降のバージョンをアプリ内アップデートできます。

## ⚠️ セキュリティ

- APKは `IKEGAMI-99/KRPR_news` のGitHub Releasesからのみ取得してください
- 第三者サイトやファイル共有サービスのAPKは使用しないでください
- 正式ReleaseにはAPKと `.sha256` を掲載します
- アプリ内更新でもSHA-256不一致ならインストールを中止します
- Androidが署名不一致を警告した場合はインストールを中止してください

## 🔒 プライバシー

- ローカル翻訳 / 要約の本文を外部AI APIへ送信しません
- GGUFを外部へ送信しません
- ユーザー登録不要
- 位置情報・連絡先・写真ライブラリ不要
- 選択したGGUFへの読み取り権限のみ保持

ネットワーク通信は公開ニュース取得、ニュースキャッシュ取得、GitHub Releasesの更新確認とAPK取得に使用します。

## 📱 対応環境

- Android 8.0 (API 26) 以上
- arm64-v8a
- GGUFはユーザー側で用意
- Google Playでは配布しません

## 🧱 技術構成

- Kotlin 2.3.20
- Jetpack Compose / Material 3
- Android Gradle Plugin 8.9.1
- Gradle 8.11.1
- compileSdk 36 / targetSdk 35
- llama.cpp / GGUF
- `io.github.ljcamargo:llamacpp-kotlin:0.4.0`
- Android Storage Access Framework
- FileProvider
- Coil
- SharedPreferences
- GitHub Actions

## 🛠️ ビルド

JDK 17を使用します。

```bash
gradle assembleDebug
```

生成先:

```text
app/build/outputs/apk/debug/app-debug.apk
```

## 🚀 署名済みRelease

GitHub Repository Secrets:

- `KEYSTORE_BASE64`
- `KEYSTORE_PASSWORD`
- `KEY_ALIAS`
- `KEY_PASSWORD`

翻訳API用Secretは不要です。

同じ署名鍵を全リリースで使います。署名鍵を失うと既存アプリへ上書き更新できなくなります。

## ⚖️ コンテンツと免責

ニュースでは投稿元と公式URLを明示します。公開RSS・公開ページ・各サービスの規約や仕様変更に応じて取得方法を調整します。

## Version

Current version: **v0.3.1**
