# Kirapara News ✨

日本版「きらめきパラダイス」、中国版「以闪亮之名」、グローバル版「Life Makeover」、韓国版「Stylight」のニュースを1つのタイムラインで追うための**非公式PWAニュースアプリ**です。

🌐 **PWA:** https://ikegami-99.github.io/KRPR_news/

> [!IMPORTANT]
> Kirapara News は非公式ファンプロジェクトです。Archosaur Games、VVANNA GIRLS、各地域の運営会社、SNS・ニュース各社とは関係ありません。

## ✨ できること

- 🇯🇵 日本 / 🇨🇳 中国 / 🇰🇷 韓国 / 🌐 Global の統合タイムライン
- 公式サイト、X、TikTok、YouTube、Weibo、Bilibili、Steam、プレス記事、Webニュースを横断収集
- APIキー不要の公開ページ / RSS / RSSHub 等を利用した収集
- 画像付きニュースカード / 複数画像ギャラリー / 全画面画像ビューア
- 小さすぎる画像、アイコン、ロゴ、QRなどの除外
- 地域フィルター / 検索 / SNS共有
- キラキラ系ライトテーマ / 病みカワ系ダークテーマ
- ホーム画面追加に対応したPWA
- GitHub Actions 上のローカルLLMによる日本語翻訳 / 要約
- GPT-5.6 Sol による1日3回の取りこぼし・翻訳品質監査
- Solが発見した欠落記事の補完と、誤訳・誤要約の保護付き修整
- 原文表示への切り替え
- AI結果がおかしい記事の再翻訳 / 再要約依頼

## 📱 インストール

APKは使用しません。ブラウザからPWAを開いてホーム画面へ追加します。

1. https://ikegami-99.github.io/KRPR_news/ を開く
2. ブラウザの「ホーム画面に追加」または「アプリをインストール」を選ぶ
3. Kirapara News のアイコンから起動する

サイト側を更新すれば新しいUIが配信されるため、APKの再インストールやPlay Storeは不要です。

## 📰 ニュース収集

GitHub Actions が毎時17分に通常のニュース収集を実行します。

```text
公式サイト / X / TikTok / YouTube
Weibo / Bilibili / Steam
PR TIMES / ゲームメディア / 一般ニュース
                ↓
         GitHub Actions
                ↓
   本文・元記事日時・画像を整理
                ↓
  小さい画像 / 重複 / 不正候補を除外
                ↓
      Sol補完記事をマージ
                ↓
     Qwen翻訳・要約を適用
                ↓
   Sol修整を最終適用して保護
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

Webニュースの発見には公開RSS等を利用しますが、**Google Newsのプロキシ記事はタイムラインへ保存しません**。元記事URLと元記事側の公開日時を優先し、日時は `data/article_dates.json` に保持して後の収集で不自然に前後しないようにします。

SNSや外部サイトは仕様変更・アクセス制限・RSSHub側の障害などで一時的に取得できない場合があります。そのため、通常収集とは別にSolによる定期監査を行います。

## 🔎 Solによる外部監査・補完

通常の `data/news.json` だけを唯一の情報源にせず、運用者のChatGPT定期タスクから **GPT-5.6 Sol** が公開情報を横断確認します。

現在は日本時間の **8:00 / 14:00 / 20:00 の1日3回**を基準に監査します。各回で直近約7日間を対象に、日本・中国・韓国・Globalの公式サイト、X、TikTok、YouTube、Weibo、Bilibili、Steam、公式コミュニティ、プレス記事、信頼できるWeb記事などを確認します。

### 取りこぼし記事

Kirapara Newsに存在しない実在の記事・投稿を確認できた場合は `data/sol_news.json` に保存します。

通常の収集処理で `data/news.json` が作り直されても、`scripts/apply_sol_edits.py` が `sol_news.json` を再マージするため、Sol追加記事は消えません。

重複、噂、根拠の弱い転載、内容が実質同一の再投稿は原則として追加しません。画像URLも元ソースで確認できる場合だけ保存します。

### 翻訳・要約の監査

初期段階では既存の**全記事**を監査します。1回で確認しきれない場合は `data/sol_audit_state.json` に進捗を保存し、複数回に分けて続行します。

全件監査が完了した後は、原則として以下だけを監査します。

- 新しく追加された記事
- 原文内容が変更された記事
- 再確認が必要になった記事

意味、固有名詞、日時、数値、イベント期間、報酬、星数、入手条件などに明確な誤りがある場合のみ修整し、単なる文体の好みでは上書きしません。

修整内容は `data/sol_overrides.json` に保存します。

## 🔒 Sol修整のQwen上書き防止

Solが修整した翻訳・要約は `scripts/apply_sol_edits.py` により `data/translations.json` にも同期されます。

```text
Solが翻訳 / 要約を修整
        ↓
data/sol_overrides.json
        ↓
scripts/apply_sol_edits.py
        ↓
data/translations.json
  model: GPT-5.6 Sol
  managedBySol: true
        ↓
Qwenからは有効な処理済みキャッシュとして見える
        ↓
再翻訳対象から除外
```

Sol管理の翻訳には `managedBySol: true`、記事側には `solLocked: true` が付きます。通常のQwen処理後にもSol修整を再適用するため、毎時のニュース更新やQwen再生成でSol版が意図せず失われない構成です。

Solの修整そのものに誤りが見つかった場合は、より新しい根拠に基づいてSol側のoverrideを更新します。

## 🖼️ 画像

記事ページやフィードから `og:image`、`twitter:image`、RSS/Atom media/enclosure、記事本文画像などを候補として収集します。

URL上のfavicon、ロゴ、QR、アバター等の除外に加え、画像本体を取得できる場合は実寸を検査します。現在は短辺260px未満、または約15万画素未満の画像を低解像度候補として除外します。検査結果は `data/image_quality.json` にキャッシュし、毎時すべてを再取得しません。

PWA側でも画像の実寸を確認するため、サーバー側で寸法を判定できなかった小画像が混ざってもカードや全画面ビューアから除外します。

## 🤖 AI翻訳・要約

通常処理では有料AI APIを使用せず、GitHub Actions のCPU上で **Qwen2.5-3B-Instruct Q4_K_M** を `llama.cpp` 経由で実行します。

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

### AI結果の再生成

AI処理済みの記事には「再要約」または「再翻訳・要約」ボタンが表示されます。静的なGitHub Pagesへ書き込み用トークンを埋め込まないため、ボタンは記事ID入りのGitHub Issue作成画面を開きます。

リポジトリ所有者がそのIssueを投稿すると `regenerate-ai.yml` が起動し、対象記事だけQwenで再生成して `data/translations.json` / `data/news.json` を更新します。第三者が同じ形式のIssueを作ってもAIジョブは起動しません。

Solによる保護対象の記事は、通常のQwen結果よりSol側のoverrideが優先されます。

> [!NOTE]
> 小型ローカルLLMによる翻訳・要約のため、誤訳や不自然な表現が発生する可能性があります。Sol監査はそれを補助する二重チェックですが、完全性を保証するものではありません。重要な内容は必ず元記事も確認してください。

## 🧱 構成

```text
KRPR_news/
├─ .github/workflows/
│  ├─ news-refresh.yml       # ニュース収集 + 整理 + Qwen翻訳/要約 + Sol修整適用
│  ├─ regenerate-ai.yml      # 指定記事のQwen結果を再生成
│  ├─ gap-analysis.yml       # 実装ギャップ解析
│  └─ pages.yml              # GitHub PagesへPWAを公開
├─ data/
│  ├─ news.json              # PWAが読む統合ニュース
│  ├─ translations.json      # Qwen / Sol 翻訳キャッシュ
│  ├─ sol_news.json          # Solが発見した取りこぼし記事
│  ├─ sol_overrides.json     # Solによる翻訳・要約修整
│  ├─ sol_audit_state.json   # Sol全件監査の進捗
│  ├─ translation_glossary.json
│  ├─ article_dates.json
│  ├─ image_quality.json
│  └─ gap_analysis.json
├─ docs/
│  ├─ index.html
│  ├─ app.js
│  ├─ ui_fixes.js
│  ├─ share.js
│  ├─ regenerate.js
│  ├─ styles.css
│  ├─ theme-kawaii.css
│  ├─ layout-fixes.css
│  ├─ regenerate.css
│  ├─ manifest.webmanifest
│  ├─ sw.js
│  └─ icon.svg
└─ scripts/
   ├─ fetch_news.py
   ├─ merge_direct_official.py
   ├─ enrich_sources.py
   ├─ enrich_social_images.py
   ├─ fetch_wechat_official.py
   ├─ discover_web_news.py
   ├─ enrich_images.py
   ├─ filter_small_images.py
   ├─ normalize_news.py
   ├─ audit_translations.py
   ├─ translate_news_llm.py
   ├─ apply_sol_edits.py
   ├─ tag_early_info.py
   └─ regenerate_ai.py
```

## 🔄 自動更新

`news-refresh.yml` がニュースデータを更新し、変更をmainへ保存します。PWAは `data/news.json` をネットワーク優先で読み、UIのアプリシェルだけService Workerでキャッシュします。

通常収集は毎時実行し、Sol監査は別系統のChatGPT定期タスクとして1日3回実行します。通常収集と監査経路を分けることで、同じ取得方法の失敗をそのまま二重化しない構成にしています。

## 💰 運用コスト

通常のニュース収集・Qwen翻訳は、公開GitHubリポジトリ、GitHub Pages、標準GitHub-hosted Actions、無料公開データ取得経路を利用しており、追加の有料AI APIを前提にしていません。

Sol監査は運用者のChatGPT定期タスクを利用するため、GitHub Actions上でGPT-5.6 Solを動かしているわけではありません。利用可能性や制限はChatGPT側の契約・機能に依存します。

GitHubや外部サービスの料金・利用条件は将来変更される可能性があります。

## 🔒 プライバシー

- PWAの利用にユーザー登録不要
- 位置情報・連絡先不要
- 通常の翻訳・要約はGitHub Actions上のローカルQwenで処理
- OpenAI / DeepL / Google翻訳等の有料翻訳APIを通常収集パイプラインには組み込まない
- Sol監査では運用者のChatGPT定期タスクが公開Web情報と公開GitHubリポジトリの内容を確認する

## ⚖️ コンテンツと免責

各記事は元の公開ページへリンクします。記事本文・画像等の権利は各権利者に帰属します。公開ページ、RSS、RSSHub、検索結果などの仕様や各サービスの規約変更により、取得方法や取得可能なソースは変わることがあります。
