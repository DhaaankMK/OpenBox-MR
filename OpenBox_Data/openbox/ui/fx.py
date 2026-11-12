"""Efeitos visuais: partículas, ondas de choque, textos flutuantes e flash de tela."""
from __future__ import annotations

import math
import random

import pygame

from .. import theme as T
from . import draw


class FX:
    def __init__(self, cfg):
        self.cfg = cfg
        self.particles: list = []   # [x, y, vx, vy, vida, vida_max, cor, tamanho]
        self.rings: list = []       # [x, y, raio, raio_max, vida, vida_max, cor]
        self.popups: list = []      # [x, y, texto, vida, cor, tamanho]
        self.flash_color = (255, 255, 255)
        self.flash_alpha = 0.0
        self._flash_surf = None

    @property
    def density(self) -> float:
        return self.cfg.q["particles"] if self.cfg.particles else 0.0

    def burst(self, x, y, color=T.CYAN, n=18, speed=300.0, size=3.0, life=0.7):
        n = int(n * self.density)
        for _ in range(n):
            a, v = random.uniform(0, math.tau), random.uniform(0.25, 1.0) * speed
            self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v, life * random.uniform(0.6, 1.0), life, color, size])
        if len(self.particles) > 450:
            del self.particles[:len(self.particles) - 450]

    def ring(self, x, y, color=T.CYAN, max_r=90.0, life=0.5):
        if self.density > 0:
            self.rings.append([x, y, 4.0, max_r, life, life, color])

    def popup(self, x, y, s, color=T.TEXT, size=28):
        self.popups.append([x, y, str(s), 0.9, color, size])

    def flash(self, color, alpha=90):
        self.flash_color, self.flash_alpha = color, float(alpha)

    def update(self, dt: float):
        keep = []
        for p in self.particles:
            p[4] -= dt
            if p[4] > 0:
                p[0] += p[2] * dt
                p[1] += p[3] * dt
                damp = max(0.0, 1.0 - 2.4 * dt)
                p[2] *= damp
                p[3] *= damp
                keep.append(p)
        self.particles = keep
        for r in self.rings:
            r[4] -= dt
            r[2] += (r[3] - r[2]) * min(1.0, dt * 7.0)
        self.rings = [r for r in self.rings if r[4] > 0]
        for p in self.popups:
            p[3] -= dt
            p[1] -= 60 * dt
        self.popups = [p for p in self.popups if p[3] > 0]
        self.flash_alpha = max(0.0, self.flash_alpha - 260 * dt)

    def draw(self, surf):
        for p in self.particles:
            k = p[4] / p[5]
            draw.glow(surf, (p[0], p[1]), 4 + p[7] * 3.5 * k, p[6], 0.5 + 0.5 * k)
        for r in self.rings:
            k = r[4] / r[5]
            draw.ring(surf, (r[0], r[1]), r[2], r[6], 3, int(220 * k))
        for p in self.popups:
            a = int(255 * min(1.0, p[3] / 0.35))
            draw.text(surf, p[2], (p[0], p[1]), p[5], p[4], True, "c", a, shadow=True)
        if self.flash_alpha > 1:
            if self._flash_surf is None or self._flash_surf.get_size() != surf.get_size():
                self._flash_surf = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            self._flash_surf.fill((*self.flash_color, int(self.flash_alpha)))
            surf.blit(self._flash_surf, (0, 0))
