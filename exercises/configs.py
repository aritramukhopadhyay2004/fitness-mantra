"""Exercise definitions. Adding an exercise = adding one entry here.

!! All thresholds are STARTING VALUES. Have a trainer / physiotherapist review them
   before real users rely on them. Angles are measured in 2D from a side view, so the
   camera position matters (see `view`).

Joint names are generic ("knee"); the engine resolves them to the left or right side,
whichever the camera sees better.
"""
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
    joints: tuple[str, str, str]    # the joint triplet that defines the rep (a, vertex, c)
    extended_above: float           # angle at/above which the rep is "at the top"
    flexed_below: float             # angle the user must reach for a full-range rep
    view: str
    setup_tip: str
    checks: tuple[FormCheck, ...] = field(default_factory=tuple)
    moving_end: str = "c"           # which end of the triplet travels: "a" (e.g. hip in a squat) or "c" (wrist in a curl)
    leave_margin: float = 15.0      # degrees below `extended_above` before a rep is "started"
    default_reps: int = 10
    cue_low: str = "Go lower - reach the green target line"


SQUAT = Exercise(
    key="squat",
    label="Squat",
    joints=("hip", "knee", "ankle"),
    extended_above=160,
    flexed_below=100,
    view="Side view",
    moving_end="a",
    setup_tip="Stand side-on to the camera, 2-3 m away, full body in frame.",
    checks=(
        FormCheck("torso", "tilt", ("shoulder", "hip"), "Chest up - you're leaning too far forward", max=55),
    ),
)

PUSHUP = Exercise(
    key="pushup",
    label="Push-up",
    joints=("shoulder", "elbow", "wrist"),
    extended_above=160,
    flexed_below=95,
    view="Side view",
    moving_end="a",
    setup_tip="Place the camera at floor level, side-on, so head to feet is visible.",
    checks=(
        FormCheck("body_line", "angle", ("shoulder", "hip", "ankle"), "Keep your hips in line - don't sag or pike", min=155),
    ),
    cue_low="Chest lower - reach the green target line",
)

BICEP_CURL = Exercise(
    key="curl",
    label="Bicep curl",
    joints=("shoulder", "elbow", "wrist"),
    extended_above=150,
    flexed_below=50,
    view="Side view",
    setup_tip="Stand side-on, working arm towards the camera, upper body in frame.",
    checks=(
        FormCheck("elbow_drift", "tilt", ("shoulder", "elbow"), "Pin your elbow to your side", max=25),
        FormCheck("torso_swing", "tilt", ("shoulder", "hip"), "Don't swing your body - keep your torso still", max=15),
    ),
    cue_low="Curl higher - squeeze at the top",
)

EXERCISES: dict[str, Exercise] = {e.key: e for e in (SQUAT, PUSHUP, BICEP_CURL)}
