"""Rep detection state machine (framework-free).

TOP --(angle drops below extended-margin)--> MOVING
MOVING --(angle <= flexed_below)-----------> BOTTOM       (full range reached)
MOVING --(angle back >= extended_above)----> TOP + "partial" event (not counted)
BOTTOM --(angle back >= extended_above)----> TOP + "rep" event (counted)
"""
from __future__ import annotations

from typing import Optional

TOP, MOVING, BOTTOM = "TOP", "MOVING", "BOTTOM"


class RepStateMachine:
    def __init__(self, extended_above: float, flexed_below: float, leave_margin: float = 15.0):
        self.ext = extended_above
        self.flexed = flexed_below
        self.leave = extended_above - leave_margin
        self.state = TOP
        self._t0 = 0.0
        self.min_angle = 180.0
        self._issues: set[str] = set()

    def reset(self) -> None:
        self.state = TOP
        self.min_angle = 180.0
        self._issues = set()

    def update(self, angle: float, t: float, issues: set[str]) -> Optional[dict]:
        if self.state == TOP:
            if angle < self.leave:
                self.state, self._t0, self.min_angle = MOVING, t, angle
                self._issues = set(issues)
            return None

        self.min_angle = min(self.min_angle, angle)
        self._issues |= issues

        if self.state == MOVING and angle <= self.flexed:
            self.state = BOTTOM
            return None

        if angle >= self.ext:
            kind = "rep" if self.state == BOTTOM else "partial"
            ev = {
                "kind": kind,
                "min_angle": self.min_angle,
                "duration": t - self._t0,
                "issues": sorted(self._issues),
            }
            self.state = TOP
            return ev
        return None
