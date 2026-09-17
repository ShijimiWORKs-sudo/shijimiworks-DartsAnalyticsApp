# Phase 6: Grip Analysis — Implementation Notes

## 実装した範囲

- MediaPipe `HandLandmarker`（Tasks API、21点トポロジー）のラッパー
  （`dartsanalytics.grip.landmarker`）。Phase 5と同じ `mediapipe` 依存を
  再利用（新規pip依存なし）。別途 `hand_landmarker.task` モデルファイルの
  ダウンロードが必要（`models/README.md`）。
- 特徴量計算（`dartsanalytics.grip.features`）：
  - `thumb_curl_angle_deg` / `index_curl_angle_deg` / `middle_curl_angle_deg`：
    各指のMCP-PIP-TIP間の関節角度（Phase 5の肘角度と同じ数式）。
  - `wrist_angle_deg`：手首→中指MCPの直線の画像平面上の角度（手首の2D向き
    の推定。3D回転は単一2D写真からは復元不可）。
  - `barrel_axis_deg`：親指先端→人差し指先端の直線の角度。**バレル自体は
    検出していない**ため、これはハンドランドマークのみから導いた「代理推定
    値」であることを明示し、confidenceを`MAX_BARREL_AXIS_CONFIDENCE=0.6`で
    ハードキャップ（他の特徴量より弱い根拠であることをconfidence自体で表現）。
  - すべて`DataKind.ESTIMATED`、confidenceは寄与ランドマークの信頼度の最小値
    （Phase 5と同じ保守的な合成則）。
- 2枚組（利き腕側＋反対側）の統合解析（`dartsanalytics.grip.analysis`）：
  `analyze_grip_photos(dominant_path, opposite_path)`。反対側写真は省略可能
  （未入力ならそのまま`None`、エラーにしない）。

## 実装しなかった範囲（意図的なスコープ縮小・断定禁止事項）

`dartsanalytics.grip.analysis.NOT_ASSESSED` として明示的にコード内・
結果JSONの両方に残している：

- **接触圧**：2D画像から測定不可能。
- **完全な3Dグリップ構造**：片側1枚の2D写真では3D復元不可。
- **バレル自体の形状・軸**：ダーツ/バレルの物体検出は未実装。
  `barrel_axis_deg`はハンドランドマークからの代理推定に過ぎない。

これは docs §8「写真からは指先・関節・バレル軸等を推定するが、2D画像だけで
実際の接触圧や完全な3Dグリップを断定しない」に対応する、コードレベルでの
強制。

## 技術的な制約・フラグ

1. **実写真での検証未実施**：このセッションには実際のグリップ写真が一切
   ない。単色画像・ノイズ画像に対して「手を検出しない」ことは確認済み
   （誤検出なし）だが、実際のグリップ写真での検出精度・ランドマーク位置の
   妥当性は**未検証**。実際の写真でのテストが必須（リリース前に必ず実施）。
2. **HandLandmarkerの信頼度はPoseLandmarkerより粗い**：`PoseLandmarker`は
   ランドマークごとのvisibilityスコアを返すが、インストール済みバージョンの
   `HandLandmarker`（Tasks API）は手全体（handedness分類）のスコアしか
   返さない。そのため、このスコアを全ランドマークに一律適用している
   （`dartsanalytics.grip.landmarks.HandLandmarkPoint`のdocstringに明記）。
   Phase 5のpose confidenceより粗い信号であることをフラグしておく。
3. **`barrel_axis_deg`は特に弱い推定**：実際のバレルではなく親指・人差し指
   先端の直線から代理推定しているため、confidenceを他の特徴量より低く
   ハードキャップしている（テストで検証済み：`test_barrel_axis_confidence_
   is_always_capped_low`）。

## 依存関係の追加

なし。Phase 5で追加済みの`mediapipe`を再利用。モデルファイルの追加ダウンロード
のみ（`models/hand_landmarker.task`、Gitには含めない）。

## テスト

- `tests/test_grip_features.py`：純粋数学部分（合成座標、モデル不要）。
- `tests/test_grip_landmarker.py`：実モデルに対する「未検出」経路・エラー
  ハンドリング（モデル未ダウンロード時は自動skip）。
- `tests/test_grip_analysis.py`：手が写っていない合成写真での統合パイプ
  ライン動作確認、JSON直列化可能性。

全テスト実行結果：186件パス（Phase 0-5の169件 + Phase 6の17件）。
`scripts/bootstrap_check.py`成功（`grip_analysis_runs`テーブルはPhase 0の
スキーマに既に存在しており、今回のマイグレーション追加は不要）。
