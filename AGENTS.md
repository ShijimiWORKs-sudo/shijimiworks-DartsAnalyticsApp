# AGENTS.md — DartsAnalyticsApp 開発ルール

このリポジトリで作業するすべてのAIエージェント（Claude / Codex 等）は、このファイルの
ルールに従うこと。詳細仕様は `docs/specs/` および `docs/codex/` を参照。

## 1. 開発フローの原則

Phaseは開発管理上の区切りであり、**各Phase終了時に自動停止してはならない**。

```
Phase完了 → テスト → 問題確認 → 次Phaseの実装 → テスト → 問題確認 → 次Phase……
```

を継続する。

### 停止して状況を報告すべき場合（これ以外では途中停止しない）

- 重大な設計矛盾
- データ破壊につながる問題
- 既存機能を大きく壊す問題
- DARTSLIVE HOMEとの通信仕様など、外部仕様が不明で推測実装が危険な場合
- 技術的に実現不能と判断される問題
- ユーザーによる判断が必要な仕様分岐
- 環境制限、権限、API制限、料金制限等によって継続できない場合
  （例：このセッションではGitHubへのpush権限が未認可で `access denied by the
  git proxy` になった — ユーザー側でリポジトリをセッションのsourcesに追加
  する必要がある。ローカルgit履歴・ワーキングツリーの作成は継続してよい。）
- 同じ問題を修正しても解決できず、これ以上進めると品質低下が予想される場合

## 2. 最重要ルール

- 最小変更。無関係なリファクタリング禁止。
- 新規依存関係は必要性を確認してから追加する（デフォルトはゼロ依存）。
- 既存テストを壊さない。
- 解析不能なものを無理に判定しない（`confidence` を下げる/保留にする）。
- AIに原因を断定させない。「絶対にこれが原因」という表現は禁止。
- すべての推定値（`DataKind.ESTIMATED` / `DataKind.ADVICE`）に confidence を持たせる。
  `dartsanalytics.common.confidence` の `require_confidence_for_estimate()` を通す。
- 動画原本を上書きしない。派生ファイルは別名で保存する。
- 解析アルゴリズムにはバージョン文字列を付ける（例: `pose_v1`, `board_calib_v1`）。
- SQLite中心のローカルファースト。外部API従量課金を必須にしない。

## 3. データの区分（測定・計算・推定・助言）

`dartsanalytics.common.enums.DataKind` で明示的に区分する。

| 区分 | 意味 | confidence必須 |
|---|---|---|
| `MEASURED` | センサー/DARTSLIVE HOME等からの直接測定値 | 任意（検出成功率があれば付与） |
| `CALCULATED` | 測定値から決定的に計算した値（統計量等） | 任意 |
| `ESTIMATED` | 画像/動画解析・姿勢推定等からの推定値 | **必須** |
| `ADVICE` | AIアドバイザーの解釈・提案 | **必須** |

confidenceのバケット分け（`docs/specs/DartsAnalyticsApp_詳細設計書_v1.0.md` §23）:

- 0.90–1.00: 高信頼
- 0.75–0.89: 十分
- 0.50–0.74: 参考
- 0.00–0.49: 判定保留

## 4. テスト要求

各Phaseで最低限：

- unit test
- integration test
- migration test
- malformed input test
- video quality negative test（動画を扱うPhaseから）
- reproducibility test（同一入力→同一出力）

分析値については固定fixtureを用意する（`tests/fixtures/`）。例：

- 全投が中心
- 全投が上側
- 全投が下側
- 左右に均等分布
- 1本だけ外れ値
- 24投中数投欠損

「動作した」だけでは完成とみなさない。着弾座標・グルーピング・動画解析・姿勢推定・
リリース解析・立ち位置解析・原因推定・改善提案については、測定値と推定値を区別して
記録・テストする。

## 5. Git運用

各Phaseごとに専用branchを作る。

```
codex/phase-0-foundation
codex/phase-1-count-up-data
codex/phase-2-dartslive-adapter
codex/phase-3-board-analysis
codex/phase-4-video-intake
codex/phase-5-pose-analysis
codex/phase-6-grip-analysis
codex/phase-7-integrated-analysis
codex/phase-8-experiments
codex/phase-9-local-ai
codex/phase-10-support-contract
```

完了後 `main` へ直接mergeしない。Draft PRを作り、以下を報告する。

- 変更内容
- テスト結果
- 未解決事項
- 実機確認が必要な事項

## 6. Phase一覧と完了条件（要約）

| Phase | 内容 | 完了条件 |
|---|---|---|
| 0 | Repository Foundation | 起動・テスト・DB migration成功 |
| 1 | COUNT-UP Data Core（モック） | 24投分のセッションがモックデータのみで再現可能、JSON export |
| 2 | DARTSLIVE HOME Adapter調査 | 実機検証できた範囲のみ採用。公開APIなしなら抽象化のみ実装し停止・報告 |
| 3 | Board Coordinate Analysis | 静止画像でキャリブレーション・グルーピング統計が再計算可能 |
| 4 | Video Intake & Shooting Guide | 4方向撮影ガイド、品質判定、NG理由表示、再撮影要求 |
| 5 | Pose Analysis | head/shoulder/elbow/wrist/hip/knee/ankle等の特徴量抽出（推定値） |
| 6 | Grip Analysis | 指位置・角度・バレル軸の推定（2Dからの断定禁止） |
| 7 | Integrated Analysis | dispersion/bias/frequent segments/candidate causes統合 |
| 8 | Experiment System | Baseline→Intervention→Test→Comparison→Decision |
| 9 | Local AI Advisor | 観測/仮説/推奨テスト/注意事項/confidenceを分離出力。断定禁止 |
| 10 | DartsSupportApp Contract | 既存契約フィールドに準拠したJSON連携 |

詳細は `docs/codex/CODEX_DARTS_ANALYTICS_IMPLEMENTATION_v1.0.md` を参照。

## 7. 動作確認コマンド

```bash
pip install -e ".[dev]"
python scripts/bootstrap_check.py   # DB migration + 起動確認
pytest                               # テスト一式
```
