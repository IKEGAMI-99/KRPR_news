# Kirapara News — AI / Agent Handoff Context

このファイルは、人間向けの概要説明よりも **AI、コーディングエージェント、自動保守ツールがリポジトリを誤解せず引き継ぐこと** を目的にしています。

README.md が利用者・開発者向けの説明、`AI_CONTEXT.md` が機械的な引き継ぎ情報です。両者が矛盾する場合は、実装・テスト・Workflowを確認し、READMEとこのファイルを同時に更新してください。

## Machine-readable project summary

```yaml
project:
  name: Kirapara News
  repository: IKEGAMI-99/KRPR_news
  default_branch: main
  deployment: GitHub Pages PWA
  current_stable: v1.0.0
  native_android_current: false
  purpose: aggregate public official news for four regional versions of Life Makeover / Kirapara

regions:
  JAPAN: きらめきパラダイス
  CHINA: 以闪亮之名
  KOREA: Stylight
  GLOBAL: Life Makeover

runtime_model:
  id: litert-community/gemma-4-E4B-it-litert-lm
  variant: LiteRT-LM
  revision: gemma-4-e4b-it-litertlm-summary-facts-region-titles-strict-ja-v2
  summary_format_version: 4
  runtime: LiteRT-LM 0.16.1
  context_token_limit: 8192
  output_token_limit: 3000
  failed_article_attempts: 3
  failed_article_cooldown: "6 hours"
  role: Japanese translation and summary

schedules:
  news_refresh: "hourly at minute 00"
  news_refresh_watchdog: "hourly at minutes 17 and 47 plus after translation; recover when last success is at least 70 minutes old"
  ai_translate: "hourly at minutes 07,22,37,52 and after successful Refresh News Cache workflow completion; max 3 articles/run"
  gap_analysis: "daily 06:30 JST"
  analytics_refresh: "every 6 hours"

write_coordination:
  collector_concurrency_group: kirapara-news-refresh
  translator_concurrency_group: kirapara-ai-translate
  manual_regeneration_concurrency_group: kirapara-data-writer
  merge_script: scripts/merge_translation_results.py
  conflict_policy: "reviewed translation first; otherwise newest updatedAtEpoch; failure cooldown uses newest lastFailureAtEpoch and is cleared by a newer successful translation"
  push_retry: "merge latest main semantically and retry up to 4 times"

legal:
  terms: docs/terms.html
  privacy: docs/privacy.html
  shared_style: docs/legal.css
  contact: "@ikegami_krpr"
  required_navigation:
    - docs/index.html footer
    - docs/menu-install.js menu
  offline_shell: true

release:
  marker: data/stable_release.json
  workflow: .github/workflows/release-stable.yml
  gate:
    - Python unittest
    - JavaScript syntax check
    - important JSON validation

contact:
  x: "@ikegami_krpr"
```

## Source of truth / canonical files

AIが変更を始める前に、対象機能について少なくとも以下を確認してください。

| 対象 | 正本・確認先 |
| --- | --- |
| 公開ニュース本体 | `data/news.json` |
| 翻訳・要約キャッシュ | `data/translations.json` |
| 現行AIモデル・revision | `scripts/strict_gemma_translate.py` |
| 翻訳の共通処理 | `scripts/translation_engine.py` / `scripts/translation_quality.py` |
| 並行書き込み時の翻訳統合 | `scripts/merge_translation_results.py` |
| 最終クロール成功時刻 | `data/crawl_status.json` |
| 手動監査・上書き | `data/sol_news.json` / `data/sol_overrides.json` |
| 画像品質判定 | `data/image_quality.json` |
| 記事日時補正 | `data/article_dates.json` |
| 実装差分析 | `data/gap_analysis.json` |
| Stable基準 | `data/stable_release.json` |
| PWA本体 | `docs/index.html` / `docs/app.js` / 関連CSS・JS |
| Service Worker | `docs/sw.js` |
| 利用規約 | `docs/terms.html` |
| プライバシーポリシー | `docs/privacy.html` |
| 法的ページ共通スタイル | `docs/legal.css` |
| ニュース収集Workflow | `.github/workflows/news-refresh.yml` |
| 収集ステップの上限・ロールバック | `scripts/run_refresh_pipeline.py` |
| AI Workflow | `.github/workflows/ai-translate.yml` |
| Stable Release gate | `.github/workflows/release-stable.yml` |
| 構造上の回帰防止 | `tests/test_project.py` |

READMEの文章だけで現在仕様を推測しないでください。READMEは説明書であり、実装の正本ではありません。

## Core invariants — do not break without explicit intent

以下は現在の設計上の不変条件です。明示的な仕様変更要求がない限り維持してください。

1. **原文ニュース収集はAIに依存しない。** AIが失敗しても原文タイムラインは更新可能であること。
2. **元記事URLを失わない。** 同一ニュースを統合しても各媒体URLは `sources` に保持すること。
3. **一時的な取得障害を削除と解釈しない。** last known good を優先し、公式X / Bilibiliなど媒体単位の履歴を不必要に消さないこと。
4. **外部取得を無期限に待たない。** `run_refresh_pipeline.py` の処理別ハードタイムアウト、失敗時スナップショット復元、Workflow全体15分上限を維持すること。
5. **手動監査済み翻訳を自動処理で破壊しない。** `managedBySol` / `solLocked` を尊重すること。
6. **異なる地域の記事を自動統合しない。** JAPAN / CHINA / KOREA / GLOBAL の境界を保持すること。
7. **ニュースJSONを固定キャッシュしない。** PWAは新しいニュースを取りに行けること。
8. **Service Worker更新後に古い実装が残留し続けないこと。** 現行のcontroller変更時リロード設計を壊さないこと。
9. **並行するニュース収集とAI書き込みの結果を失わない。** 分離concurrency group、`merge_translation_results.py`、監査済み翻訳優先、最大4回のpush再試行を維持すること。
10. **Stable Releaseをテストなしで作らない。** gateを迂回しないこと。
11. **表示上の最終更新は記事日時ではなくクロール成功時刻。** `data/crawl_status.json` を使用すること。
12. **利用規約とプライバシーポリシーへの導線を消さない。** `docs/terms.html` / `docs/privacy.html` をメニューとフッターから到達可能にし、Service Workerのshellにも保持すること。
13. **GA4の実装を変えたらプライバシーポリシーも更新する。** 新しいイベント、識別子、外部解析サービスを追加・削除した場合、`docs/privacy.html` とREADMEの説明を同期すること。
14. **1件の生成失敗で翻訳backlog全体を止めない。** 3回の生成試行を使い切った記事は失敗状態を保存して6時間後まで後回しにし、後続記事へ進むこと。

## Explicitly removed / deprecated behavior

以下は過去に存在したが、現在は意図的に削除済みです。ユーザーから復活要求がない限り再導入しないでください。

- 検索バー
- 「先行情報トップ3」および先行情報予測UI
- 予測用タグ付け・FORECAST表示
- `docs/topics.js`
- `docs/topics.css`
- `docs/early-info.css`
- `scripts/tag_early_info.py`
- `feed-status.js`
- `ui_fixes.js`
- `gallery-strip.js`
- `month-sections.js`
- `early-info.js`
- `dev-release.js`
- 旧 `theme-kawaii.js` レイヤー
- `.github/workflows/reset-lfm-state.yml`
- 現行mainにおけるAndroidネイティブアプリ / APKビルド経路

注意: `docs/x-image-fix.js` は削除済みlegacyではありません。**現在も有効なX画像処理レイヤー**です。削除対象として扱わないでください。

`tests/test_project.py` には上記の一部を回帰させないためのテストがあります。テストが仕様と衝突した場合は、単にテストを消すのではなく、現在の意図を確認してください。

## Legal / privacy contract

利用規約とプライバシーポリシーは、README内の説明よりも利用者向けの公開正本として扱います。

- `docs/terms.html`: 非公式ファンプロジェクト、自動運営、情報の非保証、外部リンク、権利帰属、責任範囲、サービス変更・停止、連絡先を説明する。
- `docs/privacy.html`: 登録不要、直接要求しない情報、GA4で扱う情報、計測イベント、Cookie等、IPアドレスの扱い、公開analyticsページ、外部サービス、連絡先を説明する。
- `docs/legal.css`: 両ページの共通表示。PWA本体で保存された `kirapara-news-theme` を各ページが読み、light / darkを引き継ぐ。
- `docs/index.html` と `docs/menu-install.js`: 利用者が規約・プライバシーへ到達するための導線。
- `docs/sw.js`: `terms.html`、`privacy.html`、`legal.css` をAPP_SHELLに含め、PWAからオフラインでも確認可能にする。
- `tests/test_project.py`: 上記ページ・導線・Service Worker登録・問い合わせ先の存在を回帰テストする。

規約文言を変更する場合は、実装事実と一致しているか確認してください。特にGA4で新しいイベントを送る変更、広告・課金・会員登録・ユーザー投稿・位置情報権限などを導入する変更は、法的ページの更新対象です。

## Data flow and precedence

概念上の処理順序は次です。

```text
external public sources
  -> source-specific collectors (hard deadline per step)
  -> restore pre-step snapshot and continue on optional timeout
  -> normalization
  -> source/history preservation
  -> duplicate merge
  -> article date/image quality correction
  -> manual Sol data/overrides reapplied
  -> valid translation cache reapplied
  -> data/news.json
  -> PWA

new/invalid translation backlog
  -> Gemma 4 E4B
  -> quality validation
  -> failed 3 attempts: persist cooldown and continue with later articles
  -> data/translations.json
  -> next news refresh / PWA rendering
```

重要なのは、**後段の自動処理が前段の信頼度の高い補正を無条件に上書きしないこと**です。

## Translation validity contract

現行の自動翻訳が「処理済み」と見なされるためには、記事本文との整合に加えて、少なくとも以下のmetadataが現行値と一致する必要があります。

```yaml
model: "litert-community/gemma-4-E4B-it-litert-lm:LiteRT-LM"
modelRevision: "gemma-4-e4b-it-litertlm-summary-facts-region-titles-strict-ja-v2"
summaryFormatVersion: 4
```

古いrevisionは表示され続ける場合がありますが、backlogから順次再処理される対象です。

LiteRT-LM Engineは `max_num_tokens=8192`、各生成は `max_output_tokens=3000` で実行します。`data/translations.json` の `failures` は翻訳本文ではなく運用状態です。現在の `contentHash` に対して3回の生成試行がすべて失敗した記事を6時間deferし、次のRunで後続記事を選べるようにします。原文変更、現行翻訳の成功、Sol管理結果の適用時は対応するfailureを破棄します。

`managedBySol` またはSol管理モデルとして明示されたエントリは別扱いで、有効な手動監査結果として保持されます。

ニュース収集とAI翻訳は別concurrency groupで並行可能です。競合時は `scripts/merge_translation_results.py` が監査済みエントリを最優先し、自動生成同士では `updatedAtEpoch` が新しい方を採用します。同時更新を単純なrebaseで解決しないでください。

## Source-specific knowledge

### X

- 公式Feedが一時的に空になった場合、`scripts/preserve_official_x_history.py` が直前履歴を保護します。
- `scripts/repair_social_sources.py` は最初に応答したFeedを採用して終了せず、全healthy mirrorのURLを統合して最も新しい投稿を残します。HTTP 200でも古いキャッシュを返すミラーがあるため、この比較をfirst-successへ戻さないでください。
- `docs/x-image-fix.js` はactiveです。
- 可能な限り元投稿側の高解像度画像候補を優先します。

### Bilibili

- `scripts/repair_social_sources.py` で動態・記事・動画を別々に収集し、複数Feedの結果を統合します。
- live Feedがすべて失敗した場合は、Git履歴にある直近のBilibili行をlast known goodとして復元します。
- 同じCHINA地域のWeibo / TapTap等が成功しても、Bilibili取得成功とはみなしません。媒体単位の障害を地域単位の成功で上書きしないでください。

### Weibo

- Sina CDN直リンクだけに依存しません。
- `scripts/mirror_weibo_images.py` で `docs/media/weibo/` にミラーします。
- `imageMirrorUrls` と元画像候補の対応を維持してください。

### TapTap

- 中国版公式 `type=official` を対象にします。
- 公開Web APIのMoment detailを優先し、失敗時に個別ページへフォールバックします。
- 記事本文・投稿メディアと無関係なページ共通画像を除外する方針です。

### 好游快爆

- `官方帖子` のみがニュース対象です。
- 一般ユーザー投稿を公式ニュースとして混入させないでください。

### WeChat

- 公開Web取得が安定しないため、通常媒体と同じ完全性を前提にしません。
- 公式リンク導線と公開Web探索を併用します。

## Failure semantics

AIや自動化エージェントは、障害時に次の優先順位を使用してください。

```text
preserve correct existing data
  > show slightly stale known-good data
  > show untranslated original data
  > omit one broken optional feature
  > delete historical data because a source returned empty
```

つまり、空レスポンス・一時403・タイムアウト・RSSHub障害などを、即座に「元記事削除」とみなしてはいけません。

## Safe modification protocol for another AI

コード変更を依頼されたAIは、原則として次の順で作業してください。

1. ユーザー要求を、UI / collector / data / AI / workflow / release / legal のどの層に影響するか分類する。
2. READMEだけでなく、関連実装とテストを読む。
3. 廃止済み機能を別名で復活させていないか確認する。
4. データを削除・再生成する変更では last known good と手動overrideへの影響を確認する。
5. Workflowを変更する場合はスケジュール、concurrency、書き込み対象を確認する。
6. PWA assetを変更する場合は `docs/index.html` と `docs/sw.js` の両方の参照を確認する。
7. GA4、Cookie、ユーザー入力、権限、外部解析サービスを変更する場合は `docs/privacy.html` を確認・更新する。
8. 自動運営、免責、外部リンク、禁止事項、サービス停止方針に影響する変更は `docs/terms.html` を確認する。
9. 変更後、最低限Python unit tests、対象JavaScriptの構文、重要JSONの妥当性を検査する。
10. GitHubへ書き込んだ後、**再fetchして実際に反映された内容を確認してから完了と報告する。**
11. READMEまたはAI_CONTEXTと実装が食い違った場合は、同じ変更で文書も更新する。

## Verification checklist

代表的な確認コマンド:

```bash
python -m unittest discover -s tests -v
node --check docs/app.js
node --check docs/menu-install.js
python -m json.tool data/news.json >/dev/null
python -m json.tool data/translations.json >/dev/null
python -m json.tool data/crawl_status.json >/dev/null
```

法的ページを変更した場合は `tests/test_project.py::ProjectStructureTests.test_legal_pages_are_linked_and_cached` 相当の条件も維持してください。

Stable Releaseでは `.github/workflows/release-stable.yml` のgateを正本としてください。

## Operational intent

このプロジェクトの優先順位は、概ね次です。

```text
1. official-source traceability
2. no catastrophic data loss on transient source failure
3. current news freshness
4. readable Japanese translation/summary
5. correct article images
6. low maintenance cost / automation
7. UI convenience
```

UI改善のために1〜5を犠牲にしないでください。

## When uncertain

仕様が曖昧な場合は、以下を証拠の強い順として扱ってください。

1. ユーザーの最新の明示要求
2. 現在mainの実装
3. 現在mainのテスト
4. 現在mainのWorkflow
5. `AI_CONTEXT.md`
6. `README.md`
7. 過去Releaseや旧Androidコード

古い実装や過去Releaseの存在だけを理由に、現行mainへ機能を戻さないでください。
