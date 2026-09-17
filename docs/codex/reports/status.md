# DartsAnalyticsApp — 進捗ステータス

最終更新: 2026-09-17（このセッションでの作業分）

## 完了したPhase

| Phase | 状態 | branch |
|---|---|---|
| 0: Repository Foundation | 完了（97テスト構成の基盤、後日migration atomicity修正込み） | `codex/phase-0-foundation` |
| 1: COUNT-UP Data Core（モック） | 完了 | `codex/phase-1-count-up-data` |
| 2: DARTSLIVE HOME Adapter | 調査完了・抽象化のみ実装（実機検証待ちで意図的に停止） | `codex/phase-2-dartslive-adapter` |
| 3: Board Coordinate Analysis | 完了（静止画像ベース） | `codex/phase-3-board-analysis` |

4本のbranchはスタック構成（0→1→2→3の順に積み重ね）。まだ `main` へのマージも
GitHubへのpushも行っていない（下記「未解決事項」参照）。全ブランチで
`pytest` 97件パス、`scripts/bootstrap_check.py` 成功を確認済み。

## 未着手のPhase

4（動画取り込み・撮影ガイド）、5（姿勢推定）、6（グリップ解析）、7（統合解析）、
8（改善実験）、9（ローカルAIアドバイザー）、10（DartsSupportApp連携）。

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
   Phase 4以降、実際のボード写真でチューニングが必要。

## 依存関係

Phase 0/1: 追加依存なし。Phase 3で `numpy`, `pillow` を追加（画像I/Oと
グルーピング統計のため。理由は `pyproject.toml` のコメント参照）。

## 次にやること

- 上記「未解決事項1」が解消され次第、4branch分をpushしてDraft PRを作成。
- ユーザーの指示があり次第、Phase 4（動画取り込み・撮影ガイド）に着手。
