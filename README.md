# Kirapara News ✨

日本版「きらめきパラダイス」、中国版「以闪亮之名」、グローバル版「Life Makeover」、韓国版「Stylight」のニュースを1つのタイムラインで追うための**非公式PWAニュースアプリ**です。

🌐 **PWA:** https://ikegami-99.github.io/KRPR_news/

> [!IMPORTANT]
> Kirapara News は非公式ファンプロジェクトです。Archosaur Games、VVANNA GIRLS、各地域の運営会社、SNS・ニュース各社とは関係ありません。

## ✨ できること

- 🇯🇵 日本 / 🇨🇳 中国 / 🇰🇷 韓国 / 🌐 Global の統合タイムライン
- 公式サイト、SNS、動画、ゲームメディア、プレス記事を横断収集
- APIキー不要の公開ページ / RSS / RSSHub 等を利用した収集
- 画像付きニュースカード
- 記事内画像の複数画像ギャラリー
- 地域フィルター / 検索
- ライト / ダークテーマ
- ホーム画面追加に対応したPWA
- オフライン用のアプリシェルキャッシュ
- GitHub Actions 上のローカルLLMによる日本語翻訳 / 要約
- 原文を保持したまま日本語表示へ切り替え

## 📱 インストール

APKは使用しません。ブラウザからPWAを開いてホーム画面へ追加します。

1. https://ikegami-99.github.io/KRPR_news/ を開く
2. ブラウザの「ホーム画面に追加」または「アプリをインストール」を選ぶ
3. Kirapara News のアイコンから起動する

サイト側を更新すれば新しいUIが配信されるため、APKの再インストールやPlay Storeは不要です。

## 📰 ニュース収集

GitHub Actions が毎時17分にニュース収集を実行します。

```text
公式サイト / X / TikTok / YouTube
Weibo / Bilibili / Steam
PR TIMES / ゲームメディア / 一般ニュース
                ↓
         GitHub Actions
                ↓
     本文・日時・画像を整理
                ↓
          data/news.json
                ↓
        Kirapara News PWA
```

現在の主な取得対象:

| 地域 | 主なソース |
| --- | --- |
| 🇯🇵 日本 | 公式サイト / 公式X / 公式TikTok / 公式YouTube / PR TIMES / 国内Webニュース |
| 🇨🇳 中国 | 公式サイト / 公式Weibo / 公式Bilibili記事 / 中国Webニュース |
| 🇰🇷 韓国 | 公式X / 公式TikTok / 公式YouTube / 韓国Webニュース |
| 🌐 Global | 公式サイト / 公式X / 公式TikTok / 公式YouTube / Steam / 海外Webニュース |

SNSや外部サイトは仕様変更・アクセス制限・RSSHub側の障害などで一時的に取得できない場合があります。取得経路は複数用意し、失敗したソースがあっても他のソースからニュースを継続できる構成にしています。

## 🖼️ 画像

記事ページやフィードから以下を候補として収集します。

- `og:image`
- `twitter:image`
- RSS / Atom の media / enclosure
- 記事本文中の画像

favicon、ロゴ、QRコード、アバター、小さすぎる画像などは可能な範囲で除外します。記事に複数の有効画像がある場合は `imageUrls` に保存し、PWA内のギャラリーから閲覧できます。

## 🤖 AI翻訳・要約

有料AI APIは使用しません。GitHub Actions のCPU上で **Qwen2.5-3B-Instruct Q4_K_M** を `llama.cpp` 経由で実行します。

```text
新着ニュース
    ↓
翻訳キャッシュ確認
    ↓
未処理の記事だけLLMへ
    ↓
海外記事: 日本語翻訳 + 日本語要約
日本語記事: 日本語要約
    ↓
data/translations.json にキャッシュ
    ↓
data/news.json へ反映
```

同じ記事を毎回推論せず、記事ID / 内容に対応した翻訳結果を再利用します。原文の `title` / `body` は保持し、日本語結果は `titleJa` / `bodyJa` / `summaryJa` として追加します。

固有名詞は `data/translation_glossary.json` の辞書を優先し、辞書にない名称は無理に日本語公式名へ変換しない方針です。

> [!NOTE]
> 小型ローカルLLMによる翻訳・要約のため、誤訳や不自然な表現が発生する可能性があります。重要な内容は必ず元記事も確認してください。

## 🧱 構成

```text
KRPR_news/
├─ .github/workflows/
│  ├─ news-refresh.yml   # ニュース収集 + LLM翻訳/要約
│  └─ pages.yml          # GitHub PagesへPWAを公開
├─ data/
│  ├─ news.json
│  ├─ translations.json
│  └─ translation_glossary.json
├─ docs/
│  ├─ index.html
│  ├─ app.js
│  ├─ styles.css
│  ├─ ai.css
│  ├─ manifest.webmanifest
│  ├─ sw.js
│  └─ icon.svg
└─ scripts/
   ├─ fetch_news.py
   ├─ merge_direct_official.py
   ├─ enrich_sources.py
   ├─ discover_web_news.py
   ├─ discover_web_news_v2.py
   ├─ enrich_images.py
   └─ translate_news_llm.py
```

## 🔄 自動更新

`news-refresh.yml` がニュースデータを更新し、変更がmainへ反映されるとGitHub Pages側も更新されます。

PWAのService Workerはアプリシェルをキャッシュしつつ、ニュースデータは新しい内容を取得できるよう更新します。

## 💰 運用コスト

現在の構成は、公開GitHubリポジトリ、GitHub Pages、標準GitHub-hosted Actions、無料公開データ取得経路を利用しており、追加の有料APIを前提にしていません。

GitHubや外部サービスの料金・利用条件は将来変更される可能性があります。

## 🔒 プライバシー

- ユーザー登録不要
- 位置情報・連絡先不要
- OpenAI / DeepL / Google翻訳等の有料AI APIへ記事本文を送信しない
- 翻訳・要約はGitHub Actions上のローカルLLMで処理

## ⚖️ コンテンツと免責

各記事は元の公開ページへリンクします。記事本文・画像等の権利は各権利者に帰属します。

公開ページ、RSS、RSSHub、検索結果などの仕様や各サービスの規約変更により、取得方法や取得可能なソースは変わることがあります。
