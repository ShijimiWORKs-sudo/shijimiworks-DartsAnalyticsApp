# DartsAnalyticsApp — 進捗ステータス

最終更新: 2026-09-17（このセッションでの作業分、**Phase 0〜10 全完了**）

## 完了したPhase

| Phase | 状態 | branch |
|---|---|---|
| 0: Repository Foundation | 完了（migration atomicity修正込み） | `codex/phase-0-foundation` |
| 1: COUNT-UP Data Core（モック） | 完了 | `codex/phase-1-count-up-data` |
| 2: DARTSLIVE HOME Adapter | 調査完了・抽象化のみ実装（実機検証待ちで意図的に停止） | `codex/phase-2-dartslive-adapter` |
| 3: Board Coordinate Analysis | 完了（静止画像ベース） | `codex/phase-3-board-analysis` |
| 4: Video Intake & Shooting Guide | 完了 | `codex/phase-4-video-intake` |
| 5: Pose Analysis | 完了（実写真未検証、下記参照） | `codex/phase-5-pose-analysis` |
| 6: Grip Analysis | 完了（実写真未検証、下記参照） | `codex/phase-6-grip-analysis` |
| 7: Integrated Analysis | 完了（一部カテゴリ意図的未実装、下記参照） | `codex/phase-7-integrated-analysis` |
| 8: Experiment System | 完了（DB永続化は未実装、下記参照） | `codex/phase-8-experiments` |
| 9: Local AI Advisor | 完了（外部LLM未使用・テンプレートベース、下記参照） | `codex/phase-9-local-ai` |
| 10: DartsSupportApp Contract | 完了（実スキーマ未検証、下記参照） | `codex/phase-10-support-contract` |

docs/codex/CODEX_DARTS_ANALYTICS_IMPLEMENTATION_v1.0.mdに定義された
全11 Phase（0〜10）の実装が完了した。11本のbranchはスタック構成
（0→1→2→…→10の順に積み重ね）。まだ`main`へのマージもGitHubへのpushも
行っていない（下記「未解決事項」参照）。全ブランチで`pytest` 267件パス、
`scripts/bootstrap_check.py` 成功を確認済み（最新branch
`codex/phase-10-support-contract` 時点）。

## 未着手のPhase

なし（全Phase完了）。ただし下記「未解決事項」に記載の検証・統合作業は
リリース前に必須。

## 未解決事項・ユーザー判断が必要な事項

1. **GitHub pushが権限エラーで失敗**：
   `access denied by the git proxy: ... is not in this session's authorized
   repository set`。このリポジトリをセッションの認可済みソースに追加する
   操作がユーザー側で必要（フォルダ連携と同様の仕組みと思われる）。追加後、
   再度pushとDraft PR作成を行う。
2. **実機確認が必要な事項（Phase 2）**：DARTSLIVE HOMEのBLE/GATTプロトコル。
   `docs/codex/reports/phase2_findings.md` 参照。ユーザーの実機で
   BLEインスペクタ（nRF Connect等）を使うか、このセッションからユーザーPCで
   コマンドを実行できる手段（現状は未提供）が必要。
3. **既存アプリ（DartsApp/DartsSupportApp）フォルダへの参照アクセス**：
   最初にリクエストしたが応答がなくタイムアウト。設計思想の細部確認は
   ペンディング（実装は指示書記載の設計書のみで進行、大きな矛盾なし）。
4. **calibration.pyの性能**：連結成分ラベリングが純Python BFS実装（scipy等
   未使用）。大きな画像は400px程度にダウンサンプルしてから処理しているが、
   将来的に処理速度が問題になる場合はscipy.ndimage.labelの採用を検討。
5. **calibrationの確信度**：単純な閾値+真円度のみで判定しており、「本当に
   ダーツボードか」の判定はしていない（丸い物体全般を高信頼と誤判定しうる）。
   実際のボード写真でチューニングが必要。
6. **【重要・リリース前必須】Phase 5姿勢推定・Phase 6グリップ解析ともに
   実際の人物映像・グリップ写真での検証が未実施**：このセッションには
   実際にダーツを投げる人物の映像、グリップを写した写真が一切なく、
   「人物/手を検出しない」ことの確認（誤検出なし）に留まる。検出精度・
   ランドマーク位置の妥当性・confidenceの較正は未検証。実際のデータでの
   テストがリリース前に必須（`docs/codex/reports/phase5_notes.md`,
   `phase6_notes.md` 参照）。
7. **HandLandmarkerの信頼度モデルがPoseLandmarkerより粗い**：ランドマーク
   ごとのvisibilityが取得できず、手全体のhandedness分類スコアを一律適用
   している（`phase6_notes.md` 参照）。
8. **Phase 7のform_correlationsも実データ未検証**：計算ロジック自体は
   合成データでテスト済みだが、実際のフォーム特徴量×着弾統計のペアリング
   データが存在しないため、意味のある相関が実際に出るかは未検証
   （`phase7_notes.md` 参照）。
9. **Phase 7で意図的に未実装の原因カテゴリ**：リリース位置・足位置・
   狙い線・用具・手首の動き（Phase 8以降または追加の特徴量抽出が必要。
   `phase7_notes.md` 参照）。
10. **Phase 8のDecisionマージン値は文書化された規約であり、測定に基づく
    閾値ではない**：実データでのキャリブレーションが必要
    （`phase8_notes.md` 参照）。
11. **DB永続化（リポジトリ/DAO層）が全Phaseを通じて未実装**：Phase 0の
    SQLiteスキーマは存在するが、`throws`/`experiments`等への実際の
    INSERT/SELECTコードはまだ無い。すべてのPhaseはメモリ上の
    dataclassに対する計算ロジックのみ提供している（意図的な段階的
    スコープ縮小 — DB結線は将来のPhase、またはこのままの範囲で
    ユーザー判断が必要）。
12. **Phase 9のAIアドバイザーは外部LLM/AI APIを一切呼ばない**：決定的な
    テンプレートベース実装（`phase9_notes.md`参照）。自然な文章生成や
    より柔軟な仮説生成が必要な場合、外部/ローカルLLMの追加は将来の
    ユーザー判断事項。
13. **【重要】Phase 10のDartsSupportApp契約は実スキーマ未検証**：
    フォルダアクセスが得られなかったため、docs §Phase10のフィールド
    リストのみに基づく実装。実際のDartsSupportApp実装との突合が
    連携前に必須（`phase10_notes.md`参照）。

## 依存関係

Phase 0/1: 追加依存なし。Phase 3で `numpy`, `pillow`（画像I/Oとグルーピング
統計）。Phase 5で `mediapipe`（姿勢推定、モデルファイル別途ダウンロード）。
Phase 6は新規pip依存なし（Phase 5のmediapipeを再利用、HandLandmarker用
モデルファイルのみ別途ダウンロード）。ffmpeg/ffprobeはPhase 4からの
外部バイナリ依存（pip外）。

## 次にやること

- 上記「未解決事項1」が解消され次第、11branch分をpushしてDraft PRを作成
  （各PRに変更内容・テスト結果・未解決事項・実機確認が必要な事項を記載）。
- 「未解決事項6・8」（実データでの検証）はユーザー側での実機・実データ提供が
  必要。それまでは測定値ではなく推定値として明示され続ける（設計原則通り）。
- 全Phase実装は完了。残る作業は実データ・実機での検証と、DB永続化層の要否
  判断（ユーザー側での優先度判断が必要）。
