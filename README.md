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
- GitHub Actions上のローカルQwenによる日本語翻訳 / 要約
- ニュース収集とAI推論を分離した軽量更新パイプライン
- GPT-5.6 Solによる1日3回の取りこぼし・翻訳品質監査
- Solが発見した欠落記事の補完と、誤訳・誤要約の保護付き修整
- GitHub Actions停止時のChatGPT外部watchdogによる自動再起動
- 原文表示への切り替え

## 📱 インストール

APKは使用しません。ブラウザからPWAを開いてホーム画面へ追加します。

1. https://ikegami-99.github.io/KRPR_news/ を開く
2. ブラウザの「ホーム画面に追加」または「アプリをインストール」を選ぶ
3. Kirapara News のアイコンから起動する

サイト側を更新すれば新しいUIが配信されるため、APKの再インストールやPlay Storeは不要です。

## 🧭 更新アーキテクチャ

ニュース収集、Qwen翻訳、Sol監査、死活監視を別系統にしています。

```text
公開ニュース / SNS
        │
        ▼
毎時 :17  news-refresh.yml
        │
        ├─ 本文・日時・画像を整理
        ├─ 重複 / 小画像を除外
        ├─ Sol補完記事をマージ
        └─ 既存の翻訳キャッシュだけ反映
        │
        ▼
   data/news.json
        │
        ├──────────────► Kirapara News PWA
        │
        ▼
2時間ごと :37  ai-translate.yml
        │
        ├─ 未処理件数を確認
        ├─ 0件なら重いAIジョブをskip
        └─ 未処理があれば最大50件をQwen処理
        │
        ▼
data/translations.json
        │
        ▼
   data/news.jsonへ反映

別系統:
Sol監査 8:00 / 14:00 / 20:00 JST
ChatGPT watchdog 毎時 :30
```

収集とAIを切り離しているため、Qwen側に障害が起きても原文ニュースの更新自体は継続できます。

## 📰 ニュース収集

`news-refresh.yml` が**毎時17分**に通常のニュース収集を実行します。

GitHub Actionsでは毎時00分付近にscheduled workflowが集中しやすいため、ピークを避けて17分にしています。

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
  Qwen / Solの既存翻訳キャッシュを反映
      ※ここではLLM推論しない
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

## 🤖 Qwen翻訳・要約

通常処理では有料AI APIを使用せず、GitHub ActionsのCPU上で **Qwen2.5-3B-Instruct Q4_K_M** を `llama.cpp` 経由で実行します。

AI処理は `ai-translate.yml` に分離され、**2時間ごとの37分**に実行します。

### backlog方式

最初に軽量な `plan` ジョブが `data/news.json` と `data/translations.json` を確認します。

```text
未翻訳 / 再生成待ち記事を確認
        ↓
 backlog = 0 ?
   │          │
  Yes        No
   │          │
   ▼          ▼
重いAI      Qwenジョブ開始
ジョブskip      │
               ▼
          最大50件を処理
```

backlogが0件の場合、Qwenモデルの復元、`llama.cpp` のインストール、モデル推論を行う重い `translate` ジョブ自体を起動しません。

未処理がある場合は、1回につき**最大50件**を処理します。同じ記事は内容ハッシュとキャッシュキーで判定し、内容が変わっていなければ毎回再推論しません。

海外記事は `titleJa` / `bodyJa` / `summaryJa` を生成し、日本語記事は原文を維持しながら `summaryJa` を生成します。

固有名詞は `data/translation_glossary.json` の辞書を優先し、辞書にない名称は無理に日本語公式名へ変換しない方針です。

### Qwen / llama.cpp キャッシュ

Actionsでは以下をキャッシュします。

- `~/.cache/kirapara-models` : Qwen 2.5 3B Q4_K_M GGUF
- `~/.cache/pip` : Pythonパッケージとビルド済み `llama-cpp-python` wheel

Qwen GGUFはSHA256を確認してから使用します。`llama-cpp-python` もpipキャッシュを再利用するため、毎回ソースからビルドするコストを減らします。

AIジョブの必須ステップは失敗を握りつぶさず、モデル取得・runtime準備・推論に失敗した場合はworkflow側で失敗として見える構成です。

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

Sol管理の翻訳には `managedBySol: true`、記事側には `solLocked: true` が付きます。

AIジョブではQwen処理の前後にSol修整を再適用します。Sol版が有効なキャッシュとして存在する記事はQwenの再生成対象から除外されるため、後からQwenに上書きされません。

Solの修整そのものに誤りが見つかった場合は、より新しい根拠に基づいてSol側のoverrideを更新します。

## 🖼️ 画像

記事ページやフィードから `og:image`、`twitter:image`、RSS/Atom media/enclosure、記事本文画像などを候補として収集します。

URL上のfavicon、ロゴ、QR、アバター等の除外に加え、画像本体を取得できる場合は実寸を検査します。現在は短辺260px未満、または約15万画素未満の画像を低解像度候補として除外します。検査結果は `data/image_quality.json` にキャッシュし、毎時すべてを再取得しません。

PWA側でも画像の実寸を確認するため、サーバー側で寸法を判定できなかった小画像が混ざってもカードや全画面ビューアから除外します。

## 🛟 refresh watchdog

通常収集とは別に、ChatGPT側の **Kirapara Refresh Watch** が毎時30分にGitHub Actionsの実行状況を確認します。

直近の成功実行が90分以上見つからず、最近開始された `Refresh News Cache` もない場合は `data/refresh_kick.json` を更新してmainへコミットします。このファイルは `news-refresh.yml` のpush triggerに含まれているため、GitHub側のcronが途切れていても外部から収集workflowを起動できます。

直近60分以内にwatchdogがキック済みの場合は重複起動を避けます。

## 🚦 同時実行の制御

ニュース収集とAI翻訳はどちらも `kirapara-data-writer` という同じconcurrency groupを使用し、`cancel-in-progress: false` にしています。

これにより、収集workflowとAI workflowが同時に `data/news.json` / `data/translations.json` を更新して競合するのを避け、先に始まった処理が完了してから次の処理へ進みます。

## 🧱 構成

```text
KRPR_news/
├─ .github/workflows/
│  ├─ news-refresh.yml       # 毎時:17のニュース収集。重いLLM推論はしない
│  ├─ ai-translate.yml       # 2時間ごと:37のQwen翻訳/要約。最大50件
│  ├─ regenerate-ai.yml      # 指定記事のQwen結果を再生成
│  ├─ gap-analysis.yml       # 実装ギャップ解析
│  └─ pages.yml              # GitHub PagesへPWAを公開
├─ data/
│  ├─ news.json              # PWAが読む統合ニュース
│  ├─ translations.json      # Qwen / Sol 翻訳キャッシュ
│  ├─ sol_news.json          # Solが発見した取りこぼし記事
│  ├─ sol_overrides.json     # Solによる翻訳・要約修整
│  ├─ sol_audit_state.json   # Sol全件監査の進捗
│  ├─ refresh_kick.json      # ChatGPT watchdogからの再起動トリガー
│  ├─ translation_glossary.json
│  ├─ article_dates.json
│  ├─ image_quality.json
│  └─ gap_analysis.json
├─ docs/
│  ├─ index.html
│  ├─ app.js
│  ├─ ui_fixes.js
│  ├─ share.js
│  ├─ styles.css
│  ├─ theme-kawaii.css
│  ├─ layout-fixes.css
│  ├─ manifest.webmanifest
│  ├─ sw.js
│  └─ icon.svg
└─ scripts/
   ├─ fetch_news.py
   ├─ merge_direct_official.py
   ├─ enrich_sources.py
   ├─ enrich_social_images.py
   ├─ upgrade_x_images.py
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

- `news-refresh.yml`: 毎時17分。ニュース収集と既存翻訳キャッシュ反映
- `ai-translate.yml`: 2時間ごとの37分。backlogがある場合だけ最大50件をQwen処理
- `Kirapara Refresh Watch`: 毎時30分。収集workflowの停止を外部監視
- Sol監査: 8:00 / 14:00 / 20:00 JST。取りこぼしと翻訳品質を外部監査

PWAは `data/news.json` をネットワーク優先で読み、UIのアプリシェルだけService Workerでキャッシュします。

## 💰 運用コスト

通常のニュース収集・Qwen翻訳は、公開GitHubリポジトリ、GitHub Pages、標準GitHub-hosted Actions、無料公開データ取得経路を利用しており、追加の有料AI APIを前提にしていません。

AIを毎時の収集から分離し、backlog 0なら重いAIジョブを起動しないことで、runner時間、モデル復元、Pythonビルドの無駄を減らしています。

Sol監査とrefresh watchdogは運用者のChatGPT定期タスクを利用するため、GitHub Actions上でGPT-5.6 Solを動かしているわけではありません。利用可能性や制限はChatGPT側の契約・機能に依存します。

GitHubや外部サービスの料金・利用条件は将来変更される可能性があります。

## 🔒 プライバシー

- PWAの利用にユーザー登録不要
- 位置情報・連絡先不要
- 通常の翻訳・要約はGitHub Actions上のローカルQwenで処理
- OpenAI / DeepL / Google翻訳等の有料翻訳APIを通常収集パイプラインには組み込まない
- Sol監査では運用者のChatGPT定期タスクが公開Web情報と公開GitHubリポジトリの内容を確認する
- refresh watchdogは公開GitHub Actionsの実行状態と `data/refresh_kick.json` だけを扱う

## ⚖️ コンテンツと免責

各記事は元の公開ページへリンクします。記事本文・画像等の権利は各権利者に帰属します。公開ページ、RSS、RSSHub、検索結果などの仕様や各サービスの規約変更により、取得方法や取得可能なソースは変わることがあります。
