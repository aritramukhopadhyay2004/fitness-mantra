"""CoachEngine: landmarks in -> rep counts, sets, live cues and a session log out.

Framework-free on purpose: no Streamlit / OpenCV / MediaPipe imports, so this file
can move into the MANTRA backend (or be ported to TypeScript) unchanged.

Input per frame: `pts` = {"left_knee": (x, y, visibility), ...} in pixel coordinates.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from core.geometry import angle_deg, tilt_from_vertical
from core.rep_counter import BOTTOM, MOVING, TOP, RepStateMachine
from core.smoothing import EMA
from exercises.configs import Exercise, FormCheck

MIN_VIS = 0.3          # a joint below this visibility is treated as missing
VISIBLE_MEAN = 0.5     # mean visibility of the rep joints needed to coach at all


@dataclass
class FrameState:
    visible: bool = False
    side: Optional[str] = None
    angle: Optional[float] = None
    pct: float = 0.0                         # 0 = top, 1 = target reached
    phase: str = TOP
    cue: str = ""
    cue_level: str = "info"                  # ok | warn | info
    triplet: Optional[list] = None           # 3 (x, y) points of the rep joints
    issue_keys: list = field(default_factory=list)
    reps_in_set: int = 0
    set_no: int = 1
    sets_total: int = 1
    reps_target: int = 10
    resting: bool = False
    rest_left: float = 0.0
    finished: bool = False


class CoachEngine:
    def __init__(self, ex: Exercise, reps_per_set: int = 10, sets: int = 3, rest_s: float = 45.0):
        self.ex = ex
        self.reps_per_set = reps_per_set
        self.sets = sets
        self.rest_s = rest_s
        self.sm = RepStateMachine(ex.extended_above, ex.flexed_below, ex.leave_margin)
        self.set_no = 1
        self.reps_in_set = 0
        self.finished = False
        self.rest_until: Optional[float] = None
        self.records: list[dict] = []
        self._side: Optional[str] = None
        self._angle_ema = EMA(0.45)
        self._check_ema = {c.key: EMA(0.45) for c in ex.checks}
        self._flash: Optional[tuple[str, str, float]] = None   # text, level, until

    # ---------------------------------------------------------------- helpers
    def _pt(self, pts: dict, side: str, joint: str):
        p = pts.get(f"{side}_{joint}")
        return p if p is not None and p[2] >= MIN_VIS else None

    def _side_score(self, pts: dict, side: str) -> float:
        vis = []
        for j in self.ex.joints:
            p = pts.get(f"{side}_{j}")
            if p is None or p[2] < MIN_VIS:
                return 0.0
            vis.append(p[2])
        return sum(vis) / len(vis)

    def _pick_side(self, pts: dict) -> Optional[str]:
        sc = {s: self._side_score(pts, s) for s in ("left", "right")}
        best = max(sc, key=sc.get)
        if sc[best] < VISIBLE_MEAN:
            return None
        if self._side and sc[self._side] >= VISIBLE_MEAN and sc[best] - sc[self._side] < 0.15:
            return self._side                                    # sticky: avoid flicker
        return best

    def _check_value(self, chk: FormCheck, side: str, pts: dict) -> Optional[float]:
        ps = [self._pt(pts, side, j) for j in chk.joints]
        if any(p is None for p in ps):
            return None
        xy = [(p[0], p[1]) for p in ps]
        if chk.kind == "angle":
            return angle_deg(*xy)
        return tilt_from_vertical(xy[0], xy[1])

    def _violations(self, side: str, pts: dict) -> list[FormCheck]:
        bad = []
        for chk in self.ex.checks:
            v = self._check_value(chk, side, pts)
            if v is None:
                continue
            v = self._check_ema[chk.key].update(v)
            if (chk.min is not None and v < chk.min) or (chk.max is not None and v > chk.max):
                bad.append(chk)
        return bad

    def _flash_now(self, text: str, level: str, t: float, secs: float = 1.6) -> None:
        self._flash = (text, level, t + secs)

    # ------------------------------------------------------------------- main
    def process(self, pts: dict, t: float) -> FrameState:
        ex = self.ex
        st = FrameState(
            set_no=self.set_no, sets_total=self.sets, reps_target=self.reps_per_set,
            reps_in_set=self.reps_in_set, finished=self.finished, phase=self.sm.state,
        )
        if self.finished:
            st.cue, st.cue_level = "Workout complete - great job!", "ok"
            return st

        side = self._pick_side(pts)
        if side is None:
            st.cue, st.cue_level = f"Step back - show your full body ({ex.view.lower()})", "warn"
            return st
        if side != self._side:
            self._angle_ema.reset()
            for e in self._check_ema.values():
                e.reset()
            self._side = side

        a, b, c = [self._pt(pts, side, j) for j in ex.joints]
        raw = angle_deg((a[0], a[1]), (b[0], b[1]), (c[0], c[1]))
        if raw is None:
            return st
        angle = self._angle_ema.update(raw)
        st.visible, st.side, st.angle = True, side, angle
        st.triplet = [(a[0], a[1]), (b[0], b[1]), (c[0], c[1])]
        span = ex.extended_above - ex.flexed_below
        st.pct = max(0.0, min(1.0, (ex.extended_above - angle) / span))

        bad = self._violations(side, pts)
        st.issue_keys = [c_.key for c_ in bad]

        # ---- rest between sets
        if self.rest_until is not None:
            if t < self.rest_until:
                st.resting, st.rest_left = True, self.rest_until - t
                st.cue, st.cue_level = f"Rest - set {self.set_no} starts in {int(st.rest_left) + 1}s", "info"
                return st
            self.rest_until = None
            self.sm.reset()

        # ---- rep detection (form issues only count while a rep is in progress)
        active_issues = {c_.key for c_ in bad} if self.sm.state != TOP else set()
        ev = self.sm.update(angle, t, active_issues)
        st.phase = self.sm.state

        if ev:
            self._on_event(ev, t)
            st.reps_in_set, st.set_no, st.finished = self.reps_in_set, self.set_no, self.finished
            st.phase = self.sm.state

        st.cue, st.cue_level = self._cue(st, bad, t)
        return st

    def _on_event(self, ev: dict, t: float) -> None:
        ex = self.ex
        depth = (ex.extended_above - ev["min_angle"]) / (ex.extended_above - ex.flexed_below)
        counted = ev["kind"] == "rep"
        rec = {
            "set": self.set_no,
            "rep": self.reps_in_set + 1 if counted else None,
            "counted": counted,
            "min_angle": round(ev["min_angle"], 1),
            "depth_pct": round(max(0.0, min(depth, 1.2)) * 100),
            "duration_s": round(ev["duration"], 2),
            "issues": [c.cue for c in ex.checks if c.key in ev["issues"]],
        }
        self.records.append(rec)

        if not counted:
            self._flash_now(ex.cue_low + " (rep not counted)", "warn", t, 2.0)
            return

        self.reps_in_set += 1
        txt = f"Rep {self.reps_in_set} - nice depth" if not rec["issues"] else f"Rep {self.reps_in_set} - {rec['issues'][0]}"
        self._flash_now(txt, "ok" if not rec["issues"] else "warn", t)

        if self.reps_in_set >= self.reps_per_set:
            if self.set_no >= self.sets:
                self.finished = True
            else:
                self.set_no += 1
                self.reps_in_set = 0
                self.rest_until = t + self.rest_s
                self.sm.reset()

    def _cue(self, st: FrameState, bad: list[FormCheck], t: float) -> tuple[str, str]:
        if self._flash and t < self._flash[2]:
            return self._flash[0], self._flash[1]
        if st.finished:
            return "Workout complete - great job!", "ok"
        if st.phase != TOP and bad:
            return bad[0].cue, "warn"
        if st.phase == BOTTOM:
            return "Good depth - now drive up", "ok"
        if st.phase == MOVING and st.angle is not None:
            if st.angle > self.sm.min_angle + 12 and self.sm.min_angle > self.ex.flexed_below:
                return self.ex.cue_low, "warn"
        return "", "info"

    # ---------------------------------------------------------------- summary
    def summary(self) -> dict:
        counted = [r for r in self.records if r["counted"]]
        issues = Counter(i for r in counted for i in r["issues"])
        partial = [r for r in self.records if not r["counted"]]
        return {
            "exercise": self.ex.label,
            "view": self.ex.view,
            "plan": {"sets": self.sets, "reps_per_set": self.reps_per_set},
            "reps_counted": len(counted),
            "clean_reps": sum(1 for r in counted if not r["issues"]),
            "partial_reps": len(partial),
            "avg_depth_pct": round(sum(r["depth_pct"] for r in counted) / len(counted)) if counted else 0,
            "avg_rep_seconds": round(sum(r["duration_s"] for r in counted) / len(counted), 2) if counted else 0,
            "form_issue_counts": dict(issues),
            "sets_completed": self.set_no - 1 + (1 if self.finished else 0),
            "records": self.records,
        }
