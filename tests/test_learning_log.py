"""Tests for the personal learning log (docs §9).

Covers: entity validation (trial_number, model_versions required),
repository round-trip + auto trial-numbering + upsert-of-outcome, and the
causal-confidence caution logic that enforces "never conclude causation
from a single trial" as executable behavior rather than just a comment.
"""

from __future__ import annotations

import pytest

from dartsanalytics.db.repositories.sqlite_repositories import (
    SqliteAnalysisReportRepository,
    SqliteExperimentRepository,
    SqliteLearningLogRepository,
)
from dartsanalytics.experiments.models import Experiment
from dartsanalytics.learning_log.analysis import (
    FEW_TRIALS_CAVEAT,
    REPEATED_TRIALS_NOTE,
    SINGLE_TRIAL_CAVEAT,
    causal_confidence_note,
    summarize_intervention_history,
)
from dartsanalytics.learning_log.models import LearningLogEntry


def test_trial_number_must_be_positive():
    with pytest.raises(ValueError):
        LearningLogEntry(
            experiment_id="e1", intervention_description="x", before_summary="b",
            change_description="c", trial_number=0, model_versions={"pose": "v1"},
        )


def test_model_versions_required():
    with pytest.raises(ValueError):
        LearningLogEntry(
            experiment_id="e1", intervention_description="x", before_summary="b",
            change_description="c", trial_number=1, model_versions={},
        )


def test_round_trip_preserves_model_versions_dict():
    entry = LearningLogEntry(
        experiment_id="e1", intervention_description="リリースを遅らせる",
        before_summary="平均220点", change_description="リリースを0.1秒遅らせる",
        trial_number=1, model_versions={"pose": "pose_landmarker_v1", "board": "board_calib_v1"},
    )
    data = entry.to_dict()
    restored = LearningLogEntry.from_dict(data)
    assert restored.model_versions == entry.model_versions


def _make_experiment(db_conn) -> Experiment:
    reports = SqliteAnalysisReportRepository(db_conn)
    experiments = SqliteExperimentRepository(db_conn)
    intervention_id = reports.save_intervention(None, "リリースタイミング調整")
    experiment = Experiment(
        intervention_id=intervention_id, baseline_session_ids=["s1"], status="baseline",
    )
    experiments.save(experiment)
    return experiment


def test_repository_assigns_incrementing_trial_numbers(db_conn):
    experiment = _make_experiment(db_conn)
    repo = SqliteLearningLogRepository(db_conn)

    assert repo.next_trial_number("リリースを遅らせる") == 1
    entry1 = LearningLogEntry(
        experiment_id=experiment.experiment_id, intervention_description="リリースを遅らせる",
        before_summary="平均220点", change_description="0.1秒遅らせる",
        trial_number=repo.next_trial_number("リリースを遅らせる"),
        model_versions={"pose": "pose_landmarker_v1"},
    )
    repo.save_entry(entry1)

    assert repo.next_trial_number("リリースを遅らせる") == 2
    entry2 = LearningLogEntry(
        experiment_id=experiment.experiment_id, intervention_description="リリースを遅らせる",
        before_summary="平均225点", change_description="0.1秒遅らせる（再試行）",
        trial_number=repo.next_trial_number("リリースを遅らせる"),
        model_versions={"pose": "pose_landmarker_v1"},
    )
    repo.save_entry(entry2)

    history = repo.list_entries_by_intervention("リリースを遅らせる")
    assert [e.trial_number for e in history] == [1, 2]

    # A different intervention_description has its own independent counter.
    assert repo.next_trial_number("グリップを変える") == 1


def test_save_entry_upserts_outcome_fields(db_conn):
    experiment = _make_experiment(db_conn)
    repo = SqliteLearningLogRepository(db_conn)
    entry = LearningLogEntry(
        experiment_id=experiment.experiment_id, intervention_description="立ち位置を変える",
        before_summary="平均210点", change_description="半歩右へ",
        trial_number=1, model_versions={"pose": "pose_landmarker_v1"},
    )
    repo.save_entry(entry)

    entry.after_summary = "平均218点"
    entry.result_summary = "continue"
    repo.save_entry(entry)  # same entry_id -> ON CONFLICT DO UPDATE, not a duplicate row

    restored = repo.get_entry(entry.entry_id)
    assert restored.after_summary == "平均218点"
    assert restored.result_summary == "continue"
    assert len(repo.list_all_entries()) == 1


def test_causal_confidence_note_never_confirms():
    assert causal_confidence_note(1) == SINGLE_TRIAL_CAVEAT
    assert causal_confidence_note(2) == FEW_TRIALS_CAVEAT.format(count=2)
    assert causal_confidence_note(5) == REPEATED_TRIALS_NOTE.format(count=5)
    for n in (1, 2, 3, 10, 100):
        note = causal_confidence_note(n)
        # No tier's wording may assert causation as settled fact.
        assert "確認された" not in note
        assert "証明された" not in note
        assert "が原因である" not in note


def test_summarize_intervention_history_orders_by_trial_and_flags_single_trial():
    e1 = LearningLogEntry(
        experiment_id="e1", intervention_description="x", before_summary="b1",
        change_description="c", trial_number=1, model_versions={"pose": "v1"},
    )
    history = summarize_intervention_history([e1])
    assert history.trial_count == 1
    assert history.caution == SINGLE_TRIAL_CAVEAT


def test_summarize_intervention_history_rejects_mixed_descriptions():
    e1 = LearningLogEntry(
        experiment_id="e1", intervention_description="x", before_summary="b",
        change_description="c", trial_number=1, model_versions={"pose": "v1"},
    )
    e2 = LearningLogEntry(
        experiment_id="e1", intervention_description="y", before_summary="b",
        change_description="c", trial_number=1, model_versions={"pose": "v1"},
    )
    with pytest.raises(ValueError):
        summarize_intervention_history([e1, e2])
