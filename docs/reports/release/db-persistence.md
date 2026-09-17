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

## §9 個人学習ログの実装（本リポジトリ層の上に追加）

指示書§9「intervention / before / change / after / result / analysis・
model versionを記録可能にし、単一試行だけで因果関係を断定しない」を、
本DB永続化層の上に追加実装した。

- **migration追加**：`db/schema/0002_learning_log.sql`で
  `learning_log_entries`テーブルを新設（既存テーブルは変更なし、後方
  互換）。`experiments`テーブル（測定値の比較）とは分離し、1
  experimentに対して人間向けの記録（何を変えたか・変更前後の要約・
  使用したアルゴリズム/モデルバージョン）を追加する設計。
- **`trial_number`の自動採番**：`SqliteLearningLogRepository
  .next_trial_number(intervention_description)`が、同じ介入内容が
  過去何回試されたかをDBから直接計算して返す。呼び出し側が回数を
  手動管理する必要がなく、カウント誤りによる「実は複数回試しているのに
  1回目と誤認する」バグを防ぐ。
- **因果断定の禁止を実行可能なロジックにした**：
  `learning_log/analysis.py`の`causal_confidence_note(trial_count)`は、
  試行回数に応じて必ず「まだ結論を出せない」という注意文を返す
  （1回目＝単一試行、2回目以上＝交絡要因への言及、多数回＝それでも
  対照群のない単一被験者記録である旨）。どの段階でも「原因が確認された」
  「証明された」という文言は返さない設計であることをテストで保証
  （`test_causal_confidence_note_never_confirms`）。これはPhase 9の
  `advisor.generate`が持つ`BANNED_ABSOLUTE_PHRASES`と同じ設計思想を
  学習ログ側にも適用したもの。
- **テスト**：`tests/test_learning_log.py`（9件）＋
  `tests/test_session_recording_service.py`に1件追加
  （`test_learning_log_entry_lifecycle`：記録→結果更新→2回目の試行→
  履歴取得までの一連の流れをApplication Service経由で確認）。

## 既知の未対応・今後の課題

- **§10「保存対象候補」の一部は未対応**：指示書§10が例示する保存対象
  （account/player/game session/COUNT-UP/round/throw/score/coordinate/
  video metadata/video analysis/calibration/equipment/grip metadata/
  advice/evidence/experiment/validation/**BLE observation**/**settings**）
  のうち、**BLE observation**と**settings**は対応するテーブルがまだ
  存在しない（Phase 0時点のスキーマに無く、今回は新規テーブル追加を
  最小限＝学習ログ用の1テーブルのみに留めた）。BLEは§3（実機検証）が
  ユーザー操作待ちで未実施のため観測データ自体がまだ存在せず、テーブル
  設計を先行して行うと「取得できるデータの形」を推測することになり
  指示書§14の「外部仕様不明で推測実装になる場合は停止する」に抵触しうる
  ため、意図的に見送った。settingsは現時点でアプリ設定の具体的な項目が
  未確定（UI未実装のため）であり、同様に見送った。どちらも今回追加した
  `migrate.py`のマイグレーション機構で後から追加できる。
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
migration・rollback・duplicate・corrupt-dataの検証）と§9（個人学習ログ）
は実装・テストとも完了。267件だった既存テストは全て引き続き合格し、
新規26件（リポジトリ17件＋学習ログ9件、Application Serviceテスト含む）
を加えた計293件が合格（`python -m pytest -q` で確認、リグレッションなし）。
