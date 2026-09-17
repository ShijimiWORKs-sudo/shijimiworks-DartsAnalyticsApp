-- 0001_initial.sql
-- Phase 0: repository foundation schema.
-- Tables mirror docs/specs/DartsAnalyticsApp_詳細設計書_v1.0.md §21.
-- Only columns needed to satisfy Phase 0/1 (COUNT-UP data core) are
-- fully fleshed out; later-phase tables are created now (so the schema
-- doesn't need churn every phase) but stay minimal until their own
-- phase implements the logic that fills them in.

PRAGMA foreign_keys = ON;

CREATE TABLE accounts (
    account_id    TEXT PRIMARY KEY,
    display_name  TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE players (
    player_id      TEXT PRIMARY KEY,
    account_id     TEXT NOT NULL REFERENCES accounts(account_id),
    display_name   TEXT NOT NULL,
    dominant_hand  TEXT CHECK (dominant_hand IN ('right', 'left', NULL)),
    dominant_eye   TEXT CHECK (dominant_eye IN ('right', 'left', NULL)),
    created_at     TEXT NOT NULL
);

CREATE TABLE equipment_profiles (
    equipment_id     TEXT PRIMARY KEY,
    player_id        TEXT NOT NULL REFERENCES players(player_id),
    barrel_maker     TEXT,
    barrel_name      TEXT,
    barrel_weight_g  REAL,
    total_weight_g   REAL,
    flight_type      TEXT,
    shaft_type       TEXT,
    shaft_length     TEXT,
    tip_type         TEXT,
    changed_at       TEXT NOT NULL,
    notes            TEXT
);

CREATE TABLE practice_sessions (
    session_id     TEXT PRIMARY KEY,
    account_id     TEXT NOT NULL REFERENCES accounts(account_id),
    player_id      TEXT NOT NULL REFERENCES players(player_id),
    equipment_id   TEXT REFERENCES equipment_profiles(equipment_id),
    game_type      TEXT NOT NULL DEFAULT 'COUNT_UP' CHECK (game_type = 'COUNT_UP'),
    practice_type  TEXT,
    status         TEXT NOT NULL CHECK (status IN ('in_progress', 'complete', 'incomplete')),
    started_at     TEXT NOT NULL,
    ended_at       TEXT,
    total_score    INTEGER,
    created_at     TEXT NOT NULL
);

CREATE TABLE countup_rounds (
    round_id      TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES practice_sessions(session_id),
    round_number  INTEGER NOT NULL CHECK (round_number BETWEEN 1 AND 8),
    round_score   INTEGER,
    UNIQUE (session_id, round_number)
);

CREATE TABLE throws (
    throw_id                  TEXT PRIMARY KEY,
    session_id                TEXT NOT NULL REFERENCES practice_sessions(session_id),
    round_id                  TEXT NOT NULL REFERENCES countup_rounds(round_id),
    round_number               INTEGER NOT NULL,
    dart_index                 INTEGER NOT NULL CHECK (dart_index BETWEEN 1 AND 3),
    throw_number_in_session    INTEGER NOT NULL CHECK (throw_number_in_session BETWEEN 1 AND 24),
    score                      INTEGER,
    segment                    TEXT,
    ring                       TEXT CHECK (ring IN ('SINGLE', 'DOUBLE', 'TRIPLE', 'BULL', 'DBULL', 'MISS', NULL)),
    declared_target            TEXT,
    actual_target              TEXT,
    detection_source           TEXT NOT NULL,
    data_kind                  TEXT NOT NULL CHECK (data_kind IN ('MEASURED', 'CALCULATED', 'ESTIMATED', 'ADVICE')),
    confidence                 REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    raw_event_json              TEXT,
    created_at                  TEXT NOT NULL,
    UNIQUE (session_id, throw_number_in_session)
);

CREATE TABLE board_calibrations (
    calibration_id     TEXT PRIMARY KEY,
    session_id         TEXT REFERENCES practice_sessions(session_id),
    center_x_px        REAL,
    center_y_px        REAL,
    radius_px          REAL,
    algorithm_version  TEXT NOT NULL,
    confidence         REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    created_at         TEXT NOT NULL
);

CREATE TABLE throw_coordinates (
    throw_id               TEXT PRIMARY KEY REFERENCES throws(throw_id),
    raw_x                  REAL,
    raw_y                  REAL,
    normalized_x           REAL,
    normalized_y           REAL,
    distance_from_bull     REAL,
    angle                  REAL,
    detected_segment       TEXT,
    detection_confidence   REAL CHECK (detection_confidence IS NULL OR (detection_confidence >= 0.0 AND detection_confidence <= 1.0)),
    coordinate_source      TEXT,
    calibration_id         TEXT REFERENCES board_calibrations(calibration_id)
);

CREATE TABLE media_assets (
    media_id       TEXT PRIMARY KEY,
    session_id     TEXT NOT NULL REFERENCES practice_sessions(session_id),
    media_type     TEXT NOT NULL CHECK (media_type IN ('video', 'photo')),
    angle          TEXT,
    file_path      TEXT NOT NULL,
    checksum       TEXT,
    quality_grade  TEXT CHECK (quality_grade IN ('A', 'B', 'C', 'reshoot', NULL)),
    created_at     TEXT NOT NULL
);

CREATE TABLE video_analysis_runs (
    run_id             TEXT PRIMARY KEY,
    media_id           TEXT NOT NULL REFERENCES media_assets(media_id),
    algorithm_version  TEXT NOT NULL,
    status             TEXT NOT NULL,
    started_at         TEXT NOT NULL,
    finished_at        TEXT
);

CREATE TABLE pose_features (
    pose_feature_id  TEXT PRIMARY KEY,
    run_id           TEXT NOT NULL REFERENCES video_analysis_runs(run_id),
    throw_id         TEXT REFERENCES throws(throw_id),
    feature_name     TEXT NOT NULL,
    feature_value    REAL,
    data_kind        TEXT NOT NULL DEFAULT 'ESTIMATED' CHECK (data_kind IN ('MEASURED', 'CALCULATED', 'ESTIMATED', 'ADVICE')),
    confidence       REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0)
);

CREATE TABLE grip_analysis_runs (
    grip_run_id        TEXT PRIMARY KEY,
    media_id           TEXT NOT NULL REFERENCES media_assets(media_id),
    algorithm_version  TEXT NOT NULL,
    result_json        TEXT,
    confidence         REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    created_at         TEXT NOT NULL
);

CREATE TABLE analysis_reports (
    report_id    TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES practice_sessions(session_id),
    report_json  TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE hypotheses (
    hypothesis_id  TEXT PRIMARY KEY,
    report_id      TEXT NOT NULL REFERENCES analysis_reports(report_id),
    description    TEXT NOT NULL,
    confidence     REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    created_at     TEXT NOT NULL
);

CREATE TABLE interventions (
    intervention_id  TEXT PRIMARY KEY,
    hypothesis_id    TEXT REFERENCES hypotheses(hypothesis_id),
    description      TEXT NOT NULL,
    created_at       TEXT NOT NULL
);

CREATE TABLE experiments (
    experiment_id         TEXT PRIMARY KEY,
    intervention_id       TEXT NOT NULL REFERENCES interventions(intervention_id),
    baseline_session_ids  TEXT NOT NULL,
    test_session_ids      TEXT,
    status                TEXT NOT NULL CHECK (status IN ('baseline', 'testing', 'decided')),
    decision              TEXT CHECK (decision IN ('continue', 'revert', 'retest', NULL)),
    created_at            TEXT NOT NULL
);

CREATE TABLE experiment_results (
    experiment_result_id  TEXT PRIMARY KEY,
    experiment_id         TEXT NOT NULL REFERENCES experiments(experiment_id),
    metric_name           TEXT NOT NULL,
    baseline_value        REAL,
    test_value            REAL,
    delta                 REAL
);

CREATE INDEX idx_throws_session ON throws(session_id);
CREATE INDEX idx_countup_rounds_session ON countup_rounds(session_id);
CREATE INDEX idx_media_assets_session ON media_assets(session_id);
