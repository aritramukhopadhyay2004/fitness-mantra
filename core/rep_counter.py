"""Rep detection state machine (framework-free).

Supports both:
- direction="flex":   TOP (>= extended_above) -> MOVING -> BOTTOM (<= flexed_below) -> TOP ("rep")
- direction="extend": TOP (<= flexed_below)   -> MOVING -> BOTTOM (>= extended_above) -> TOP ("rep")
"""
from __future__ import annotations

from typing import Optional

TOP, MOVING, BOTTOM = "TOP", "MOVING", "BOTTOM"


class RepStateMachine:
    def __init__(
        self,
        extended_above: float,
        flexed_below: float,
        leave_margin: float = 15.0,
        direction: str = "flex",
    ):
        self.ext = extended_above
        self.flexed = flexed_below
        self.direction = direction
        self.leave = (
            extended_above - leave_margin
            if direction == "flex"
            else flexed_below + leave_margin
        )
        self.state = TOP
        self._t0 = 0.0
        self.min_angle = 180.0
        self.peak_angle = 0.0
        self._issues: set[str] = set()

    def reset(self) -> None:
        self.state = TOP
        self.min_angle = 180.0
        self.peak_angle = 0.0
        self._issues = set()

    def update(self, angle: float, t: float, issues: set[str]) -> Optional[dict]:
        if self.direction == "extend":
            return self._update_extend(angle, t, issues)
        return self._update_flex(angle, t, issues)

    def _update_flex(self, angle: float, t: float, issues: set[str]) -> Optional[dict]:
        if self.state == TOP:
            if angle < self.leave:
                self.state, self._t0, self.min_angle, self.peak_angle = MOVING, t, angle, angle
                self._issues = set(issues)
            return None

        self.min_angle = min(self.min_angle, angle)
        self.peak_angle = max(self.peak_angle, angle)
        self._issues |= issues

        if self.state == MOVING and angle <= self.flexed:
            self.state = BOTTOM
            return None

        if angle >= self.ext:
            kind = "rep" if self.state == BOTTOM else "partial"
            ev = {
                "kind": kind,
                "min_angle": self.min_angle,
                "peak_angle": self.peak_angle,
                "duration": t - self._t0,
                "issues": sorted(self._issues),
            }
            self.state = TOP
            return ev
        return None

    def _update_extend(self, angle: float, t: float, issues: set[str]) -> Optional[dict]:
        if self.state == TOP:
            if angle > self.leave:
                self.state, self._t0, self.min_angle, self.peak_angle = MOVING, t, angle, angle
                self._issues = set(issues)
            return None

        self.min_angle = min(self.min_angle, angle)
        self.peak_angle = max(self.peak_angle, angle)
        self._issues |= issues

        if self.state == MOVING and angle >= self.ext:
            self.state = BOTTOM
            return None

        if angle <= self.flexed:
            kind = "rep" if self.state == BOTTOM else "partial"
            ev = {
                "kind": kind,
                "min_angle": self.min_angle,
                "peak_angle": self.peak_angle,
                "duration": t - self._t0,
                "issues": sorted(self._issues),
            }
            self.state = TOP
            return ev
        return None
