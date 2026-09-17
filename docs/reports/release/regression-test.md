# 回帰テスト拡充報告（§12）

最終更新: 2026-09-17

## 要求されるカテゴリ（指示書§12、原文）

Unit（score/coordinate/grouping/calibration/advice rules/repositories）、
Integration（application service/DB/video pipeline/BLE adapter）、
Persistence（restart/migration/rollback/duplicate/invalid-corrupt
data）、Accuracy（known data/real COUNT-UP data）、Device（camera/BLE/
file import-export）、Recovery（interrupted analysis/invalid video/BLE
disconnect/DB failure）。

## 現状: 327件のテストが全て合格（`python -m pytest -q`）

以下、カテゴリごとに対応するテストファイル・件数・状態を整理する。

### Unit

| 対象 | テストファイル | 状態 |
|---|---|---|
| score | `test_scoring.py` | 実装済み |
| coordinate | `test_coordinates.py` | 実装済み |
| grouping | `test_grouping.py`（14件、今回3件追加） | 実装済み |
| calibration | `test_calibration.py`, `test_recalibration.py`（今回新規7件） | 実装済み |
| advice rules | `test_advisor.py`, `test_causes.py`, `test_correlation.py` | 実装済み |
| repositories | `test_repositories.py`（今回新規14件）, `test_learning_log.py`（今回新規9件） | 実装済み |

その他既存Unit: `test_confidence.py`, `test_entities.py`,
`test_dartslive_adapter.py`, `test_angles.py`, `test_video_quality.py`,
`test_reshoot.py`, `test_frame_metrics.py`, `test_ffmpeg_tools.py`,
`test_video_intake.py`, `test_pose_geometry.py`, `test_pose_features.py`,
`test_pose_landmarker.py`, `test_pose_release.py`,
`test_pose_video_analysis.py`, `test_pose_multi_angle.py`（今回新規7件）,
`test_grip_features.py`, `test_grip_landmarker.py`,
`test_grip_analysis.py`, `test_heatmap.py`, `test_frequent_segments.py`,
`test_late_round.py`, `test_integrated_report.py`,
`test_experiment_comparison.py`, `test_experiment_decision.py`,
`test_experiment_models.py`, `test_mock_generator.py`,
`test_session_result.py`, `test_export.py`,
`test_support_app_contract.py`, `test_accuracy_validation.py`（今回新規
10件、ツール自体のUnitテストとして分類 — 実データ検証とは別）。

### Integration（今回新規、`tests/test_integration_pipeline.py` 2件）

- `test_full_pipeline_mock_session_to_persisted_advisor_output`：mock
  COUNT-UPセッション生成 → grouping/frequent-segment/late-round統計 →
  IntegratedAnalysisReport → candidate causes → AdvisorOutput →
  Application Service経由でDB保存 → 新規接続で再読み込み、という
  countup/board/integrated/advisor/application/db 全層を貫通する
  end-to-endテスト。モジュール単体テストでは検出できない「層と層の
  境界での不整合」（フィールド名の変更漏れ、型の不一致等）を検出する
  ために新規追加。
- `test_pipeline_handles_session_with_no_coordinate_data`：座標データが
  まだ無いセッション（DARTSLIVE HOME計測のみ、カメラ解析前）でも
  パイプライン全体がクラッシュせず適切に「評価できない」と報告することを
  確認。

`application service <-> DB`は上記1件目で直接カバー。`video pipeline`は
`test_video_intake.py`/`test_video_quality.py`/`test_reshoot.py`が個々の
段階を単体でカバーしているが、動画ファイル1本を実際に
intake→quality→pose解析まで通す完全なend-to-endの統合テストは
（実際の動画ファイルが必要なため）今回未追加 — 既知の制約として明記。
`BLE adapter`の統合は`test_dartslive_adapter.py`の
`test_mock_adapter_yields_24_events_and_matches_mock_generator`が
アダプタ経由とPhase 1直接生成の一致を確認する形で既にカバーしている
（Phase 7実装時点、変更なし）。

### Persistence（§10実装時に整備、`tests/test_repositories.py` +
`tests/test_migration.py`）

- restart: `test_restart_persistence_survives_reconnect`
- migration: `test_migration.py`全体（冪等性・部分失敗ロールバック含む、
  既存）
- rollback: `test_unit_of_work_rolls_back_whole_transaction_on_error`
- duplicate: `test_duplicate_throw_number_in_session_rejected`
- invalid/corrupt data: `test_corrupt_data_kind_rejected_by_check_constraint`,
  `test_corrupt_confidence_out_of_range_rejected`

### Accuracy

- known data（合成データでの検証）: `test_grouping.py`,
  `test_accuracy_validation.py`ほぼ全件
- real COUNT-UP data: **未実施**（§4参照、ユーザーからの実データ提供待ち）

### Device

- camera: `test_ffmpeg_tools.py`, `test_video_quality.py`
  （実カメラではなく合成/生成した動画ファイルでのテスト。実機カメラでの
  検証は§6同様、実データ待ち）
- BLE: `test_dartslive_adapter.py`（Mockアダプタのみ、実機は§3でユーザー
  操作待ち）
- file import/export: `test_export.py`, `test_support_app_contract.py`

### Recovery（今回新規、`tests/test_db_recovery.py` 3件 + 既存テストの
再整理）

| 要求項目 | 対応 |
|---|---|
| interrupted analysis | `test_migration.py::test_partial_migration_failure_rolls_back_cleanly`（既存）, `test_repositories.py::test_unit_of_work_rolls_back_whole_transaction_on_error`（既存） |
| invalid video | `test_ffmpeg_tools.py::test_probe_metadata_missing_file_raises_probe_error`, `::test_probe_metadata_missing_binary_raises_clear_error`（既存） |
| BLE disconnect | `test_dartslive_adapter.py::test_mock_adapter_requires_connect_before_events`, `::test_unimplemented_ble_adapter_refuses_to_guess`（既存 — 実BLEアダプタ自体が未実装のため、インターフェース境界での挙動確認が限界） |
| DB failure | **今回新規**：`test_db_recovery.py`（破損DBファイルを開こうとした場合に`sqlite3.DatabaseError`が飛ぶこと／DBパスがディレクトリと衝突した場合に明確なエラーになること／1つの接続の失敗が別の正常なDBファイルに影響しないこと） |

DB failureのテストで当初「読み取り専用ディレクトリへの書き込み」を
想定していたが、**このセッションの実行環境がrootユーザーであり、
Linuxのパーミッションビットはrootに対して機能しない**ことが判明した
ため、権限に依存しない失敗モード（DBパスが既存ディレクトリと衝突する
ケース）に差し替えた。この判断自体もテストの信頼性を担保する上で
重要な発見だったため、テストファイルのコメントに明記した。

## 今回のセッションでのテスト件数推移

| 時点 | 件数 |
|---|---|
| §10着手前（Phase 0〜10完了時点） | 267 |
| §10 DB永続化層 | 284 |
| §9 個人学習ログ | 293 |
| §5 グルーピング | 296 |
| §6 動画解析（multi_angle） | 303 |
| §7 キャリブレーション（recalibration） | 310 |
| §8 AI助言パイプライン | 312 |
| §4 精度検証ツール | 322 |
| §12 回帰テスト拡充（本セクション） | **327** |

## 既知の未対応・制約

- Integration category の「video pipeline」全体を貫通するテスト
  （実ファイル使用）は未追加。理由：実際のダーツ投球動画が本セッション
  には無く、合成動画（単色/ノイズフレーム）でのend-to-endテストは
  `test_video_intake.py`等の個別テストと実質的に重複するため、優先度を
  下げた。
- Accuracy/Device category の「real data」側は引き続き未実施
  （§4/§6/§3それぞれのユーザー操作待ち事項に依存）。
- BLE関連のRecovery/Deviceテストは、実アダプタが存在しない
  （`UnimplementedBleDartsLiveHomeAdapter`）ため、インターフェース境界
  （「未実装なら推測せず例外を投げる」）の確認が限界であり、実機との
  接続断・再接続シナリオの検証は§3のBLE実機検証が完了してからでないと
  実施できない。

## 結論

指示書§12が要求する6カテゴリ（Unit/Integration/Persistence/Accuracy/
Device/Recovery）全てに対応するテストが少なくとも1件以上存在することを
確認した。今回新規に追加したのはIntegration（2件）とDB Recovery
（3件）。Accuracy/Deviceの「real data」側と、Recovery/Deviceの
「実BLE」側は、ユーザー操作待ちの外部要因により引き続き未実施である
ことを明記する。327件のテストが全て合格。
