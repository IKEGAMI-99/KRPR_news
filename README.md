# Kirapara News ✨

日本版「きらめきパラダイス」、中国版「以闪亮之名」、Global版「Life Makeover」、韓国版「Stylight」の公開ニュースを、1つのタイムラインで確認する非公式PWAです。

**公開PWA:** https://ikegami-99.github.io/KRPR_news/

**現在の安定版:** `v1.0.0 Stable`（2026-08-28）  
**Release:** https://github.com/IKEGAMI-99/KRPR_news/releases/tag/v1.0.0

> [!IMPORTANT]
> Kirapara Newsは非公式ファンプロジェクトです。Archosaur Games、VVANNA GIRLS、各地域の運営会社、SNS・ニュース各社とは関係ありません。
>
> 本サイトはニュース収集、データ整理、画像処理、翻訳・要約、公開更新の大部分を自動処理して運営しています。すべての記事や更新内容を公開前に人が個別確認しているわけではありません。重要な日時、価格、報酬、イベント条件などは必ず元記事・公式情報をご確認ください。

## 安定版について

`v1.0.0` から現行の配布形態を **PWA版に一本化**しています。ブラウザから公開PWAを開き、ホーム画面へ追加することでアプリとして利用できます。

過去の `v0.3.x` ReleaseにあるAndroid APKは旧ネイティブ版です。現在の `main` ではAndroidネイティブ実装とAPKビルドWorkflowを削除しているため、旧APKを現行 `v1.0.0` の配布物として再利用していません。現在の機能・収集ロジック・Gemma 4翻訳・画像処理はPWA版を基準にしています。

`v1.0.0` のReleaseは、単体テストとJavaScript構文チェックに成功した `main` のスナップショットをStableとして固定します。ニュース本文や翻訳キャッシュはその後も定期Workflowで更新されるため、Releaseタグはアプリ本体の安定基準点、公開PWAのニュースデータは継続更新される運用です。

## 主な機能

- 🇯🇵 日本 / 🇨🇳 中国 / 🇰🇷 韓国 / 🌐 Global の統合タイムラインと地域フィルター
- 公式サイト、X、TikTok、YouTube、Weibo、Bilibili、TapTap、好游快爆、Steamなどの横断収集
- 公式X / Bilibiliの複数Feedを突き合わせ、古いキャッシュの混入や一時障害でも最新投稿と直前履歴を保持
- 同一ニュースを1枚のカードへ統合し、Weibo / TapTap / Bilibiliなど複数の元記事ボタンを保持
- 複数画像のスワイプ表示と全画面ビューア
- Weibo画像のリポジトリ内ミラーと、GitHub Pages同一オリジンからの安定配信
- TapTap記事では本文に属する画像を優先し、ページ共通画像や無関係画像の混入を抑制
- 低解像度画像、ロゴ、QR、トラッキング画像などの除外
- Gemma 4 E4Bによる日本語翻訳・箇条書き要約
- 原文 / 日本語の切り替え、共有、ライト / ダークテーマ
- 海外版と日本版の公開記事を照合する実装差分析
- GA4の集計値を確認するアクセス解析ページ
- ホーム画面への追加と、アプリシェルのオフライン利用
- ヘッダーに「最後にクロールが完了した時刻」だけを表示

検索バーと旧トップ3予測UIは2026-08-28に完全削除しました。関連するUI、JavaScript、CSS、収集・AI処理コードも削除しています。

## 自動運営について

Kirapara Newsは、定期実行されるGitHub Actionsと収集・整形スクリプトを中心に自動運営しています。

通常時は、ニュース取得、重複統合、日時・画像の正規化、Weibo画像のミラー、Gemma 4 E4Bによる翻訳・要約、GitHub Pagesへの反映までが自動で進みます。一部の品質監査、例外対応、機能改善、障害修正は必要に応じて手動で行います。

自動処理を前提としているため、取得元の仕様変更、通信障害、AIの誤認識などにより、記事の取得漏れ、反映遅延、重複、誤った画像、翻訳・要約の誤りなどが発生する可能性があります。

## 設計思想

Kirapara Newsは「大量の海外公式情報を、できるだけ手間なく追えること」を最優先に設計しています。そのため、完全な編集型ニュースサイトではなく、**元情報への導線を保った自動集約レイヤー**として構成しています。

### 1. 元情報を最優先する

Kirapara News内の翻訳、要約、実装差分析はあくまで補助情報です。記事カードには可能な限り元記事URLを保持し、同じ告知が複数媒体に存在する場合も `sources` に各URLを残します。サイト内表示だけで情報を閉じず、最終確認は公式サイトや公式SNSへ戻れることを前提にしています。

### 2. 障害時に「消す」より「直前の正常値を残す」

外部Feedが一時的に空になった、取得先がタイムアウトした、といった障害を「公式が投稿を削除した」と誤認すると、大量の記事が一度に消える危険があります。そのため、公式X / Bilibiliの媒体単位の履歴保護など、**last known good（最後に確認できた正常値）を優先するフェイルセーフ**を採用しています。

一時的に少し古い情報が残ることより、取得障害だけで過去記事が大量消失することのほうを重大な障害として扱います。

### 3. AIを必須経路にしない

AI翻訳・要約は便利ですが、モデル起動失敗や生成エラーがニュース取得そのものを止めてはいけません。原文ニュースの収集・保存とAI処理を分離し、AIが失敗しても原文のタイムラインは継続して更新できる構成にしています。

翻訳結果には品質検査を入れ、手動で確認・修正した結果は `managedBySol` / `solLocked` で自動再生成から保護します。自動化を優先しつつ、人が直した正しい情報を機械が翌時間に壊す、という悲しい自動化あるあるを避ける設計です。

### 4. 専用サーバーをできるだけ持たない

常時稼働する専用アプリサーバーや独自データベースを前提にせず、GitHub Actionsをバッチ処理基盤、Gitリポジトリ内のJSONをデータ層、GitHub Pagesを配信基盤として利用しています。

構成要素を減らすことで、個人運営でも保守しやすく、処理履歴やデータ変更をGitのコミットとして追跡できることを重視しています。外部サービスへの依存はニュース取得元とGA4など必要な範囲に限定しています。

### 5. 失敗を局所化する

1つのニュースソース、画像、AI処理、分析機能が失敗しても、サイト全体が使えなくならないことを重視しています。取得先ごとのフォールバック、画像ミラー、ネットワーク優先＋ローカル保持、原文表示の維持などを組み合わせ、個別機能の障害を全体障害へ広げにくくしています。

### 6. 軽さと透明性を優先する

フロントエンドはビルド必須の大型フレームワークを使わず、HTML / CSS / JavaScriptを直接配信します。ニュースデータもJSONとして確認でき、収集・整形・翻訳・表示の各段階をリポジトリ上で追跡できます。

機能を追加する際も、見た目の派手さより「更新が止まらない」「元記事へ戻れる」「原因を追える」「後から直せる」を優先します。

## 技術構成

Kirapara Newsは、大きく **収集層 / 正規化・保存層 / AI処理層 / 配信層 / 監視・分析層** に分けています。

| 層 | 主な技術 | 役割 |
| --- | --- | --- |
| 収集 | Python / GitHub Actions | 各公式サイト・SNS・Web記事の取得 |
| 正規化・保存 | Python / JSON / Git | 日時、画像、地域、出典、重複の正規化と履歴管理 |
| AI処理 | Gemma 4 E4B / LiteRT-LM | 日本語翻訳、要約、品質検査 |
| 配信 | GitHub Pages / HTML / CSS / JavaScript / Service Worker | PWAとしてタイムラインを表示 |
| 監視・分析 | GitHub Actions / GA4 / watchdog / Sol監査 | 更新状態、利用状況、品質の確認 |

### データをAPIではなくJSONで受け渡す理由

フロントエンドと定期処理の間に常駐APIサーバーを置かず、`data/news.json`、`data/translations.json`、`data/crawl_status.json` などを明示的なデータ契約として利用しています。

これにより、GitHub Pagesは静的配信のまま保てます。また、現在の状態をリポジトリから直接確認でき、問題が起きた場合も「収集」「正規化」「翻訳」「表示」のどこで壊れたのかを切り分けやすくなります。

主なJSONの役割は次のとおりです。

| ファイル | 役割 |
| --- | --- |
| `data/news.json` | PWAが読む正規化済みニュース本体 |
| `data/translations.json` | AI翻訳・要約キャッシュ |
| `data/crawl_status.json` | 最後にニュース収集が正常完了した時刻 |
| `data/article_dates.json` | 検証済みの記事公開日時 |
| `data/image_quality.json` | 画像候補の品質判定結果 |
| `data/sol_news.json` / `data/sol_overrides.json` | 手動監査・補正情報 |
| `data/gap_analysis.json` | 地域ごとの公開情報比較結果 |
| `data/stable_release.json` | Stable Releaseの基準バージョン |

### 収集パイプライン

収集は媒体ごとの取得方法を完全に同一化せず、取得先の性質に合わせて分けています。RSSや通常HTMLで安定して取れる媒体は一般的な取得処理を使い、TapTap、好游快爆、Weibo、WeChatなど特殊な媒体は専用処理やフォールバックを持ちます。

収集後は地域、タイトル、本文、公開日時、画像、元URLを正規化し、その後に同一ニュースの統合、画像品質判定、手動補正、既存翻訳の再適用を行います。最終的に `data/news.json` がPWA向けの単一タイムラインになります。

### 同一ニュースの統合

同じ公式告知がWeibo、TapTap、Bilibiliなど複数媒体へ投稿される場合、タイムライン上で同じ内容が何枚も並ばないように `scripts/merge_duplicate_sources.py` で統合します。

ただし統合時も情報源は捨てず、各URLを `sources` 配列へ残します。代表本文・画像は情報量の多い候補を使い、元記事ボタンは媒体ごとに表示します。地域をまたいだ記事は自動統合しません。

### 画像処理

画像は単に最初に見つかったURLを採用せず、本文との関連性や表示品質を考慮します。低解像度画像、ロゴ、QRコード、トラッキング用画像、ページ共通素材などをできるだけ除外します。

Weibo画像は外部CDN直リンクの表示が不安定なため `docs/media/weibo/` へミラーし、PWAではGitHub Pages同一オリジンの画像を優先します。Xでは元投稿側の高解像度候補を優先し、TapTapでは記事本文・投稿メディアに属する画像を優先します。

### AI翻訳・要約

AI処理はGitHub Actions上で **Gemma 4 E4B** を **LiteRT-LM 0.16.1** から実行します。モデルファイルはSHA-256を検証し、モデルとPython依存パッケージはActions cacheを利用して毎回の復元コストを抑えます。

記事本文のハッシュと翻訳revisionで再処理要否を判断し、古いrevisionの結果はbacklogとして順次置き換えます。生成後は日本語以外の文章が残っていないかなどを品質検査し、不適切な出力は有効な翻訳として採用しません。

15分ごとに最大3件をまとめて処理するのは、5分ごとにモデルを起動する方式よりrunner起動、checkout、モデル復元の回数を減らしながら、同等の最大処理量を維持するためです。

### 書き込み競合対策

ニュース収集とAI翻訳は、長いGemma処理中も原文ニュース収集を止めないため、それぞれ `kirapara-news-refresh` と `kirapara-ai-translate` の別concurrency groupで並行実行します。

両方が `data/news.json` と `data/translations.json` を更新し得るため、push前に最新`main`をmergeし、`scripts/merge_translation_results.py` で翻訳キャッシュを意味的に統合します。`managedBySol` の監査済み結果を最優先し、それ以外は新しい `updatedAtEpoch` を採用します。競合時は、収集側が新しい原文記事セットを保持して最新翻訳を再適用し、翻訳側は最新の収集結果へ生成済み翻訳を再適用します。pushは最大4回再試行するため、同時実行でも一方の結果を失いません。

### PWAとキャッシュ戦略

Service Workerはアプリシェルをキャッシュしますが、ニュースJSON、アクセス解析JSON、外部画像を固定キャッシュしません。ニュースはネットワーク優先で取得し、取得できない場合のみ端末に残る直前データを利用します。

この方針は「オフラインでも画面自体は開ける」「しかしオンライン復帰後も古いニュースを延々見せない」の両立を狙っています。Service Workerが更新された場合はcontroller変更時に既存タブを一度だけ再読み込みし、古いJavaScriptや画像処理ロジックが残り続ける問題も避けます。

### テストとStable Release

Python側は `unittest` でプロジェクト構造、各収集処理、重複統合、クロール状態、公式X履歴保護などを検査します。Stable Release作成時はPython単体テストに加え、`docs/**/*.js` のJavaScript構文チェックと主要JSONの妥当性検査を通過したコミットだけをRelease対象にします。

Stableタグはニュースデータを凍結するものではなく、PWA本体の安定基準点です。公開ニュースと翻訳キャッシュはStable公開後も定期Workflowで更新され続けます。

## AI / エージェント向け引継ぎ

このリポジトリを別のAI、コーディングエージェント、自動保守ツールが編集する場合は、**[`AI_CONTEXT.md`](./AI_CONTEXT.md) をREADMEとセットで読んでください。** `AI_CONTEXT.md` には人間向け説明よりも、現在の正本ファイル、データの優先順位、不変条件、障害時の判断、廃止済み機能、検証手順を機械的に判断しやすい形式で記載しています。

特に次の条件は、明示的な仕様変更がない限り維持します。

- AI翻訳が失敗しても原文ニュース収集を止めない
- 一時的な取得障害を「記事削除」と解釈せずlast known goodを保持する
- 同一ニュース統合後も媒体ごとの元URLを `sources` に残す
- `managedBySol` / `solLocked` の手動監査結果を自動処理で上書きしない
- JAPAN / CHINA / KOREA / GLOBALをまたいで記事を自動統合しない
- ニュースJSONをService Workerで固定キャッシュしない
- 分離したdata writerの意味的マージ、監査済み翻訳優先、最大4回のpush再試行を維持する
- Stable Releaseのテストgateを迂回しない
- 検索バー、旧「先行情報トップ3」、予測UIを勝手に復活させない
- `docs/x-image-fix.js` は削除済みlegacyではなく現行の有効機能として扱う

AIが変更を完了したと判断する前に、関連実装・テスト・Workflowを確認し、GitHubへ書き込んだ後は再fetchして実際の反映まで確認することを運用ルールとします。

## 更新アーキテクチャ

```text
公開サイト / SNS / RSS
        │
        ▼
毎時 :00  news-refresh.yml
        │
        ├─ 収集
        ├─ 公式X取得失敗時は直前の公式履歴を保持
        ├─ 同一ニュースを統合し複数の出典URLを保持
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
毎時 :07 / :22 / :37 / :52 ＋ 収集完了時  ai-translate.yml
        │
        ├─ 未処理が0件なら重いAIジョブを開始しない
        ├─ 未処理があれば1回最大3件をGemma 4で処理
        └─ 日本語品質検査後に翻訳キャッシュへ保存
```

ニュース収集は毎時00分に開始します。GitHub Actionsの混雑や取得先の応答時間により実際の完了時刻は数分以上ずれることがあります。ヘッダーの「最終更新」は記事の公開日時ではなく、`news-refresh.yml` が収集・画像処理まで正常に完了して `data/crawl_status.json` を更新した時刻です。新着記事が0件でもクロール自体が成功すればこの時刻は更新されます。

5分ごとに1件ずつ処理していたAI構成は、モデル復元・ランタイム準備・checkoutの回数が多すぎるため廃止しました。現在は15分ごとに最大3件をまとめ、同等の最大処理量を保ちながらrunner起動回数を4分の1にしています。

ニュース収集とAI処理は `kirapara-news-refresh` / `kirapara-ai-translate` の別concurrency groupで並行実行します。競合時は単純なrebaseに頼らず、最新`main`と生成済みキャッシュを意味的に統合し、監査済み翻訳または新しい翻訳を残して最大4回pushを再試行します。定期cronの取りこぼしに備え、`Refresh News Cache` が成功すると `workflow_run` でもAI処理を起動します。

## ニュース収集

主な対象は次のとおりです。

| 地域 | 主なソース |
| --- | --- |
| 🇯🇵 日本 | 公式サイト / 公式X / TikTok / YouTube / 国内Webニュース |
| 🇨🇳 中国 | 公式サイト / Weibo / Bilibili / TapTap / 好游快爆 / WeChat / 中国Webニュース |
| 🇰🇷 韓国 | 公式X / TikTok / YouTube / 韓国Webニュース |
| 🌐 Global | 公式サイト / 公式X / TikTok / YouTube / Steam / 海外Webニュース |

公式Xは `scripts/repair_social_sources.py` で複数の公開Feedを同時に取得し、最初に応答した1件だけを採用せず、取得できたFeedをURL単位で統合します。これにより、HTTP 200を返していても内容が古いミラーに引っ張られず、いずれかのミラーにある最新投稿を取り込めます。全Feedが失敗した場合も `scripts/preserve_official_x_history.py` で直前の公式投稿履歴を保持し、一時障害を「投稿が削除された」と誤認して過去記事を大量に消さない構成です。

Bilibiliも動態・記事・動画を別々に収集し、複数Feedの結果を統合します。取得先がすべて失敗した場合はGit履歴に残る直近のBilibili記事を復元します。中国地域のWeiboやTapTapだけが取得できた場合でも、その成功を理由にBilibiliのlast known goodを削除しません。

YouTubeはチャンネルページ内の任意の `channelId` ではなく、正規URLのチャンネルIDを優先します。Global版は公式チャンネル `UCaaIsX56nWN0fvGJXQ8yvhA` に固定し、同じ運営会社の別ゲーム動画が混入しないようにしています。

Google NewsのプロキシURLはタイムラインへ保存しません。Web記事は元記事URLと、取得できる場合は発行元の明示的な公開日時を優先します。確認済み日時は `data/article_dates.json`、画像検査結果は `data/image_quality.json` に保持します。

WeiboはSina CDNの直接表示がブラウザやPWA環境で不安定になるため、収集時に取得できた画像を `docs/media/weibo/` へ保存し、`imageMirrorUrls` として記事データに紐付けます。PWAはGitHub Pages上の同一オリジン画像を優先し、必要な場合のみ元のSina画像をフォールバックとして使います。Service Worker更新時には既存タブを一度リロードし、古い画像配信ロジックが残り続けないようにしています。

TapTapは中国版「以闪亮之名」の公式投稿一覧 `type=official` から直近のMoment IDを取得し、TapTapの公開Web API `webapiv2/moment/v3/detail` からタイトル、本文、公開時刻、画像を取得します。API取得に失敗した記事だけ個別Webページのメタデータへフォールバックし、`公式TapTap` として通常の翻訳・要約パイプラインへ流します。画像は記事本文・投稿メディアに紐付く候補を優先し、ページ共通素材や別投稿の画像が混入しにくいようにフィルタします。

好游快爆は「以闪亮之名」ゲームページの `官方帖子` セクションだけを収集対象にします。一般ユーザーのフォーラム投稿は対象外です。公式投稿の個別ページから本文、公開日時、画像を取得し、個別ページがJavaScript依存などで十分に読めない場合も、公式一覧で確認できたタイトルと元記事URLを保持して `官方好游快爆` として取り込みます。

同一地域で同じ告知と判定できる記事は `scripts/merge_duplicate_sources.py` で1件に統合します。公開時刻が近く、ハッシュタグや公式接頭辞を除去したタイトルが包含関係または高い類似度にある場合を同一候補とし、本文・画像は最も情報量の多い代表記事を使用します。各媒体のURLは `sources` 配列に残し、PWAでは `Weiboで開く`、`TapTapで開く`、`Bilibiliで開く`、`好游快爆で開く` のように元記事ごとのボタンを表示します。異なる地域の記事は統合しません。

WeChatは既存の公開Web探索による収集を継続しつつ、中国の公式リンク欄にも入口を追加しています。WeChatには安定した公開WebプロフィールURLがないため、メニューのWeChatリンクは公式公众号名「以闪亮之名」を検索できるSogou微信検索を開きます。

外部サービスの仕様変更、アクセス制限、RSSHub側の障害により、一部ソースを一時的に取得できない場合があります。地域全体ではなく媒体ごとに成功・失敗を扱い、取得できなかった公式X / Bilibiliは直前の正常データを保持します。

## 翻訳・要約

通常のAI処理はGitHub Actions上の **Gemma 4 E4B** と **LiteRT-LM 0.16.1** を使用します。

- モデルファイルはSHA-256を検証
- モデルとpipパッケージをActions cacheへ保存
- 記事本文のハッシュで再処理の要否を判定
- 現行revision以外のGemma結果はbacklogとして順次再処理
- 日本語以外の文章が残った出力を品質検査で無効化
- 固有名詞は `data/translation_glossary.json` を優先
- Sol管理の修正は `managedBySol` / `solLocked` で再上書きを防止

AI処理に失敗しても、原文ニュースの収集と表示は継続します。翻訳・要約は参考情報であり、日時、数値、報酬、開催条件などは必ず元記事も確認してください。

## PWAと表示性能

フロントエンドはビルド不要のHTML / CSS / JavaScriptです。

- `data/news.json` はネットワーク優先で取得し、失敗時は端末内の直前データを表示
- `data/crawl_status.json` はネットワークから取得し、端末には直近の成功値も保存
- 同一記事に複数の `sources` がある場合はカードを複製せず、元記事ボタンだけを複数表示
- タイトル下は件数や「最新記事」の日時を表示せず、クロール完了時刻だけを表示
- Service Workerはアプリシェルだけをキャッシュ
- ニュースJSON、アクセス解析JSON、外部画像はService Workerで固定キャッシュしない
- 画像ギャラリーは1つだけ生成し、非表示ギャラリーを複製しない
- 画像ビューアはスワイプ移動に対応し、戻る操作ではビューアやメニューを先に閉じる
- カード描画完了イベントで補助機能を更新し、複数の `MutationObserver` による全件再走査を行わない
- カードに `content-visibility: auto` を使用
- 新しいService Workerが制御を引き継いだ際は既存PWAタブを一度だけ再読み込みして更新を反映

## メニュー

メニュー上部にはホーム画面追加、実装差分析、アクセス解析を並べています。その下に各地域の公式リンク、自動更新スケジュール、運用情報を配置しています。

中国の公式リンク欄には、公式サイトが案内しているWeibo、Bilibili、百度贴吧、WeChat、小紅書、好游快爆に加え、公式投稿やストア説明で案内されているTapTap、抖音を表示します。WeChatと小紅書は公開プロフィールURLの安定性を考慮し、公式アカウント名を確認できる検索ページを入口にしています。ニュース転載サイトは公式リンク欄へ追加しません。

現在のスケジュール表示は実際のワークフローと揃えています。

- ニュース収集: 毎時 :00
- Gemma 4 E4B 翻訳・要約: 毎時 :07 / :22 / :37 / :52に加え、ニュース収集完了時にも起動、1回最大3記事
- Sol監査: 08:00 / 14:00 / 20:00 JST
- 更新watchdog: 毎時 :30、異常時のみ再起動

## ワークフロー

| Workflow | 実行 | 役割 |
| --- | --- | --- |
| `news-refresh.yml` | 毎時00分 | ニュース収集、公式X / Bilibiliの複数Feed統合と履歴保護、同一記事の出典統合、画像・日時の正規化、Weibo画像ミラー、クロール完了時刻の記録 |
| `ai-translate.yml` | 毎時07 / 22 / 37 / 52分、ニュース収集完了時 | backlog確認、最大3件のGemma 4 E4B翻訳・要約、競合時の意味的キャッシュ統合 |
| `regenerate-ai.yml` | リポジトリ所有者のIssue | 指定記事のAI結果を再生成 |
| `gap-analysis.yml` | 毎日06:30 JST | 地域別の実装差分析を更新 |
| `analytics-refresh.yml` | 6時間ごと | GA4の集計スナップショットを更新（公開は `pages.yml` に一本化） |
| `pages.yml` | `docs/**` 更新時 | GitHub PagesへPWAを公開 |
| `release-stable.yml` | Stable marker更新時 / 手動 | テスト後に指定バージョンのStable Releaseを作成 |

運用環境では、ChatGPT側のSol監査（08:00 / 14:00 / 20:00 JST）と更新watchdogも併用しています。これらはGitHub Actions内でGPTを実行する仕組みではなく、リポジトリ外の運用タスクです。

## v1.0.0 Stableの主な変更

- 現行PWAを最初の正式Stableとして固定
- Androidネイティブ版からPWA版へ配布基準を一本化
- 検索バー、旧トップ3予測UI、関連タグ付け処理を削除
- Gemma 4 E4B + LiteRT-LMへ翻訳・要約系を統一
- Gemma翻訳を15分ごと最大3件のバッチ処理へ変更
- 実装差分析から予測表示を外し、公開記事同士の比較に整理
- メニューの実装差分析直下にアクセス解析を追加
- Weibo画像を収集時にリポジトリへミラーし、Pages同一オリジン配信へ変更
- TapTap画像を記事メディア中心にフィルタし、無関係画像の混入を抑制
- 公式X Feed障害時に直前の公式投稿履歴を保持する保護処理を追加
- X画像は元投稿側の高解像度候補を優先
- 画像ビューアに左右スワイプ移動を追加
- 戻る操作で画像ビューアやメニューより先にPWA自体が閉じる問題を修正
- PWA更新後も古い画像ロジックが残る問題をService Workerのcontroller変更時リロードで修正
- ニュース収集を毎時00分へ戻し、クロール完了日時を独立ファイルで記録
- ヘッダー表示を「記事件数・最新記事日時」から「最終クロール完了日時のみ」へ変更
- 中国版の公式TapTap投稿を毎時収集する `fetch_taptap_official.py` を追加
- 中国版の好游快爆 `官方帖子` を毎時収集する `fetch_haoyoukuaibao.py` を追加
- 中国の公式リンク欄をWeibo / Bilibili / TapTap / 好游快爆 / 抖音 / 小紅書 / 百度贴吧 / WeChatまで拡張
- 同一ニュースを1カードへ統合し、複数媒体の元記事URLを `sources` として保持する処理を追加
- 複数出典の記事カードに媒体別の元記事ボタンを表示するUIを追加
- `main` がクロール中に進んだ場合の収集結果pushを最大4回再試行するように変更

## ディレクトリ構成

```text
KRPR_news/
├─ AI_CONTEXT.md
├─ .github/
│  ├─ release-notes/
│  │  └─ v1.0.0.md
│  └─ workflows/
│     ├─ news-refresh.yml
│     ├─ ai-translate.yml
│     ├─ regenerate-ai.yml
│     ├─ gap-analysis.yml
│     ├─ analytics-refresh.yml
│     ├─ pages.yml
│     └─ release-stable.yml
├─ data/
│  ├─ news.json
│  ├─ crawl_status.json
│  ├─ translations.json
│  ├─ translation_glossary.json
│  ├─ sol_news.json
│  ├─ sol_overrides.json
│  ├─ article_dates.json
│  ├─ image_quality.json
│  ├─ stable_release.json
│  └─ gap_analysis.json
├─ docs/
│  ├─ index.html
│  ├─ app.js
│  ├─ source-buttons.js
│  ├─ source-buttons.css
│  ├─ crawl-status.js
│  ├─ sw.js
│  ├─ gap.html
│  ├─ analytics/
│  ├─ media/weibo/
│  └─ 各機能のCSS / JS
├─ scripts/
│  ├─ fetch_news.py
│  ├─ fetch_taptap_official.py
│  ├─ fetch_haoyoukuaibao.py
│  ├─ fetch_wechat_official.py
│  ├─ preserve_official_x_history.py
│  ├─ merge_duplicate_sources.py
│  ├─ translation_engine.py
│  ├─ translation_quality.py
│  ├─ strict_gemma_translate.py
│  ├─ normalize_news.py
│  ├─ mirror_weibo_images.py
│  └─ 収集・画像・分析用スクリプト
└─ tests/
   ├─ test_project.py
   ├─ test_taptap.py
   ├─ test_haoyoukuaibao.py
   ├─ test_duplicate_sources.py
   ├─ test_preserve_official_x_history.py
   └─ test_crawl_status.py
```

## ローカル確認

Python 3.12を想定しています。通常の静的検査と単体テストは外部パッケージ不要です。

```bash
python -m unittest discover -s tests -v
python -m http.server 8000
```

ブラウザで `http://localhost:8000/docs/` を開きます。localhostでは作業コピーの `data/news.json`、`data/crawl_status.json`、`data/gap_analysis.json` を読み、公開版ではGitHub上の `main` を読みます。

## プライバシーとアクセス解析

Kirapara Newsは、ニュース閲覧に必要のない個人情報を利用者へ要求しません。一方、公開PWAの利用状況を把握して表示や機能を改善するため、Google Analytics 4（GA4）を使用しています。

### Kirapara Newsが直接要求しない情報

- 利用にユーザー登録は不要です。
- 氏名、メールアドレス、電話番号、連絡先の入力は必要ありません。
- 端末の位置情報権限や連絡先権限を要求する機能はありません。
- Kirapara News独自のユーザーアカウントや個人プロフィールは作成しません。

### Google Analytics 4で扱う情報

公開ページではGA4により、ページ表示、参照元、ブラウザ・端末に関する情報、国・地域などのおおよその地域情報を集計します。また、Kirapara Newsの実装では次の操作をイベントとして記録します。

- 元記事ボタンのクリック（リンク先URLとボタン表示名）
- 地域タブの切り替え（日本 / 中国 / 韓国 / Globalなど）
- 「続きを読む」の操作

Google AnalyticsではCookieや類似の識別子が利用される場合があります。これらは利用状況やセッションを集計するためにGoogle側で処理されます。

Google AnalyticsはIPアドレスを国・地域などのおおよその位置情報を判定するために使用しますが、Google Analyticsの仕様上、IPアドレス自体はGA4へ記録・保存されません。Kirapara Newsの運営者がGA4から個々の閲覧者のIPアドレスを確認することもできません。

Google Analyticsによるデータの取り扱いについては、GoogleのプライバシーポリシーおよびGoogle Analyticsの説明が適用されます。

- Google プライバシーポリシー: https://policies.google.com/privacy?hl=ja
- Google Analyticsにおけるデータ保護: https://support.google.com/analytics/answer/9019185?hl=ja

### 公開アクセス解析ページ

`/analytics/` は非公開の管理画面ではありません。閲覧数、流入元、国・地域、端末種別などの**集計値だけを表示する公開ページ**です。個々の閲覧者を識別する情報やIPアドレスを表示する機能はありません。

### 利用目的

アクセス解析データは、Kirapara Newsの利用状況の把握、UIやニュース収集機能の改善、表示上の問題や障害の把握を目的として使用します。

通常のニュース翻訳・要約はGitHub Actions上で動作するローカルAIモデルで処理します。閲覧者が入力した個人情報を翻訳・要約AIへ送信する機能はありません。

収集したニュース本文や画像は各公開元から取得したもので、著作権その他の権利は各権利者に帰属します。

## 免責事項

Kirapara Newsは自動収集・自動処理を中心に運営する非公式ファンプロジェクトです。掲載情報の正確性、完全性、最新性、継続的な提供を保証するものではありません。

取得元の仕様変更、通信障害、データ解析の誤り、AI翻訳・要約の誤りなどにより、記事の取得漏れ、反映遅延、誤表示、誤訳、誤った要約、画像の取り違えなどが発生する場合があります。掲載内容と公式発表に相違がある場合は、元記事および各公式媒体の情報を優先してください。

本サイトの情報を利用したこと、または利用できなかったことによって生じた損害・不利益について、法令上免責が認められない場合を除き、運営者は責任を負いません。ゲーム内の購入、応募、イベント参加、期限を伴う判断などは、必ず公式情報を確認したうえで利用者自身の判断で行ってください。

収集したニュース本文、画像、名称、商標その他の権利は各権利者に帰属します。権利者から掲載内容について要請があった場合は、確認のうえ必要な対応を行います。

実装差分析は公開記事を自動照合した参考情報です。同一コンテンツの判定、実装日の抽出、地域差の推定には誤りが含まれる場合があります。

## バグ報告・改善提案

バグ、不具合、表示崩れ、記事や画像の誤り、取得漏れ、翻訳・要約の問題、改善してほしい点などがありましたら、Xの **[@ikegami_krpr](https://x.com/ikegami_krpr)** までご連絡ください。

自動運営のため、すべての問題を即時に検知できるとは限りません。具体的な記事URL、画面の状況、再現手順などを添えていただけると原因確認に役立ちます。
