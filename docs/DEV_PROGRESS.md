# DEV_PROGRESS.md（指示書§15）

最終更新: 2026-09-17

このファイルは、`CLAUDE_RELEASE_UNRESOLVED_RESOLUTION_v1.0.md`の§15
「フェーズ運用」に基づき、コンテキスト/セッション上の理由で作業を
中断する必要が生じた場合に備えて継続的に更新する。**現時点では停止して
いない**（§14の停止条件に該当する事態は発生していない）— 以下は
「今どこまで進んでいるか」のスナップショート。

## completed（今回の指示書対応で完了した項目）

- §1 監査: 完了（git状態・DB/repository不在・BLEツール不在等を確認、
  以降のセクションの実装作業そのものに反映）
- §2 GitHub push: 完了 → `docs/reports/release/github-push.md`
  （結論: このセッションのリポジトリ認可ポリシーによりpush不可、
  ユーザー操作待ち）
- §11 DartsSupportApp契約突合: 完了 → `docs/reports/release/darts-support-schema-diff.md`
  （結論: 両アプリのデータモデルが根本的に異なる、4択をユーザーに提示、
  ユーザー判断待ち）
- §10 DB永続化（Repository pattern）: 完了 → `docs/reports/release/db-persistence.md`
  - `src/dartsanalytics/db/repositories/`（interfaces.py, sqlite_repositories.py）
  - `src/dartsanalytics/db/unit_of_work.py`
  - `src/dartsanalytics/application/session_recording_service.py`
  - restart/rollback/duplicate/corrupt-dataの証拠テスト含む
- §9 個人学習ログ: 完了（db-persistence.mdに追記する形で報告）
  - `src/dartsanalytics/db/schema/0002_learning_log.sql`
  - `src/dartsanalytics/learning_log/`（models.py, analysis.py）
  - SessionRecordingServiceにrecord_learning_log_entry等を追加
- §5 グルーピング解析（BULL率とグルーピング品質の分離）: 完了 →
  `docs/reports/release/grouping-validation.md`
  - `GroupingStats.cep_radius`フィールド追加
  - 分離を保証する新規テスト2件

## uncompleted（未着手・作業中）

- §3 BLE実機検証: 未着手。**ユーザーの手元操作が必須**
  （Windows Bluetooth設定でのペアリング等）。このセッションには
  `device_bash`（ユーザーPC上のシェル）が無いため、代行不可。
  ユーザーへの依頼テンプレートを`docs/reports/ble/`配下に用意し、
  `docs/reports/release/ble-real-device.md`へ結果をまとめる予定だが、
  実測データが無いと着手できない。
- §4 COUNT-UP実データ精度検証: 未着手。**実データ（10〜30ゲーム分の
  DARTSLIVE HOMEエクスポート）がユーザーから提供され次第**着手可能。
  比較ツール自体（exact match/score error/coordinate error/false
  positive-negative/number confusion/BULL近傍誤差/round error）は
  実データが無くても設計・実装は可能なので、次のセッションではまず
  ツール実装から着手する（実データ無しでも合成データでツール自体の
  正しさは検証できる）。
- §6 動画解析検証報告: 未着手。`docs/reports/release/video-validation.md`
  を作成する必要がある。Phase 4/5/6（video intake, pose analysis, grip
  analysis）は実装済みなので、既存コードの監査＋ドキュメント化が中心
  になる見込み（§5のgrouping-validation.mdと同じパターン）。
- §7 キャリブレーション検証報告: 未着手。
  `docs/reports/release/calibration-validation.md`。Phase 3の
  `board/calibration.py`は静止画・単純な閾値ベースの実装のみで、
  homography/lens distortion/camera parametersは未実装であることを
  明記する必要がある。
- §8 AI助言パイプライン報告: 未着手。Phase 7(causes)/Phase 9(advisor)の
  既存実装を、指示書§8が要求する
  `evidence/confidence/inference flag/expected effect/recommended
  change/test protocol/before-after`の型に対応付けてドキュメント化する。
  専用の成果物パスは指示書に明記されていない（本文中に言及があるのみ）
  ため、`docs/reports/release/ai-advisor-pipeline.md`として作成する予定。
- §12 回帰テスト拡充: 未着手。`docs/reports/release/regression-test.md`。
  現在296件のテストがUnit中心。Integration（application service ↔
  DB、video pipeline全体）、Recovery（中断された解析、不正な動画、
  BLE切断、DB障害）のカテゴリでのテスト拡充が必要。
- §13 リリース判定報告: 未着手（他の全項目の結果に依存するため最後に
  作成）。`docs/reports/release/release-readiness.md`。
- §15 本ファイルの継続更新: 進行中（このコミット時点の状態を反映）。

## current branch

`codex/release-resolution-db-persistence`
（`codex/phase-10-support-contract`から分岐。まだ`main`にマージしておらず、
GitHubへもpushできていない — §2参照）

## latest commit

```
6824d7f Grouping analysis: explicit CEP field + accuracy/precision separation tests (§5)
```
（このファイル自体は次のコミットに含まれるため、上記は「このファイルを
書いた時点での1つ前」のコミット。最新は`git log -1 --oneline`で確認）

## test results

`python -m pytest -q` → 296 passed, 0 failed（このファイル作成時点）。
既存267件（Phase 0〜10完了時点）から、リポジトリ層17件＋学習学習ログ9件＋
グルーピング3件を追加。リグレッションなし。

## blocker

現時点で真の停止条件（§14）には該当していない。ただし以下2項目は
**ユーザー操作待ち**として報告済みで、これらのセクション自体はユーザー
入力なしには着手できない：

1. §2 GitHub push: リポジトリ認可の変更（Claude/Coworkセッション側の
   設定）が必要。詳細は`docs/reports/release/github-push.md`。
2. §11 DartsSupportApp契約: 4つの統合方針のどれを取るかユーザー判断が
   必要。詳細は`docs/reports/release/darts-support-schema-diff.md`。
3. §3 BLE実機検証: ユーザーの手元でのBluetooth操作が必要（このセッション
   にはユーザーPC上のシェルアクセスが無い）。
4. §4 COUNT-UP実データ精度検証: 実データ（10〜30ゲーム）の提供が必要。

これら4項目以外は、指示書§14の「それ以外は、可能な範囲で継続して実装・
テスト・証拠化する」に従い、ユーザーへの質問なしで継続作業中。

## required user action

- （優先度: 高、ブロッキング）GitHubのDartsAnalyticsAppリポジトリへの
  push権限をこのセッション/Coworkの許可リポジトリ一覧に追加してほしい
  （`docs/reports/release/github-push.md`参照）。
- （優先度: 中）DartsSupportAppとの連携方針を4択から選んでほしい
  （`docs/reports/release/darts-support-schema-diff.md`参照）。
- （優先度: 中、時間のある時でよい）DARTSLIVE HOME実機でのBLEペアリング
  検証（Windows Bluetooth設定）。
- （優先度: 中、時間のある時でよい）実際のCOUNT-UPプレイデータ
  （DARTSLIVE HOME側の記録、10〜30ゲーム分）の提供。

## next command/action

次のセッション（またはこのセッションの継続）でまず行うこと：
1. §6 動画解析検証報告（`docs/reports/release/video-validation.md`）—
   既存実装の監査からブロッキングなしで着手可能。
2. §7 キャリブレーション検証報告（`docs/reports/release/calibration-validation.md`）
   — 同上。
3. §8 AI助言パイプライン報告（`docs/reports/release/ai-advisor-pipeline.md`）
   — 同上。
4. §4の比較ツール自体の実装（実データが来る前に、合成データでツールの
   正しさだけ先に検証しておく）。
5. §12 回帰テスト拡充。
6. §13 リリース判定報告（最後）。

作業再開コマンド:
```
cd /home/claude/work/shijimiworks-DartsAnalyticsApp
git status --short && git log --oneline -5
python -m pytest -q
```
