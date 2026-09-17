# Phase 5: Pose Analysis — Implementation Notes

## 実装した範囲

- MediaPipe `PoseLandmarker`（Tasks API）のラッパー
  （`dartsanalytics.pose.landmarker`）。
- 特徴量計算（`dartsanalytics.pose.features`）：body_tilt（体幹傾き）、
  shoulder_tilt / hip_tilt（肩・腰の水平からの傾き）、
  left/right elbow_angle（肘角度）。各値は`DataKind.ESTIMATED`で、
  confidenceは寄与するランドマークの信頼度の最小値（保守的な合成則、
  統計的に厳密ではないことを明記）。
- リリース/フォロースルー**候補**検出（`dartsanalytics.pose.release`）：
  手首の速度ピークをヒューリスティックで検出。confidenceは0.1〜0.7に
  意図的にキャップ（未検証のヒューリスティックが「測定値」のように
  扱われないようにするため）。
- 動画1本を通しての一括処理（`dartsanalytics.pose.analysis.analyze_video_pose`）：
  Phase 4のフレームサンプリング + Pose検出 + 特徴量計算 + リリース候補検出。

## 実装しなかった範囲（意図的なスコープ縮小）

- 手首の回転角度・指の検出（別のhand landmarkモデルが必要、今回未導入）。
- 膝・足首の角度（ランドマーク自体は取得しているが、角度計算は未実装。
  肩・肘・体幹傾きのみを先に実装し、テストを厚くすることを優先した）。
- ダーツ自体の認識（設計書で明示的に別モジュール）。

## 技術的な制約・フラグ

1. **実人物映像での検証未実施**：このセッションには実際にダーツを投げる
   人物の映像・写真が一切ない。ノイズ画像・単色画像に対して「人物を検出
   しない」ことは確認済み（誤検出なし）だが、実際の投球動作に対する
   検出精度・ランドマーク位置の妥当性・confidenceの較正は**未検証**。
   実際の動画でのテストが必須（リリース前に必ず実施すること）。
2. **mediapipeモデルファイルの外部依存**：インストールされている
   mediapipe（0.10.32）は新しいTasks APIのみを公開しており、
   モデル同梱の旧`mediapipe.solutions`は利用不可。`.task`モデルファイルを
   別途ダウンロードする必要がある（`models/README.md`参照、一度だけ、
   以降はローカルで完結）。ユーザーのWindows PCでも同じ手順が必要。
3. **リリース候補は検証済みの生体力学モデルではない**：「手首速度が
   ピークになるタイミング」という単純な仮定に基づく。実際のダーツの
   離脱タイミングとズレる可能性があり、confidenceは低め（最大0.7）に
   抑えている。

## 依存関係の追加

`mediapipe>=0.10.30`（pyproject.toml）。理由：姿勢推定を自前実装するのは
現実的でなく、CPU動作可能な軽量な標準的選択肢のため。
