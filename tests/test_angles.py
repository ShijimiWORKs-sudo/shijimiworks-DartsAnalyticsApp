from dartsanalytics.video.angles import ADDITIONAL_ANGLES, GUIDE_TEXT, REQUIRED_ANGLES, ShootingAngle, guide_text


def test_required_angles_is_the_four_from_spec():
    assert len(REQUIRED_ANGLES) == 4
    assert set(REQUIRED_ANGLES) == {
        ShootingAngle.FRONT,
        ShootingAngle.DOMINANT_SIDE,
        ShootingAngle.OPPOSITE_SIDE,
        ShootingAngle.WIDE,
    }


def test_additional_angles_is_the_three_from_spec():
    assert len(ADDITIONAL_ANGLES) == 3
    assert set(ADDITIONAL_ANGLES) == {
        ShootingAngle.HAND_CLOSEUP,
        ShootingAngle.FOOT_CLOSEUP,
        ShootingAngle.DART_FLIGHT,
    }


def test_required_and_additional_do_not_overlap():
    assert set(REQUIRED_ANGLES).isdisjoint(set(ADDITIONAL_ANGLES))


def test_every_angle_has_guide_text():
    for angle in list(REQUIRED_ANGLES) + list(ADDITIONAL_ANGLES):
        text = guide_text(angle)
        assert isinstance(text, str)
        assert len(text) > 0


def test_guide_text_dict_covers_all_enum_values():
    assert set(GUIDE_TEXT.keys()) == set(ShootingAngle)
