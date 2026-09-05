# Kirapara News ✨

日本版「きらめきパラダイス」、中国版「以闪亮之名」、韓国版「Stylight」、Global版「Life Makeover」の公開ニュースを、1つのタイムラインで確認する非公式PWAです。

**公開PWA:** https://ikegami-99.github.io/KRPR_news/  
**Stable Release:** `v1.0.0`（2026-08-28）  
**現在のPWAシェル表示:** `v77`

## 不具合修正（2026-09-05 / v77）

- 通信失敗時は表示中のニュースを保持し、端末保存が失敗・古い場合にも記事を消したり巻き戻したりしない
- 複数の更新要求が重なった場合、最後に要求した結果だけを反映
- 画像ビューアを開き直しても、削除済みビューアのキーボードイベントを蓄積しない
- PWAシェルはHTTPエラー時も保存済みキャッシュへフォールバックし、キャッシュ書き込み失敗時は正常な通信結果をそのまま使用
- オフラインのクエリ付きページURLでも対応する保存済みページを表示し、PWA更新時は他アプリのキャッシュを削除しない
- 上記の実行時回帰テストを追加し、SEO生成物と現行文書表記を既存テストで正しく検証

> [!IMPORTANT]
> Kirapara Newsは非公式ファンプロジェクトです。Archosaur Games、VVANNA GIRLS、各地域の運営会社、SNS・ニュース各社とは関係ありません。
>
> ニュース収集、画像処理、翻訳・要約、公開更新の大部分を自動化しています。AI翻訳・要約には誤りが含まれる可能性があるため、日時、価格、報酬、イベント条件など重要な情報は元記事・公式情報も確認してください。

## 最近の主な変更（2026-09-03〜09-04）

- ニュース保持上限を **260件から800件**へ拡張
- SEO用の静的記事ページを自動生成し、`sitemap.xml` / `robots.txt` / canonical / OGP / Twitter Card / `NewsArticle` JSON-LD を追加
- SEO記事ページの生成上限もデフォルト **800件**に設定
- ホームページ側のSEOメタデータを追加
- PWAタイトル横に小さく **`v71`** を表示
- アプリ共有時の紹介画像を、必要に応じてブラウザ側で **幅1536px** へ高品質リサイズして添付
- Gemma 4 E4Bの日本語品質チェックを強化し、中国語・韓国語・英語の残留、原文丸コピー、日本語かな不足、中国式の割引表記などを検出
- 品質チェックで失敗した場合、失敗理由をGemmaへ返し、原文から最大3回まで再生成する方式へ変更
- 3回とも生成に失敗した記事のクールダウンを **6時間から3時間**へ短縮
- 1記事が失敗しても翻訳backlog全体を止めず、後続記事を処理する方式を継続
- 品質チェックで繰り返し修正された用語を `translation_glossary.json` へ候補登録する自動フィードバック機能を追加
- 自動修正候補は最初から辞書として使わず、**独立した3記事で同じ原語→訳語が確認された場合のみ自動昇格**
- 同じ原語で複数の訳語が昇格条件に達した場合は自動昇格を停止し、Sol監査待ちにする安全策を追加
- `verified=true` かつ `trainingEligible=true` の辞書項目だけをLoRA/SFT用seedへ出力する既存設計と自動辞書学習を接続
- ChatGPT側の **Kirapara News Sol監査** を再開。08:00 / 14:00 / 20:00 JSTに翻訳・要約・欠落記事・辞書候補を監査する運用

## 主な機能

- 🇯🇵 日本 / 🇨🇳 中国 / 🇰🇷 韓国 / 🌐 Global の統合タイムライン
- 地域フィルターと20件単位のページング
- 公式サイト、X、TikTok、YouTube、Weibo、Bilibili、TapTap、好游快爆、Steam、公開Web記事などを横断収集
- 同じ告知を複数媒体から取得した場合、1枚のカードへ統合しつつ各元記事URLを保持
- 一時的なFeed障害で記事を大量削除しないlast-known-good保護
- 複数画像表示、全画面ビューア、画像品質フィルタ
- Weibo画像のリポジトリ内ミラー
- Gemma 4 E4Bによる日本語翻訳・要約
- 翻訳結果に対する自動品質検査と理由付き再生成
- Sol監査済み翻訳のロック・優先保持
- 原文 / 日本語の切り替え
- Web Share APIを利用した文章＋紹介画像共有
- ライト / ダークテーマ
- 海外版と日本版の公開記事を照合する実装差分析
- GA4集計スナップショットを使ったアクセス解析ページ
- PWA / Service Workerによるホーム画面追加とオフラインアプリシェル
- SEO向け静的記事ページ、サイトマップ、robots.txt

検索バー、旧「先行情報トップ3」、予測タグ、ChatGPTに聞くボタンなど、現在不要になった機能は削除済みです。削除済み機能はREADMEの古い説明を根拠に復活させないでください。

## 設計思想

Kirapara Newsは、完全な編集型ニュースサイトではなく、**大量の海外公式情報を、元情報への導線を失わず自動整理するレイヤー**として設計しています。

### 1. 原文をAIより上位に置く

ニュース収集はAIに依存しません。Gemmaが停止しても原文タイムラインは更新できます。翻訳・要約は補助情報であり、元記事URLは可能な限り保持します。

### 2. 一時障害を「削除」と解釈しない

外部Feedが一時的に空になっても、公式投稿が消えたとは限りません。公式XやBilibiliなどは媒体単位で直前の正常履歴を保持し、取得障害だけで大量の記事が消えないようにしています。

### 3. 1件の失敗を全体障害にしない

収集元、画像、翻訳のどれか1件が失敗しても、処理全体を止めないことを優先します。翻訳では3回の生成を使い切った記事を3時間deferし、後続記事へ進みます。

### 4. AIの出力をそのまま信用しない

Gemmaの出力は品質バリデータを通し、機械的に問題を検出します。さらにSol監査済みの修正は自動生成より優先します。

### 5. 修正結果から少しずつ学ぶ

再利用可能な翻訳ルールは辞書へ蓄積します。ただし自動修正は即時採用せず、複数の独立観測で再現したものだけを昇格させます。自動化が自分の誤りを教材にして増幅する、ありがちな悲劇を避けるためです。

### 6. 専用サーバーをできるだけ持たない

GitHub Actionsをバッチ基盤、Git管理されたJSONをデータ層、GitHub Pagesを配信基盤として利用しています。常時稼働する独自APIサーバーやDBへの依存を最小限にしています。

## システム構成

```text
公開公式ソース / SNS / Web記事
        ↓
媒体別collector
        ↓
正規化・履歴保護・重複統合
        ↓
日時 / 画像品質補正
        ↓
Sol追加記事・override適用
        ↓
data/news.json
        ↓
┌─────────────────────┬──────────────────────┐
│ PWA / GitHub Pages  │ Gemma 4 E4B 翻訳     │
│                     │ + 自動品質チェック    │
└─────────────────────┴──────────────────────┘
                              ↓
                     data/translations.json
                              ↓
                 自動辞書候補 / Sol監査
                              ↓
               data/translation_glossary.json
                              ↓
              verified項目のみLoRA seed化
```

## 翻訳・要約パイプライン

通常の自動翻訳は **Gemma 4 E4B + LiteRT-LM 0.16.1** を使用します。

| 項目 | 現在値 |
| --- | --- |
| Model | `litert-community/gemma-4-E4B-it-litert-lm` |
| Runtime | LiteRT-LM 0.16.1 |
| Model revision | `gemma-4-e4b-it-litertlm-summary-facts-region-titles-strict-ja-v2` |
| Summary format | 4 |
| Context limit | 8,192 tokens |
| Max output | 3,000 tokens |
| 1回のWorkflow処理上限 | 最大3記事 |
| 1記事の生成試行 | 最大3回 |
| 3回失敗後の再試行待ち | 3時間 |

### 品質チェック

`scripts/translation_quality.py` が主に次を検査します。

- JSON形式と必須フィールド
- `summaryJa` の形式
- 中国語一般語の残留
- 韓国語・英語文の過剰残留
- 日本語かな文字の不足
- 原文がほぼそのまま返されていないか
- 中国式の `○折` 表記が残っていないか
- 用語集で保持指定された固有名詞を誤って検出対象にしないこと

NGの場合は単なる同一プロンプト再実行ではなく、前回の失敗理由をGemmaへ返します。例として「中国語の一般語が残っている」「日本語かなが不足」「○折が残っている」などを明示し、前回出力の修正ではなく原文からJSON全体を作り直させます。

### Sol監査

Sol監査はGitHub Actions内でGPTを直接実行する仕組みではなく、ChatGPT側の運用タスクです。現在は **08:00 / 14:00 / 20:00 JST** に実行する構成です。

監査では、可能な範囲で一次情報と照合し、以下を確認します。

- 翻訳・要約の意味
- 固有名詞
- 日付・時刻
- 数値・星数・価格・報酬
- イベント期間・入手条件
- collectorで欠落した実在ニュース
- 再利用可能な翻訳ルール

既存記事の修正は `data/sol_overrides.json`、欠落ニュース補完は `data/sol_news.json`、監査進捗は `data/sol_audit_state.json` を使用します。`data/news.json` と `data/translations.json` をSol監査から直接編集しない設計です。

## 翻訳辞書と自動フィードバック

辞書の正本は `data/translation_glossary.json` で、schemaは `krpr.translation-glossary.v2` です。

各エントリは単なる `原語: 訳語` だけでなく、地域、カテゴリ、保持/翻訳、信頼度、根拠URL、provenance、学習可否などを持ちます。

### Sol修正

Solが一次情報などから確認した再利用可能な短い用語ルールは、原則として監査済み辞書項目として登録できます。

### プログラム修正

`scripts/auto_glossary_feedback.py` は、品質チェックで検出され、再翻訳によって解消された一部の一般語を自動候補として記録します。

現在の対象例:

- `礼包` → `パック` / `セット`
- `活动` → `イベント` / `キャンペーン`
- `任务` → `ミッション` / `クエスト`
- `合伙人` → `プレイヤー`
- `网页链接` → `Webリンク`

自動候補は最初、以下の安全側状態で保持します。

```text
active = false
verified = false
trainingEligible = false
provenance = auto-quality-correction
```

同じ地域・同じ原語→訳語について、異なる記事内容から **3件以上の独立した成功観測** が得られ、競合する訳語がない場合だけ、次の状態へ昇格します。

```text
active = true
verified = true
trainingEligible = true
confidence = 0.95
```

既存のSol監査済み・手動辞書と競合する場合は自動辞書を優先しません。同じ原語について複数の自動候補が3件条件を満たした場合も、自動昇格を停止して監査待ちにします。

## LoRA / SFT seed

`scripts/glossary_schema.py` は、辞書のうち **`verified=true` かつ `trainingEligible=true`** の項目だけを学習seedへ変換します。

`data/training/glossary_lora_seed.jsonl` は手動編集せず、`translation_glossary.json` を正本として `glossary-lora-export.yml` から生成します。

このため、現在の改善ループは概念的に次の形です。

```text
誤訳・不自然な出力
    ↓
品質チェック
    ↓
理由付き再翻訳
    ↓
同じ修正を複数記事で観測
    ↓
辞書へ昇格
    ↓
次回の翻訳プロンプトで利用
    ↓
検証済み項目だけ将来のLoRA/SFT seedへ
```

## SEO

JavaScriptタイムラインだけでは検索クローラが記事本文を安定して取得しにくいため、`scripts/generate_seo.py` がPagesデプロイ時に静的HTMLを生成します。

生成物:

- `docs/articles/<article-id>.html`
- `docs/sitemap.xml`
- `docs/robots.txt`

各記事ページには次を含めます。

- `<title>` / description
- canonical URL
- OGP
- Twitter Card
- `schema.org/NewsArticle` JSON-LD
- 公開日時
- 代表画像
- 元記事へのリンク

デフォルトのSEO記事生成上限は **800件** です。

## データ保持とページング

収集・正規化・重複統合など主要処理の保持上限は現在 **800件** です。以前の260件上限から拡張しました。

PWAは800件を一度にDOMへ展開せず、地域ごとに **20件単位** でページングします。地域とページ番号はURLへ保持し、ニュース件数が変わった場合はページ数を再計算します。

## 共有

アプリ共有では、文章とKirapara News紹介画像をWeb Share APIへ渡します。

紹介画像が幅1536px未満の場合は、ブラウザのCanvasで縦横比を維持したまま **1536px幅** へリサイズし、JPEG品質0.94で共有用ファイルを生成します。元画像がすでに十分大きい場合は不要な拡大を行いません。

## 主なJSON

| ファイル | 役割 |
| --- | --- |
| `data/news.json` | 正規化済みニュース本体 |
| `data/translations.json` | Gemma / Sol翻訳・要約キャッシュと失敗状態 |
| `data/translation_glossary.json` | 翻訳辞書の正本 |
| `data/sol_news.json` | Solが補完した欠落ニュース |
| `data/sol_overrides.json` | Sol監査による既存記事の修正 |
| `data/sol_audit_state.json` | Sol監査の進捗 |
| `data/crawl_status.json` | 最後にニュース収集が正常完了した時刻 |
| `data/article_dates.json` | 検証済み記事日時 |
| `data/image_quality.json` | 画像品質判定 |
| `data/gap_analysis.json` | 地域間の実装差分析 |
| `data/stable_release.json` | Stable Release marker |

## 自動実行スケジュール

| 処理 | スケジュール |
| --- | --- |
| News Refresh | 毎時 `:00` |
| Gemma翻訳 | 毎時 `:07 / :22 / :37 / :52` + News Refresh成功後 |
| News Refresh Watchdog | 毎時 `:17 / :47` + 翻訳完了後 |
| Gap Analysis | 毎日 06:30 JST |
| Analytics Refresh | 6時間ごと |
| Sol監査 | 08:00 / 14:00 / 20:00 JST（ChatGPT側運用タスク） |

Watchdogは最終成功から70分以上更新がない場合に回復処理を行います。

## 主なGitHub Actions

| Workflow | 役割 |
| --- | --- |
| `.github/workflows/news-refresh.yml` | ニュース収集、正規化、履歴保護、重複統合、画像・日時補正 |
| `.github/workflows/news-refresh-watchdog.yml` | News Refresh停止の監視・回復 |
| `.github/workflows/ai-translate.yml` | Gemma翻訳、品質検査、再試行、自動辞書フィードバック、競合を考慮した保存 |
| `.github/workflows/glossary-lora-export.yml` | verified辞書からLoRA/SFT seedを生成 |
| `.github/workflows/regenerate-ai.yml` | 指定記事のAI結果を再生成 |
| `.github/workflows/gap-analysis.yml` | 実装差分析 |
| `.github/workflows/analytics-refresh.yml` | GA4スナップショット更新 |
| `.github/workflows/pages.yml` | SEO生成を含むGitHub Pagesデプロイ |
| `.github/workflows/release-stable.yml` | Stable Release gate |

## 競合時の書き込み保護

News Refresh（`kirapara-news-refresh`）とAI翻訳（`kirapara-ai-translate`）は別のconcurrency groupで動作できます。翻訳結果のpush時にmainが進んでいた場合は、単純なforce pushをせず最新mainへ意味的に翻訳キャッシュを再適用します。

優先順位は概ね次の通りです。

1. Sol監査済み / `managedBySol` / `solLocked`
2. 新しい自動翻訳結果
3. 古い自動翻訳結果

翻訳pushは最大4回まで再試行します。

## PWA / フロントエンド

- GitHub Pages上で静的配信
- Service Workerはアプリシェル中心にキャッシュ
- `data/news.json` は固定キャッシュせず新しいニュースを取得
- 新しいService Workerが制御を引き継いだ場合は古い実装が残留し続けないよう更新
- 20件単位ページング
- `content-visibility: auto` などを使用して大量記事でもDOM負荷を抑制
- 原文 / 日本語切り替え
- ライト / ダークテーマ
- 画像スワイプ・全画面ビューア

## Stable Release

`v1.0.0` はPWA版を正式なStable基準として固定したReleaseです。現在の `main` ではAndroidネイティブ版 / APKビルド経路を削除しており、PWAを現行実装の正本としています。

Stable Releaseはニュースデータを固定するものではありません。アプリ本体の基準点をReleaseとして残しつつ、ニュース・翻訳キャッシュ・分析データは定期Workflowで継続更新されます。

## 開発時の正本

READMEは利用者・開発者向け概要です。実装判断ではREADMEだけを鵜呑みにせず、現行コード・Workflow・テストを確認してください。

特に重要な正本:

- `AI_CONTEXT.md` — AI / coding agent向け引き継ぎ
- `scripts/strict_gemma_translate.py` — 現行Gemma構成・失敗ポリシー
- `scripts/translation_quality.py` — 翻訳品質検査
- `scripts/auto_glossary_feedback.py` — 自動辞書候補・昇格
- `scripts/glossary_schema.py` — 辞書schema / LoRA seed変換
- `.github/workflows/ai-translate.yml` — 翻訳Workflow
- `.github/workflows/news-refresh.yml` — 収集Workflow
- `tests/test_project.py` — 構造上の回帰防止

## 法的情報・プライバシー

- 利用規約: `docs/terms.html`
- プライバシーポリシー: `docs/privacy.html`
- 問い合わせ: X `@ikegami_krpr`

GA4のイベントや外部解析サービスなど、データ取扱いに関わる実装を変更した場合はプライバシーポリシーも同期して更新してください。

---

Kirapara Newsは、**原文保持 → 自動翻訳 → 機械品質チェック → 理由付き再試行 → Sol監査 → 辞書へのフィードバック**という多段構成で、完全自動化と品質維持の両立を狙っています。
