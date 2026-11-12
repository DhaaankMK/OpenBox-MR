"""Cena base e gerenciador de cenas com transição em fade."""
from __future__ import annotations

import pygame

from ..ui.widgets import UI


class Scene:
    name = "scene"
    cursors = True      # desenhar cursores das mãos/mouse por cima

    def __init__(self, ctx):
        self.ctx = ctx
        self.ui = UI(ctx)

    def enter(self, **kw): ...
    def exit(self): ...
    def event(self, e): ...
    def update(self, dt: float): ...
    def draw(self, surf): ...


class SceneManager:
    FADE = 0.22

    def __init__(self, ctx):
        self.ctx = ctx
        self.classes: dict = {}
        self.cache: dict = {}
        self.current: Scene | None = None
        self._pending = None
        self._alpha = 0.0          # 0 = visível, 1 = preto
        self._state = "idle"       # idle | out | in
        self._fade_surf = None

    def register(self, name, cls):
        self.classes[name] = cls

    def get(self, name) -> Scene:
        if name not in self.cache:
            self.cache[name] = self.classes[name](self.ctx)
        return self.cache[name]

    def start(self, name, **kw):
        self._switch(name, kw)
        self._alpha, self._state = 1.0, "in"

    def go(self, name, **kw):
        if self._state == "out":
            return
        self._pending = (name, kw)
        self._state = "out"

    def _switch(self, name, kw):
        if self.current is not None:
            self.current.exit()
        self.current = self.get(name)
        self.current.enter(**kw)

    def event(self, e):
        if self.current and self._state == "idle":
            self.current.event(e)

    def update(self, dt):
        if self._state == "out":
            self._alpha = min(1.0, self._alpha + dt / self.FADE)
            if self._alpha >= 1.0 and self._pending:
                name, kw = self._pending
                self._pending = None
                self._switch(name, kw)
                self._state = "in"
        elif self._state == "in":
            self._alpha = max(0.0, self._alpha - dt / self.FADE)
            if self._alpha <= 0.0:
                self._state = "idle"
        if self.current:
            self.current.update(dt)

    def draw(self, surf):
        if self.current:
            self.current.draw(surf)
        if self._alpha > 0.01:
            if self._fade_surf is None or self._fade_surf.get_size() != surf.get_size():
                self._fade_surf = pygame.Surface(surf.get_size())
                self._fade_surf.fill((0, 0, 0))
            self._fade_surf.set_alpha(int(255 * self._alpha))
            surf.blit(self._fade_surf, (0, 0))
