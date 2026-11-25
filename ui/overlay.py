"""Draws the coaching overlay onto a BGR frame (burned into the video, so it also
survives the browser's native full-screen mode)."""
from __future__ import annotations

import math

import cv2
import numpy as np

from core.engine import FrameState
from core.geometry import ghost_limb_end
from exercises.configs import Exercise

GREEN = (90, 220, 110)
RED = (70, 70, 245)
AMBER = (0, 190, 255)
WHITE = (245, 245, 245)
DARK = (25, 25, 25)
LEVEL_COLOR = {"ok": GREEN, "warn": AMBER, "info": WHITE}

CONNECTIONS = [
    ("left_shoulder", "right_shoulder"), ("left_hip", "right_hip"),
    ("left_shoulder", "left_hip"), ("right_shoulder", "right_hip"),
    ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
    ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
]


def _i(p):
    return int(round(p[0])), int(round(p[1]))


def text(img, s, org, scale, color=WHITE, thick=2, anchor="left"):
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), _ = cv2.getTextSize(s, font, scale, thick)
    x, y = org
    if anchor == "center":
        x -= tw // 2
    elif anchor == "right":
        x -= tw
    cv2.putText(img, s, (x, y), font, scale, DARK, thick + 3, cv2.LINE_AA)
    cv2.putText(img, s, (x, y), font, scale, color, thick, cv2.LINE_AA)
    return tw, th


def dashed_line(img, p1, p2, color, thick=3, dash=14):
    x1, y1 = p1
    x2, y2 = p2
    dist = math.hypot(x2 - x1, y2 - y1)
    if dist < 1:
        return
    n = int(dist // dash)
    for k in range(0, n, 2):
        a = k * dash / dist
        b = min((k + 1) * dash / dist, 1.0)
        cv2.line(img, _i((x1 + (x2 - x1) * a, y1 + (y2 - y1) * a)),
                 _i((x1 + (x2 - x1) * b, y1 + (y2 - y1) * b)), color, thick, cv2.LINE_AA)


def panel(img, x, y, w, h, alpha=0.55):
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, img.shape[1]), min(y + h, img.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    roi = img[y0:y1, x0:x1]
    img[y0:y1, x0:x1] = cv2.addWeighted(roi, 1 - alpha, np.full_like(roi, 20), alpha, 0)


def draw_skeleton(img, pts, color=WHITE):
    for a, b in CONNECTIONS:
        pa, pb = pts.get(a), pts.get(b)
        if pa and pb and pa[2] > 0.3 and pb[2] > 0.3:
            cv2.line(img, _i(pa), _i(pb), color, 3, cv2.LINE_AA)
    for p in pts.values():
        if p[2] > 0.3:
            cv2.circle(img, _i(p), 5, DARK, -1, cv2.LINE_AA)
            cv2.circle(img, _i(p), 3, color, -1, cv2.LINE_AA)


def draw_gauge(img, st: FrameState, k):
    h, w = img.shape[:2]
    bw, top, bot = int(34 * k), int(h * 0.22), int(h * 0.80)
    x = w - int(70 * k)
    panel(img, x - 8, top - int(34 * k), bw + 16, bot - top + int(52 * k))
    cv2.rectangle(img, (x, top), (x + bw, bot), (90, 90, 90), 2)
    fill_top = int(bot - (bot - top) * st.pct)
    color = GREEN if st.pct >= 1.0 else (AMBER if st.pct >= 0.6 else RED)
    cv2.rectangle(img, (x + 2, fill_top), (x + bw - 2, bot - 2), color, -1)
    cv2.line(img, (x - 10, top), (x + bw + 10, top), GREEN, 3, cv2.LINE_AA)       # target line
    text(img, "TARGET", (x + bw // 2, top - int(10 * k)), 0.42 * k, GREEN, 1, "center")
    text(img, f"{int(st.pct * 100)}%", (x + bw // 2, bot + int(26 * k)), 0.6 * k, color, 2, "center")


def draw_overlay(img: np.ndarray, st: FrameState, ex: Exercise, pts: dict, paused: bool = False) -> np.ndarray:
    h, w = img.shape[:2]
    k = max(h / 720.0, 0.6)

    bad = bool(st.issue_keys) and st.phase != "TOP"
    draw_skeleton(img, pts, RED if bad else WHITE)

    if st.visible and st.triplet:
        a, b, c = st.triplet
        # target (ghost) position of the end that travels
        if ex.mode == "hold":
            target_deg = (ex.hold_min + ex.hold_max) / 2
        elif ex.direction == "extend":
            target_deg = ex.extended_above
        else:
            target_deg = ex.flexed_below
        g = ghost_limb_end(c, b, a, target_deg) if ex.moving_end == "a" else ghost_limb_end(a, b, c, target_deg)
        if g:
            col = GREEN if st.pct >= 1.0 else (140, 235, 150)
            dashed_line(img, _i(b), _i(g), col, max(2, int(3 * k)))
            cv2.circle(img, _i(g), int(11 * k), col, 2, cv2.LINE_AA)
        # live working limb
        lc = GREEN if st.pct >= 1.0 else AMBER
        cv2.line(img, _i(a), _i(b), lc, int(5 * k), cv2.LINE_AA)
        cv2.line(img, _i(b), _i(c), lc, int(5 * k), cv2.LINE_AA)
        cv2.circle(img, _i(b), int(9 * k), lc, -1, cv2.LINE_AA)
        text(img, f"{int(st.angle)}°", (int(b[0]) + int(16 * k), int(b[1]) - int(10 * k)), 0.9 * k, lc, 2)
        draw_gauge(img, st, k)

    # HUD (top-left)
    panel(img, 12, 12, int(330 * k), int(112 * k))
    text(img, ex.label.upper(), (26, int(44 * k)), 0.9 * k, WHITE, 2)
    text(img, f"SET {st.set_no}/{st.sets_total}", (26, int(80 * k)), 0.75 * k, AMBER, 2)
    text(img, f"REP {st.reps_in_set}/{st.reps_target}", (26, int(112 * k)), 0.75 * k, GREEN, 2)

    # coaching cue (bottom-centre)
    if st.cue:
        (tw, th), _ = cv2.getTextSize(st.cue, cv2.FONT_HERSHEY_SIMPLEX, 0.95 * k, 2)
        px, py = (w - tw) // 2 - 20, h - int(95 * k)
        panel(img, px, py, tw + 40, th + int(34 * k), 0.65)
        text(img, st.cue, (w // 2, py + th + int(14 * k)), 0.95 * k, LEVEL_COLOR.get(st.cue_level, WHITE), 2, "center")

    if paused:
        panel(img, 0, 0, w, h, 0.45)
        text(img, "PAUSED", (w // 2, h // 2), 2.0 * k, AMBER, 4, "center")
    return img
