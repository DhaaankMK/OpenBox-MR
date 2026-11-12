"""Renderização das mãos (esqueleto holográfico) e dos cursores."""
from __future__ import annotations

import math

import pygame

from .. import theme as T
from ..tracking.gestures import GESTURE_NAMES
from . import draw

CONNECTIONS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11), (11, 12),
               (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (17, 18), (18, 19), (19, 20), (0, 17)]
PALM_POLY = [0, 1, 5, 9, 13, 17]
TIPS = (4, 8, 12, 16, 20)


class HandRenderer:
    def __init__(self, cfg):
        self.cfg = cfg
        self._layer = None

    def draw(self, surf, hands, held_slots=()):
        style = self.cfg.skeleton_style
        if style == "off" or not hands:
            return
        if self._layer is None or self._layer.get_size() != surf.get_size():
            self._layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        layer = self._layer
        layer.fill((0, 0, 0, 0))
        for hv in hands:
            if hv.disp is None:
                continue
            pts = hv.disp
            col = T.GREEN if hv.slot in held_slots else hv.color
            fade = 0.45 if hv.stale else 1.0
            pygame.draw.polygon(layer, (*col, int(30 * fade)), [(int(pts[i][0]), int(pts[i][1])) for i in PALM_POLY])
            for a, b in CONNECTIONS:
                if style == "neon":
                    draw.neon_line(layer, pts[a], pts[b], col, 2, True)
                elif style == "solid":
                    pygame.draw.line(layer, (*col, int(130 * fade)), (int(pts[a][0]), int(pts[a][1])), (int(pts[b][0]), int(pts[b][1])), 11)
                    pygame.draw.line(layer, (255, 255, 255, int(235 * fade)), (int(pts[a][0]), int(pts[a][1])), (int(pts[b][0]), int(pts[b][1])), 2)
                else:
                    pygame.draw.line(layer, (*col, int(210 * fade)), (int(pts[a][0]), int(pts[a][1])), (int(pts[b][0]), int(pts[b][1])), 1)
            for i in range(21):
                rad = 5 if i in TIPS else 3
                pygame.draw.circle(layer, (255, 255, 255, int(235 * fade)), (int(pts[i][0]), int(pts[i][1])), rad if style != "minimal" else 2)
        for hv in hands:
            if hv.disp is not None and hv.gesture == "POINT" and not hv.stale:
                d = hv.disp[8] - hv.disp[5]
                n = float((d[0] ** 2 + d[1] ** 2) ** 0.5)
                if n > 1:
                    end = hv.disp[8] + d / n * 420
                    draw.neon_line(layer, hv.disp[8], end, T.RED if hv.slot == 0 else T.AMBER, 2, True)
        surf.blit(layer, (0, 0))

        use_glow = self.cfg.q["glow"]
        for hv in hands:
            if hv.disp is None:
                continue
            col = T.GREEN if hv.slot in held_slots else hv.color
            if use_glow and style in ("neon", "solid"):
                for i in TIPS:
                    draw.glow(surf, hv.disp[i], 18, col, 0.55)
                draw.glow(surf, hv.palm, max(30, hv.size_px * 0.8), col, 0.22)
            if hv.pinching:
                pulse = 14 + 3 * math.sin(pygame.time.get_ticks() * 0.012)
                draw.ring(surf, hv.mid, pulse, T.GREEN, 2, 230)
                draw.glow(surf, hv.mid, 26, T.GREEN, 0.8)
            wr = hv.disp[0]
            draw.text(surf, GESTURE_NAMES.get(hv.gesture, "—").upper(), (wr[0], wr[1] + 26), 13, col, True, "c", 190, shadow=True)


def draw_cursors(surf, pointers, now: float):
    for p in pointers:
        x, y = int(p.x), int(p.y)
        if p.kind == "hand":
            col = p.color
            if p.down:
                draw.glow(surf, (x, y), 30, T.GREEN, 0.9)
                pygame.draw.circle(surf, T.GREEN, (x, y), 8)
                draw.ring(surf, (x, y), 15, (255, 255, 255), 2, 230)
            else:
                r = 18 + (4 if p.hover is not None else 0)
                if p.hand is not None:      # o anel fecha conforme você junta os dedos (aviso do clique)
                    r = int(r * (1.0 - 0.45 * max(0.0, min(1.0, (0.85 - p.hand.pinch_ratio) / 0.55))))
                draw.glow(surf, (x, y), 26, col, 0.5)
                draw.ring(surf, (x, y), r, col, 2, 240)
                pygame.draw.circle(surf, (255, 255, 255), (x, y), 3)
            if p.dwell > 0.02:
                draw.arc(surf, (x, y), 26, T.AMBER, p.dwell, 4, 255)
        else:
            pygame.draw.circle(surf, (255, 255, 255), (x, y), 9 if p.down else 6, 2)
            if p.hover is not None:
                draw.glow(surf, (x, y), 22, T.ACCENT_HI, 0.5)
