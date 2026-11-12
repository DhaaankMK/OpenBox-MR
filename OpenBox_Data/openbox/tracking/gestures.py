"""Reconhecimento de gestos a partir dos 21 landmarks da mão (invariante a escala e rotação).

Gestos: OPEN, FIST, POINT, GUN (indicador + polegar levantado), PEACE, ROCK, PINCH, THUMBS_UP.
Gatilho de arma ("dedo-pistola"): arma com o polegar levantado; dispara quando o polegar desce.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

Z_WEIGHT = 0.6  # a profundidade do MediaPipe é ruidosa: pesa menos que x/y

# (nome, MCP, PIP, TIP)
FINGERS = (("index", 5, 6, 8), ("middle", 9, 10, 12), ("ring", 13, 14, 16), ("pinky", 17, 18, 20))

GESTURE_NAMES = {
    "NONE": "—", "OPEN": "Palma aberta", "FIST": "Punho", "POINT": "Apontar", "GUN": "Pistola",
    "PEACE": "Paz", "ROCK": "Rock", "PINCH": "Pinça", "THUMBS_UP": "Joinha",
}


def d3(a, b) -> float:
    dx, dy, dz = a[0] - b[0], a[1] - b[1], (a[2] - b[2]) * Z_WEIGHT
    return float((dx * dx + dy * dy + dz * dz) ** 0.5)


@dataclass
class GestureInfo:
    size: float
    pinch_ratio: float
    pinching: bool
    fingers: Tuple[bool, bool, bool, bool, bool]  # polegar, indicador, médio, anelar, mindinho
    gesture: str
    grabbing: bool
    swipe: Optional[str] = None
    curl: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)   # 0 = esticado, 1 = dobrado (indicador..mindinho)
    pinch_strength: float = 0.0
    armed: bool = False       # dedo-pistola pronta (polegar levantado)
    trigger: bool = False     # gatilho puxado (polegar abaixado depois de armado)
    aim: Tuple[float, float] = (0.0, -1.0)   # direção do indicador (vetor unitário, mesmo espaço do frame)


class HandAnalyzer:
    """Mantém estado por mão: histerese da pinça, debounce de gestos, gatilho e swipe."""

    def __init__(self):
        self.pinching = False
        self.gesture = "NONE"
        self._cand = "NONE"
        self._cand_n = 0
        self._eng_n = 0
        self._hist: deque = deque()
        self._last_swipe = -10.0
        self.armed = False
        self.trigger = False
        self._up_n = 0

    def update(self, P: np.ndarray, palm_n, t: float, engage: float, release: float,
               fist_grab: bool = True) -> GestureInfo:
        """P: (21,3) em unidades de pixel do frame (x*W, y*H, z*W). palm_n: (x,y) normalizado."""
        size = max(d3(P[0], P[9]), 1e-6)
        ratio = d3(P[4], P[8]) / size

        # Pinça: fecha < engage (2 frames, ou na hora se for decisiva) · abre > release
        if self.pinching:
            if ratio > release:
                self.pinching = False
                self._eng_n = 0
        elif ratio < engage:
            self._eng_n += 1
            if self._eng_n >= 2 or ratio < engage * 0.75:
                self.pinching = True
        else:
            self._eng_n = 0

        # Dedos estendidos: ponta mais longe do pulso que a articulação PIP
        ext, curl = [], []
        thumb = d3(P[4], P[17]) > d3(P[3], P[17]) * 1.05 and d3(P[4], P[5]) > 0.55 * size
        ext.append(thumb)
        for _, mcp, pip, tip in FINGERS:
            ext.append(d3(P[tip], P[0]) > d3(P[pip], P[0]) + 0.10 * size)
            e = d3(P[tip], P[0]) / max(d3(P[mcp], P[0]), 1e-6)
            curl.append(float(min(1.0, max(0.0, (1.9 - e) / 1.0))))
        _, idx, mid, ring, pinky = ext
        n = int(idx) + int(mid) + int(ring) + int(pinky)

        thumb_d = d3(P[4], P[5]) / size
        gun_pose = idx and not mid and not ring and not pinky

        if self.pinching:
            raw = "PINCH"
        elif n == 4:
            raw = "OPEN"
        elif n == 0:
            raw = "THUMBS_UP" if (thumb and P[4][1] < P[0][1] - 0.6 * size) else "FIST"
        elif gun_pose:
            raw = "GUN" if thumb_d > 0.62 else "POINT"
        elif idx and mid and not ring and not pinky:
            raw = "PEACE"
        elif idx and pinky and not mid and not ring:
            raw = "ROCK"
        else:
            raw = "NONE"

        if raw == "PINCH":
            self.gesture, self._cand, self._cand_n = raw, raw, 0
        elif raw == self.gesture:
            self._cand, self._cand_n = raw, 0
        else:
            if raw == self._cand:
                self._cand_n += 1
            else:
                self._cand, self._cand_n = raw, 1
            if self._cand_n >= 2:
                self.gesture = raw

        # Gatilho: levanta o polegar para armar; ao abaixar, dispara
        if gun_pose and not self.pinching:
            if thumb_d > 0.62:
                self._up_n += 1
                self.trigger = False
                if self._up_n >= 2:
                    self.armed = True
            elif thumb_d < 0.48:
                self._up_n = 0
                if self.armed:
                    self.trigger = True
        else:
            self.armed = self.trigger = False
            self._up_n = 0

        swipe = self._detect_swipe(palm_n, t)
        grabbing = self.pinching or (fist_grab and self.gesture == "FIST")
        a = P[8][:2] - P[5][:2]
        an = float((a[0] ** 2 + a[1] ** 2) ** 0.5) or 1.0
        strength = float(min(1.0, max(0.0, (0.85 - ratio) / max(0.85 - engage, 0.05))))
        return GestureInfo(size, ratio, self.pinching, tuple(ext), self.gesture, grabbing, swipe,
                           tuple(curl), strength, self.armed, self.trigger, (float(a[0] / an), float(a[1] / an)))

    def _detect_swipe(self, palm_n, t: float) -> Optional[str]:
        self._hist.append((t, float(palm_n[0]), float(palm_n[1])))
        while self._hist and t - self._hist[0][0] > 0.32:
            self._hist.popleft()
        if self.gesture != "OPEN" or t - self._last_swipe < 0.8 or len(self._hist) < 3:
            return None
        _, x0, y0 = self._hist[0]
        _, x1, y1 = self._hist[-1]
        dx, dy = x1 - x0, y1 - y0
        if abs(dx) > 0.26 and abs(dy) < 0.5 * abs(dx):
            self._last_swipe = t
            self._hist.clear()
            return "right" if dx > 0 else "left"
        return None
