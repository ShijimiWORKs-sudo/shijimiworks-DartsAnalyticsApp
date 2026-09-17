# リリース判定報告（§13）

最終更新: 2026-09-17

本報告は`CLAUDE_RELEASE_UNRESOLVED_RESOLUTION_v1.0.md`の全セクション
（§1〜§12）の結果を一覧化するものであり、**指示書§13の明示的な指示
「『未検証』を『検証済み』と書き換えない」を厳守する**。実データ・実機
での検証が済んでいない項目は、それを実装・ツール化した場合でも
「未検証」のまま記載する。

## §16 最終ゴール13項目との対応

| # | 項目 | 状態 | 詳細 |
|---|---|---|---|
| 1 | GitHubへ安全にpush可能 | ❌ **未達成**（ユーザー操作待ち） | `github-push.md`。このセッションのリポジトリ認可ポリシーによりpush不可。作業branch 12本、全てローカル（クラウドサンドボックス内）に存在、`main`へは未マージ。 |
| 2 | BLEは実機検証結果または明確な制約が記録済み | 🟡 **部分達成**（制約は明確、実機検証は未実施） | `ble-real-device.md`。実機検証はユーザー操作待ちだが、検証を実施するための自動化スクリプト・手順書を用意し、制約（環境にBluetoothハードウェア無し、ユーザーPCへのシェルアクセス無し）を明記済み。 |
| 3 | COUNT-UP実データで精度検証済み | ❌ **未達成**（ツールのみ実装、実データでの検証は未実施） | `accuracy-validation.md`。比較ツール（exact match/score error/coordinate error/false positive-negative/number confusion/BULL近傍誤差/round error）は実装・合成データでテスト済みだが、実データでの計測は0件。 |
| 4 | グルーピング評価が分離されている | ✅ **達成** | `grouping-validation.md`。BULL率（精度指標）とグルーピング品質（まとまり指標）が構造的に分離されたフィールドとして実装され、両者が独立に動くことをテストで実証。 |
| 5 | 動画解析の条件と精度が記録済み | 🟡 **部分達成**（条件は明記済み、精度は未検証） | `video-validation.md`。撮影条件・品質チェック閾値・非同期撮影の明示・多視点統合ロジックは実装済み。実際の投球動画での精度検証は0件（実データ無し）。 |
| 6 | キャリブレーションが実装・検証済み | 🟡 **部分達成**（簡易実装のみ、高度な補正は未実装） | `calibration-validation.md`。盤中心・半径検出とその永続化・再キャリブレーション判定ロジックは実装・合成データでテスト済み。homography/lens distortion/camera parameters/board plane/segment boundaryは未実装。実データでの精度検証も未実施。 |
| 7 | DB永続化済み | ✅ **達成** | `db-persistence.md`。Repository/UnitOfWorkパターンで18テーブル中17テーブルへの読み書きを実装、テスト済み。 |
| 8 | 再起動後もデータ保持 | ✅ **達成** | `db-persistence.md`の`test_restart_persistence_survives_reconnect`で実証。 |
| 9 | migrationが検証済み | ✅ **達成** | `db-persistence.md` / 既存`test_migration.py`。冪等性・部分失敗時のロールバックをテストで確認。0001/0002の2マイグレーション。 |
| 10 | DartsSupportAppとのschema差分が明確 | ✅ **達成**（差分は明確、統合方針は未決定） | `darts-support-schema-diff.md`。両アプリのデータモデルが根本的に異なることをフィールド対応表で明確化。統合方針は4択を提示、ユーザー判断待ち。 |
| 11 | 回帰テスト済み | 🟡 **部分達成**（6カテゴリ全てに最低限のテストあり、一部は限定的） | `regression-test.md`。Unit/Integration/Persistence/Accuracy/Device/Recovery全カテゴリに対応するテストが存在（計327件合格）。Accuracy/Deviceの「実データ」側、Recoveryの「実BLE」側は範囲外（既知の制約として明記）。 |
| 12 | 既知の制約が明文化されている | ✅ **達成** | 本報告書および各`docs/reports/release/*.md`の「既知の未対応・制約」節に、セクションごとに明文化済み。 |
| 13 | release-readinessで未解決事項が一覧化されている | ✅ **達成**（本報告書） | 以下の「未解決事項一覧」参照。 |

**13項目中、完全達成6項目、部分達成4項目、未達成3項目。**

## 未解決事項一覧（優先度付き）

### ユーザー操作が必須（このセッションでは対応不可）

1. **【最優先】GitHubリポジトリ認可**：`shijimiworks-DartsAnalyticsApp`
   リポジトリへのpush権限を、このセッション/Coworkの許可リポジトリ
   一覧に追加していただく必要がある（詳細: `github-push.md`）。
2. **DartsSupportApp統合方針の決定**：4択（新規import経路追加/
   DartsAnalyticsApp契約の作り直し/両アプリ独立のまま/OpenAI API拡張
   ポイントの活用）からユーザーに選んでいただく必要がある（詳細:
   `darts-support-schema-diff.md`）。
3. **BLE実機検証**：`scripts/ble_investigate.py`の実行、または手動での
   確認（詳細: `ble-real-device.md`, `docs/reports/ble/HOWTO_ja.md`）。
4. **COUNT-UP実データの提供**：10〜30ゲーム分のDARTSLIVE HOME
   プレイデータ（詳細: `accuracy-validation.md`）。
5. **実際の投球動画・グリップ写真の提供**（あれば）：Phase 5/6の
   Pose/Grip解析の実データ検証、および`video-validation.md`の精度検証に
   必要。

### 技術的に未実装（実データ到着後に着手予定、推測実装を避けるため
意図的に先送り）

6. カメラキャリブレーションの高度化（homography/lens distortion/camera
   parameters/board plane補正/segment boundary整列）— `calibration-
   validation.md`。
7. 候補原因カテゴリ9種中4種（リリース位置/足位置/狙い線/用具/手首の
   動き）— `ai-advisor-pipeline.md`, 元々`integrated/causes.py`
   docstringに明記済み。
8. 動画品質チェックの4項目（全身可視性/肢の隠れ/ボード可視性/リリース
   可視性）とPose解析confidenceとの結線 — `video-validation.md`。
9. `pose/multi_angle.py`のセッション全体オーケストレーションへの結線
   （Application Service層への統合）— `video-validation.md`。

### 設計上意図的に対応しなかったもの（今回のスコープ外という判断）

10. §10「保存対象候補」のうちBLE observation/settingsテーブル
    （データの形が未確定のため先送り、`db-persistence.md`参照）。
11. Integration testの「video pipeline」を実ファイルで貫通させる
    end-to-endテスト（実動画ファイルが無いため — `regression-test.md`）。

## テストサマリー

`python -m pytest -q` → **327 passed, 0 failed**（本報告書作成時点）。
指示書対応開始前（Phase 0〜10完了時点）は267件だったため、今回のセッション
で60件のテストを新規追加した。リグレッションは0件。

## git状態サマリー

- 作業branch: `codex/release-resolution-db-persistence`
  （`codex/phase-10-support-contract`から分岐）
- 直近コミット: `7a99c61`（BLE tooling）を含む、本報告書作成のコミット
  が最新となる予定
- `main`へのマージ・GitHubへのpushはいずれも未実施（上記「未解決事項」
  #1参照）
- 全ての変更はこのクラウドセッションのローカルリポジトリと、
  `docs/DEV_PROGRESS.md`に記載の通りユーザーのローカルフォルダ
  （`C:\制作データ\20_DartsAnalyticsApp`）の両方に反映済み
  （`device_commit_files`によるファイル単位の同期、git commitとしての
  同期ではない点に注意 — ユーザー側でgit管理する場合は改めて
  `git add`/`git commit`が必要）

## 結論

個人利用可能かつポートフォリオ提示可能な状態への引き上げは、大きく
前進した。特にDB永続化層（Repository pattern）、個人学習ログ、グルーピング
指標の分離、多視点動画特徴量統合、再キャリブレーション判定、AI助言の
evidence/expected_effect、実データ精度検証ツール、回帰テストの
Integration/Recovery拡充、BLE検証自動化ツールは、いずれも「報告して
終了」ではなく実装・テスト・証拠化まで完了した。

一方で、GitHubへのpush・DartsSupportApp統合・BLE実機検証・実データでの
精度検証という4つのユーザー操作待ち事項は、このセッションの権限・環境の
制約上、これ以上進めることができない。これらはいずれも指示書§14が
明示的に定める停止条件（実機操作/データ提供/ユーザー判断が必要な
schema変更）に該当するものであり、推測での実装は行っていない。
