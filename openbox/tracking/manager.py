"""Estado das mãos no thread principal: interpolação a 60 FPS, compensação de latência,
ponteiros estáveis, velocidade de arremesso e colisores para a física."""
from __future__ import annotations

import math
from collections import deque

import numpy as np

from .filters import OneEuro

HAND_COLORS = [(0, 228, 255), (255, 84, 214)]
TIPS = (4, 8, 12, 16, 20)
PALM_IDS = [0, 5, 9, 13, 17]


def _clamp01(v):
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def fit_velocity(samples, window: float = 0.12, now: float | None = None):
    """Regressão linear (mínimos quadrados) sobre amostras (t, x, y) recentes -> (vx, vy) em px/s."""
    if len(samples) < 3:
        return 0.0, 0.0
    t_last = samples[-1][0]
    if now is not None and now - t_last > 0.2:
        return 0.0, 0.0
    pts = [s for s in samples if t_last - s[0] <= window]
    if len(pts) < 3:
        pts = list(samples)[-3:]
    ts = np.array([p[0] for p in pts]) - pts[0][0]
    if ts[-1] < 1e-3:
        return 0.0, 0.0
    A = np.vstack([ts, np.ones_like(ts)]).T
    vx = np.linalg.lstsq(A, np.array([p[1] for p in pts]), rcond=None)[0][0]
    vy = np.linalg.lstsq(A, np.array([p[2] for p in pts]), rcond=None)[0][0]
    return float(vx), float(vy)


class HandView:
    def __init__(self, slot: int):
        self.slot = slot
        self.color = HAND_COLORS[slot % len(HAND_COLORS)]
        self.reset()

    def reset(self):
        self.visible = False
        self.stale = False
        self.label = "?"
        self.gesture = "NONE"
        self.pinching = False
        self.grabbing = False
        self.fingers = (False,) * 5
        self.aim = np.array([0.0, -1.0])
        self.trigger = False
        self.armed = False
        self.curl = (0.0, 0.0, 0.0, 0.0)
        self.pinch_ratio = 1.0
        self.size_px = 100.0
        self.target = None
        self.disp = None
        self.prev_disp = None
        self.vel_pts = np.zeros((21, 2))
        self.vel_px = np.zeros(2)
        self.t_capture = 0.0
        self.samples = deque(maxlen=14)
        self.ptr_filter = OneEuro(min_cutoff=1.3, beta=0.012)
        self.ptr = np.zeros(2)
        self.index_tip = self.thumb_tip = self.mid = self.palm = np.zeros(2)
        self.pinch_down = self.pinch_up = self.grab_down = self.grab_up = False
        self._prev_pinch = self._prev_grab = False

    # ------------------------------------------------------------ dados novos do tracker
    def ingest(self, h, view, t):
        first = not self.visible
        self.visible, self.stale = True, h.stale
        self.label, self.gesture, self.fingers = h.label, h.info.gesture, h.info.fingers
        self.pinch_ratio = h.info.pinch_ratio
        self.aim = np.array(h.info.aim)
        self.trigger, self.armed, self.curl = h.info.trigger and not h.stale, h.info.armed, h.info.curl
        self.size_px = view.size_to_px(h.size_n)
        self.target = view.to_px(h.n[:, :2])
        self.vel_px = view.vel_to_px(h.vel_n)
        self.t_capture = t
        if first or self.disp is None:
            self.disp = self.target.copy()
            self.prev_disp = self.disp.copy()
            self.ptr_filter.reset()
            self.samples.clear()
            self.vel_pts[:] = 0
        if h.stale:
            return
        pinching, grabbing = h.info.pinching, h.info.grabbing
        if pinching and not self._prev_pinch:
            self.pinch_down = True
        if not pinching and self._prev_pinch:
            self.pinch_up = True
        if grabbing and not self._prev_grab:
            self.grab_down = True
        if not grabbing and self._prev_grab:
            self.grab_up = True
        self._prev_pinch, self._prev_grab = pinching, grabbing
        self.pinching, self.grabbing = pinching, grabbing
        g = (self.target[4] + self.target[8]) / 2 if pinching else self.target[PALM_IDS].mean(axis=0)
        self.samples.append((t, float(g[0]), float(g[1])))

    def lost(self):
        """A mão sumiu de vez: gera os eventos de soltar."""
        if self._prev_pinch:
            self.pinch_up = True
        if self._prev_grab:
            self.grab_up = True
        self._prev_pinch = self._prev_grab = False
        self.pinching = self.grabbing = False
        self.visible = False
        self.disp = None

    def clear_edges(self):
        self.pinch_down = self.pinch_up = self.grab_down = self.grab_up = False

    # ------------------------------------------------------------ a cada frame de render
    def advance(self, dt, now, cfg, view):
        if self.target is None or not self.visible:
            return
        age = max(0.0, now - self.t_capture)
        ext = min(age, 0.12) * cfg.prediction
        shift = self.vel_px * ext * 0.7
        lim = 0.06 * view.W
        n = float(np.hypot(*shift))
        if n > lim:
            shift = shift * (lim / n)
        goal = self.target + shift
        if self.disp is None:
            self.disp = goal.copy()
        if float(np.abs(goal[9] - self.disp[9]).max()) > 260:
            self.disp = goal.copy()  # salto grande: ressincroniza
        else:
            self.disp += (goal - self.disp) * (1.0 - math.exp(-dt * 38.0))
        if self.prev_disp is not None and dt > 1e-4:
            self.vel_pts = 0.5 * self.vel_pts + 0.5 * (self.disp - self.prev_disp) / dt
        self.prev_disp = self.disp.copy()

        d = self.disp
        self.index_tip, self.thumb_tip = d[8], d[4]
        self.mid = (d[4] + d[8]) / 2.0
        self.palm = d[PALM_IDS].mean(axis=0)
        w = _clamp01((0.85 - self.pinch_ratio) / 0.5)
        raw = self.index_tip * (1.0 - w) + self.mid * w   # ao pinçar, o cursor migra para o ponto da pinça
        self.ptr = self.ptr_filter(raw, now)

    # ------------------------------------------------------------ utilidades
    @property
    def grab_point(self):
        return self.mid if self.pinching else self.palm

    def throw_velocity(self, window: float = 0.12, now: float | None = None):
        """Velocidade (px/s) por regressão linear das últimas amostras (robusta a ruído)."""
        return fit_velocity(self.samples, window, now)

    def colliders(self, cfg):
        if not self.visible or self.stale or self.grabbing or not cfg.hand_colliders or self.disp is None:
            return []
        r = max(cfg.post["collider_min"], self.size_px * 0.16)
        out = [(float(self.disp[i][0]), float(self.disp[i][1]), r,
                float(self.vel_pts[i][0]), float(self.vel_pts[i][1])) for i in TIPS]
        pv = self.vel_pts[PALM_IDS].mean(axis=0)
        out.append((float(self.palm[0]), float(self.palm[1]), self.size_px * 0.55, float(pv[0]), float(pv[1])))
        return out


class HandsManager:
    def __init__(self, tracker, cfg, view):
        self.tracker, self.cfg, self.view = tracker, cfg, view
        self.views = {0: HandView(0), 1: HandView(1)}
        self._seq = -1
        self.latency = 0.0
        self.fps = 0.0
        self.infer_ms = 0.0
        self.swipes: list = []

    def update(self, dt: float, now: float):
        snap = self.tracker.snapshot
        if snap.seq != self._seq:
            self._seq = snap.seq
            self.latency = max(0.0, now - snap.t)
            self.fps, self.infer_ms = snap.fps, snap.infer_ms
            present = set()
            for h in snap.hands:
                self.views[h.slot].ingest(h, self.view, snap.t)
                present.add(h.slot)
            for slot, hv in self.views.items():
                if slot not in present and hv.visible:
                    hv.lost()
        while self.tracker.events:
            self.swipes.append(self.tracker.events.popleft())
        for hv in self.views.values():
            hv.color = self.cfg.hand_color(hv.slot)
            hv.advance(dt, now, self.cfg, self.view)

    def visible(self):
        return [hv for hv in self.views.values() if hv.visible]

    def clear_edges(self):
        for hv in self.views.values():
            hv.clear_edges()

    def colliders(self):
        out = []
        for hv in self.views.values():
            out.extend(hv.colliders(self.cfg))
        return out
