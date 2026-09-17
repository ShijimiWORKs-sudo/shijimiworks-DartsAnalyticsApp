# COUNT-UP実データ精度検証報告（§4）

最終更新: 2026-09-17

## 状態：ツール実装済み、実データでの検証は未実施（ユーザー操作待ち）

指示書§4は「実データは10ゲーム以上、可能なら30ゲームを使用する」ことを
前提とするが、本セッションには実際のDARTSLIVE HOMEプレイデータが一切無い。
指示書§14/§15（「それ以外は、可能な範囲で継続して実装・テスト・証拠化
する」）に従い、**実データが届いた時点ですぐ実行できる比較ツールを先行
実装**した。ツール自体の正しさは合成データで検証済みだが、**実データに
対する精度の数値はまだ一切存在しない**。「未検証」を「検証済み」と
書き換えないという指示書§13のルールをここでも厳守する。

## 実装：`src/dartsanalytics/validation/accuracy.py`

`compare_sessions(reference, candidate)`が、同一の実際のゲームを2つの
情報源（典型的には reference=DARTSLIVE HOME BLE計測、candidate=本アプリの
board-cameraによる検出）で記録した`PracticeSession`を突き合わせ、
`throw_number_in_session`をキーに1投ずつ比較する。

重要な設計判断：**DARTSLIVE HOME側も「完全なground truth」とは呼ばない**。
指示書§4自身の注記（「DARTSLIVE HOME側のグラフ等から得られる値は完全な
ground truthと断定せず」）に従い、関数の引数名は`ground_truth`ではなく
`reference`とした。DARTSLIVE HOME自体の値にも誤差がありうるという前提を
コード上の命名レベルで維持している。

### 指示書§4が要求する評価指標との対応

| 要求指標 | 実装 | 備考 |
|---|---|---|
| exact match | `AccuracyReport.exact_match_rate` | スコア完全一致率 |
| score error | `mean_score_error`（符号付き平均） / `mean_abs_score_error`（絶対値平均） | candidate - reference |
| coordinate error | `mean_coordinate_error` | 正規化座標でのユークリッド距離平均（両側に座標がある投のみ） |
| false positive / false negative | `false_positive_count` / `false_negative_count` | candidate側にのみ存在する投＝FP、reference側にのみ存在＝FN |
| number confusion | `number_confusion_rate` | セグメント番号（1〜20）の食い違い率。BULL/DBULL/MISSは番号を持たないため対象外 |
| BULL近傍誤差 | `bull_vicinity_agreement_rate` | 両側の「BULL周辺（`DEFAULT_BULL_VICINITY_RADIUS`）内か否か」の一致率 |
| round error | `round_score_errors`（ラウンド番号→誤差の辞書） | ラウンドスコアの差 |

### 比較対象一覧（指示書§4）との対応

| 比較対象 | 対応 |
|---|---|
| 総合スコア | `total_score_reference`/`total_score_candidate`/`total_score_error` |
| ラウンドスコア | `round_score_errors` |
| 1投平均 | `total_score_error / n_both_present`から算出可能（専用フィールドは無いが計算は容易） |
| BULL/DOUBLE/TRIPLE | `ring_confusion_rate`（リング種別の食い違い率） |
| MISS | 同上（MISSもring種別の1つとして扱われる） |
| ナンバー出現頻度 | 未実装（個別のヒストグラム集計は今回のスコープ外、`throw_comparisons`の生データから後付けで集計可能） |
| 座標 | `mean_coordinate_error` |
| グルーピング中心・X/Y偏り・BULL周辺集中度 | 既存の`board.grouping.compute_grouping_stats`をreference/candidate双方に個別適用することで比較可能（本モジュールでは直接ラップしていないが、既存モジュールとの組み合わせで実現できる設計） |

「ナンバー出現頻度」の専用集計と、grouping統計の2セッション比較用ラッパー
関数は、実データが届いてから実際に必要な形が分かってから追加する方が
適切と判断し、今回は見送った（要求されている生データ
（`throw_comparisons`、各投のreference/candidateセグメント）は既に
`AccuracyReport`から取得可能なため、追加の実装コストは小さい）。

## テスト（`tests/test_accuracy_validation.py`, 10件）

合成データによる**ツール自体の正しさ**の検証：
- 完全一致セッション同士でexact_match_rate=1.0、score_error=0
- スコア食い違い時の符号付きscore_error
- リング一致・番号不一致（number_confusion）の検出
- リング不一致（ring_confusion）の検出
- false negative（reference側のみに存在する投）
- false positive（candidate側のみに存在する投）
- 座標誤差（3-4-5直角三角形で0.05になることを明示的に確認）
- BULL周辺一致率
- ラウンドスコア誤差
- 総合スコア誤差

いずれも合成データでの検証であり、実データでの精度を示すものではない
（モジュールdocstring・本報告書双方に明記）。

## 2026-09-17追記：ユーザーからDARTSLIVE HOME実データ（要約統計のみ）を受領

ユーザーから、DARTSLIVE HOME本体のマイページ（Webダッシュボード）を
スクリーンショットしたもの8枚を受領した（対象プレイヤー：「ヨースケ」、
ユーザー本人のアカウント）。内容は以下の通り：

- COUNT-UPスコア推移グラフ（直近30ゲーム分、および日別）
- 各ゲームモード（01 GAMES/CRICKET/COUNT-UP/CRICKET COUNT-UP/
  EAGLE'S EYE/SHOOT OUT/HALF-IT）のBEST/AVERAGE一覧表
- AWARD集計（TON80/HIGH TON/HAT TRICKなど、およびS-BULL/D-BULL等の
  累積回数）
- PLAYER LIST画面（RATING等のサマリ）

**これは指示書§4が要求する「1投ごとの構造化データ」ではない**。DARTSLIVE
HOMEのWebダッシュボードは、ゲーム単位・日単位の集計値（合計スコア・
平均・ベスト）とグラフ表示のみを提供しており、投ごとのセグメント
（リング・番号）や座標に相当する情報は含まれていない。したがって、
`compare_sessions()`が要求する`throw_number_in_session`単位の突き合わせ
（exact match/coordinate error/number confusion等）は、**このデータからは
実行できない**。折れ線グラフ上の各点の正確な値も、軸目盛からの目視推定に
なってしまうため、推測による数値の捏造を避ける本プロジェクトの方針
（AGENTS.md §2「AIに原因を断定させない」/「解析不能なものを無理に判定
しない」）に従い、ここでは読み取っていない。

一方、SCORE集計表に明記されていた正確な数値（COUNT-UP: BEST 666 /
AVERAGE 427.36、過去30ゲーム分）は、テキストとして確実に読み取れる実測値
である。これを`MockCountUpGenerator`が生成する合成セッションのセッション
合計スコア分布と比較した（seed 1〜30の30セッション、それぞれ24投完了）：

| 指標 | 実データ（ヨースケ、直近30ゲーム） | モック生成（30セッション） |
|---|---|---|
| 平均（AVERAGE） | 427.36 | 408.17 |
| 最高（BEST） | 666 | 575 |

平均は比較的近い（差5%弱）が、モック生成の30セッションでは実データの
ベストスコア666に達するセッションが1件も無かった（モック側の分布は
268〜575、標準偏差約76）。これは**「モックのスコア分布は妥当な範囲だが、
実プレイヤーが記録するような高得点セッション（好調な回・連続ハイスコア）
をモックの単純な確率モデルは再現しにくい可能性がある」という観察**で
あり、断定はできない（n=30はサンプル数として小さく、プレイヤー個人の
技量・調子のばらつきも未知数のため）。この観察はモック生成ロジックの
改善検討材料として記録するに留め、精度検証済みとはしない。

**結論：今回受領したデータは「セッション合計スコアの参考値」としては
有用だが、指示書§4が求める1投単位の精度検証（exact match rate等）を
実施するには不十分**。実施には以下のいずれかが必要：
1. DARTSLIVE HOME側の1投ごとの生データ（§3のBLE実機検証で取得を試みて
   いるnotifyデータがこれに該当する可能性が高い）
2. または、もしDARTSLIVE HOMEのマイページに個々のゲーム記録を投ごとに
   表示する画面（存在すれば）があれば、そのスクリーンショット

## 次のステップ（ユーザー操作待ち）

1. 上記の通り、セッション合計スコアの参考値は受領済み。1投単位の
   精度検証には、DARTSLIVE HOME側のBLE実機検証（§3）で1投ごとの
   notifyデータを取得するか、投ごとの記録画面があればそのスクリーン
   ショットの提供を受ける必要がある。
2. `compare_sessions()`を実データのセッションペアに対して実行し、
   実際の`exact_match_rate`等を計測する。
3. 計測結果を本報告書に追記し、「検証済み」の状態にする（それまでは
   「ツール実装済み・未検証」のまま）。

## 結論

指示書§4が要求する比較ツール（exact match/score error/coordinate
error/false positive-negative/number confusion/BULL近傍誤差/round
error）は実装・テスト済み。実データでの検証はDARTSLIVE HOME実データの
提供（および§3のBLE実機検証）を待って初めて実施可能であり、現時点では
「未検証」のまま報告する。322件のテストが全て合格（新規10件を含む）。
