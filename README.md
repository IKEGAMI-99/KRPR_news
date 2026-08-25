# Kirapara News ✨

日本版「きらめきパラダイス」、中国版「以闪亮之名」、グローバル版「Life Makeover」、韓国版「Stylight」の公式ニュースを1つのタイムラインで追うための**非公式Androidファンアプリ**です。

> [!IMPORTANT]
> 本アプリは非公式ファンアプリです。Archosaur Games、VVANNA GIRLS、各地域の運営会社・SNS事業者とは関係ありません。

## 📥 最新版APK

**現在の正式版: v0.3.4**

### [⬇️ Kirapara News v0.3.4 APKをダウンロード](https://github.com/IKEGAMI-99/KRPR_news/releases/download/v0.3.4/Kirapara-News-v0.3.4.apk)

- [SHA-256ファイル](https://github.com/IKEGAMI-99/KRPR_news/releases/download/v0.3.4/Kirapara-News-v0.3.4.apk.sha256)
- [最新のGitHub Release](https://github.com/IKEGAMI-99/KRPR_news/releases/latest)
- [すべてのReleases](https://github.com/IKEGAMI-99/KRPR_news/releases)

> [!WARNING]
> APKは必ず `IKEGAMI-99/KRPR_news` のGitHub Releasesから取得してください。第三者が再配布したAPKは使用しないでください。

## ✨ v0.3.4

v0.3.4では、AndroidのScoped Storageとnative llama.cppのファイルアクセス問題を避けるため、GGUFの読み込み方式を変更しました。

```text
ユーザーが選択したGGUF
        ↓
Android Storage Access Framework
        ↓
初回だけアプリ専用モデル領域へコピー
        ↓
通常のファイルパス
        ↓
公式 llama.cpp
        ↓
翻訳 / 日本語要約
```

### 重要: 初回だけモデルを準備します

GGUFを初めて読み込む時は、選択したモデルをアプリ専用領域へ一度コピーします。

- 元のGGUFは削除しません
- 2回目以降はコピー済みモデルを再利用します
- コピー中は診断ログへ10%刻みで進捗を記録します
- モデル本体と同程度の追加空き容量が必要です
- 空き容量不足の場合はモデル読み込み前にエラーを表示します

例: 約5.15GBのGGUFなら、余裕分を含めて約5.4GB以上の空き容量を推奨します。

この方式は5GB前後のストレージを追加で使いますが、`content://` や `/proc/self/fd/...` をnative側で再オープンする端末依存問題を避け、llama.cppには通常ファイルだけを渡します。

## 🧠 ローカルGemma 4 / GGUF

設定 → **ローカルGemma 4** → **GGUFを選択** から、端末に保存済みのGGUFを指定します。

ニュースは通常、各地域の**原文**で表示します。

- 海外記事: **日本語に翻訳**
- 全記事: **日本語要約**

を押した時だけ端末内のGGUFを実行します。

モデルや記事本文をGoogle翻訳、DeepL、外部LLM API等へ送信しません。翻訳・要約結果は記事とモデルごとに端末へキャッシュします。

### 現在の推論バックエンド

- 公式 `llama.cpp` Android runtime
- GGUF
- arm64-v8a
- Context: 4096 tokens
- CPU / NEON
- CPU backend variantsを端末に応じて選択

Gemma 4のwide/MoEモデルで発生していたllama.cpp側のsplit-input問題の修正を含む固定コミットを使用しています。

### Hexagon NPUについて

llama.cpp本家にはSnapdragon Hexagon / HTPバックエンドがありますが、まだ実験的な実装です。

現在のAPKにはHexagon用HTPライブラリを同梱していないためCPU/NEONを使用します。NPU対応をUI上だけ装うことはせず、専用nativeビルドと実機検証後に追加する方針です。

## 🌐 ニュース取得

翻訳サーバーは使用しません。GitHub Actionsは**原文ニュースを集めるだけ**です。

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
        ↓
必要な記事だけ端末内Gemmaで処理
```

アプリはまずGitHub上の軽量ニュースキャッシュを読み、利用できない場合のみ公開RSS / RSSHub等へ直接アクセスします。

## 📰 接続中のニュースソース

| 地域 | ソース | 方法 | APIキー |
| --- | --- | --- | --- |
| 🇯🇵 日本 | きらめきパラダイス公式YouTube | YouTube公開RSS | 不要 |
| 🇨🇳 中国 | 以闪亮之名 公式Weibo | RSSHub 複数ホスト | 不要 |
| 🇨🇳 中国 | 以闪亮之名 公式Bilibili | RSSHub | 不要 |
| 🌎 Global | Life Makeover公式YouTube | 公開ページ + YouTube RSS | 不要 |
| 🇰🇷 韓国 | Stylight公式YouTube | 公開ページ + YouTube RSS | 不要 |

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
- APKのSHA-256検証
- 診断ログの書き出し

## 🧾 診断ログ

設定 → **診断ログ** から `.txt` ファイルとして書き出せます。

主な記録内容:

- アプリバージョン
- Android / 端末 / ABI
- 選択モデル名
- モデル準備（コピー）開始 / 10%刻みの進捗 / 完了
- GGUF読み込み開始 / 成功 / 失敗
- AI翻訳 / 要約の開始・完了・エラー
- ニュース取得エラー
- アップデート確認 / ダウンロード / SHA-256検証エラー

記事本文そのものを大量にログ保存する用途にはしていません。

## 🔄 アプリ内アップデート

設定 → **アップデート** から最新版を確認できます。

```text
GitHub Releases
      ↓
アプリ内でAPKダウンロード
      ↓
SHA-256検証
      ↓
Android標準インストーラー起動
```

ダウンロードと検証はアプリ内で完結します。

> [!NOTE]
> 通常のAndroidアプリでは、最後のOSによる「インストール」確認だけは省略できません。

## 📥 初回インストール

1. README上部の **v0.3.4 APKをダウンロード** を開く
2. `Kirapara-News-v0.3.4.apk` をダウンロード
3. APKを開く
4. 必要な場合は「この提供元からのアプリを許可」を有効にする
5. インストールする

正式署名版を導入した後は、以降のバージョンをアプリ内アップデートできます。

## ⚠️ セキュリティ

- APKはこのGitHubリポジトリのReleasesからのみ取得してください
- 第三者サイトやファイル共有サービスのAPKは使用しないでください
- 正式ReleaseにはAPKと `.sha256` を掲載します
- アプリ内更新でもSHA-256不一致ならインストールを中止します
- Androidが署名不一致を警告した場合はインストールを中止してください

## 🔒 プライバシー

- 翻訳 / 要約本文を外部AI APIへ送信しません
- GGUFを外部へ送信しません
- ユーザー登録不要
- 位置情報・連絡先不要
- 選択したGGUFへの読み取り権限のみ保持

ネットワーク通信はニュース取得、ニュースキャッシュ取得、GitHub Releasesの更新確認とAPK取得に使用します。

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
- 公式 llama.cpp / GGUF
- Android NDK 29 / CMake 3.31.6
- Android Storage Access Framework
- app-specific model storage
- FileProvider
- Coil
- GitHub Actions

## 🛠️ ビルド

JDK 17を使用します。公式llama.cpp Android runtimeの準備にはAndroid NDK / CMakeが必要です。

```bash
bash scripts/prepare_llama_android.sh
gradle assembleDebug
```

## 🚀 署名済みRelease

GitHub Repository Secrets:

- `KEYSTORE_BASE64`
- `KEYSTORE_PASSWORD`
- `KEY_ALIAS`
- `KEY_PASSWORD`

翻訳API用Secretは不要です。同じ署名鍵を全リリースで使用します。

## ⚖️ コンテンツと免責

ニュースでは投稿元と公式URLを明示します。公開RSS・公開ページ・各サービスの規約や仕様変更に応じて取得方法を調整します。

## Version

Current version: **v0.3.4**
