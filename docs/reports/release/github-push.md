# GitHub Push — 検証結果

最終更新: 2026-09-17

## 実施内容

1. `git remote -v` → `origin` は
   `https://github.com/ShijimiWORKs-sudo/shijimiworks-DartsAnalyticsApp.git`
   （fetch/push とも）に設定済み。
2. `git ls-remote origin` → エラー無し、出力ゼロ件（リモート側リポジトリが
   空、またはこのプロキシ経路では読み取り一覧も取得できない状態）。
3. **安全な検証方法**：`main`へは絶対にpushせず、既存の作業branch
   `codex/phase-0-foundation`をそのまま同名でリモートにpushするコマンドで
   検証（新規作成・破壊的操作なし）。

```
git push origin codex/phase-0-foundation:codex/phase-0-foundation
```

## 結果

```
remote: access denied by the git proxy: ShijimiWORKs-sudo/shijimiworks-DartsAnalyticsApp
is not in this session's authorized repository set, so the proxy will not inject
a credential for it. To fix, add the repository to the session's sources.
fatal: unable to access '...': The requested URL returned error: 403
```

## 原因の分類

指示書§2の5分類のうち、**「2. repository permission」に該当するが、
GitHub側の権限ではなく、このClaudeセッション自体のエグレス（プロキシ）
ポリシーによるもの**：

- credential（認証情報の欠落・誤り）: 該当しない（そもそも資格情報を
  注入する前段階でブロックされている）。
- **repository permission**: 該当。ただしGitHubリポジトリのアクセス権限
  ではなく、「このリポジトリがこのセッションの認可済みソース集合に
  含まれていない」というセッション側のポリシー。
- branch protection: 未評価（プロキシ段階でブロックされるため、GitHub側
  のbranch protectionルールに到達すらしていない）。
- terminal sandbox / permission: 該当しない（コマンド自体は正常に実行され、
  明確なエラーメッセージが返っている）。
- network: 該当しない（プロキシへの接続自体は成功しており、プロキシが
  明示的に拒否している）。

`/root/.ccr/README.md`（このセッションのエグレスプロキシの説明書）にも
「403/407はエグレスポリシーによる拒否であり、再試行や回避を行わず報告する
こと」と明記されている。したがって、このセッションから状況を変える手段は
無い。

## 必要なユーザー操作

このセッション（Claude Cowork/Codexタスク）の設定で、
`ShijimiWORKs-sudo/shijimiworks-DartsAnalyticsApp` を「セッションの認可済み
リポジトリ（sources）」に追加する必要がある。具体的な設定画面名はこの
セッションからは確認できないため、Claudeのタスク設定・リポジトリ連携設定
画面を確認してほしい。

追加後、以下を再実行すれば全11 branchをpushできる見込み：

```
git push origin codex/phase-0-foundation:codex/phase-0-foundation
git push origin codex/phase-1-count-up-data:codex/phase-1-count-up-data
git push origin codex/phase-2-dartslive-adapter:codex/phase-2-dartslive-adapter
git push origin codex/phase-3-board-analysis:codex/phase-3-board-analysis
git push origin codex/phase-4-video-intake:codex/phase-4-video-intake
git push origin codex/phase-5-pose-analysis:codex/phase-5-pose-analysis
git push origin codex/phase-6-grip-analysis:codex/phase-6-grip-analysis
git push origin codex/phase-7-integrated-analysis:codex/phase-7-integrated-analysis
git push origin codex/phase-8-experiments:codex/phase-8-experiments
git push origin codex/phase-9-local-ai:codex/phase-9-local-ai
git push origin codex/phase-10-support-contract:codex/phase-10-support-contract
```

（`main`へは直接pushしない。各branchについて個別にDraft PRを作成する。）

## 禁止事項の遵守

このセッションはPAT・パスワード・秘密鍵のいずれも収集・ログ出力・
ファイル保存していない。上記エラーメッセージはGitの標準エラー出力を
そのまま転記したものであり、認証情報を含まない。

## 結論

**分類：ユーザー操作待ち（セッションのリポジトリ認可設定）**。
指示書§14の停止条件「secret/authenticationが必要」に近いが、正確には
「セッションのリポジトリ許可リストへの追加」という、Claude側の設定変更が
必要な状態。GitHub側の設定変更は不要（認可されれば通常のpushで成功する
はずの状態であることをプロキシのエラーメッセージから確認済み）。
