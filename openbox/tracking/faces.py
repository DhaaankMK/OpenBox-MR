"""Rostos no thread principal: mapeia para pixels, suaviza e anima a física dos chapéus (mola)."""
from __future__ import annotations

import math

import numpy as np

from .face_tracker import POS


class FaceView:
    def __init__(self, slot: int):
        self.slot = slot
        self.visible = False
        self.stale = False
        self.pts = None            # dict nome -> (x, y) px suavizado
        self._target = None
        self.width = 160.0
        self.roll = self.yaw = self.pitch = 0.0
        self.mouth_open = self.blink_l = self.blink_r = self.smile = 0.0
        self.hat_pos = None
        self.hat_vel = np.zeros(2)
        self.anchor = np.zeros(2)
        self._prev_anchor = None
        self.center = np.zeros(2)
        self.vel = np.zeros(2)
        self._prev_center = None

    def ingest(self, f, view):
        px = view.to_px(f.n[:, :2])
        self._target = px
        self.width = view.size_to_px(f.width_n)
        self.roll, self.yaw, self.pitch = f.roll, f.yaw, f.pitch
        self.mouth_open, self.blink_l, self.blink_r, self.smile = f.mouth_open, f.blink_l, f.blink_r, f.smile
        self.stale = f.stale
        if not self.visible or self.pts is None:
            self.pts = px.copy()
            self.hat_pos = None
        self.visible = True

    def lost(self):
        self.visible = False
        self.hat_pos = None
        self.pts = None
        self._prev_center = None
        self.vel = np.zeros(2)

    def advance(self, dt):
        if not self.visible or self._target is None:
            return
        k = 1.0 - math.exp(-dt * 30.0)
        self.pts += (self._target - self.pts) * k
        c = (self.p("top") + self.p("chin")) / 2
        if self._prev_center is not None and dt > 1e-4:
            self.vel = 0.6 * self.vel + 0.4 * (c - self._prev_center) / dt
        self._prev_center, self.center = c.copy(), c
        a = self.p("top") + (self.p("top") - self.p("chin")) * 0.06      # um pouco acima da testa
        self.anchor = a
        if self.hat_pos is None:
            self.hat_pos, self.hat_vel = a.copy(), np.zeros(2)
        else:   # mola subamortecida: o chapéu "balança" quando a cabeça se move
            acc = 220.0 * (a - self.hat_pos) - 16.0 * self.hat_vel
            self.hat_vel = self.hat_vel + acc * dt
            self.hat_pos = self.hat_pos + self.hat_vel * dt
            if float(np.hypot(*(a - self.hat_pos))) > self.width * 1.2:
                self.hat_pos = a.copy()

    def p(self, key: str) -> np.ndarray:
        return self.pts[POS[key]]

    @property
    def eye_l(self):
        a, b = self.p("eye_l_o"), self.p("eye_l_i")
        return (a + b) / 2

    @property
    def eye_r(self):
        a, b = self.p("eye_r_o"), self.p("eye_r_i")
        return (a + b) / 2

    @property
    def mouth(self):
        return (self.p("lip_up") + self.p("lip_lo")) / 2

    @property
    def hat_tilt(self) -> float:
        if self.hat_pos is None:
            return 0.0
        return float(np.clip((self.hat_pos[0] - self.anchor[0]) * 0.006, -0.5, 0.5))


class FacesManager:
    def __init__(self, tracker, cfg, view):
        self.tracker, self.cfg, self.view = tracker, cfg, view
        self.views = {0: FaceView(0), 1: FaceView(1)}
        self._seq = -1
        self.head = (0.0, 0.0)
        self.has_head = False
        self.fps = 0.0
        self.infer_ms = 0.0

    def update(self, dt, now):
        snap = self.tracker.snapshot
        if snap.seq != self._seq:
            self._seq = snap.seq
            self.fps, self.infer_ms = snap.fps, snap.infer_ms
            present = set()
            for f in snap.faces:
                self.views[f.slot].ingest(f, self.view)
                present.add(f.slot)
            for slot, fv in self.views.items():
                if slot not in present and fv.visible:
                    fv.lost()
            if snap.faces:
                n = snap.faces[0].n[POS["nose"]]
                tx, ty = (n[0] - 0.5) * 2.0, (n[1] - 0.5) * 2.0
                self.head = (self.head[0] + (tx - self.head[0]) * 0.5, self.head[1] + (ty - self.head[1]) * 0.5)
                self.has_head = True
            else:
                self.has_head = False
        for fv in self.views.values():
            fv.advance(dt)

    def visible(self):
        return [fv for fv in self.views.values() if fv.visible]

    def colliders(self):
        """A cabeça também é um corpo: bolas quicam no rosto."""
        if not self.cfg.hand_colliders:
            return []
        return [(float(fv.center[0]), float(fv.center[1]), fv.width * 0.42, float(fv.vel[0]), float(fv.vel[1]))
                for fv in self.views.values() if fv.visible and not fv.stale]
