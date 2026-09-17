-- 0002_learning_log.sql
-- §9 個人学習ログ: intervention/before/change/after/result/
-- analysis・model versionを記録し、過去結果を再現可能にする。
--
-- 既存の experiments/experiment_results (0001) は「測定値の比較」を持つが、
-- 「何を変えたか」「解析に使ったアルゴリズム/モデルのバージョン」という
-- 人間向けの記録は持たない。学習ログは1 experimentに対して1エントリを
-- 追加する形で、その情報を補う（experimentsテーブル自体は変更しない —
-- 既存データ・既存コードへの後方互換性を壊さない）。
--
-- trial_number: 同じ intervention_description を持つエントリの何回目の
-- 試行かを保存する（アプリ側で計算してセットする。単一試行だけで因果関係を
-- 断定しないという設計原則（docs §9）を、後から「この介入は何回試したか」
-- を機械的に問い合わせられる形にするための列）。

CREATE TABLE learning_log_entries (
    entry_id                  TEXT PRIMARY KEY,
    experiment_id              TEXT NOT NULL REFERENCES experiments(experiment_id),
    intervention_description   TEXT NOT NULL,
    before_summary              TEXT NOT NULL,
    change_description          TEXT NOT NULL,
    after_summary                TEXT,
    result_summary               TEXT,
    model_versions_json          TEXT NOT NULL,
    trial_number                  INTEGER NOT NULL CHECK (trial_number >= 1),
    created_at                    TEXT NOT NULL
);

CREATE INDEX idx_learning_log_intervention
    ON learning_log_entries(intervention_description);
