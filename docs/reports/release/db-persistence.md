# DB永続化レイヤー実装報告（§10）

最終更新: 2026-09-17

## 概要

指示書§10「UI → Application Service → Repository Interface → Local DB
Repository」のパターンで、Phase 0で定義済みのSQLiteスキーマ
(`db/schema/0001_initial.sql`、18テーブル）に対する永続化レイヤーを実装した。
これまでPhase 0〜10はすべて「メモリ上のdataclass → JSON export」で完結して
おり（`experiments/models.py`のdocstringに明記の通り「no repository/DAO
layer exists yet in any Phase」）、DB書き込み・読み込みコードは今回が初。

## 実装構成

```
src/dartsanalytics/
  application/
    session_recording_service.py   # Application Service（UI相当の呼び出し口）
  db/
    unit_of_work.py                # UnitOfWork（トランザクション境界）
    repositories/
      interfaces.py                 # Repository Interface（typing.Protocol）
      sqlite_repositories.py        # Local DB Repository（SQLite実装）
```

- **Repository Interface**（`interfaces.py`）: `AccountRepository` /
  `PlayerRepository` / `EquipmentRepository` / `SessionRepository` /
  `CalibrationRepository` / `MediaRepository` / `PoseFeatureRepository` /
  `GripAnalysisRepository` / `AnalysisReportRepository` /
  `ExperimentRepository` の10個を`typing.Protocol`で定義。将来SQLite以外の
  実装（またはテスト用インメモリfake）に差し替え可能な設計。
- **Local DB Repository**（`sqlite_repositories.py`）: 上記10インターフェース
  すべてに対するSQLite実装。既存の`dartsanalytics.models.entities` /
  `board.calibration` / `video.models` / `experiments.models` /
  `advisor.models` / `grip.analysis` / `pose.features`のdataclassをそのまま
  読み書きし、DB専用の並行データ型は作らない。
- **UnitOfWork**（`unit_of_work.py`）: `SqliteUnitOfWork`が1コネクションを
  開き、上記10リポジトリをまとめて公開。`with`ブロックの正常終了で
  `commit()`、例外発生で`rollback()`。複数リポジトリにまたがる書き込み
  （例：セッション＋ラウンド＋投擲）が1トランザクションで原子的に完結する。
- **Application Service**（`session_recording_service.py`）:
  `SessionRecordingService`が上記を組み合わせた具体的なユースケースを提供
  （`record_countup_session` / `get_session_history` /
  `record_board_calibration` / `record_media_asset` /
  `record_grip_analysis` / `record_advisor_output` / `record_experiment` /
  `record_experiment_decision`）。UI層はこのサービスのみを呼び、sqlite3を
  直接扱わない。

## 対応テーブル（18テーブル中17テーブルへの読み書きを実装）

`accounts`, `players`, `equipment_profiles`, `practice_sessions`,
`countup_rounds`, `throws`, `throw_coordinates`, `board_calibrations`,
`media_assets`, `video_analysis_runs`, `pose_features`,
`grip_analysis_runs`, `analysis_reports`, `hypotheses`, `interventions`,
`experiments`, `experiment_results`。

未対応: `schema_migrations`（migrate.pyが内部管理する専用テーブルであり、
アプリ側リポジトリの対象外）。

## テスト（`tests/test_repositories.py` 14件 + `tests/test_session_recording_service.py` 3件、計17件、すべて合格）

指示書§10が要求する評価項目ごとに、実際に確認した証拠：

| 要求項目 | テスト | 結果 |
|---|---|---|
| 再起動後の永続性 | `test_restart_persistence_survives_reconnect` — 1つ目の`SqliteUnitOfWork`で書き込み→接続を閉じる→新規`SqliteUnitOfWork`（＝新規`sqlite3.Connection`）で読み出し | 合格（アプリ再起動を模擬） |
| マイグレーション | 既存`tests/test_migration.py`（8件、Phase 0実装済み）を再確認 — 冪等性・部分失敗時のロールバックを含む | 合格（変更なし、既存のまま） |
| ロールバック | `test_unit_of_work_rolls_back_whole_transaction_on_error` — 正常なセッション書き込みの直後に、存在しないplayer_idを参照する2件目の書き込みでFOREIGN KEY違反を起こし、`with`ブロック全体（1件目の正常な書き込みを含む）が消えることを確認 | 合格 |
| 重複処理 | `test_duplicate_throw_number_in_session_rejected` — 同一`(session_id, throw_number_in_session)`に別`throw_id`で2件目を書き込もうとすると`sqlite3.IntegrityError`になることを確認 | 合格（下記「発見した設計上の問題」参照） |
| 破損データ処理 | `test_corrupt_data_kind_rejected_by_check_constraint` / `test_corrupt_confidence_out_of_range_rejected` — 不正な`data_kind`値・範囲外の`confidence`値がCHECK制約で拒否されることを確認 | 合格 |

その他、全リポジトリの往復（save → get で同じ値が戻る）を個別にテスト
（account/player/equipment、session+rounds+throws、calibration、
media_asset、pose_features、grip_analysis、analysis_report+hypothesis、
experiment+results）。

## 発見した設計上の問題と修正

実装中、`_save_throw`/`_save_round`に最初`INSERT OR REPLACE`を使ったところ、
重複処理テストが「例外が飛ばない」で失敗した。原因を調査した結果、
`INSERT OR REPLACE`はテーブルの**あらゆる**UNIQUE制約の衝突を「古い行を
削除して新しい行を挿入」で解決するため、`throws.UNIQUE(session_id,
throw_number_in_session)`という2次的な一意制約に別の`throw_id`で衝突した
場合、エラーにならず**無言で別の投擲データが消える**というデータ消失バグに
なっていた。

修正として、主キー（`throw_id`/`round_id`）のみを対象にした
`INSERT ... ON CONFLICT(pk) DO UPDATE SET ...`（SQLiteのUPSERT構文）に変更。
これにより：
- 同じ`throw_id`での再保存（意図した更新）は引き続き成功する
- 別の`throw_id`が`(session_id, throw_number_in_session)`に衝突した場合は
  `sqlite3.IntegrityError`が正しく飛ぶ（データ消失を防ぐ）

この修正は今回のテスト作成中に見つかったバグであり、テストを先に書いた
ことで実装ミスとして検出できた（指示書§12が求める「回帰テスト」の価値を
このレイヤー自身が示した例）。

## 既知の未対応・今後の課題

- **UI層は存在しない**：`SessionRecordingService`はUI相当の呼び出し口を
  実証する参照実装だが、実際のUI（CLI/GUI/モバイル等）はこのプロジェクトの
  スコープにまだ含まれていない（指示書自身も「DB persistence」を「UI」とは
  別項目として扱っている）。
- **マイグレーション「ロールバック」は「schema変更の巻き戻し」ではない**：
  `migrate.py`が保証するのは「1マイグレーションの部分適用を防ぐ」ロール
  バックであり、適用済みマイグレーションを取り消すダウンマイグレーション
  機能は無い（Phase 0から変更なし、今回のスコープ外）。
- **並行アクセス**は検証していない（同一DBファイルへの複数プロセス同時
  書き込み）。個人利用の単一プロセスアプリという前提（docs §25
  「ローカルファースト、1インストールにつき1SQLiteファイル」）に基づき、
  今回のスコープからは意図的に除外した。将来複数端末同期を追加する場合は
  改めて検証が必要。
- **`pose_features`/`grip_analysis_runs`のスキーマは1機能分のみ検証**：
  Phase 5/6が生成する実際の`VideoPoseResult`/`GripAnalysisResult`全体を
  そのままDBに流し込むend-to-endの結線（動画解析パイプライン→
  リポジトリ）はまだ書いていない。今回実装したのは「渡されたPoseFeatures/
  GripAnalysisResultを正しく保存・復元できる」ことの検証であり、Phase 5/6
  の実行結果を自動的にDBへ書き込む配線はスコープ外（必要になった時点で
  Application Service層にメソッドを追加すればよい設計にはなっている）。

## 結論

指示書§10の要求（Repository/DAOパターンによる永続化レイヤー、restart・
migration・rollback・duplicate・corrupt-dataの検証）は実装・テストとも
完了。267件だった既存テストは全て引き続き合格し、新規17件を加えた
計284件が合格（`python -m pytest -q` で確認、リグレッションなし）。
