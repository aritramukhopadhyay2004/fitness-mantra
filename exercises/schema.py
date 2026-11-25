"""Exercise and FormCheck schema + shared biomechanical form-check templates."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class FormCheck:
    key: str
    kind: str                       # "angle" (3 joints) | "tilt" (top, bottom joints vs vertical)
    joints: tuple[str, ...]
    cue: str
    min: Optional[float] = None     # violation if value < min
    max: Optional[float] = None     # violation if value > max


@dataclass(frozen=True)
class Exercise:
    key: str
    label: str
    joints: tuple[str, str, str]    # (a, vertex, c)
    extended_above: float           # upper angle threshold
    flexed_below: float             # lower angle threshold
    view: str
    setup_tip: str
    checks: tuple[FormCheck, ...] = field(default_factory=tuple)
    moving_end: str = "c"           # "a" (proximal travels) | "c" (distal travels)
    leave_margin: float = 15.0      # degrees from start before rep starts
    default_reps: int = 10
    cue_low: str = "Go lower - reach the green target line"
    direction: str = "flex"         # "flex" (high->low->high) | "extend" (low->high->low)
    mode: str = "rep"               # "rep" | "hold" (isometric seconds)
    hold_min: float = 0.0           # target lower angle for hold mode
    hold_max: float = 180.0         # target upper angle for hold mode
    category: str = "Upper Body"
    muscle_group: str = "Chest"
    equipment: str = "Bodyweight"
    exercise_type: str = "Compound"
    difficulty: str = "Intermediate"
    primary_muscle: str = ""
    secondary_muscles: tuple[str, ...] = field(default_factory=tuple)
    splits: tuple[str, ...] = ("Full Body",)
    biomechanics_note: str = ""


# Reusable biomechanical form checks grounded in ACSM / NSCA guidelines
CHK_TORSO_UPRIGHT_55 = FormCheck(
    "torso", "tilt", ("shoulder", "hip"), "Chest up - you're leaning too far forward", max=55
)
CHK_TORSO_UPRIGHT_35 = FormCheck(
    "torso", "tilt", ("shoulder", "hip"), "Keep your torso upright - avoid leaning forward", max=35
)
CHK_TORSO_STILL_15 = FormCheck(
    "torso_swing", "tilt", ("shoulder", "hip"), "Don't swing your body - keep your torso still", max=15
)
CHK_TORSO_HINGE_ROW = FormCheck(
    "torso_hinge", "tilt", ("shoulder", "hip"), "Maintain your hip hinge (45-75 deg) - don't stand upright", min=35, max=80
)
CHK_BODY_LINE_155 = FormCheck(
    "body_line", "angle", ("shoulder", "hip", "ankle"), "Keep your hips in line - don't sag or pike", min=155
)
CHK_PIN_ELBOW_25 = FormCheck(
    "elbow_drift", "tilt", ("shoulder", "elbow"), "Pin your elbow to your side", max=25
)
CHK_OHP_LOCKOUT_BACK = FormCheck(
    "lumbar_lean", "tilt", ("shoulder", "hip"), "Brace core - avoid excessive lower-back lean", max=20
)
CHK_HIP_TRUST_SHIN = FormCheck(
    "shin_vertical", "tilt", ("knee", "ankle"), "Keep shins near vertical at the top", max=25
)
CHK_DEADLIFT_LOCKOUT = FormCheck(
    "knee_lock", "angle", ("hip", "knee", "ankle"), "Drive through legs without hyperextending knees", min=120
)
