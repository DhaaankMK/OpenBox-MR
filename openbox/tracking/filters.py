"""Filtro One-Euro: suavização adaptativa (estável parado, responsivo em movimento rápido)."""
from __future__ import annotations

import math

import numpy as np


def _alpha(dt: float, cutoff):
    tau = 1.0 / (2.0 * math.pi * np.maximum(cutoff, 1e-6))
    return 1.0 / (1.0 + tau / dt)


class OneEuro:
    """Funciona com escalares ou arrays numpy (cada elemento é filtrado de forma independente)."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.02, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x = None
        self._dx = None
        self._t = None

    def reset(self):
        self._x = self._dx = self._t = None

    def __call__(self, x, t: float):
        x = np.asarray(x, dtype=np.float64)
        if self._x is None:
            self._x, self._dx, self._t = x.copy(), np.zeros_like(x), t
            return x.copy()
        dt = max(t - self._t, 1e-3)
        dx = (x - self._x) / dt
        a_d = _alpha(dt, self.d_cutoff)
        self._dx = a_d * dx + (1.0 - a_d) * self._dx
        cutoff = self.min_cutoff + self.beta * np.abs(self._dx)
        a = _alpha(dt, cutoff)
        self._x = a * x + (1.0 - a) * self._x
        self._t = t
        return self._x.copy()
