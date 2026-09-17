"""Re-shoot / additional-shot decision logic (docs §Phase4 NG理由表示・再撮影要求,
§6.6 追加動画は「不足した特徴量を取得するため」にのみ要求する).

`recommend_additional_angles` is explicitly a placeholder policy, not a
needs-analysis: real "which feature is missing" detection needs Phase 5+
pose/object features. Documenting that limitation here (rather than
pretending this function is smarter than it is) matters more than the
function itself — see docs §Phase4 report for the same note.
"""

from __future__ import annotations

from dartsanalytics.video.angles import REQUIRED_ANGLES, ADDITIONAL_ANGLES, ShootingAngle
from dartsanalytics.video.models import MediaAsset

_RESHOOT_GRADES = ("reshoot",)
_BORDERLINE_GRADES = ("C",)

# Placeholder mapping: which additional angle would plausibly help if a
# required angle keeps coming back borderline. Not derived from any
# feature-need analysis (Phase 5+ scope) — just a reasonable first guess.
_BORDERLINE_FOLLOWUP: dict[ShootingAngle, ShootingAngle] = {
    ShootingAngle.DOMINANT_SIDE: ShootingAngle.HAND_CLOSEUP,
    ShootingAngle.WIDE: ShootingAngle.FOOT_CLOSEUP,
}


def missing_required_angles(captured: dict[ShootingAngle, str | None]) -> list[ShootingAngle]:
    """Which of the 4 required angles still need a (re)shoot.

    `captured` maps angle -> best quality_grade obtained so far for that
    angle (None/'reshoot' both count as "not yet satisfied").
    """
    return [
        angle
        for angle in REQUIRED_ANGLES
        if captured.get(angle) is None or captured.get(angle) in _RESHOOT_GRADES
    ]


def recommend_additional_angles(captured: dict[ShootingAngle, str | None]) -> list[ShootingAngle]:
    """Additional angles worth requesting given borderline (grade 'C')
    required-angle footage. Conservative and explicitly a placeholder —
    see module docstring.
    """
    recommendations: list[ShootingAngle] = []
    for angle, grade in captured.items():
        if grade in _BORDERLINE_GRADES and angle in _BORDERLINE_FOLLOWUP:
            followup = _BORDERLINE_FOLLOWUP[angle]
            if followup not in recommendations:
                recommendations.append(followup)
    return recommendations


def summarize_session_intake(assets: list[MediaAsset]) -> dict:
    """Best grade obtained per required angle, what's still missing, and
    what additional shots are recommended — the data a shooting-guide UI
    screen needs in one call."""
    best_grade_by_angle: dict[ShootingAngle, str | None] = {}
    grade_rank = {"reshoot": 0, "C": 1, "B": 2, "A": 3, None: -1}
    for asset in assets:
        if asset.angle is None:
            continue
        current = best_grade_by_angle.get(asset.angle)
        if grade_rank.get(asset.quality_grade, -1) > grade_rank.get(current, -1):
            best_grade_by_angle[asset.angle] = asset.quality_grade

    missing = missing_required_angles(best_grade_by_angle)
    additional = recommend_additional_angles(best_grade_by_angle)

    return {
        "best_grade_by_angle": {a.value: g for a, g in best_grade_by_angle.items()},
        "missing_required_angles": [a.value for a in missing],
        "recommended_additional_angles": [a.value for a in additional],
        "all_required_satisfied": len(missing) == 0,
    }
