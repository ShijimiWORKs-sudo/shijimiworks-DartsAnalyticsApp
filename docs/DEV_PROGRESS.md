# DEV_PROGRESS.md（指示書§15）

最終更新: 2026-09-17（GitHub push完了・DartsSupportApp統合実装・Pose品質
結線後の状態）

このファイルは、`CLAUDE_RELEASE_UNRESOLVED_RESOLUTION_v1.0.md`の§15
「フェーズ運用」に基づき、コンテキスト/セッション上の理由で作業を
中断する必要が生じた場合に備えて継続的に更新する。**現時点では停止して
いない** — 指示書の§1〜§13全セクションについて、可能な範囲での実装・
テスト・証拠化が完了し、当初「ユーザー操作待ち」としていた項目のうち
GitHub push・DartsSupportApp統合方針も解決した。詳細な総括は
`docs/reports/release/release-readiness.md`を参照。

## completed（指示書§1〜§13、全セクション対応済み。2026-09-17に4項目が追加で解決）

| § | 内容 | 成果物 |
|---|---|---|
| §1 | 初期監査 | 以降の実装作業に反映（専用ファイルなし） |
| §2 | GitHub push | `docs/reports/release/github-push.md`。**2026-09-17: 全13ブランチをGitHubへpush完了**（gitバンドル経由でユーザー自身のPCの認証を使用）。 |
| §3 | BLE実機検証ツール | `scripts/ble_investigate.py`, `docs/reports/ble/`, `docs/reports/release/ble-real-device.md`。ツール実装済み、BLE対応USBドングルをユーザーが購入手配中。 |
| §4 | 実データ精度検証ツール | `src/dartsanalytics/validation/accuracy.py`, `docs/reports/release/accuracy-validation.md`。**2026-09-17: セッション合計スコアの実データ参考比較を実施**（1投単位の検証はBLE実機検証待ち）。 |
| §5 | グルーピング解析 | `docs/reports/release/grouping-validation.md` |
| §6 | 動画解析検証 | `src/dartsanalytics/pose/multi_angle.py`, `src/dartsanalytics/pose/quality_integration.py`（2026-09-17新規）, `docs/reports/release/video-validation.md`。**2026-09-17: 品質チェック4項目中3項目とPose confidenceの結線を実装。** |
| §7 | キャリブレーション検証 | `src/dartsanalytics/board/recalibration.py`, `docs/reports/release/calibration-validation.md` |
| §8 | AI助言パイプライン | `docs/reports/release/ai-advisor-pipeline.md` |
| §9 | 個人学習ログ | `src/dartsanalytics/learning_log/`, `db/schema/0002_learning_log.sql` |
| §10 | DB永続化（Repository pattern） | `src/dartsanalytics/db/repositories/`, `db/unit_of_work.py`, `application/session_recording_service.py`, `docs/reports/release/db-persistence.md`。**2026-09-17: `record_multi_angle_pose_analysis()`追加で multi_angle.py のオーケストレーション結線も完了。** |
| §11 | DartsSupportApp契約突合 | `docs/reports/release/darts-support-schema-diff.md`。**2026-09-17: ユーザーが統合方針の選択肢4を選択、`contract/support_app_assessment.py`として実装完了。** |
| §12 | 回帰テスト拡充 | `tests/test_integration_pipeline.py`, `tests/test_db_recovery.py`, `docs/reports/release/regression-test.md` |
| §13 | リリース判定報告 | `docs/reports/release/release-readiness.md`（2026-09-17に大幅更新） |

**全て「未検証」を「検証済み」と書き換えることなく報告済み**（§13の
明示的ルールを遵守 — 実データ/実機検証が必要な項目は今回もツール実装・
制約明記までに留め、検証済みとは記載していない）。

## uncompleted（このセッションでは対応不可、ユーザー操作待ち — 2026-09-17時点で2点に縮小）

`docs/reports/release/release-readiness.md`の「未解決事項一覧」参照。

1. **BLE実機検証**：ユーザーがBLE対応USBドングル（Rikuto Bluetooth 5.4）
   を購入手配済み。到着後、`scripts/ble_investigate.py`の実行が必要
   （`ble-real-device.md`, `scripts/ble_investigate.py`）。
2. **COUNT-UP実データ（1投単位）の提供**：セッション合計スコアの参考値は
   受領済みだが、1投ごとの構造化データはBLE実機検証結果に依存
   （`accuracy-validation.md`）。

~~GitHubリポジトリへのpush権限~~・~~DartsSupportApp統合方針の4択判断~~は
2026-09-17に解決済み。

これら残り2点はいずれも指示書§14の停止条件（実機操作/データ提供）に
該当するため、このセッションから先へは進められない。

## current branch

`codex/release-resolution-db-persistence`
（`codex/phase-10-support-contract`から分岐）

**GitHub状態（2026-09-17更新）**：13ブランチ全て（main含む）が
`https://github.com/ShijimiWORKs-sudo/shijimiworks-DartsAnalyticsApp`
にpush済み（`git ls-remote origin`で確認）。`main`への統合マージは
まだ行っていない — 各Phase branchが個別に存在する状態。

## latest commit

`git log -1 --oneline`で確認すること。2026-09-17時点でのこのブランチの
最新コミットは、multi_angle DB結線＋pose品質結線＋release-readiness.md/
DEV_PROGRESS.md更新を含むコミット（本ファイル更新時点で確定）。
GitHub側もこの内容まで反映済み。

## test results

`python -m pytest -q` → 360 passed, 0 failed（このファイル最終更新時点）。
セクション対応開始前（Phase 0〜10完了時点）の267件から93件を新規追加、
リグレッション0件。

## blocker

真の停止条件（§14）には該当していない（作業自体は完了）。ただし
上記「uncompleted」の2項目は、このセッションの権限・環境では対応不可な
ユーザー操作待ち事項として確定している。

## required user action

1. （優先度: 中、時間のある時でよい）BLE対応USBドングル到着後、
   `scripts/ble_investigate.py`を実行してDARTSLIVE HOMEのBLE実機検証を
   行ってほしい（`docs/reports/ble/HOWTO_ja.md`参照）。
2. （優先度: 中、時間のある時でよい）実際のCOUNT-UPプレイデータ
   （1投単位の詳細データ、BLE実機検証で取得予定）を提供してほしい。

## next command/action

指示書§1〜§13の対応は完了、GitHub push・DartsSupportApp統合実装も完了。
次に行うべきことは、上記2つのユーザー操作を待つこと：

- BLEログが届いた場合 → 生データを解析し、
  `UnimplementedBleDartsLiveHomeAdapter`の実装に着手する。
- 実データ（1投単位）が届いた場合 → `dartsanalytics.validation.accuracy
  .compare_sessions()`を実行し、`accuracy-validation.md`を実測値で更新
  する。

作業再開コマンド:
```
cd /home/claude/work/shijimiworks-DartsAnalyticsApp
git status --short && git log --oneline -5
python -m pytest -q
```
