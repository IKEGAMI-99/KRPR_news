# Kirapara News ✨

日本版「きらめきパラダイス」、中国版「以闪亮之名」、Global版「Life Makeover」、韓国版「Stylight」の公開ニュースを、1つのタイムラインで確認する非公式PWAです。

**公開PWA:** https://ikegami-99.github.io/KRPR_news/

> [!IMPORTANT]
> Kirapara Newsは非公式ファンプロジェクトです。Archosaur Games、VVANNA GIRLS、各地域の運営会社、SNS・ニュース各社とは関係ありません。

## 主な機能

- 🇯🇵 日本 / 🇨🇳 中国 / 🇰🇷 韓国 / 🌐 Global の統合タイムラインと地域フィルター
- 公式サイト、X、TikTok、YouTube、Weibo、Bilibili、Steamなどの横断収集
- 複数画像のスワイプ表示と全画面ビューア
- Weibo画像のリポジトリ内ミラーと、GitHub Pages同一オリジンからの安定配信
- 低解像度画像、ロゴ、QR、トラッキング画像などの除外
- Gemma 4 E4Bによる日本語翻訳・箇条書き要約
- 原文 / 日本語の切り替え、共有、ライト / ダークテーマ
- 海外版と日本版の公開記事を照合する実装差分析
- GA4の集計値を確認するアクセス解析ページ
- ホーム画面への追加と、アプリシェルのオフライン利用
- ヘッダーに「最後にクロールが完了した時刻」だけを表示

検索バーと「先行情報トップ3 / 先行情報」機能は2026-08-28に完全削除しました。関連するUI、JavaScript、CSS、収集・AI処理コードも削除しており、READMEや実装差分析にも先行情報機能を残していません。

## 更新アーキテクチャ

```text
公開サイト / SNS / RSS
        │
        ▼
毎時 :00  news-refresh.yml
        │
        ├─ 収集・重複排除
        ├─ 日時・画像の正規化
        ├─ Weibo画像を docs/media/weibo にミラー
        ├─ Sol補完データの再適用
        ├─ 有効な翻訳キャッシュを反映
        └─ クロール完了時刻を data/crawl_status.json に記録
        │
        ▼
   data/news.json ──────────► Kirapara News PWA
   data/crawl_status.json ──► ヘッダーの「最終更新」
        │
        ▼
毎時 :07 / :22 / :37 / :52  ai-translate.yml
        │
        ├─ 未処理が0件なら重いAIジョブを開始しない
        ├─ 未処理があれば1回最大3件をGemma 4で処理
        └─ 日本語品質検査後に翻訳キャッシュへ保存
```

ニュース収集は毎時00分に開始します。GitHub Actionsの混雑や取得先の応答時間により実際の完了時刻は数分以上ずれることがあります。ヘッダーの「最終更新」は記事の公開日時ではなく、`news-refresh.yml` が収集・画像処理まで正常に完了して `data/crawl_status.json` を更新した時刻です。新着記事が0件でもクロール自体が成功すればこの時刻は更新されます。

5分ごとに1件ずつ処理していたAI構成は、モデル復元・ランタイム準備・checkoutの回数が多すぎるため廃止しました。現在は15分ごとに最大3件をまとめ、同等の最大処理量を保ちながらrunner起動回数を4分の1にしています。

ニュース収集とAI処理は同じ `kirapara-data-writer` concurrency groupを使います。両方が同時に `data/news.json` と `data/translations.json` を書き換える競合を防ぐためです。

## ニュース収集

主な対象は次のとおりです。

| 地域 | 主なソース |
| --- | --- |
| 🇯🇵 日本 | 公式サイト / 公式X / TikTok / YouTube / 国内Webニュース |
| 🇨🇳 中国 | 公式サイト / Weibo / Bilibili / 中国Webニュース |
| 🇰🇷 韓国 | 公式X / TikTok / YouTube / 韓国Webニュース |
| 🌐 Global | 公式サイト / 公式X / TikTok / YouTube / Steam / 海外Webニュース |

YouTubeはチャンネルページ内の任意の `channelId` ではなく、正規URLのチャンネルIDを優先します。Global版は公式チャンネル `UCaaIsX56nWN0fvGJXQ8yvhA` に固定し、同じ運営会社の別ゲーム動画が混入しないようにしています。

Google NewsのプロキシURLはタイムラインへ保存しません。Web記事は元記事URLと、取得できる場合は発行元の明示的な公開日時を優先します。確認済み日時は `data/article_dates.json`、画像検査結果は `data/image_quality.json` に保持します。

WeiboはSina CDNの直接表示がブラウザやPWA環境で不安定になるため、収集時に取得できた画像を `docs/media/weibo/` へ保存し、`imageMirrorUrls` として記事データに紐付けます。PWAはGitHub Pages上の同一オリジン画像を優先し、必要な場合のみ元のSina画像をフォールバックとして使います。Service Worker更新時には既存タブを一度リロードし、古い画像配信ロジックが残り続けないようにしています。

外部サービスの仕様変更、アクセス制限、RSSHub側の障害により、一部ソースを一時的に取得できない場合があります。ある地域の収集が全滅した場合は、その地域の直前データを保持します。

## 翻訳・要約

通常のAI処理はGitHub Actions上の **Gemma 4 E4B** と **LiteRT-LM 0.16.1** を使用します。

- モデルファイルはSHA-256を検証
- モデルとpipパッケージをActions cacheへ保存
- 記事本文のハッシュで再処理の要否を判定
- 日本語以外の文章が残った出力を品質検査で無効化
- 固有名詞は `data/translation_glossary.json` を優先
- Sol管理の修正は `managedBySol` / `solLocked` で再上書きを防止

AI処理に失敗しても、原文ニュースの収集と表示は継続します。翻訳・要約は参考情報であり、日時、数値、報酬、開催条件などは必ず元記事も確認してください。

## PWAと表示性能

フロントエンドはビルド不要のHTML / CSS / JavaScriptです。

- `data/news.json` はネットワーク優先で取得し、失敗時は端末内の直前データを表示
- `data/crawl_status.json` はネットワークから取得し、端末には直近の成功値も保存
- タイトル下は件数や「最新記事」の日時を表示せず、クロール完了時刻だけを表示
- Service Workerはアプリシェルだけをキャッシュ
- ニュースJSON、アクセス解析JSON、外部画像はService Workerで固定キャッシュしない
- 画像ギャラリーは1つだけ生成し、非表示ギャラリーを複製しない
- カード描画完了イベントで補助機能を更新し、複数の `MutationObserver` による全件再走査を行わない
- カードに `content-visibility: auto` を使用
- 新しいService Workerが制御を引き継いだ際は既存PWAタブを一度だけ再読み込みして更新を反映

## メニュー

メニュー上部にはホーム画面追加、実装差分析、アクセス解析を並べています。その下に各地域の公式リンク、自動更新スケジュール、運用情報を配置しています。

現在のスケジュール表示は実際のワークフローと揃えています。

- ニュース収集: 毎時 :00
- Gemma 4 E4B 翻訳・要約: 毎時 :07 / :22 / :37 / :52、1回最大3記事
- Sol監査: 08:00 / 14:00 / 20:00 JST
- 更新watchdog: 毎時 :30、異常時のみ再起動

## ワークフロー

| Workflow | 実行 | 役割 |
| --- | --- | --- |
| `news-refresh.yml` | 毎時00分 | ニュース収集、画像・日時の正規化、Weibo画像ミラー、クロール完了時刻の記録 |
| `ai-translate.yml` | 毎時07 / 22 / 37 / 52分 | backlog確認、最大3件の翻訳・要約 |
| `regenerate-ai.yml` | リポジトリ所有者のIssue | 指定記事のAI結果を再生成 |
| `gap-analysis.yml` | 毎日06:30 JST | 地域別の実装差分析を更新 |
| `analytics-refresh.yml` | 6時間ごと | GA4の集計スナップショットを更新（公開は `pages.yml` に一本化） |
| `pages.yml` | `docs/**` 更新時 | GitHub PagesへPWAを公開 |

運用環境では、ChatGPT側のSol監査（08:00 / 14:00 / 20:00 JST）と更新watchdogも併用しています。これらはGitHub Actions内でGPTを実行する仕組みではなく、リポジトリ外の運用タスクです。

## 2026-08-28時点の主な整理

- 検索バー、先行情報トップ3、先行情報タグ付け処理を削除
- Gemma 4 E4B + LiteRT-LMへ翻訳・要約系を統一
- 実装差分析から予測表示を外し、公開記事同士の比較に整理
- メニューの実装差分析直下にアクセス解析を追加
- Weibo画像を収集時にリポジトリへミラーし、Pages同一オリジン配信へ変更
- PWA更新後も古い画像ロジックが残る問題をService Workerのcontroller変更時リロードで修正
- ニュース収集を毎時00分へ戻し、クロール完了日時を独立ファイルで記録
- ヘッダー表示を「記事件数・最新記事日時」から「最終クロール完了日時のみ」へ変更

## ディレクトリ構成

```text
KRPR_news/
├─ .github/workflows/
│  ├─ news-refresh.yml
│  ├─ ai-translate.yml
│  ├─ regenerate-ai.yml
│  ├─ gap-analysis.yml
│  ├─ analytics-refresh.yml
│  └─ pages.yml
├─ data/
│  ├─ news.json
│  ├─ crawl_status.json
│  ├─ translations.json
│  ├─ translation_glossary.json
│  ├─ sol_news.json
│  ├─ sol_overrides.json
│  ├─ article_dates.json
│  ├─ image_quality.json
│  └─ gap_analysis.json
├─ docs/
│  ├─ index.html
│  ├─ app.js
│  ├─ crawl-status.js
│  ├─ sw.js
│  ├─ gap.html
│  ├─ analytics/
│  ├─ media/weibo/
│  └─ 各機能のCSS / JS
├─ scripts/
│  ├─ fetch_news.py
│  ├─ translation_engine.py
│  ├─ translation_quality.py
│  ├─ strict_gemma_translate.py
│  ├─ normalize_news.py
│  ├─ mirror_weibo_images.py
│  └─ 収集・画像・分析用スクリプト
└─ tests/
   └─ test_project.py
```

## ローカル確認

Python 3.12を想定しています。通常の静的検査と単体テストは外部パッケージ不要です。

```bash
python -m unittest discover -s tests -v
python -m http.server 8000
```

ブラウザで `http://localhost:8000/docs/` を開きます。localhostでは作業コピーの `data/news.json`、`data/crawl_status.json`、`data/gap_analysis.json` を読み、公開版ではGitHub上の `main` を読みます。

## プライバシーとアクセス解析

- PWAの利用にユーザー登録、位置情報、連絡先は不要です。
- 通常の翻訳・要約はGitHub Actions上のローカルモデルで処理します。
- 公開ページではGoogle Analytics 4を使用し、ページ表示、参照元、端末種別、概略地域などの集計に使います。Google側でCookieや類似識別子が利用される場合があります。
- `/analytics/` は非公開管理画面ではなく、閲覧数、流入元、国・地域、端末種別の**集計値だけを表示する公開ページ**です。
- 個別閲覧者のIPアドレスをKirapara Newsのアクセス解析画面に表示する機能はありません。
- 収集したニュース本文や画像は各公開元から取得したもので、権利は各権利者に帰属します。

## 免責

各カードは元の公開ページへリンクします。取得元の仕様や利用条件の変更により、取得方法・表示可能な画像・更新頻度は変わることがあります。

実装差分析は過去の公開記事を自動照合した参考値です。同一コンテンツの判定や実装日の抽出には誤りが含まれる場合があります。
