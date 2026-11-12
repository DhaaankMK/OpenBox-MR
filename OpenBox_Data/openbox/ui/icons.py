"""Ícones vetoriais desenhados com primitivas do pygame (sem arquivos de imagem)."""
from __future__ import annotations

import math

import pygame


def _poly(surf, color, pts, w, closed=True):
    pygame.draw.lines(surf, color, closed, [(int(x), int(y)) for x, y in pts], w)


def draw(name: str, surf, cx: float, cy: float, s: float = 12, color=(255, 255, 255), w: int = 2):
    """Desenha o ícone `name` centrado em (cx, cy) com 'raio' s."""
    f = _ICONS.get(name)
    if f:
        f(surf, cx, cy, s, color, w)


def _orb(surf, cx, cy, s, c, w):
    pygame.draw.circle(surf, c, (int(cx), int(cy)), int(s * 0.85), w)
    pygame.draw.arc(surf, c, pygame.Rect(cx - s * 0.5, cy - s * 0.5, s, s), 1.6, 2.9, max(1, w - 1))


def _cube(surf, cx, cy, s, c, w):
    pts = [(cx + s * math.cos(math.radians(-90 + 60 * k)), cy + s * math.sin(math.radians(-90 + 60 * k))) for k in range(6)]
    _poly(surf, c, pts, w)
    for k in (1, 3, 5):
        pygame.draw.line(surf, c, (cx, cy), pts[k], max(1, w - 1))


def _crystal(surf, cx, cy, s, c, w):
    pts = [(cx, cy - s), (cx + s * 0.72, cy - s * 0.15), (cx, cy + s), (cx - s * 0.72, cy - s * 0.15)]
    _poly(surf, c, pts, w)
    pygame.draw.line(surf, c, pts[3], pts[1], max(1, w - 1))
    pygame.draw.line(surf, c, (cx - s * 0.3, cy - s * 0.15), (cx, cy - s), max(1, w - 1))


def _target(surf, cx, cy, s, c, w):
    pygame.draw.circle(surf, c, (int(cx), int(cy)), int(s), w)
    pygame.draw.circle(surf, c, (int(cx), int(cy)), int(s * 0.55), w)
    pygame.draw.circle(surf, c, (int(cx), int(cy)), max(1, int(s * 0.18)))


def _trash(surf, cx, cy, s, c, w):
    pygame.draw.rect(surf, c, pygame.Rect(cx - s * 0.6, cy - s * 0.4, s * 1.2, s * 1.3), w, border_radius=3)
    pygame.draw.line(surf, c, (cx - s * 0.85, cy - s * 0.5), (cx + s * 0.85, cy - s * 0.5), w)
    pygame.draw.rect(surf, c, pygame.Rect(cx - s * 0.25, cy - s * 0.85, s * 0.5, s * 0.35), w)
    for dx in (-0.25, 0.25):
        pygame.draw.line(surf, c, (cx + s * dx, cy - s * 0.1), (cx + s * dx, cy + s * 0.55), max(1, w - 1))


def _gravity(surf, cx, cy, s, c, w):
    pygame.draw.line(surf, c, (cx, cy - s), (cx, cy + s * 0.6), w)
    _poly(surf, c, [(cx - s * 0.5, cy + s * 0.1), (cx, cy + s * 0.65), (cx + s * 0.5, cy + s * 0.1)], w, False)
    pygame.draw.line(surf, c, (cx - s * 0.8, cy + s), (cx + s * 0.8, cy + s), w)


def _trail(surf, cx, cy, s, c, w):
    for i, k in enumerate((0.34, 0.5, 0.72)):
        pygame.draw.circle(surf, c, (int(cx - s * 0.7 + i * s * 0.7), int(cy + s * 0.5 - i * s * 0.5)), int(s * k), w)


def _hand(surf, cx, cy, s, c, w):
    pygame.draw.rect(surf, c, pygame.Rect(cx - s * 0.6, cy - s * 0.05, s * 1.2, s * 0.95), w, border_radius=int(s * 0.35))
    for i in range(4):
        x = cx - s * 0.45 + i * s * 0.3
        pygame.draw.line(surf, c, (x, cy), (x, cy - s * (0.8 if i in (1, 2) else 0.6)), w)
    pygame.draw.line(surf, c, (cx - s * 0.6, cy + s * 0.25), (cx - s * 0.95, cy - s * 0.15), w)


def _gear(surf, cx, cy, s, c, w):
    pygame.draw.circle(surf, c, (int(cx), int(cy)), int(s * 0.55), w)
    for k in range(8):
        a = k * math.pi / 4
        pygame.draw.line(surf, c, (cx + math.cos(a) * s * 0.7, cy + math.sin(a) * s * 0.7),
                         (cx + math.cos(a) * s, cy + math.sin(a) * s), w + 1)


def _play(surf, cx, cy, s, c, w):
    pygame.draw.polygon(surf, c, [(cx - s * 0.6, cy - s * 0.8), (cx + s * 0.85, cy), (cx - s * 0.6, cy + s * 0.8)])


def _pause(surf, cx, cy, s, c, w):
    pygame.draw.rect(surf, c, pygame.Rect(cx - s * 0.6, cy - s * 0.8, s * 0.45, s * 1.6), border_radius=2)
    pygame.draw.rect(surf, c, pygame.Rect(cx + s * 0.15, cy - s * 0.8, s * 0.45, s * 1.6), border_radius=2)


def _home(surf, cx, cy, s, c, w):
    _poly(surf, c, [(cx - s, cy), (cx, cy - s), (cx + s, cy)], w, False)
    _poly(surf, c, [(cx - s * 0.7, cy - s * 0.1), (cx - s * 0.7, cy + s * 0.85), (cx + s * 0.7, cy + s * 0.85), (cx + s * 0.7, cy - s * 0.1)], w, False)


def _camera(surf, cx, cy, s, c, w):
    pygame.draw.rect(surf, c, pygame.Rect(cx - s, cy - s * 0.6, s * 2, s * 1.4), w, border_radius=4)
    pygame.draw.circle(surf, c, (int(cx), int(cy + s * 0.1)), int(s * 0.4), w)


def _check(surf, cx, cy, s, c, w):
    _poly(surf, c, [(cx - s * 0.8, cy), (cx - s * 0.2, cy + s * 0.6), (cx + s * 0.85, cy - s * 0.6)], w + 1, False)


def _cross(surf, cx, cy, s, c, w):
    pygame.draw.line(surf, c, (cx - s * 0.7, cy - s * 0.7), (cx + s * 0.7, cy + s * 0.7), w + 1)
    pygame.draw.line(surf, c, (cx - s * 0.7, cy + s * 0.7), (cx + s * 0.7, cy - s * 0.7), w + 1)


def _chev(dx, dy):
    def f(surf, cx, cy, s, c, w):
        a = (cx - dx * s * 0.5 - dy * s * 0.7, cy - dy * s * 0.5 + dx * s * 0.7)
        b = (cx + dx * s * 0.5, cy + dy * s * 0.5)
        d = (cx - dx * s * 0.5 + dy * s * 0.7, cy - dy * s * 0.5 - dx * s * 0.7)
        _poly(surf, c, [a, b, d], w + 1, False)
    return f


def _bolt(surf, cx, cy, s, c, w):
    pygame.draw.polygon(surf, c, [(cx + s * 0.2, cy - s), (cx - s * 0.6, cy + s * 0.1), (cx - s * 0.05, cy + s * 0.1),
                                  (cx - s * 0.2, cy + s), (cx + s * 0.6, cy - s * 0.15), (cx + s * 0.05, cy - s * 0.15)])


def _sliders(surf, cx, cy, s, c, w):
    for i, k in enumerate((-0.6, 0.0, 0.6)):
        y = cy + s * k
        pygame.draw.line(surf, c, (cx - s, y), (cx + s, y), max(1, w - 1))
        pygame.draw.circle(surf, c, (int(cx + s * (0.4 - i * 0.4)), int(y)), max(2, int(s * 0.22)))


def _info(surf, cx, cy, s, c, w):
    pygame.draw.circle(surf, c, (int(cx), int(cy)), int(s), w)
    pygame.draw.line(surf, c, (cx, cy - s * 0.05), (cx, cy + s * 0.5), w)
    pygame.draw.circle(surf, c, (int(cx), int(cy - s * 0.42)), max(1, int(s * 0.1)))


def _eye(surf, cx, cy, s, c, w):
    pygame.draw.ellipse(surf, c, pygame.Rect(cx - s, cy - s * 0.55, s * 2, s * 1.1), w)
    pygame.draw.circle(surf, c, (int(cx), int(cy)), max(2, int(s * 0.3)))


def _refresh(surf, cx, cy, s, c, w):
    pygame.draw.arc(surf, c, pygame.Rect(cx - s * 0.8, cy - s * 0.8, s * 1.6, s * 1.6), 0.5, 5.6, w)
    _poly(surf, c, [(cx + s * 0.55, cy - s * 0.95), (cx + s * 0.85, cy - s * 0.35), (cx + s * 0.2, cy - s * 0.4)], w, False)


def _star(surf, cx, cy, s, c, w):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = s if i % 2 == 0 else s * 0.45
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    _poly(surf, c, pts, w)


def _heart(surf, cx, cy, s, c, w):
    pts = []
    for i in range(24):
        t = i / 24 * math.tau
        pts.append((cx + 16 * math.sin(t) ** 3 / 17 * s,
                    cy - (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 17 * s + s * 0.1))
    _poly(surf, c, pts, w)


def _bomb(surf, cx, cy, s, c, w):
    pygame.draw.circle(surf, c, (int(cx - s * 0.1), int(cy + s * 0.2)), int(s * 0.75), w)
    pygame.draw.line(surf, c, (cx + s * 0.35, cy - s * 0.35), (cx + s * 0.75, cy - s * 0.8), w)
    pygame.draw.circle(surf, c, (int(cx + s * 0.8), int(cy - s * 0.85)), max(2, int(s * 0.15)))


def _coin(surf, cx, cy, s, c, w):
    pygame.draw.circle(surf, c, (int(cx), int(cy)), int(s * 0.9), w)
    pygame.draw.circle(surf, c, (int(cx), int(cy)), int(s * 0.5), max(1, w - 1))


def _gift(surf, cx, cy, s, c, w):
    pygame.draw.rect(surf, c, pygame.Rect(cx - s * 0.8, cy - s * 0.2, s * 1.6, s * 1.0), w, border_radius=2)
    pygame.draw.rect(surf, c, pygame.Rect(cx - s * 0.9, cy - s * 0.6, s * 1.8, s * 0.4), w, border_radius=2)
    pygame.draw.line(surf, c, (cx, cy - s * 0.6), (cx, cy + s * 0.8), w)


def _fist(surf, cx, cy, s, c, w):
    pygame.draw.rect(surf, c, pygame.Rect(cx - s * 0.7, cy - s * 0.5, s * 1.4, s * 1.2), w, border_radius=int(s * 0.4))
    for i in range(3):
        pygame.draw.line(surf, c, (cx - s * 0.35 + i * s * 0.35, cy - s * 0.5), (cx - s * 0.35 + i * s * 0.35, cy - s * 0.05), max(1, w - 1))


def _clock(surf, cx, cy, s, c, w):
    pygame.draw.circle(surf, c, (int(cx), int(cy)), int(s), w)
    pygame.draw.line(surf, c, (cx, cy), (cx, cy - s * 0.65), w)
    pygame.draw.line(surf, c, (cx, cy), (cx + s * 0.45, cy + s * 0.2), w)


_ICONS = {
    "star": _star, "heart": _heart, "bomb": _bomb, "coin": _coin, "gift": _gift, "fist": _fist, "clock": _clock,
    "orb": _orb, "cube": _cube, "crystal": _crystal, "target": _target, "trash": _trash, "gravity": _gravity,
    "trail": _trail, "hand": _hand, "gear": _gear, "play": _play, "pause": _pause, "home": _home,
    "camera": _camera, "check": _check, "cross": _cross, "bolt": _bolt, "sliders": _sliders, "info": _info,
    "eye": _eye, "refresh": _refresh,
    "left": _chev(-1, 0), "right": _chev(1, 0), "up": _chev(0, -1), "down": _chev(0, 1),
}
