"""Shooting angles and on-screen guide text (docs §Phase4, §6, shooting-procedure doc).

Four angles are the required base set; three more exist purely to fill
gaps the quality checker finds (docs: "4本で不足した場合は追加動画を要求
できる設計にする"). Guide text is transcribed from
docs/specs/DartsAnalyticsApp_スマホ動画撮影手順_v1.0.md so the app's UI
text stays in sync with the spec instead of being re-worded ad hoc.
"""

from __future__ import annotations

from enum import Enum


class ShootingAngle(str, Enum):
    FRONT = "front"  # 正面・全身
    DOMINANT_SIDE = "dominant_side"  # 利き腕側面・全身
    OPPOSITE_SIDE = "opposite_side"  # 反対側面・全身
    WIDE = "wide"  # 遠景・投擲位置からボードまで全体
    HAND_CLOSEUP = "hand_closeup"  # 追加動画A：手元アップ
    FOOT_CLOSEUP = "foot_closeup"  # 追加動画B：足元
    DART_FLIGHT = "dart_flight"  # 追加動画C：ダーツ飛翔


REQUIRED_ANGLES: tuple[ShootingAngle, ...] = (
    ShootingAngle.FRONT,
    ShootingAngle.DOMINANT_SIDE,
    ShootingAngle.OPPOSITE_SIDE,
    ShootingAngle.WIDE,
)

ADDITIONAL_ANGLES: tuple[ShootingAngle, ...] = (
    ShootingAngle.HAND_CLOSEUP,
    ShootingAngle.FOOT_CLOSEUP,
    ShootingAngle.DART_FLIGHT,
)

# Verbatim from docs/specs/DartsAnalyticsApp_スマホ動画撮影手順_v1.0.md
# "アプリ上の指示文" section.
GUIDE_TEXT: dict[ShootingAngle, str] = {
    ShootingAngle.FRONT: (
        "スマホを投げる位置の正面に固定してください。頭から足先まで全身を入れ、"
        "スローラインと可能ならボード全体も映してください。"
    ),
    ShootingAngle.DOMINANT_SIDE: (
        "利き腕側の真横にスマホを固定してください。頭から足先まで入れ、"
        "特に肩・肘・手首・手が隠れないようにしてください。"
    ),
    ShootingAngle.OPPOSITE_SIDE: (
        "反対側の真横にスマホを固定してください。頭から足先まで入れ、"
        "肩・腰・頭・足の動きが見えるようにしてください。"
    ),
    ShootingAngle.WIDE: (
        "投げる位置からボードまでが一つの画面に収まるようにしてください。"
        "足元、スローライン、投擲者、ボード全体を映してください。"
    ),
    ShootingAngle.HAND_CLOSEUP: "肩から指先まで。リリース前後を重点的に撮ってください。",
    ShootingAngle.FOOT_CLOSEUP: "両足、スローライン、身体の前後移動が分かる画角で撮ってください。",
    ShootingAngle.DART_FLIGHT: (
        "可能な範囲でダーツが見えるように、利き腕側面から高解像度で撮影してください。"
    ),
}


def guide_text(angle: ShootingAngle) -> str:
    return GUIDE_TEXT[angle]
