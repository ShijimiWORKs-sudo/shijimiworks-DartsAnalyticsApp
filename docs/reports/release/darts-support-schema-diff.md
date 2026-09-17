# DartsSupportApp スキーマ突合結果（§11）

最終更新: 2026-09-17

## 実施内容

`ShijimiWORKs-sudo/shijimiworks-DartsSupportApp` のGitHubリポジトリを
`git clone --depth 1`で取得し（読み取り専用、書き込み・push一切なし）、
以下を確認した：

- `src/db/schema.ts`（SQLite migration DDL、`CURRENT_SCHEMA_VERSION = 1`）
- `src/domain/types.ts`（ドメイン型）
- `src/domain/practice.ts`, `src/domain/assessment.ts`
- `src/db/repository.ts`（1234行、SQLite/メモリ両対応リポジトリ）
- `README.md`, `docs/IMPLEMENTATION_NOTES.md`

default branch: `codex/phase-daily-practice-form-ai-import`（他に3branch、
`main`は存在しない/未作成の模様）。

## 【重要な発見】DartsAnalyticsApp側の前提が実態と一致していない

DartsAnalyticsAppの設計書（`詳細設計書_v1.0.md` §2, §21, §Phase10）は
「既存の共通契約方針」「投擲座標の共通化」を前提に、
`account_id / player_id / practice_menu_id / game_session_id / record_id /
game_type / practice_type / BULL・DOUBLE・TRIPLE / throw coordinates /
sync_state / analysis_version` という最小フィールドを定義していた。

しかし実際のDartsSupportApp（2026-08-06時点でiPhone実機QA済みの初期版）は
**この契約と設計思想がほぼ完全に異なる**：

- **自動ゲーム進行・投擲座標データが存在しない**：`README.md`に明記
  「この初期版ではOpenAI API連携、動画の自動解析、骨格推定、正式な
  01/CRICKET/MATCHゲーム進行は実装していません」。COUNT-UP結果や
  1投ごとの座標を保存するテーブルは無い。
- **`practice_results`は手入力の主観的な振り返りログ**：
  `bull_count`（手入力）、`achievement_level`（4段階の主観評価）、
  `condition_label`、`body_feel`、`good_points`、`concern_points`など。
  構造化された得点・座標データではない。
- **フォーム評価はChatGPTクリップボード経由の自由記述テキスト解析**：
  `ai_form_assessments`は`raw_text`（ChatGPT応答全文）を見出し単位で
  パースして`parsed_json`に保存する仕組み（`stance/setup/takeback/
  release/followThrough/headShoulderElbow/threeThrowReproducibility/...`
  等の見出し）。DartsAnalyticsAppのような構造化された特徴量・confidence
  スコアは無い。
- **`form_videos`のdirectionは`front/side/back/slow/other`の5値**：
  DartsAnalyticsAppの4方向（正面・利き腕側面・反対側面・遠景）とは
  分類が異なる（`slow`はスローモーション撮影を指すと推測されるが未確認）。
- **IDの命名**：DartsSupportApp内部では主キーは単に`id`（テーブルごとに
  暗黙的に型付け）、外部キーが`account_id`/`player_id`等。
  DartsAnalyticsApp契約が想定する`game_session_id`/`record_id`という
  名前のフィールドは存在しない（`practice_sessions.id`が対応する概念に
  近いが、ゲームセッションではなく「練習セッション」）。
- **`practice_menu_id`に相当**：`practice_menu_templates.id` /
  `daily_practice_items.template_id`が近いが、COUNT-UPのような特定
  ゲームモードの概念とは無関係（自由記述の練習メニュー）。

## フィールド対応表（分かる範囲）

| DartsAnalyticsApp契約（docs §Phase10想定） | DartsSupportApp実装の対応物 | 一致度 |
|---|---|---|
| `account_id` | `accounts.id` | ほぼ一致（列名は`id`） |
| `player_id` | `players.id` | ほぼ一致 |
| `practice_menu_id` | `practice_menu_templates.id` or `daily_practice_items.id` | 概念が異なる（自由記述メニューであり、COUNT-UP等のゲームモード概念を含まない） |
| `game_session_id` | `practice_sessions.id` | 概念が異なる（「練習セッション」であり、DARTSLIVE HOME等の自動ゲームセッションではない） |
| `record_id` | 対応なし | DartsSupportAppに1投単位のレコード概念が無い |
| `game_type` | 対応なし | DartsSupportAppはゲームタイプを持たない（正式ゲーム進行は未実装と明記） |
| `practice_type` | `practice_menu_templates.purpose` / `target_area`（自由記述） | 構造が異なる（enumではなく自由文字列） |
| `BULL/DOUBLE/TRIPLE` | `practice_results.bull_count`（手入力の集計値のみ） | 大きく異なる（1投単位ではなくセッション集計、かつ手入力） |
| throw coordinates | 対応なし | 存在しない |
| `sync_state` | 対応なし | 存在しない（このアプリはローカル単体、同期の概念が無い） |
| `analysis_version` | 対応なし | 存在しない |

## 結論・評価

`SupportAppThrowRecord`（Phase 10で実装済み、`docs §Phase10`のフィールド
リストに忠実な実装）は、**設計書に書かれた仕様としては正確だが、実際に
存在するDartsSupportAppとは連携できない**。理由は契約の細部の不一致では
なく、両アプリが前提とするデータモデルそのものが異なるため：

- DartsAnalyticsApp: DARTSLIVE HOMEからの自動測定 + 1投単位の構造化
  座標データ + 自動フォーム解析（confidence付き）。
- DartsSupportApp: 手入力の練習管理 + ChatGPTクリップボード経由の
  自由記述フォーム評価。自動ゲーム進行・自動計測は明示的に「実装しない」
  と宣言されている初期版。

## 【ユーザー判断が必要（指示書§14停止条件に該当）】

この不一致は「DartsSupportAppの破壊的schema変更にユーザー判断が必要」
という停止条件そのものに該当するため、Claudeの判断だけでどちらかの
アプリを変更することはしていない（DartsSupportAppへの書き込み・pushは
一切行っていない）。以下のいずれかの方針をユーザーに選んでいただきたい：

1. **DartsSupportApp側にDartsAnalyticsApp向けのimport経路を新設する**
   （例：`ai_form_assessments`と同様に、DartsAnalyticsAppが生成した
   構造化JSONを取り込む新テーブル/新機能を追加）。DartsSupportApp側の
   スキーマ変更が必要（追加のみで既存テーブルは壊さない設計にできる）。
2. **DartsAnalyticsApp側のcontractをDartsSupportAppの実際のスキーマに
   合わせて作り直す**（`practice_sessions`/`practice_results`相当の
   手入力ライクな要約データとしてexportする、座標データは含めない等）。
   ただし、DartsAnalyticsAppの強みである構造化座標・confidenceデータの
   大半を失うことになる。
3. **両アプリを当面完全に独立させ、契約統合は行わない**（DartsAnalyticsApp
   はポートフォリオ用の独立分析ツールとして完結させる）。この場合、
   Phase 10の`SupportAppThrowRecord`は「将来の連携仕様案」として位置づけ、
   実際のDartsSupportAppとの接続コードは書かない。
4. **DartsSupportApp側にOpenAI API連携が入る際の拡張ポイント
   （`docs/IMPLEMENTATION_NOTES.md`の「OpenAI API連携の拡張ポイント」）
   を使い、DartsAnalyticsAppの解析結果を`ai_form_assessments`の
   `source_type='darts_analytics_app'`のような形で流し込む**：
   DartsSupportApp設計者（＝ユーザー自身）の想定した拡張パターンに
   最も近い可能性がある。

このセッションはこの4択について推測で実装を進めず、報告のみとする。
