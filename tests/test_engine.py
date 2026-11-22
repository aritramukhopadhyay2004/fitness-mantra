import math

import pytest

from core.engine import CoachEngine
from core.geometry import angle_deg, ghost_limb_end, tilt_from_vertical
from exercises.configs import EXERCISES
from tests.synth import rep_angles, squat_pose, sweep

DT = 1 / 30


def run(engine, angles, t=0.0, **pose_kw):
    st = None
    for a in angles:
        st = engine.process(squat_pose(a, **pose_kw), t)
        t += DT
    return st, t


def squat(reps=10, sets=3, rest=45):
    return CoachEngine(EXERCISES["squat"], reps, sets, rest)


def test_geometry():
    assert angle_deg((0, 1), (0, 0), (1, 0)) == pytest.approx(90)
    assert angle_deg((1, 0), (0, 0), (-1, 0)) == pytest.approx(180)
    assert tilt_from_vertical((0, 0), (0, 100)) == pytest.approx(0)
    assert tilt_from_vertical((100, 0), (0, 0)) == pytest.approx(90)
    # ghost limb at target angle really produces that angle, same limb length
    a, b, c = (0, -100), (0, 0), (60, 80)
    g = ghost_limb_end(a, b, c, 90)
    assert angle_deg(a, b, g) == pytest.approx(90, abs=0.01)
    assert math.hypot(*g) == pytest.approx(math.hypot(60, 80))


def test_synthetic_pose_has_requested_knee_angle():
    p = squat_pose(100)
    ang = angle_deg(p["left_hip"][:2], p["left_knee"][:2], p["left_ankle"][:2])
    assert ang == pytest.approx(100, abs=0.01)


def test_three_full_squats_counted():
    e = squat()
    _, t = run(e, [172] * 10)
    for _ in range(3):
        _, t = run(e, rep_angles(), t)
    s = e.summary()
    assert s["reps_counted"] == 3 and s["partial_reps"] == 0
    assert s["clean_reps"] == 3
    assert s["avg_depth_pct"] >= 100


def test_half_rep_not_counted_and_cue_given():
    e = squat()
    _, t = run(e, [172] * 10)
    st, t = run(e, rep_angles(bottom=125), t)
    s = e.summary()
    assert s["reps_counted"] == 0 and s["partial_reps"] == 1
    assert "not counted" in st.cue or "Go lower" in st.cue


def test_live_go_lower_cue_while_rising_short_of_depth():
    e = squat()
    _, t = run(e, [172] * 10)
    st, t = run(e, sweep(172, 125) + [125] * 5 + sweep(125, 140), t)
    assert "lower" in st.cue.lower()


def test_torso_lean_flagged_in_record():
    e = squat()
    _, t = run(e, [172] * 10)
    _, t = run(e, rep_angles(), t, torso_tilt=70)
    s = e.summary()
    assert s["reps_counted"] == 1
    assert s["form_issue_counts"], "forward lean should be flagged"
    assert s["clean_reps"] == 0


def test_sets_rest_and_finish():
    e = squat(reps=2, sets=2, rest=10)
    _, t = run(e, [172] * 10)
    for _ in range(2):
        st, t = run(e, rep_angles(), t)
    assert st.resting and e.set_no == 2
    # reps during rest are ignored
    _, t = run(e, rep_angles(), t)
    assert e.summary()["reps_counted"] == 2
    # wait out the rest, then do set 2
    _, t = run(e, [172] * 330, t)
    for _ in range(2):
        st, t = run(e, rep_angles(), t)
    assert e.finished and st.finished
    s = e.summary()
    assert s["reps_counted"] == 4 and s["sets_completed"] == 2


def test_no_counting_when_body_not_visible():
    e = squat()
    st = None
    for a in rep_angles():
        st = e.process(squat_pose(a, vis=0.1), 0.0)
    assert not st.visible and "Step back" in st.cue
    assert e.summary()["reps_counted"] == 0


def test_other_exercises_load():
    for ex in EXERCISES.values():
        assert ex.flexed_below < ex.extended_above


def test_moving_end_config():
    assert EXERCISES["squat"].moving_end == "a" and EXERCISES["pushup"].moving_end == "a"
    assert EXERCISES["curl"].moving_end == "c"
    # squat ghost hip: ankle & knee stay planted, hip lands at the target knee angle
    p = squat_pose(150)
    a, b, c = (p[f"left_{j}"][:2] for j in ("hip", "knee", "ankle"))
    g = ghost_limb_end(c, b, a, EXERCISES["squat"].flexed_below)
    assert angle_deg(g, b, c) == pytest.approx(EXERCISES["squat"].flexed_below, abs=0.01)
    assert math.hypot(g[0] - b[0], g[1] - b[1]) == pytest.approx(math.hypot(a[0] - b[0], a[1] - b[1]))
