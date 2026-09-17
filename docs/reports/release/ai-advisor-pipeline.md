# AI助言パイプライン報告（§8）

最終更新: 2026-09-17

指示書§8には成果物パスの指定が無いため、他の§項目と同じパターン
（監査＋ギャップ修正＋報告書）に合わせて`docs/reports/release/
ai-advisor-pipeline.md`として作成した。

## 要求されるパイプライン（指示書§8、原文）

```
measurement → features → statistics/rules → candidate cause →
confidence → AI explanation → controlled experiment → remeasurement
```

各助言には可能な範囲で: evidence / confidence / inference flag /
expected effect / recommended change / test protocol / before/after
を持たせる。単一原因を断定しない。複数仮説を候補として扱い、変更は
一度に大きくしすぎず、再計測で検証する。

## パイプライン各段階の実装対応

| 段階 | 実装モジュール | 状態 |
|---|---|---|
| measurement | Phase 1/2（COUNT-UPデータ、DARTSLIVE HOMEアダプタ） | 実装済み（BLE実機検証は§3、ユーザー操作待ち） |
| features | Phase 3(board)/5(pose)/6(grip) | 実装済み（実データ未検証、§4/§6/§7参照） |
| statistics/rules | `board.grouping`, `integrated.frequent_segments`, `integrated.late_round` | 実装済み |
| candidate cause | `integrated.correlation` (FormCorrelation) → `integrated.causes` (CandidateCause) | 実装済み（9カテゴリ中5カテゴリのみ、他は未実装として明記済み） |
| confidence | 各段階で`DataKind`+`confidence`を伝播、`MAX_CAUSE_CONFIDENCE=0.6`で上限キャップ | 実装済み |
| AI explanation | `advisor.generate.build_advisor_output` | 実装済み（外部LLM APIなし、決定論的テンプレート — §25「外部AI APIは必須にしない」の解釈、モジュールdocstring参照） |
| controlled experiment | `experiments.comparison`/`experiments.decision`（Phase 8） | 実装済み |
| remeasurement | `experiments.comparison.compare_baseline_vs_test`のTest側 + 今回実装した`learning_log`（§9） | 実装済み |

パイプライン全段階が実装済みであることを確認した。既存のPhase 3/5/6/7/8/9
がそれぞれ担当し、`advisor.generate`が各段階の出力を結合する構成に
なっている。

## 各助言が持つべき7項目への対応状況

指示書§8: 「evidence / confidence / inference flag / expected effect /
recommended change / test protocol / before/after」

監査の結果、`Hypothesis`/`RecommendedTest`（`advisor/models.py`）には
**confidence・inference flag（data_kind）・recommended change
（description）・test protocol（measurement_plan/decision_criteria）は
既に実装済み**だったが、**evidenceとexpected effectが欠落**していた
（`CandidateCause`自身は`supporting_evidence`を持っていたが、
`Hypothesis`/`RecommendedTest`へ変換する際に破棄されていた）。

### 今回の修正

1. **`CandidateCause`に`outcome_metric_name`フィールドを追加**
   （`integrated/causes.py`）：どの測定指標との相関から生成された候補
   かを構造化データとして保持（従来は`description`文字列内にのみ
   埋め込まれていた）。
2. **`Hypothesis`に`evidence: list[str]`フィールドを追加**
   （`advisor/models.py`）：`CandidateCause.supporting_evidence`
   （例：`pearson_r=0.62`, `n=40`）をそのまま引き継ぐ。
3. **`RecommendedTest`に`evidence`と`expected_effect`フィールドを追加**：
   `expected_effect`は「〇〇を変更した場合、△△（outcome_metric_name）に
   改善方向の変化が見られるかを確認する対象とする（改善を保証するもの
   ではない）」という**必ずヘッジされた文言**で生成する。「変更すれば
   改善する」という断定は一切行わない（`BANNED_ABSOLUTE_PHRASES`の
   回帰テストに`expected_effect`も含めるようスキャン範囲を拡張済み）。
4. **`before/after`は意図的にフィールド化しなかった**：提案の時点では
   まだ「前後」のデータが存在しない（実験実施後に初めて生まれる）ため、
   `RecommendedTest`にプレースホルダーを持たせるのではなく、Phase 8の
   `experiments.comparison.ExperimentComparison`（baseline_value/
   test_value/delta）と今回実装した§9の`learning_log`
   （before_summary/after_summary/result_summary）が、その役割を実際に
   担う設計とした。docstringにこの設計判断を明記。

### 単一原因の断定禁止・複数仮説の候補としての扱い

- `generate_candidate_causes`は複数の`CandidateCause`を独立に生成し、
  1つに絞り込む処理は行わない（`build_advisor_output`も全候補を
  そのまま`hypotheses`/`recommended_tests`に変換）。
- 全生成テキストに対する`BANNED_ABSOLUTE_PHRASES`
  （"絶対に"/"必ずこれが原因"/"間違いなく原因"/"確定的な原因"）の
  回帰スキャンにより、断定的表現が混入しないことをテストで保証
  （既存、今回`expected_effect`もスキャン対象に追加）。
- `STANDARD_CAVEATS`に「これらは推定・仮説であり、断定的な原因ではない」
  「変更は一度に1項目のみ試し、Baseline/Testで比較すること」が常に
  含まれる（既存、変更なし）。

## テスト

`tests/test_causes.py`に1件追加（`outcome_metric_name`の伝播確認）、
`tests/test_advisor.py`に1件追加（`evidence`/`expected_effect`が
`CandidateCause`から`Hypothesis`/`RecommendedTest`へ正しく伝播し、
`expected_effect`が必ずヘッジ文言を含むことを確認）。既存の
`test_never_generates_a_banned_absolute_phrase`のスキャン対象に
`expected_effect`を追加。合計312件のテストが全て合格。

## 既知の未対応・制約

- 9カテゴリ中4カテゴリ（リリース位置/足位置/狙い線/用具/手首の動き）は
  依然未実装（Phase 7時点からの既知の制約、理由は
  `integrated/causes.py`モジュールdocstringに明記済み — 必要な特徴量
  抽出ロジック自体がまだ存在しない）。
- AI explanation段階は外部LLM APIを一切使わない決定論的テンプレートで
  あり、「AI」という名称ではあるが自然言語生成モデルではない
  （既存の設計判断、今回変更なし）。
- `expected_effect`の文言は「改善方向の変化を確認する対象とする」という
  一般的な言い回しであり、具体的な改善幅・確率等の定量的な期待値は
  一切生成しない（過大な確信を主張しないため、意図的な設計）。
