# DEV_PROGRESS.md（指示書§15）

最終更新: 2026-09-17（§1〜§13 全セクション対応完了時点）

このファイルは、`CLAUDE_RELEASE_UNRESOLVED_RESOLUTION_v1.0.md`の§15
「フェーズ運用」に基づき、コンテキスト/セッション上の理由で作業を
中断する必要が生じた場合に備えて継続的に更新する。**現時点では停止して
いない** — 指示書の§1〜§13全セクションについて、可能な範囲での実装・
テスト・証拠化が完了した。詳細な総括は
`docs/reports/release/release-readiness.md`を参照。

## completed（指示書§1〜§13、全セクション対応済み）

| § | 内容 | 成果物 |
|---|---|---|
| §1 | 初期監査 | 以降の実装作業に反映（専用ファイルなし） |
| §2 | GitHub push検証 | `docs/reports/release/github-push.md` |
| §3 | BLE実機検証ツール | `scripts/ble_investigate.py`, `docs/reports/ble/`, `docs/reports/release/ble-real-device.md` |
| §4 | 実データ精度検証ツール | `src/dartsanalytics/validation/accuracy.py`, `docs/reports/release/accuracy-validation.md` |
| §5 | グルーピング解析 | `docs/reports/release/grouping-validation.md` |
| §6 | 動画解析検証 | `src/dartsanalytics/pose/multi_angle.py`, `docs/reports/release/video-validation.md` |
| §7 | キャリブレーション検証 | `src/dartsanalytics/board/recalibration.py`, `docs/reports/release/calibration-validation.md` |
| §8 | AI助言パイプライン | `docs/reports/release/ai-advisor-pipeline.md` |
| §9 | 個人学習ログ | `src/dartsanalytics/learning_log/`, `db/schema/0002_learning_log.sql` |
| §10 | DB永続化（Repository pattern） | `src/dartsanalytics/db/repositories/`, `db/unit_of_work.py`, `application/session_recording_service.py`, `docs/reports/release/db-persistence.md` |
| §11 | DartsSupportApp契約突合 | `docs/reports/release/darts-support-schema-diff.md` |
| §12 | 回帰テスト拡充 | `tests/test_integration_pipeline.py`, `tests/test_db_recovery.py`, `docs/reports/release/regression-test.md` |
| §13 | リリース判定報告 | `docs/reports/release/release-readiness.md` |

**全て「未検証」を「検証済み」と書き換えることなく報告済み**（§13の
明示的ルールを遵守 — 実データ/実機検証が必要な項目は今回もツール実装・
制約明記までに留め、検証済みとは記載していない）。

## uncompleted（このセッションでは対応不可、ユーザー操作待ち）

`docs/reports/release/release-readiness.md`の「未解決事項一覧」参照。
要約すると以下4点：

1. GitHubリポジトリへのpush権限（`github-push.md`）
2. DartsSupportApp統合方針の4択判断（`darts-support-schema-diff.md`）
3. BLE実機検証の実施（`ble-real-device.md`, `scripts/ble_investigate.py`）
4. COUNT-UP実データ（10〜30ゲーム）の提供（`accuracy-validation.md`）

これらはいずれも指示書§14の停止条件（実機操作/外部仕様不明/schema変更の
ユーザー判断）に該当するため、このセッションから先へは進められない。

## current branch

`codex/release-resolution-db-persistence`
（`codex/phase-10-support-contract`から分岐。まだ`main`にマージしておらず、
GitHubへもpushできていない — §2参照）

## latest commit

このファイルの更新自体が最新コミットに含まれる。`git log -1 --oneline`
で確認すること（release-readiness.md追加時点の直前コミットは
`7a99c61 BLE real-device verification: user-runnable investigation
tooling (§3)`）。

## test results

`python -m pytest -q` → 327 passed, 0 failed（このファイル最終更新時点）。
セクション対応開始前（Phase 0〜10完了時点）の267件から60件を新規追加、
リグレッション0件。

## blocker

真の停止条件（§14）には該当していない（作業自体は完了）。ただし
上記「uncompleted」の4項目は、このセッションの権限・環境では対応不可な
ユーザー操作待ち事項として確定している。

## required user action

1. （優先度: 高）GitHubのDartsAnalyticsAppリポジトリへのpush権限を
   このセッション/Coworkの許可リポジトリ一覧に追加してほしい。
2. （優先度: 中）DartsSupportAppとの連携方針を4択から選んでほしい。
3. （優先度: 中、時間のある時でよい）`scripts/ble_investigate.py`を
   実行してDARTSLIVE HOMEのBLE実機検証を行ってほしい
   （`docs/reports/ble/HOWTO_ja.md`参照）。
4. （優先度: 中、時間のある時でよい）実際のCOUNT-UPプレイデータ
   （10〜30ゲーム分）を提供してほしい。

## next command/action

指示書§1〜§13の対応は完了。次に行うべきことは、上記4つのユーザー操作を
待つこと。ユーザーからの入力（GitHubリポジトリ認可の変更、統合方針の
選択、BLEログファイル、実データ）のいずれかが届いた時点で、そのセクション
から作業を再開する：

- GitHubリポジトリ認可が下りた場合 → `git push origin <各branch>`を
  11+1本のbranchに対して実行し、`main`へのマージを検討する。
- DartsSupportApp統合方針が決まった場合 → 選ばれた方針に沿って
  `src/dartsanalytics/contract/support_app.py`を修正、またはDartsSupportApp
  側への変更を実施する（破壊的変更には改めて確認を挟む）。
- BLEログが届いた場合 → 生データを解析し、
  `UnimplementedBleDartsLiveHomeAdapter`の実装に着手する。
- 実データが届いた場合 → `dartsanalytics.validation.accuracy
  .compare_sessions()`を実行し、`accuracy-validation.md`を実測値で更新
  する。

作業再開コマンド:
```
cd /home/claude/work/shijimiworks-DartsAnalyticsApp
git status --short && git log --oneline -5
python -m pytest -q
```
