"""Synthetic side-view skeletons so the logic can be tested without a camera or model."""
from __future__ import annotations

import math

from core.geometry import rotate

NAMES = ["shoulder", "elbow", "wrist", "hip", "knee", "ankle"]


def squat_pose(knee_deg: float, torso_tilt: float = 10.0, vis: float = 0.95, ankle=(300.0, 600.0)) -> dict:
    shank, thigh, torso = 150.0, 150.0, 180.0
    a = ankle
    k = (a[0] + shank * math.sin(math.radians(20)), a[1] - shank * math.cos(math.radians(20)))
    u = (a[0] - k[0], a[1] - k[1])
    n = math.hypot(*u)
    u = (u[0] / n, u[1] / n)
    cands = []
    for sign in (1, -1):
        d = rotate(u, sign * knee_deg)
        cands.append((k[0] + thigh * d[0], k[1] + thigh * d[1]))
    h = min(cands, key=lambda p: p[0])                      # hip sits behind the knee
    s = (h[0] + torso * math.sin(math.radians(torso_tilt)), h[1] - torso * math.cos(math.radians(torso_tilt)))
    e = (s[0], s[1] + 100)
    w = (s[0] + 20, s[1] + 190)
    coords = {"shoulder": s, "elbow": e, "wrist": w, "hip": h, "knee": k, "ankle": a}
    pts = {}
    for side, v in (("left", vis), ("right", 0.1)):
        for name, (x, y) in coords.items():
            pts[f"{side}_{name}"] = (x, y, v)
    return pts


def sweep(a: float, b: float, n: int = 30):
    """Smooth a -> b angle ramp (cosine ease)."""
    return [a + (b - a) * (1 - math.cos(math.pi * i / (n - 1))) / 2 for i in range(n)]


def rep_angles(top=172.0, bottom=85.0, hold=10):
    return sweep(top, bottom) + [bottom] * hold + sweep(bottom, top) + [top] * 8
