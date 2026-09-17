# グルーピング解析検証報告（§5）

最終更新: 2026-09-17

## 要求事項（指示書§5、原文要約）

BULL率とグルーピング品質を分離する。候補指標: centroid / mean center
distance / X・Y standard deviation / radial RMS / CEP / 95% radius /
BULL中心からの平均距離 / 投間の分散。単に「ブル率が高い＝まとまっている」
と判定しない。

## 現状の実装（`src/dartsanalytics/board/grouping.py`, Phase 3実装済み）

`GroupingStats`（`compute_grouping_stats`の戻り値）は、指示書が挙げる
候補指標をほぼ全て実装済みだった：

| 候補指標 | 対応フィールド | 備考 |
|---|---|---|
| centroid | `group_center_x` / `group_center_y` | |
| mean center distance | `mean_center_distance` | グループ自身の重心からの平均距離 |
| X/Y standard deviation | `std_x` / `std_y` | |
| radial RMS | `rms_distance` | |
| CEP | `percentile_radii["p50"]` | 今回`cep_radius`として明示フィールド化（後述） |
| 95% radius | `percentile_radii["p95"]` | |
| BULL中心からの平均距離 | `bull_rate` / `bull_vicinity_rate` / `vertical_bias` / `horizontal_bias` | BULL(0,0)基準 |
| 投間の分散 | `covariance_xy` | |

## 今回の変更点

1. **`cep_radius`フィールドを明示的に追加**：これまで`percentile_radii["p50"]`
   という辞書キー経由でしかアクセスできなかった値を、指示書が名指しする
   「CEP」という名前のフィールドとして公開した（値自体は変更なし、
   `percentile_radii["p50"]`と等価であることをテストで保証）。

2. **「精度(accuracy)」と「まとまり(precision)」の分離を、コード上のコメント
   だけでなくテストで保証**：`GroupingStats`のdocstringに、指標を
   「精度系（BULLという真の狙い所からの近さ: bull_rate /
   bull_vicinity_rate / vertical_bias / horizontal_bias）」と
   「まとまり系（このグループ自身の重心からの散らばり: std_x/std_y/
   covariance_xy/mean_center_distance/rms_distance/max_distance/
   percentile_radii/cep_radius）」の2系統に明確に区別する説明を追加した。

3. **「BULL率が高い＝まとまっている」という誤判定を防ぐための新規テスト
   2件**（`tests/test_grouping.py`）：
   - `test_high_bull_rate_does_not_imply_tight_grouping_metrics`：
     24投中20投がBULL、4投が大きく外れた散らばりを持つ場合
     （`bull_heavy_with_outliers`フィクスチャ）、bull_rate≈0.83（高い）
     でありながら、max_distance/rms_distance/percentile_radii["p95"]は
     いずれも大きい値になることを確認。「BULL率が高いから安定している」
     という誤読を防ぐ。
   - `test_tight_grouping_does_not_imply_high_bull_rate`：24投全てが
     BULLから離れた1点付近にタイトに集まっている場合
     （`tight_but_off_target`フィクスチャ）、std_x/std_y/max_distance/
     cep_radiusは全て非常に小さい（＝グルーピング品質は高い）にも
     関わらず、bull_rate/bull_vicinity_rateは0であることを確認。
     「まとまっているから当たっている」という逆方向の誤読も防ぐ。

いずれもテストは合格（既存11件＋新規3件＝14件、`tests/test_grouping.py`）。

## 既存の未対応・注意点（Phase 3から変更なし）

- **CEPの一般的定義との違い**：標準的な「CEP」は真の狙い所（BULL）からの
  誤差半径を指すことが多いが、本実装の`cep_radius`はこのグループ自身の
  重心からの誤差半径（precision-CEP、まとまり指標）である。これは意図的
  （accuracy指標とprecision指標を混同しないため）だが、用語が業界標準と
  完全一致しないことをdocstringと本報告書に明記した。
- **「BULL周辺」半径は非公式の慣習値**（`DEFAULT_BULL_VICINITY_RADIUS =
  0.15`、正規化board半径に対する比率）。公式リングの定義ではないため、
  上書き可能なパラメータとして実装されている（Phase 3から変更なし）。
- **実データでの検証は未実施**：本報告は固定フィクスチャ（合成座標）に
  よるロジック検証であり、§4（実COUNT-UPデータ精度検証）が未実施
  （ユーザー提供の実データ待ち）のため、実際のDARTSLIVE HOMEデータに
  対するグルーピング指標の妥当性はまだ確認できていない。

## 結論

指示書§5が要求する「BULL率とグルーピング品質の分離」は、Phase 3時点で
概ね実装済みだったことを確認した。今回の作業は（a）CEPを名前付き
フィールドとして明示化、（b）分離が実際に機能していることを示す
テストを新規追加、の2点。新規コードのロジック変更は最小限（既存の
`percentile_radii["p50"]`を再利用しているのみ）で、既存テストへの
影響はない。
