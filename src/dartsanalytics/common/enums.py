"""Shared enums used across the app.

These encode the vocabulary from docs/specs/DartsAnalyticsApp_詳細設計書_v1.0.md
so every module (DB layer, analysis, AI advisor) speaks the same language.
"""

from __future__ import annotations

from enum import Enum


class DataKind(str, Enum):
    """Separates 'what we know' from 'what we inferred' (design principle #3:
    「直接測定」「計算値」「推定」「助言」を明確に分離する).
    """

    MEASURED = "MEASURED"       # Direct measurement (e.g. from DARTSLIVE HOME)
    CALCULATED = "CALCULATED"   # Deterministic calculation from measured data
    ESTIMATED = "ESTIMATED"     # Inferred from image/video analysis, pose estimation, etc.
    ADVICE = "ADVICE"           # AI advisor interpretation / suggestion


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"            # 0.90-1.00 高信頼
    SUFFICIENT = "SUFFICIENT"  # 0.75-0.89 十分
    REFERENCE = "REFERENCE"    # 0.50-0.74 参考
    PENDING = "PENDING"        # 0.00-0.49 判定保留


class DetectionSource(str, Enum):
    DARTSLIVE_HOME = "dartslive_home"
    BOARD_CAMERA = "board_camera"
    MANUAL_ENTRY = "manual_entry"
    MOCK = "mock"


class Ring(str, Enum):
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"
    TRIPLE = "TRIPLE"
    BULL = "BULL"
    DBULL = "DBULL"
    MISS = "MISS"


class SessionStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class GameType(str, Enum):
    COUNT_UP = "COUNT_UP"
