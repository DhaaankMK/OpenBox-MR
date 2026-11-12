"""Entrada unificada: mãos (pinça = clique) e mouse viram 'ponteiros' com o mesmo comportamento."""
from __future__ import annotations

import pygame

from .. import theme as T


class Pointer:
    def __init__(self, pid: str, kind: str):
        self.id, self.kind = pid, kind
        self.x = self.y = 0.0
        self.down = False
        self.pressed = False    # ficou pressionado neste frame
        self.released = False   # foi solto neste frame
        self.hand = None        # HandView (se kind == 'hand')
        self.gesture = "NONE"
        self.color = T.TEXT
        self.over_ui = False
        self.hover = None
        self.dwell = 0.0        # 0..1 progresso do clique por permanência
        self.px = self.py = 0.0
        self.speed = 0.0

    @property
    def pos(self):
        return (self.x, self.y)


class InputManager:
    def __init__(self, cfg, hands):
        self.cfg, self.hands = cfg, hands
        self.pointers: list = []
        self.hand_ptrs: dict = {}
        self.mouse = Pointer("mouse", "mouse")
        self.mouse.color = (255, 255, 255)
        self._mouse_prev_down = False
        self._mouse_prev_pos = (0, 0)
        self._mouse_last_active = -99.0

    def update(self, dt: float, now: float, camera_ok: bool):
        ptrs = []
        for hv in self.hands.visible():
            p = self.hand_ptrs.get(hv.slot)
            if p is None:
                p = self.hand_ptrs[hv.slot] = Pointer(f"hand{hv.slot}", "hand")
            p.hand, p.gesture, p.color = hv, hv.gesture, hv.color
            nx, ny = float(hv.ptr[0]), float(hv.ptr[1])
            p.speed = ((nx - p.x) ** 2 + (ny - p.y) ** 2) ** 0.5 / max(dt, 1e-3)
            p.x, p.y = nx, ny
            p.pressed, p.released = hv.pinch_down, hv.pinch_up
            p.down = hv.pinching
            p.over_ui = False
            ptrs.append(p)
        self.hands.clear_edges()

        # Mouse: aparece quando é movido/clicado, ou quando não há mãos/câmera
        mx, my = pygame.mouse.get_pos()
        mdown = bool(pygame.mouse.get_pressed()[0])
        if (mx, my) != self._mouse_prev_pos or mdown or mdown != self._mouse_prev_down:
            self._mouse_last_active = now
        m = self.mouse
        m.pressed, m.released = mdown and not self._mouse_prev_down, (not mdown) and self._mouse_prev_down
        m.down, m.x, m.y, m.over_ui = mdown, float(mx), float(my), False
        self._mouse_prev_down, self._mouse_prev_pos = mdown, (mx, my)
        if self.cfg.mouse_fallback and (now - self._mouse_last_active < 3.0 or (not ptrs and not camera_ok)):
            ptrs.append(m)
        self.pointers = ptrs

    def primary(self):
        return self.pointers[0] if self.pointers else None
