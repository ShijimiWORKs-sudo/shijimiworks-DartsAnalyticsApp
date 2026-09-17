import json

from dartsanalytics.countup.export import export_session_json, write_session_json
from dartsanalytics.models.entities import PracticeSession
from tests.fixtures.countup_patterns import all_dbull_session


def test_export_session_json_is_valid_json_with_result():
    session = all_dbull_session()
    text = export_session_json(session)
    data = json.loads(text)
    assert data["session_id"] == session.session_id
    assert len(data["throws"]) == 24
    assert data["result"]["total_score"] == 1200


def test_export_round_trips_back_to_an_equal_session():
    session = all_dbull_session()
    data = json.loads(export_session_json(session))
    data.pop("result")  # `result` is a derived summary, not part of the entity
    restored = PracticeSession.from_dict(data)
    assert restored.session_id == session.session_id
    assert restored.total_score == session.total_score
    assert len(restored.throws) == len(session.throws)
    assert len(restored.rounds) == len(session.rounds)


def test_write_session_json_creates_file(tmp_path):
    session = all_dbull_session()
    out_path = tmp_path / "exports" / "session.json"
    written = write_session_json(session, out_path)
    assert written == out_path
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["session_id"] == session.session_id
