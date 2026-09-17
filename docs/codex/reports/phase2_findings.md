# Phase 2: DARTSLIVE HOME Adapter — Investigation Findings

Status: **調査完了・実装は抽象化のみ（実機検証ができないため停止）**

## 実施した調査

- Web検索：「DARTSLIVE HOME BLE GATT protocol reverse engineering unofficial
  API COUNT-UP」— DARTSLIVE HOME固有のBLEプロトコル解析情報は見つからず。
- DARTSLIVE HOME公式製品ページ（dartslive.com）を確認 — Bluetooth接続自体には
  言及なし。公開API/SDK/サードパーティ連携についての記載も確認できず。
- 公式マニュアルPDF（docs §28のURL）はネットワークから直接内容取得できる範囲
  では、一般利用者向けの操作説明であり、BLE GATTサービス/characteristic UUID
  等のプロトコル仕様は含まれていない。

## 確認できなかった事項（設計書 §Phase2 の確認事項）

- OSからDARTSLIVE HOMEがどう認識されるか
- BLE/GATTサービスのUUID構成
- notify characteristicの構造
- 1投で受信される生データのバイト列/フォーマット
- CHANGEイベントの発生条件
- 接続/切断時の挙動
- 複数台接続時の挙動

これらはすべて **実機とのBLE通信を実際に観測しないと確認できない**。

## なぜここで止めるか

`docs/codex/CODEX_DARTS_ANALYTICS_IMPLEMENTATION_v1.0.md` §9 および AGENTS.md
の停止条件に該当：「DARTSLIVE HOMEとの通信仕様など、外部仕様が不明で推測実装が
危険な場合」。加えて、このセッションには以下の環境制限がある。

- クラウドのサンドボックス環境にはBluetoothハードウェアが存在しない。
- ユーザーのPC（m720s-creative）にはこのセッションからシェルを実行する手段
  （device_bash相当）が提供されておらず、実機でBLEスキャン/notifyを観測する
  スクリプトをこちらから実行できない。

これも環境制限による継続不能条件（「環境制限、権限...によって継続できない
場合」）に該当するため、推測でのプロトコル実装は行わない。

## 今回実装した範囲（抽象化のみ）

`src/dartsanalytics/adapters/dartslive_home.py`:

- `IDartsLiveHomeAdapter`（ABC）: `connect()` / `disconnect()` /
  `is_connected` / `raw_events()` / `to_throw()` を定義。実装は1モジュールに
  隔離（設計原則「依存部分を1モジュールに閉じ込める」）。
- `MockDartsLiveHomeAdapter`: `IDartsLiveHomeAdapter` を実装し、
  `MockCountUpGenerator` を使って擬似的な投擲イベントを流す。Phase 1の
  モックデータと同じ経路（`DetectionSource.MOCK`）で、結合テスト・UI開発に
  使用できる。
- `UnimplementedBleDartsLiveHomeAdapter`: 実BLE実装のプレースホルダー。
  `connect()` は `NotImplementedError` を送出し、必要な実機検証手順を
  docstringに明記する。**推測によるプロトコル実装は一切含まない。**

## 次のPhaseへの影響

Phase 1（COUNT-UPデータコア）は本Phaseの結果に依存しないため、後続Phase
（3以降）の実装は継続する。DARTSLIVE HOME実機との接続実装は、以下のいずれかが
揃った時点で再開する。

1. ユーザーの実機（DARTSLIVE HOME + Windows PC）でBLEスキャン/notifyを
   観測できる環境（例：Windows上でのPythonスクリプト実行、nRF Connect等の
   BLEインスペクタアプリ、またはこのセッションからそのPC上でコマンドを
   実行できる手段）。
2. 観測結果（サービスUUID、characteristic、1投分のペイロード構造）の共有。

それまでは `MockDartsLiveHomeAdapter` を使って上位層（セッション管理、
解析、UI）の開発・テストを進める。
