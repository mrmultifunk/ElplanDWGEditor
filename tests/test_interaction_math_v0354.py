from interaction_math import wheel_zoom_factor


def test_zero_vertical_delta_never_zooms():
    assert wheel_zoom_factor(0, 0) is None


def test_horizontal_only_equivalent_zero_vertical_delta_never_zooms():
    # The helper intentionally receives only the vertical components. A Qt
    # event with angleDelta.x != 0 and both y components == 0 must be ignored.
    assert wheel_zoom_factor(angle_y=0, pixel_y=0) is None


def test_classic_wheel_preserves_existing_step_size():
    assert wheel_zoom_factor(120, 0) == 1.18
    assert abs(wheel_zoom_factor(-120, 0) - (1 / 1.18)) < 1e-12


def test_touchpad_pixel_delta_is_smooth_and_directional():
    up = wheel_zoom_factor(0, 30)
    down = wheel_zoom_factor(0, -30)
    assert up is not None and 1.0 < up < 1.18
    assert down is not None and (1 / 1.18) < down < 1.0
    assert abs(up * down - 1.0) < 1e-12


def test_touchpad_driver_spike_is_limited_to_one_step():
    assert wheel_zoom_factor(0, 1000) == 1.18
    assert abs(wheel_zoom_factor(0, -1000) - (1 / 1.18)) < 1e-12
