"""Mapeia coordenadas normalizadas do frame da câmera para pixels da janela (modo 'cover', sem distorção)."""
from __future__ import annotations

import numpy as np


class CameraView:
    def __init__(self, width: int, height: int):
        self.W, self.H = width, height
        self.fw, self.fh = 1280, 720
        self._recalc()

    def set_frame(self, fw: int, fh: int):
        if (fw, fh) != (self.fw, self.fh) and fw > 0 and fh > 0:
            self.fw, self.fh = fw, fh
            self._recalc()

    def _recalc(self):
        self.s = max(self.W / self.fw, self.H / self.fh)
        self.ox = (self.W - self.fw * self.s) / 2.0
        self.oy = (self.H - self.fh * self.s) / 2.0
        self._scale = np.array([self.fw * self.s, self.fh * self.s])
        self._off = np.array([self.ox, self.oy])

    def to_px(self, n):
        return np.asarray(n) * self._scale + self._off

    def vel_to_px(self, v):
        return np.asarray(v) * self._scale

    def size_to_px(self, size_n: float) -> float:
        return float(size_n * self.fw * self.s)

    def crop(self):
        """Retângulo do frame (px da câmera) visível na janela: x, y, w, h."""
        cw = min(self.fw, int(round(self.W / self.s)))
        ch = min(self.fh, int(round(self.H / self.s)))
        cx = max(0, min(self.fw - cw, int(round(-self.ox / self.s))))
        cy = max(0, min(self.fh - ch, int(round(-self.oy / self.s))))
        return cx, cy, cw, ch
