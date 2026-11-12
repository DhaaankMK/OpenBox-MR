"""Funções de easing e molas para animações de interface."""
from __future__ import annotations

import math


def clamp01(t: float) -> float:
    return 0.0 if t < 0.0 else 1.0 if t > 1.0 else t


def ease_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 1.0 - (1.0 - t) ** 3


def ease_in_out(t: float) -> float:
    t = clamp01(t)
    return t * t * (3.0 - 2.0 * t)


def ease_out_back(t: float, s: float = 1.70158) -> float:
    t = clamp01(t) - 1.0
    return t * t * ((s + 1.0) * t + s) + 1.0


def lerp(a, b, t):
    return a + (b - a) * t


class Spring:
    """Mola amortecida: segue `target` com leve 'overshoot'."""

    def __init__(self, value=0.0, k=180.0, c=18.0):
        self.x, self.v, self.target, self.k, self.c = value, 0.0, value, k, c

    def update(self, dt: float) -> float:
        dt = min(dt, 1 / 30)
        self.v += (self.k * (self.target - self.x) - self.c * self.v) * dt
        self.x += self.v * dt
        return self.x

    def snap(self, value):
        self.x, self.v, self.target = value, 0.0, value


class Appear:
    """Anima 0→1 ao abrir e 1→0 ao fechar (com easing)."""

    def __init__(self, speed=5.0):
        self.t, self.open, self.speed = 0.0, False, speed

    def update(self, dt):
        self.t = clamp01(self.t + dt * self.speed * (1.0 if self.open else -1.4))
        return self.t

    @property
    def visible(self):
        return self.open or self.t > 0.001

    @property
    def e(self):
        return ease_out_back(self.t) if self.open else ease_out_cubic(self.t)
