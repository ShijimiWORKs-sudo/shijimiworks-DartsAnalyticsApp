# Phase 8: Experiment System — Implementation Notes

## 実装した範囲

`dartsanalytics.experiments`パッケージ。docs §20の
`Baseline → Intervention(変更1項目) → Test → Comparison → Decision`に対応：

- **比較（Comparison）**：`dartsanalytics.experiments.comparison`。
  docs §20の8指標（BULL率・BULL周辺集中率・平均中心距離・X標準偏差・
  Y標準偏差・95%半径・COUNT-UP平均・ラウンド後半の崩れ）をbaseline群/
  test群（それぞれ1つ以上のセッションをプール、docs §20「Baseline
  30〜60投」に対応）で算出し、baseline値・test値・差分(delta)を返す。
  新規計算ロジックはほぼゼロ — Phase 3の`board.grouping`、Phase 1の
  `countup.session_result`、Phase 7の`integrated.late_round`をそのまま
  再利用（重複実装を避ける、AGENTS.md「最小変更」原則）。
- **判定（Decision）**：`dartsanalytics.experiments.decision`。
  docs §20「Decisionは「継続」「戻す」「再試験」などの事実ベースの結果に
  する」を、AIの主観を排した決定的ルールとして実装：
  1. baseline/testいずれかのスロー数が`MIN_THROWS_PER_GROUP=30`未満なら
     即`retest`（データ不足、docs §20「Baseline 30〜60投」を満たさない）。
  2. 各指標のdeltaを指標ごとに定義済みのマージン（`METRIC_MARGINS`、
     ノイズとみなす閾値、仕様に数値指定は無いため文書化された規約値）
     と比較し、improved/worsened/変化なしに分類。
  3. improved過半数（評価対象の半分以上）かつworsened以下 → `continue`。
     worsened > improved → `revert`。それ以外（拮抗・過半数未達） →
     `retest`。
  4. `reasoning`に各指標の判定根拠を文字列で残す（ブラックボックス判定
     にしない）。
- **Experimentモデル**：`dartsanalytics.experiments.models.Experiment`。
  DB `experiments`テーブル（Phase 0スキーマ既存）に対応する軽量
  dataclass（to_dict/from_dict）。DB読み書きコードは追加していない
  （board/pose/grip/integrated同様、リポジトリ/DAO層はどのPhaseにも
  まだ存在しないため、Phase 8だけ追加するのはスコープ外と判断）。

## 実装しなかった範囲

- **DB永続化（リポジトリ層）**：前述の通り、既存パターンに合わせて未実装。
- **`InterventionType`ごとの提案文生成**（docs §17の改善提案フォーマット
  「観測事実→関連するフォーム特徴→原因候補→今回試す変更→測定方法→
  変更後の判定基準」）：Phase 7の`candidate_causes`が「関連するフォーム
  特徴→原因候補」までを担い、Phase 8は「変更後の判定基準」以降
  （比較・判定）を担う設計だが、「今回試す変更」の自動提案文生成は
  Phase 9（ローカルAIアドバイザー）の役割として残す。

## 技術的な制約・フラグ

1. **マージン値は文書化された規約であり、測定に基づく閾値ではない**
   （`decision.py`の`METRIC_MARGINS`コメント参照）。実データでの
   キャリブレーションが今後必要。
2. **実データでの検証未実施**：Phase 5/6/7と同様、実際のBaseline/Test
   データが存在しないため、合成データでのロジック検証のみ。

## 手動end-to-end検証（合成データ）

Baseline（30投、平均分散した低スコア12点/投、着弾偏り大）→ Test（30投、
中心付近・高スコア22点/投）という「明確に改善した」想定シナリオで
`compare_baseline_vs_test` → `decide`を実行：

- `bull_rate`: 0.0 → 1.0（改善）、`countup_average`: 12.0 → 22.0（改善）、
  他5指標はbaseline/testとも分散ほぼゼロの合成データだったため
  「ノイズ範囲内」判定。
- 結果：`improved_count=3`, `worsened_count=0`, `evaluated_count=8` にも
  関わらず、**過半数（4/8）に届かないため`decision=retest`**（`continue`
  ではない）。

これは意図した挙動：「悪化が無い」だけでは`continue`と判定しない、という
保守的なルールが実際に機能していることを確認した（AGENTS.md「AIに原因を
断定させない」と同じ慎重さを、Decision自体にも適用する設計が効いている
実例）。ログはこのレポートに転記済み。

## テスト

`tests/test_experiment_comparison.py`, `test_experiment_decision.py`,
`test_experiment_models.py`。合計21件追加、全248件パス。
`scripts/bootstrap_check.py`成功（スキーマ変更なし、`experiments`/
`experiment_results`テーブルはPhase 0で作成済み）。

## 依存関係の追加

なし。
