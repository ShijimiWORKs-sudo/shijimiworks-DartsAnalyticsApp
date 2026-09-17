# Phase 10: DartsSupportApp Contract — Implementation Notes

## 実装した範囲

`dartsanalytics.contract.support_app`。docs §Phase10の最小フィールド
リストに対応する`SupportAppThrowRecord`（1投＝1レコード）と、
`PracticeSession`＋`Throw`から構築する関数群、JSON export/write関数。

フィールド対応：

| docs §Phase10 | 実装 | 備考 |
|---|---|---|
| account_id | `session.account_id`そのまま | |
| player_id | `session.player_id`そのまま | |
| practice_menu_id | 呼び出し側が渡すオプション値 | このアプリ内部には「練習メニュー」概念が無い |
| game_session_id | `session.session_id` | 内部モデルでは`session_id`のまま（リネームは契約層のみ） |
| record_id | `throw.throw_id` | 同上（内部は`throw_id`のまま） |
| timestamp | `throw.created_at` | |
| game_type | `session.game_type.value` | |
| practice_type | `session.practice_type` | |
| BULL/DOUBLE/TRIPLE | `throw.ring.value` | 実際は`Ring`enum全種（SINGLE/DBULL/MISSも含む上位互換）をそのまま通す |
| throw coordinates | `normalized_x`/`normalized_y`/`distance_from_bull` | 欠損時は`None`（存在すれば`distance_from_bull`から算出、無ければ計算） |
| sync state | `SyncState`enum（新規、`common/enums.py`に追加） | デフォルト`pending` |
| analysis version | 呼び出し側が渡すオプション値 | デフォルト`raw_measurement_v1`（DARTSLIVE HOME直接測定にはアルゴリズムバージョンが無いため） |

## 【重要】実際のDartsSupportAppとの未検証事項

このセッションは最初に`DartsApp`/`DartsSupportApp`フォルダへの参照アクセス
をリクエストしたが（docs §1「既存プロジェクトの設計思想を確認するため」）、
応答がなくタイムアウトした（`status.md`未解決事項3参照）。そのため、
**このモジュールはdocs §Phase10に書かれた最小フィールドリストをそのまま
実装したのみであり、実際のDartsSupportAppのJSONスキーマ（フィールド名・
型・ネスト構造・転送方式）との整合性は一切確認できていない**。

実際に連携する際は、DartsSupportApp側の実装（またはその設計者）に以下を
確認する必要がある：
- フィールド名の正確な表記・大文字小文字規則
- `practice_menu_id`の発行元・形式
- ネストの有無（フラットな配列か、セッション単位でグループ化するか）
- 転送方式（ファイル/HTTP/その他）とバッチサイズ
- `sync_state`の値がDartsSupportApp側の期待する語彙と一致するか

## 実装しなかった範囲

- 実際のDartsSupportAppへの送信・同期処理（ファイル書き出しまでで、
  ネットワーク送信・ファイル監視等は未実装。非機能要件§25「外部API従量
  課金を必須にしない」もあり、まず何を送るかのcontractだけを固める
  というdocsのPhase分割方針に沿った意図的なスコープ）。
- セッション単位の集計情報（IntegratedAnalysisReport, AdvisorOutput等）
  のcontractへの統合：docs §Phase10のフィールドリストは1投単位の項目
  のみを列挙しており、統合レポートの連携仕様は明記されていないため、
  推測で拡張しなかった。

## テスト

`tests/test_support_app_contract.py`（8件）。全267件パス。
`scripts/bootstrap_check.py`成功（スキーマ変更なし）。

## 依存関係の追加

なし。

---

# 全Phase完了時点でのサマリ（Phase 0〜10）

docs/codex/CODEX_DARTS_ANALYTICS_IMPLEMENTATION_v1.0.md記載の全11 Phase
（0〜10）の実装が完了した。`docs/codex/reports/status.md`に累積の未解決
事項・技術的制約を一覧化している。特に以下はリリース前に必ず対応が必要：

1. GitHub pushの権限解消（このセッションでは実施不可）。
2. Phase 2（DARTSLIVE HOME BLEプロトコル）の実機検証。
3. Phase 5（姿勢推定）・Phase 6（グリップ解析）の実データでの精度検証。
4. Phase 7（form correlations）・Phase 8（Decisionマージン）の実データ
   でのキャリブレーション。
5. Phase 10のDartsSupportApp実スキーマとの突合。
6. DB永続化（リポジトリ/DAO層）はどのPhaseでも未着手 — 現状はすべて
   メモリ上のdataclass/関数のみで、実際にSQLiteへ書き込むコードが無い。
