import pytest

from dartsanalytics.adapters import (
    IDartsLiveHomeAdapter,
    MockDartsLiveHomeAdapter,
    UnimplementedBleDartsLiveHomeAdapter,
)
from dartsanalytics.common.enums import DataKind, DetectionSource


def test_cannot_instantiate_abstract_interface_directly():
    with pytest.raises(TypeError):
        IDartsLiveHomeAdapter()  # type: ignore[abstract]


def test_mock_adapter_requires_connect_before_events():
    adapter = MockDartsLiveHomeAdapter(seed=1)
    with pytest.raises(RuntimeError):
        list(adapter.raw_events())


def test_mock_adapter_connect_disconnect_lifecycle():
    adapter = MockDartsLiveHomeAdapter(seed=1)
    assert adapter.is_connected is False
    adapter.connect()
    assert adapter.is_connected is True
    adapter.disconnect()
    assert adapter.is_connected is False


def test_mock_adapter_yields_24_events_and_matches_mock_generator():
    """Integration test: adapter path and Phase 1's direct MockCountUpGenerator
    path must produce identical throw content for the same seed."""
    from dartsanalytics.countup.mock import MockCountUpGenerator

    adapter = MockDartsLiveHomeAdapter(seed=5)
    adapter.connect()
    events = list(adapter.raw_events())
    assert len(events) == 24

    direct_session = MockCountUpGenerator(seed=5).generate(
        account_id="a", player_id="p", num_throws=24
    )
    direct_scores = [t.score for t in direct_session.throws]
    adapter_scores = [e["score"] for e in events]
    assert direct_scores == adapter_scores


def test_mock_adapter_to_throw_produces_valid_measured_throw():
    adapter = MockDartsLiveHomeAdapter(seed=3)
    adapter.connect()
    raw_event = next(iter(adapter.raw_events()))
    throw = adapter.to_throw(
        raw_event,
        session_id="s1",
        round_id="r1",
        round_number=1,
        dart_index=1,
        throw_number_in_session=1,
    )
    assert throw.detection_source is DetectionSource.MOCK
    assert throw.data_kind is DataKind.MEASURED
    assert throw.confidence is None  # MEASURED never requires one
    assert throw.score == raw_event["score"]


def test_unimplemented_ble_adapter_refuses_to_guess():
    adapter = UnimplementedBleDartsLiveHomeAdapter()
    assert adapter.is_connected is False
    with pytest.raises(NotImplementedError):
        adapter.connect()
    with pytest.raises(NotImplementedError):
        list(adapter.raw_events())
