"""Pure geometry helpers. No framework dependencies."""
from __future__ import annotations

import math
from typing import Optional, Sequence

Point = Sequence[float]


def angle_deg(a: Point, b: Point, c: Point) -> Optional[float]:
    """Interior angle at b (degrees, 0-180) formed by a-b-c. None if degenerate."""
    bax, bay = a[0] - b[0], a[1] - b[1]
    bcx, bcy = c[0] - b[0], c[1] - b[1]
    n = math.hypot(bax, bay) * math.hypot(bcx, bcy)
    if n < 1e-6:
        return None
    cos = (bax * bcx + bay * bcy) / n
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def tilt_from_vertical(top: Point, bottom: Point) -> float:
    """Angle (degrees) between the segment bottom->top and the upright vertical.

    0 = perfectly upright, 90 = horizontal. Image y grows downwards.
    """
    dx = top[0] - bottom[0]
    dy = bottom[1] - top[1]
    return abs(math.degrees(math.atan2(dx, dy)))


def rotate(v: Point, deg: float) -> tuple[float, float]:
    r = math.radians(deg)
    cs, sn = math.cos(r), math.sin(r)
    return (v[0] * cs - v[1] * sn, v[0] * sn + v[1] * cs)


def ghost_limb_end(a: Point, b: Point, c: Point, target_deg: float) -> Optional[tuple[float, float]]:
    """Where the distal point c *should* be when the angle at b equals target_deg.

    Keeps the user's limb length and bend direction, so it can be drawn as a
    target guide line the user has to reach.
    """
    bax, bay = a[0] - b[0], a[1] - b[1]
    n = math.hypot(bax, bay)
    if n < 1e-6:
        return None
    length = math.hypot(c[0] - b[0], c[1] - b[1])
    cross = bax * (c[1] - b[1]) - bay * (c[0] - b[0])
    sign = 1.0 if cross >= 0 else -1.0
    ux, uy = bax / n, bay / n
    rx, ry = rotate((ux, uy), sign * target_deg)
    return (b[0] + rx * length, b[1] + ry * length)
