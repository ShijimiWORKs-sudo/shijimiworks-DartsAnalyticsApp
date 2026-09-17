# Phase 9: Local AI Advisor — Implementation Notes

## 実装した範囲

`dartsanalytics.advisor`パッケージ。docs §19の入出力仕様に対応：

- **入力**：`IntegratedAnalysisReport`（Phase 7、統計値・ボード座標特徴量
  ・フォーム/グリップ特徴量由来のcandidate_causesを含む）＋
  `experiment_history: list[Experiment]`（Phase 8、過去の改善履歴）。
- **出力の4分離**（docs §19「観測/推定/提案/注意点を分離する」）：
  - `Observation`（観測）：`DataKind.CALCULATED`。GroupingStats/
    LateRoundComparison/FrequentSegmentStatsからの事実のみ。推論なし。
  - `Hypothesis`（推定）：`DataKind.ADVICE`。Phase 7の`CandidateCause`を
    そのままラップ（confidenceも変更しない）。
  - `RecommendedTest`（提案）：`DataKind.ADVICE`。docs §17の改善提案
    フォーマットのうち「今回試す変更／測定方法／変更後の判定基準」に対応。
    測定方法・判定基準は常にPhase 8の`experiments.compare_baseline_vs_test`
    / `experiments.decide`を指し示す（独自の検証ロジックを新設せず、
    Phase 8の仕組みに一本化）。
  - `Caveat`（注意点）：常に3つの標準注意文を含む（推定であり断定でない
    旨／実データ未検証の可能性／一度に1項目のみ変更する原則）。
    candidate_causesが空の場合は追加の注意文を出す。

## 実装しなかった範囲・設計判断

- **外部LLM/AI APIの呼び出しは一切行わない**：docs §25「外部AI APIは
  必須にしない」を、「外部AI APIは必須要件にしてはならない」と読み、
  このモジュール自体は決定的なテンプレートベースの実装とした（ネット
  ワーク依存ゼロ、完全ローカル動作）。将来、この構造化出力を自然な文章
  に変換する層としてLLMを追加することは可能だが、「観測/推定/提案/注意点
  の分離」と「断定しない」というルール自体はLLMの有無に関わらず本モジュ
  ールで機械的に強制する（`BANNED_ABSOLUTE_PHRASES`によるテストでの
  リグレッションガード付き）。
- **`RecommendedTest`の具体的な「今回試す変更」内容は生成しない**：
  カテゴリ名（例：「肘/前腕角度」）は示すが、「肘の角度を5度上げる」等の
  具体的な数値提案はしていない。ダーツ技術的な妥当性を判断する根拠が
  このリポジトリには無く、誤った具体的指示を機械的に生成するのは
  「解析不能なものを無理に判定しない」の精神に反するため、意図的な
  スコープ縮小。

## 技術的な制約・フラグ

1. **Hypothesis/RecommendedTestの信頼度はPhase 7のcandidate_causesを
   そのまま継承**：Phase 7自体が実データ未検証（`phase7_notes.md`参照）
   であるため、Phase 9の推定・提案も同じ制約を引き継ぐ。
2. **`BANNED_ABSOLUTE_PHRASES`はリグレッションガードであり、意味理解に
   基づく断定検出ではない**：文字列一致のみ。将来テンプレート文言を追加
   する際は、この禁止語リストとの整合を手動で確認する必要がある。

## 手動end-to-end検証（合成データ）

Phase 7で使用した「前半ブル中心・高得点、後半下側偏り・低得点」の合成
24投セッション＋合成フォーム相関（r=0.82）＋過去の改善実験履歴2件
（continue 1件, retest 1件）で`build_advisor_output`を実行し、出力を
目視確認：

- 観測4件（着弾統計、前半/後半比較、連続偏りストリーク、過去実験の内訳）
  すべて事実のみで構成され、推論を含まない。
- 仮説1件（肘/前腕角度、confidence=0.492）、提案1件（同カテゴリ、
  Phase 8の比較・判定関数を明示的に指し示す）。
- 全出力テキストに`BANNED_ABSOLUTE_PHRASES`が含まれないことを確認
  （テストとしても`test_never_generates_a_banned_absolute_phrase`で
  固定化済み）。

期待通りの挙動を確認。詳細ログはこのレポートに転記済み。

## テスト

`tests/test_advisor.py`（11件）。全259件パス。
`scripts/bootstrap_check.py`成功（スキーマ変更なし、`hypotheses`/
`interventions`テーブルへの永続化コードは未実装 — Phase 7/8同様、
リポジトリ/DAO層はどのPhaseにもまだ無い）。

## 依存関係の追加

なし。
