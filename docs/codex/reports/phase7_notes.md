# Phase 7: Integrated Analysis — Implementation Notes

## 実装した範囲

`dartsanalytics.integrated` パッケージ。docs §Phase7の出力6項目に対応：

- **dispersion / directional bias**：新規実装せず、Phase 3の
  `dartsanalytics.board.grouping.GroupingStats`をそのまま再利用（すでに
  `vertical_bias`/`horizontal_bias`を含む）。重複実装を避けるための意図的
  な設計判断（`integrated/frequent_segments.py`のdocstringに明記）。
- **frequent segments**（docs §12の7項目のうち1・2・6を新規実装、3・4・5は
  GroupingStats再利用、7はlate_roundへ分離）：
  `dartsanalytics.integrated.frequent_segments`。
  - `segment_counts` / `ring_counts`：実着弾セグメント・リング種別の頻度。
  - `find_direction_streaks`：左右/上下について「連続して同方向へ外れる」
    連続回数を計算。中心(0.0)はどちらの方向にも属さずストリークを切る。
  - 隣接セグメントを含めた**可視化**（docs §12）はUI層の責務であり、この
    リポジトリにはまだUIが一切ない（AGENTS.mdのPhase一覧参照）ため、
    可視化そのものは実装していない。元データ（頻度）のみ提供。
- **late-round degradation**：`dartsanalytics.integrated.late_round`。
  セッションのラウンドを前半/後半に分割し、平均得点とGroupingStatsを比較
  する`CALCULATED`な比較。ラウンド数<2または座標データ皆無の場合は
  `insufficient_data=True`を返し、無理に比較値を作らない。
- **form correlations**：`dartsanalytics.integrated.correlation`。
  1投単位でのフォーム特徴量↔着弾のペアリングは、docs §14「4動画の統合
  方法」により厳密な同時刻同期を前提にできない（`throw_group_id`が付与
  できた場合のみ本当の1投単位リンクが可能）。そのため、本モジュールは
  **セッション単位の集計値同士**（例：あるセッションの平均body_tiltと
  そのセッションのvertical_bias）をペアとして受け取り、Pearson相関係数を
  計算する設計にした。ペア数が`MIN_SAMPLES_FOR_CORRELATION=5`未満、また
  はどちらかの軸に分散が無い場合は`None`を返す（相関「0」を捏造しない）。
  confidenceはサンプル数に応じて上昇するが`MAX_CORRELATION_CONFIDENCE=0.7`
  でハードキャップ。
- **candidate causes**（docs §16 原因推定のルール）：
  `dartsanalytics.integrated.causes`。`FormCorrelation`のうち
  `|pearson_r| >= CORRELATION_THRESHOLD_FOR_CANDIDATE(0.5)`のものだけを
  候補原因に変換する。カテゴリはdocs §16の9分類のうち、Phase 5/6で既に
  特徴量が存在するものだけを`FEATURE_CATEGORY_MAP`で対応付け。すべて
  `DataKind.ADVICE`、confidenceは`MAX_CAUSE_CONFIDENCE=0.6`でハードキャップ。
  説明文に必ず「原因と断定するものではない」旨を含める（AGENTS.md §2:
  「AIに原因を断定させない」の強制）。
- **統合レポート**：`dartsanalytics.integrated.report.build_integrated_report`
  が上記すべてを1セッション分にまとめる。`form_correlations`は呼び出し側
  （複数セッション履歴を持つ将来のオーケストレーション層、あるいはPhase 9
  のAIアドバイザー）が計算して渡す設計（1セッションだけでは相関計算不可能
  なため）。

## 実装しなかった範囲（docs §16の9分類のうち未対応、理由付き）

`dartsanalytics.integrated.causes`のdocstringに明記：

- **リリース位置**：較正済みの「リリース位置→着弾位置」マッピングが必要
  だが、どのPhaseでも未実装（Phase 5の`pose.release`はリリース候補の
  **タイムスタンプ**のみで、空間的な位置の較正はしていない）。
- **足位置**：遠景動画（撮影D）からの立ち位置追跡は未実装（Phase 4は
  取り込み・品質判定のみで特徴量抽出はしていない）。
- **狙い線**：`declared_target`と`actual_target`のズレ分析は、意味のある
  結果を得るのに十分なセッション数が必要で、今回は未実装。
- **用具**：用具変更前後の比較はPhase 8（Baseline→Intervention→Test→
  Comparison→Decision）の役割そのものであり、ここで単発の疑似判定をする
  とPhase 8と重複・矛盾するため意図的に未実装。
- **手首の動き**（Phase 5由来）：`pose.release`は手首の**速度**のみを
  追跡しており、方向性の偏りと対応付けられる特徴量がまだ存在しないため
  未対応。

## 技術的な制約・フラグ

1. **`form_correlations`は実データでの検証が一切できていない**：現時点
   ではPhase 5/6のフォーム特徴量とPhase 3の着弾統計を実際に複数セッション
   分ペアリングしたデータが存在しない（実映像・実グリップ写真が無いのと
   同じ理由）。相関計算のロジック自体は合成データでテスト済みだが、実際に
   意味のある相関が出るかどうかは未検証。
2. **DBスキーマ変更なし**：docs §21の`analysis_reports`テーブル
   （`report_json`カラム）はPhase 0で既に作成済みのため、Phase 7では
   マイグレーション追加不要（Phase 6のgrip_analysis_runs再利用と同じ
   パターン）。

## 手動end-to-end検証（合成データ）

前半4ラウンドをブル中心・高得点、後半4ラウンドを下側偏り・低得点とした
合成24投セッション＋合成フォーム相関（r=0.82, n=8）で
`build_integrated_report`を実行し、出力を目視確認：

- `dispersion.vertical_bias = -0.145`（全体では下寄り）。
- `late_round.early_score_average=25.0` → `late_score_average=8.0`
  （score_delta=-17.0）、`early_dispersion.bull_rate=1.0` →
  `late_dispersion.bull_rate=0.0`：後半崩れのパターンを正しく検出。
- `candidate_causes[0].confidence = 0.492`（`MAX_CAUSE_CONFIDENCE=0.6`
  以下、confidenceバケットでは「判定保留」寄りで、断定的な表現なし）。

期待通りの挙動を確認（詳細ログはこのレポートに転記済み、DBへの永続保存は
まだ行っていない — Phase 7はレポート生成ロジックのみ、保存呼び出し側は
未実装）。

## テスト

`tests/test_frequent_segments.py`, `test_late_round.py`,
`test_correlation.py`, `test_causes.py`, `test_integrated_report.py`。
合計41件追加、全227件パス。`scripts/bootstrap_check.py`成功（スキーマ変更
なしのため`0001_initial`のみ）。

## 依存関係の追加

なし（numpyの`corrcoef`をPhase 3から再利用）。
