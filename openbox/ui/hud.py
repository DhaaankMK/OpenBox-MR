"""Componentes de HUD compartilhados pelas cenas."""
from __future__ import annotations

import pygame

from .. import theme as T
from . import draw, icons
from .widgets import Panel


class TopBar(Panel):
    """Barra superior de vidro: título à esquerda (depois do botão voltar) e status à direita."""

    def __init__(self, ctx, title, subtitle="", left=76):
        super().__init__((16, 12, ctx.W - 32, 56), None, T.ACCENT_HI, radius=16)
        self.ctx, self.title_s, self.sub, self.left = ctx, title, subtitle, left

    def draw(self, surf):
        super().draw(surf)
        r, c = self.rect, self.ctx
        draw.spaced(surf, self.title_s, (r.x + self.left, r.y + 9), 22, T.TEXT, True, 5)
        if self.sub:
            draw.text(surf, self.sub, (r.x + self.left, r.y + 34), 13, T.MUTED)
        # status à direita
        x = r.right - 18
        cam_ok = c.camera.ready
        items = []
        if c.cfg.show_fps:
            items.append((f"{c.app.clock.get_fps():.0f} FPS", T.GREEN if c.app.clock.get_fps() > 45 else T.AMBER))
        n = len(c.hands.visible())
        items.append((f"{n} {'MÃO' if n == 1 else 'MÃOS'}", T.CYAN if n else T.DIM))
        if cam_ok and c.hands.latency > 0:
            items.append((f"{c.hands.latency * 1000:.0f} ms", T.GREEN if c.hands.latency < 0.09 else T.AMBER))
        items.append(("CÂMERA" if cam_ok else "SEM CÂMERA", T.GREEN if cam_ok else T.RED))
        for s, col in items:
            w = draw.text_width(s, 14, True) + 30
            pill = pygame.Rect(x - w, r.centery - 14, w, 28)
            draw.rrect(surf, pill, (0, 0, 0, 90), 14)
            pygame.draw.circle(surf, col, (pill.x + 14, pill.centery), 4)
            draw.text(surf, s, (pill.x + 24, pill.centery), 14, T.TEXT, True, "ml")
            x -= w + 8


def hint_bar(surf, ctx, items, y=None, alpha=255):
    """Faixa inferior com dicas de gestos: items = [(icone, 'texto'), ...]."""
    total = sum(48 + draw.text_width(t, 15) + 26 for _, t in items) + 20
    y = ctx.H - 64 if y is None else y
    r = pygame.Rect((ctx.W - total) // 2, y, total, 44)
    draw.glass(surf, r, 14, (10, 14, 34, int(140 * alpha / 255)), (*T.GLASS_BORDER[:3], int(60 * alpha / 255)))
    x = r.x + 22
    for ic, t in items:
        icons.draw(ic, surf, x + 10, r.centery, 10, T.CYAN)
        draw.text(surf, t, (x + 30, r.centery), 15, T.TEXT, False, "ml", alpha)
        x += 48 + draw.text_width(t, 15) + 26 - 8
