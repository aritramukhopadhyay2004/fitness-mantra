"""Tiny signal smoothing helpers."""
from __future__ import annotations

from typing import Optional


class EMA:
    """Exponential moving average. alpha closer to 1 = more responsive, less smooth."""

    def __init__(self, alpha: float = 0.4):
        self.alpha = alpha
        self.value: Optional[float] = None

    def update(self, x: float) -> float:
        self.value = x if self.value is None else self.alpha * x + (1 - self.alpha) * self.value
        return self.value

    def reset(self) -> None:
        self.value = None
