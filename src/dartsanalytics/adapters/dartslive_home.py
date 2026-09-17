"""DARTSLIVE HOME adapter — isolated per design principle (docs §4.1):

    Bluetooth層は IDartsLiveHomeAdapter として隔離し、初期実装では
    実機プロトコル検証を必須とする。

See docs/codex/reports/phase2_findings.md for the Phase 2 investigation
that led to this being an abstraction + mock only, with no guessed BLE
protocol implementation: no public GATT/characteristic spec could be
confirmed, and this session has no way to observe real device traffic
(no BLE hardware in the cloud sandbox, no shell access on the user's PC
from here). Implementing a protocol without that evidence would be
exactly the "外部仕様が不明で推測実装が危険な場合" stop condition this
project's rules call out — so this module does not attempt it.

Every concrete adapter must be confined to this module (no BLE-specific
code should leak into session/analysis code elsewhere), and once a real
adapter IS implemented from verified hardware observation, it must be
commented "非公式・実機検証済み" at the point it relies on anything
beyond DARTSLIVE HOME's public documentation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator

from dartsanalytics.common.enums import DataKind, DetectionSource
from dartsanalytics.countup.mock import MockCountUpGenerator
from dartsanalytics.models.entities import Throw


class IDartsLiveHomeAdapter(ABC):
    """Adapter boundary between "a source of COUNT-UP throw events" and the
    rest of the app. A session consumer should only ever depend on this
    interface, never on a concrete adapter's internals.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish a connection to the device. Idempotent if already connected."""

    @abstractmethod
    def disconnect(self) -> None:
        """Tear down the connection. Idempotent if already disconnected."""

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def raw_events(self) -> Iterator[dict[str, Any]]:
        """Yield one raw event per dart thrown, in throw order, until the
        session ends or disconnect() is called. The shape of each dict is
        adapter-specific; use to_throw() to convert it into the canonical
        Throw entity rather than reading raw_event fields directly elsewhere
        in the app (that keeps adapter-specific detail confined here).
        """

    @abstractmethod
    def to_throw(
        self,
        raw_event: dict[str, Any],
        *,
        session_id: str,
        round_id: str,
        round_number: int,
        dart_index: int,
        throw_number_in_session: int,
    ) -> Throw:
        """Convert one raw_events() item into a Throw entity."""


class MockDartsLiveHomeAdapter(IDartsLiveHomeAdapter):
    """Fake adapter for integration testing and UI development while the
    real BLE protocol is unverified (see module docstring). Internally
    reuses MockCountUpGenerator so mock-adapter sessions and Phase 1's
    direct mock-generator sessions are byte-for-byte consistent.
    """

    def __init__(self, seed: int, num_throws: int = 24):
        self._seed = seed
        self._num_throws = num_throws
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def raw_events(self) -> Iterator[dict[str, Any]]:
        if not self._connected:
            raise RuntimeError("MockDartsLiveHomeAdapter.connect() must be called first")
        generator = MockCountUpGenerator(seed=self._seed)
        session = generator.generate(
            account_id="mock-account", player_id="mock-player", num_throws=self._num_throws
        )
        for throw in session.throws:
            yield {
                "score": throw.score,
                "segment": throw.segment,
                "ring": throw.ring.value if throw.ring else None,
            }

    def to_throw(
        self,
        raw_event: dict[str, Any],
        *,
        session_id: str,
        round_id: str,
        round_number: int,
        dart_index: int,
        throw_number_in_session: int,
    ) -> Throw:
        from dartsanalytics.common.enums import Ring

        return Throw(
            session_id=session_id,
            round_id=round_id,
            round_number=round_number,
            dart_index=dart_index,
            throw_number_in_session=throw_number_in_session,
            detection_source=DetectionSource.MOCK,
            data_kind=DataKind.MEASURED,
            score=raw_event["score"],
            segment=raw_event["segment"],
            ring=Ring(raw_event["ring"]) if raw_event.get("ring") else None,
            actual_target=raw_event["segment"],
        )


class UnimplementedBleDartsLiveHomeAdapter(IDartsLiveHomeAdapter):
    """Placeholder for the real BLE adapter — intentionally not implemented.

    Do NOT fill this in with a guessed GATT service/characteristic UUID or
    payload layout. Implement it only after observing real DARTSLIVE HOME
    traffic (e.g. via a BLE inspector such as nRF Connect, or a bleak
    script run on hardware that can see the device) and record findings in
    docs/codex/reports/ before writing code here. See
    docs/codex/reports/phase2_findings.md for what is still unknown.
    """

    _NOT_READY = (
        "DARTSLIVE HOME's BLE protocol has not been verified against real "
        "hardware in this project yet (see docs/codex/reports/phase2_findings.md). "
        "Implement this adapter only from confirmed real-device observation, "
        "never from a guess."
    )

    def connect(self) -> None:
        raise NotImplementedError(self._NOT_READY)

    def disconnect(self) -> None:
        raise NotImplementedError(self._NOT_READY)

    @property
    def is_connected(self) -> bool:
        return False

    def raw_events(self) -> Iterator[dict[str, Any]]:
        raise NotImplementedError(self._NOT_READY)

    def to_throw(self, raw_event, **kwargs):
        raise NotImplementedError(self._NOT_READY)
