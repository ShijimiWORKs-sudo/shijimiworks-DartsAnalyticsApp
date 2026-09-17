import pytest

from dartsanalytics.experiments.decision import Decision
from dartsanalytics.experiments.models import Experiment


def test_creates_with_defaults():
    exp = Experiment(intervention_id="iv1", baseline_session_ids=["s1", "s2"])
    assert exp.status == "baseline"
    assert exp.test_session_ids == []
    assert exp.decision is None
    assert exp.experiment_id  # auto-generated


def test_rejects_empty_baseline_sessions():
    with pytest.raises(ValueError):
        Experiment(intervention_id="iv1", baseline_session_ids=[])


def test_rejects_invalid_status():
    with pytest.raises(ValueError):
        Experiment(intervention_id="iv1", baseline_session_ids=["s1"], status="bogus")


def test_to_dict_and_from_dict_round_trip():
    exp = Experiment(
        intervention_id="iv1",
        baseline_session_ids=["s1", "s2"],
        test_session_ids=["s3", "s4"],
        status="decided",
        decision=Decision.CONTINUE,
    )
    data = exp.to_dict()
    restored = Experiment.from_dict(data)
    assert restored.experiment_id == exp.experiment_id
    assert restored.decision == Decision.CONTINUE
    assert restored.baseline_session_ids == ["s1", "s2"]


def test_to_dict_is_json_serializable():
    import json

    exp = Experiment(intervention_id="iv1", baseline_session_ids=["s1"], decision=Decision.RETEST)
    json.dumps(exp.to_dict(), ensure_ascii=False)


def test_decision_none_serializes_to_null():
    exp = Experiment(intervention_id="iv1", baseline_session_ids=["s1"])
    assert exp.to_dict()["decision"] is None
