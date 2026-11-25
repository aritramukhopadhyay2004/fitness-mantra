"""Exercise registry and category / split indexes.

All exercises are defined in modular category files (`upper_body.py`, `lower_body.py`,
`core.py`, `conditioning.py`) and re-exported here so existing imports (`from exercises.configs import EXERCISES`)
continue to work unchanged.
"""
from __future__ import annotations

from exercises.conditioning import CONDITIONING_EXERCISES
from exercises.core import CORE_EXERCISES
from exercises.lower_body import LOWER_BODY_EXERCISES
from exercises.schema import Exercise, FormCheck
from exercises.upper_body import UPPER_BODY_EXERCISES

ALL_EXERCISES: tuple[Exercise, ...] = (
    UPPER_BODY_EXERCISES
    + LOWER_BODY_EXERCISES
    + CORE_EXERCISES
    + CONDITIONING_EXERCISES
)

EXERCISES: dict[str, Exercise] = {e.key: e for e in ALL_EXERCISES}

CATEGORIES: list[str] = list(dict.fromkeys(e.category for e in ALL_EXERCISES))

WORKOUT_SPLITS: list[str] = [
    "All",
    "Push Day",
    "Pull Day",
    "Leg Day",
    "Core Day",
    "Upper Body",
    "Lower Body",
    "Full Body",
    "HIIT",
    "Functional Training",
    "Flexibility & Mobility",
    "Strength Training",
    "Calisthenics",
]

__all__ = [
    "ALL_EXERCISES",
    "CATEGORIES",
    "EXERCISES",
    "Exercise",
    "FormCheck",
    "WORKOUT_SPLITS",
]
