# Claude / Codex 実装指示書 v1.0

## 0. 作業場所

```text
C:\制作データ\20_DartsAnalyticsApp
```

このフォルダをDartsAnalyticsAppの正式作業ディレクトリとする。

## 1. 最初に読む資料

必ず以下を最初から最後まで読むこと。

```text
docs/specs/DartsAnalyticsApp_詳細設計書_v1.0.md
docs/specs/DartsAnalyticsApp_スマホ動画撮影手順_v1.0.md
```

さらに、既存プロジェクトの設計思想を確認するため、利用可能なら以下も参照する。

```text
C:\制作データ\10_App\DartsApp
C:\制作データ\10_App\DartsSupportApp
```

ただし既存アプリのコードを無断で変更しない。

## 2. 最重要ルール

- 最小変更
- 無関係なリファクタリング禁止
- 新規依存関係は必要性を確認
- 既存テストを壊さない
- 解析不能なものを無理に判定しない
- AIに原因を断定させない
- すべての推定値にconfidenceを持たせる
- 動画原本を上書きしない
- 解析アルゴリズムにバージョンを付ける
- SQLite中心のローカルファースト
- 外部API従量課金を必須にしない

## 3. 作業方式

一度に全機能を実装しない。以下のPhaseを順番に実行する。

### Phase 0：Repository Foundation

実施：
- Git初期化
- README
- AGENTS.md
- docs構造
- テスト基盤
- SQLite基盤
- 共通型

完了条件：起動、テスト、DB migrationが成功。

### Phase 1：COUNT-UP Data Core

実施：
- Account/Player
- COUNT-UP session
- 8 rounds
- 24 throws
- throw record
- raw event
- session result
- JSON export

DARTSLIVE HOMEはまだ必須にしない。まずモックデータで完全に再現できる状態を作る。

### Phase 2：DARTSLIVE HOME Adapter Investigation

最初に調査だけを行う。

確認事項：
- OSからDARTSLIVE HOMEがどう認識されるか
- BLE/GATTサービス
- notify characteristic
- 1投で受信されるデータ
- CHANGEイベント
- 接続/切断
- 複数台接続の挙動

公式公開APIが確認できない場合は、アダプタを抽象化したまま実装し、実機検証可能な範囲だけを採用する。

DARTSLIVE HOMEの非公式プロトコルを利用する場合は、コード内に「非公式・実機検証済み」の注記を入れ、依存部分を1モジュールに閉じ込める。

### Phase 3：Board Coordinate Analysis

- ボード画像入力
- キャリブレーション
- 中心推定
- 円/リング推定
- 座標正規化
- グルーピング統計
- ヒートマップ

まず静止画像でテストする。リアルタイム化は後回し。

### Phase 4：Video Intake & Shooting Guide

- 4角度の撮影ガイド
- 動画インポート
- メタデータ保存
- 品質判定
- NG理由表示
- 再撮影要求

撮影ガイドは必ず次の4種類を持つ。

1. 正面・全身
2. 利き腕側面・全身
3. 反対側面・全身
4. 遠景・投擲位置からボードまで全体

4本で不足した場合は追加動画を要求できる設計にする。

### Phase 5：Pose Analysis

まず姿勢推定のみ。

特徴量：
- head
- shoulder
- elbow
- wrist
- hip
- knee
- ankle
- body tilt
- arm angles
- release/follow-through候補

ダーツ自体の認識は別モジュール。

### Phase 6：Grip Analysis

左右写真から、
- 指位置
- 指の角度
- バレル軸
- 手首角度
を推定する。

2Dから接触圧などを断定しない。

### Phase 7：Integrated Analysis

投擲結果とフォーム特徴量を統合する。

出力：
- dispersion
- directional bias
- frequent segments
- late-round degradation
- form correlations
- candidate causes

### Phase 8：Experiment System

改善案を1つずつ試せるようにする。

```text
Baseline
→ Intervention
→ Test
→ Comparison
→ Decision
```

Decisionは「継続」「戻す」「再試験」などの事実ベースの結果にする。

### Phase 9：Local AI Advisor

AIは最終解釈のみ担当する。

入力：特徴量、統計、動画から抽出した特徴、過去実験。

出力：
- 観測
- 仮説
- 推奨テスト
- 注意事項
- confidence

「絶対にこれが原因」といった断定は禁止。

### Phase 10：DartsSupportApp Contract

既存の共通契約方針に合わせる。

最低限：
- account_id
- player_id
- practice_menu_id
- game_session_id
- record_id
- timestamp
- game_type
- practice_type
- BULL/DOUBLE/TRIPLE
- throw coordinates
- sync state
- analysis version

## 4. 動画解析の実装ルール

4本の動画は同じ投球を同期しているとは仮定しない。

各動画から代表フレーム/代表投球を抽出し、セッション単位の特徴量として統合する。

完全に同一投を追跡できた場合のみthrow_group_idを付与する。

## 5. テスト要求

各Phaseで最低限：

- unit test
- integration test
- migration test
- malformed input test
- video quality negative test
- reproducibility test

分析値については固定fixtureを作る。

例：
- 全投が中心
- 全投が上側
- 全投が下側
- 左右に均等分布
- 1本だけ外れ値
- 24投中数投欠損

## 6. UI/UX

最初の画面から「何を撮影すればよいか」が分かるようにする。

動画撮影画面には必ず、
- カメラ位置の図
- 映す範囲
- OK条件
- NG条件
- 再撮影ボタン
を置く。

## 7. Git

各Phaseごとに専用branchを作る。

例：

```text
codex/phase-0-foundation
codex/phase-1-count-up-data
codex/phase-2-dartslive-adapter
codex/phase-3-board-analysis
codex/phase-4-video-intake
codex/phase-5-pose-analysis
codex/phase-6-grip-analysis
codex/phase-7-integrated-analysis
codex/phase-8-experiments
codex/phase-9-local-ai
codex/phase-10-support-contract
```

完了後mainへ直接mergeしない。Draft PRを作り、
- 変更内容
- テスト結果
- 未解決事項
- 実機確認が必要な事項
を報告する。

## 8. Codex/Claudeへの実行開始指示

以下をそのまま実行開始メッセージとして使用する。

```text
C:\制作データ\20_DartsAnalyticsApp で作業してください。

最初に以下を最初から最後まで読んでください。

1. docs/specs/DartsAnalyticsApp_詳細設計書_v1.0.md
2. docs/specs/DartsAnalyticsApp_スマホ動画撮影手順_v1.0.md
3. docs/codex/CODEX_DARTS_ANALYTICS_IMPLEMENTATION_v1.0.md

今回はPhase 0だけを実行してください。

最初にリポジトリの現状を調査し、既存ファイルを確認してください。
その後、Phase 0の範囲だけを実装してください。

最小変更、無関係なリファクタリング禁止、新規依存は必要最小限としてください。

完了後、mainへマージせず、専用branchとDraft PRを作成してください。

報告には必ず以下を含めてください。
- 実施内容
- 変更ファイル
- テスト実行結果
- DB migration結果
- 起動確認結果
- 未実装項目
- 次Phaseで必要な確認事項
```

## 9. Phase 2で特に注意

DARTSLIVE HOMEの公式資料でBluetooth連携自体は確認できるが、第三者向け公開APIの存在は本設計では前提にしない。したがってPhase 2は「実装」より「実機プロトコル確認」を先にする。

## 10. 完成イメージ

最終的には、

```text
DARTSLIVE HOME
   ↓
COUNT-UP 8R / 24投
   ↓
投擲データ
   ↓
ボード座標 + グルーピング
   ↓
4方向スマホ動画
   ↓
姿勢・リリース・フォーム特徴量
   ↓
グリップ写真 + 用具情報
   ↓
統合解析
   ↓
原因候補
   ↓
1つの改善案
   ↓
30～60投の再測定
   ↓
改善効果の比較
```

という「測定→仮説→実験→検証」のループを完成させる。
