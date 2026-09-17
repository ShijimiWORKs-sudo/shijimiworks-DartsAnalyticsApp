# リリース判定報告（§13）

最終更新: 2026-09-17（GitHub push完了・DartsSupportApp統合方針決定＆実装・
Pose品質結線後の状態）

本報告は`CLAUDE_RELEASE_UNRESOLVED_RESOLUTION_v1.0.md`の全セクション
（§1〜§12）の結果を一覧化するものであり、**指示書§13の明示的な指示
「『未検証』を『検証済み』と書き換えない」を厳守する**。実データ・実機
での検証が済んでいない項目は、それを実装・ツール化した場合でも
「未検証」のまま記載する。

## §16 最終ゴール13項目との対応

| # | 項目 | 状態 | 詳細 |
|---|---|---|---|
| 1 | GitHubへ安全にpush可能 | ✅ **達成**（2026-09-17追記） | `github-push.md`。ユーザー自身のPCの認証を使い、gitバンドル経由で全13ブランチ（main含む）をGitHubへpush済み。`git ls-remote`で反映を確認済み。 |
| 2 | BLEは実機検証結果または明確な制約が記録済み | 🟡 **部分達成**（BLE対応USBドングルを購入手配、実機検証はこれから） | `ble-real-device.md`。検証を実施するための自動化スクリプト・手順書は用意済み。セッション開始時点の制約（環境にBluetoothハードウェア無し）はユーザーがBLE対応USBドングル（Bluetooth 5.4、EDR/LE対応、ドライバー不要）を購入することで解消見込み。到着後の実機検証待ち。 |
| 3 | COUNT-UP実データで精度検証済み | 🟡 **部分達成**（セッション合計スコアの参考値は受領・比較済み、1投単位の精度検証は未実施） | `accuracy-validation.md`。比較ツール本体は実装・合成データでテスト済み。ユーザーからDARTSLIVE HOME実機のセッション合計スコア実データ（30ゲーム、BEST/AVERAGE）を受領し、モック生成器の分布と比較する参考評価を実施済み。ただし1投ごとの構造化データ（exact match rate等、本来の§4要求）はまだ無く、BLE実機検証待ち。 |
| 4 | グルーピング評価が分離されている | ✅ **達成** | `grouping-validation.md`。BULL率（精度指標）とグルーピング品質（まとまり指標）が構造的に分離されたフィールドとして実装され、両者が独立に動くことをテストで実証。 |
| 5 | 動画解析の条件と精度が記録済み | 🟡 **部分達成**（条件・品質チェック↔Pose結線・多視点統合の結線は実装済み、実映像での精度は未検証） | `video-validation.md`。撮影条件・品質チェック閾値・非同期撮影の明示・多視点統合ロジックに加え、2026-09-17追記で品質チェック4項目中3項目とPose解析confidenceの結線、`multi_angle.py`のApplication Service層への統合を実装・合成データでテスト済み。実際の投球動画での精度検証は0件（実データ無し）。 |
| 6 | キャリブレーションが実装・検証済み | 🟡 **部分達成**（簡易実装のみ、高度な補正は未実装） | `calibration-validation.md`。盤中心・半径検出とその永続化・再キャリブレーション判定ロジックは実装・合成データでテスト済み。homography/lens distortion/camera parameters/board plane/segment boundaryは未実装。実データでの精度検証も未実施。 |
| 7 | DB永続化済み | ✅ **達成** | `db-persistence.md`。Repository/UnitOfWorkパターンで18テーブル中17テーブルへの読み書きを実装、テスト済み。 |
| 8 | 再起動後もデータ保持 | ✅ **達成** | `db-persistence.md`の`test_restart_persistence_survives_reconnect`で実証。 |
| 9 | migrationが検証済み | ✅ **達成** | `db-persistence.md` / 既存`test_migration.py`。冪等性・部分失敗時のロールバックをテストで確認。0001/0002の2マイグレーション。 |
| 10 | DartsSupportAppとのschema差分が明確 | ✅ **達成**（差分明確化に加え、統合方針をユーザーが決定・実装も完了、2026-09-17追記） | `darts-support-schema-diff.md`。ユーザーが4択中「選択肢4：OpenAI API連携拡張ポイントの活用」を選択、DartsAnalyticsApp側のエクスポート実装（`contract/support_app_assessment.py`）を追加。DartsSupportApp側のスキーマ変更・実装はスコープ外（別リポジトリのため）。 |
| 11 | 回帰テスト済み | 🟡 **部分達成**（6カテゴリ全てに最低限のテストあり、一部は限定的） | `regression-test.md`。Unit/Integration/Persistence/Accuracy/Device/Recovery全カテゴリに対応するテストが存在（計360件合格）。Accuracy/Deviceの「実データ」側、Recoveryの「実BLE」側は範囲外（既知の制約として明記）。 |
| 12 | 既知の制約が明文化されている | ✅ **達成** | 本報告書および各`docs/reports/release/*.md`の「既知の未対応・制約」節に、セクションごとに明文化済み。 |
| 13 | release-readinessで未解決事項が一覧化されている | ✅ **達成**（本報告書） | 以下の「未解決事項一覧」参照。 |

**13項目中、完全達成8項目、部分達成5項目、未達成0項目**（2026-09-17時点。
初回作成時は完全達成6/部分達成4/未達成3〈うち2項目は未達成、集計ミスで
「3」と記載していた点も本追記で訂正〉。今回のセッションでGitHub push・
DartsSupportApp統合実装・Pose品質結線の3項目が完全達成へ移行、実データ
比較が部分達成へ前進）。

## 未解決事項一覧（優先度付き、2026-09-17更新）

### ユーザー操作待ち（一部は対応中）

1. **BLE実機検証**：ユーザーがBLE対応USBドングル（Rikuto Bluetooth 5.4、
   EDR/LE対応、ドライバー不要 — スペック確認済み、相性上の懸念点なし）を
   購入手配済み。到着後、`scripts/ble_investigate.py`の実行、または
   手動での確認が必要（詳細: `ble-real-device.md`,
   `docs/reports/ble/HOWTO_ja.md`）。
2. **COUNT-UP実データ（1投単位）の提供**：セッション合計スコアの参考値は
   受領済みだが、`compare_sessions()`が要求する1投ごとの構造化データ
   （セグメント・座標）はBLE実機検証で取得予定のデータに依存する
   （詳細: `accuracy-validation.md`）。
3. **実際の投球動画・グリップ写真の提供**（あれば）：Phase 5/6の
   Pose/Grip解析の実データ検証、および`video-validation.md`の精度検証に
   必要。

解決済み（このセッションで対応完了）：
- ~~GitHubリポジトリ認可~~ → git bundle経由でユーザー自身の認証を使い
  push完了。
- ~~DartsSupportApp統合方針の決定~~ → ユーザーが選択肢4を選択、
  DartsAnalyticsApp側の実装も完了。

### 技術的に未実装（実データ到着後に着手予定、推測実装を避けるため
意図的に先送り）

4. カメラキャリブレーションの高度化（homography/lens distortion/camera
   parameters/board plane補正/segment boundary整列）— `calibration-
   validation.md`。
5. 候補原因カテゴリ9種中4種（リリース位置/足位置/狙い線/用具/手首の
   動き）— `ai-advisor-pipeline.md`, 元々`integrated/causes.py`
   docstringに明記済み。それぞれ新しい特徴抽出器が必要で、単純な
   「結線」では対応できないため引き続き先送り。

解決済み（このセッションで対応完了）：
- ~~動画品質チェックの4項目とPose解析confidenceとの結線~~ → 3/4項目
  （全身可視性/肢の隠れ/リリース可視性）を実装・合成データでテスト済み
  （`pose/quality_integration.py`）。残る1項目（ボード可視性）は
  物体検出器が別途必要なため、引き続き`None`のまま正直に未評価とした
  （詳細: `video-validation.md`）。
- ~~`pose/multi_angle.py`のセッション全体オーケストレーションへの結線~~
  → `SessionRecordingService.record_multi_angle_pose_analysis()`として
  実装・テスト済み（詳細: `video-validation.md`）。

### 設計上意図的に対応しなかったもの（今回のスコープ外という判断）

6. §10「保存対象候補」のうちBLE observation/settingsテーブル
   （データの形が未確定のため先送り、`db-persistence.md`参照）。
7. Integration testの「video pipeline」を実ファイルで貫通させる
   end-to-endテスト（実動画ファイルが無いため — `regression-test.md`）。

## テストサマリー

`python -m pytest -q` → **360 passed, 0 failed**（本追記時点）。
指示書対応開始前（Phase 0〜10完了時点）は267件、初回release-readiness
作成時点は327件だったため、今回のセッション全体で93件のテストを新規
追加した。リグレッションは0件。

## git状態サマリー（2026-09-17更新）

- 作業branch: `codex/release-resolution-db-persistence`
  （`codex/phase-10-support-contract`から分岐）
- **全13ブランチ（main含む）がGitHubリポジトリ
  `ShijimiWORKs-sudo/shijimiworks-DartsAnalyticsApp`にpush済み**
  （`git ls-remote origin`で確認済み。クラウドセッションからの直接push
  はリポジトリ認可ポリシー上できないため、gitバンドルを経由してユーザー
  自身のPCの認証でpushする方式を取った）。`main`ブランチへのマージ
  （12本のPhase branchの統合）はまだ行っていない — 各branchが個別に
  GitHub上に存在する状態。
- 全ての変更はこのクラウドセッションのローカルリポジトリと、
  `docs/DEV_PROGRESS.md`に記載の通りユーザーのローカルフォルダ
  （`C:\制作データ\20_DartsAnalyticsApp`）の両方に反映済み。

## 結論

個人利用可能かつポートフォリオ提示可能な状態への引き上げは、大きく
前進した。今回のセッションで、GitHubへのpush・DartsSupportApp統合方針の
決定と実装・動画品質チェックとPose解析の結線・multi_angleのオーケスト
レーション結線という、当初「ユーザー操作待ち」または「技術的未実装」と
していた項目のうち4つが完全に解決した。特にGitHub push問題は、クラウド
セッションのリポジトリ認可ポリシーというこのセッション自身の制約が原因
だったが、gitバンドル経由でユーザー自身のPCの認証を使うという回避策で
解決できた。

残る未解決事項は、BLE実機検証（ユーザーがBLE対応USBドングルを購入手配
済み、到着待ち）と、それに連鎖する1投単位のCOUNT-UP実データでの精度
検証のみである。いずれも指示書§14が明示的に定める停止条件（実機操作・
データ提供が必要）に該当するものであり、推測での実装は行っていない。
カメラキャリブレーションの高度化と候補原因カテゴリの残り4種は、実データ
到着後に着手する設計上の判断として、引き続き意図的に先送りしている。
