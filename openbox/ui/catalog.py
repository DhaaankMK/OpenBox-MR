"""Menus de criação: Catálogo (grade por categoria, clique/arrastar para criar), Menu Radial (gesto ROCK ou botão
direito do mouse) e Barra Rápida com favoritos. Funcionam com clique de pinça das mãos e com mouse."""
from __future__ import annotations

import math

import pygame

from .. import theme as T
from ..game import items as I
from . import draw, icons
from .anim import Appear, Spring, ease_out_back, ease_out_cubic
from .widgets import Widget

_icon_cache: dict = {}
TOOL_ICON = {"explosion": "bolt", "lightning": "bolt", "shockwave": "target", "eraser": "trash"}


class _StubFace:
    def __init__(self, cx, cy, w):
        self.width, self.roll = w, 0.0
        self._p = {"nose": (cx, cy + 0.15 * w), "lip_up": (cx, cy + 0.3 * w), "lip_lo": (cx, cy + 0.34 * w)}
        import numpy as np
        self.eye_l, self.eye_r = np.array([cx - 0.2 * w, cy]), np.array([cx + 0.2 * w, cy])

    def p(self, k):
        import numpy as np
        return np.array(self._p[k], dtype=float)


def item_icon(item, size: int):
    """Miniatura do item, desenhada com os mesmos renderizadores do jogo (em cache)."""
    key = (item.id, size)
    img = _icon_cache.get(key)
    if img is not None:
        return img
    import numpy as np
    from ..physics.world import Body
    from . import creature_draw, hats, sprites
    S = pygame.Surface((size, size), pygame.SRCALPHA)
    try:
        if item.kind == "body":
            spr = sprites.base_sprite(item.id, size * 0.34, item.color)
            k = min(1.0, size * 0.9 / max(spr.get_width(), spr.get_height()))
            if k < 1.0:
                spr = pygame.transform.smoothscale(spr, (max(2, int(spr.get_width() * k)), max(2, int(spr.get_height() * k))))
            S.blit(spr, spr.get_rect(center=(size // 2, size // 2)))
        elif item.kind == "creature":
            from ..game.creatures import Brain
            b = Body(item.id, size / 2, size * 0.58, size * 0.19)
            b.brain, b.grounded, b.angle = Brain(item.id), True, 0.0
            b.brain.face = 1
            creature_draw.draw_creature(S, b, 0.0)
        elif item.kind == "weapon":
            hats.draw_weapon(S, item.id, size * 0.22, size * 0.52, 0.0, 0.0, size / 130.0)
        elif item.kind == "hat":
            hats.draw_hat(S, item.id, (size / 2, size * 0.66), size * 0.7, 0.0, 0.0)
        elif item.kind == "accessory":
            hats.draw_accessory(S, item.id, _StubFace(size / 2, size * 0.45, size * 0.7), 0.0)
        else:
            icons.draw(TOOL_ICON.get(item.id, "gear"), S, size / 2, size / 2, size * 0.28, item.color, 3)
    except Exception as exc:       # um ícone com erro não derruba o menu
        print(f"[catalog] ícone {item.id}: {exc!r}")
    _icon_cache[key] = S
    return S


class CatalogPanel(Widget):
    """Catálogo completo. on_pick(item, pointer) é chamado ao pressionar um item."""

    def __init__(self, ctx, on_pick, on_hat_none=None):
        super().__init__((ctx.W // 2 - 470, 80, 940, 560))
        self.ctx, self.on_pick, self.on_hat_none = ctx, on_pick, on_hat_none
        self.appear = Appear(6.0)
        self.cat = 0
        self.pinned = False
        self.restrict = None            # conjunto de categorias permitidas (ex.: só chapéus em Sobrevivência)
        self.hover = None
        self._hov = {}
        self.cells: list = []
        self.visible = False

    # ---- abrir/fechar ----
    @property
    def is_open(self):
        return self.appear.open

    def open(self, cat: str | None = None):
        self.appear.open = True
        self.visible = True
        if cat:
            for i, (cid, _, _) in enumerate(self._cats()):
                if cid == cat:
                    self.cat = i
        self.ctx.audio.play("notificacao", 0.35)

    def close(self):
        self.appear.open = False

    def toggle(self):
        self.close() if self.appear.open else self.open()

    def _cats(self):
        return [c for c in I.CATEGORIES if self.restrict is None or c[0] in self.restrict]

    def _layout(self):
        r = self.rect
        cell = self.ctx.cfg.post["cell"]
        gap = 14
        gx, gy = r.x + 196, r.y + 78
        cols = max(3, (r.w - 196 - 28) // (cell + gap))
        cat_id = self._cats()[min(self.cat, len(self._cats()) - 1)][0]
        self.cells = []
        for n, it in enumerate(I.by_cat(cat_id)):
            self.cells.append((pygame.Rect(gx + (n % cols) * (cell + gap), gy + (n // cols) * (cell + gap + 6), cell, cell), it))

    def _tab_rects(self):
        return [pygame.Rect(self.rect.x + 16, self.rect.y + 80 + i * 64, 166, 54) for i in range(len(self._cats()))]

    # ---- interação ----
    def on_press(self, p):
        r = self.rect
        if pygame.Rect(r.right - 54, r.y + 14, 40, 40).collidepoint(p.x, p.y):
            self.close()
            return
        if pygame.Rect(r.right - 150, r.y + 14, 84, 40).collidepoint(p.x, p.y):
            self.pinned = not self.pinned
            self._sound("click")
            return
        for i, tr in enumerate(self._tab_rects()):
            if tr.collidepoint(p.x, p.y):
                self.cat = i
                self._sound("click")
                return
        self._layout()
        for cr, it in self.cells:
            if cr.collidepoint(p.x, p.y):
                if pygame.Rect(cr.right - 22, cr.y, 22, 22).collidepoint(p.x, p.y):
                    fav = self.ctx.cfg.favorites
                    if it.id in fav:
                        fav.remove(it.id)
                    elif len(fav) < 8:
                        fav.append(it.id)
                    else:
                        self.ctx.toast("Barra rápida cheia (8 itens)", "warn")
                    self._sound("click")
                    return
                self.on_pick(it, p)
                if not self.pinned and it.kind not in ("hat", "accessory", "weapon"):
                    self.close()
                return
        if it_none := pygame.Rect(r.right - 262, r.bottom - 52, 120, 36):
            if it_none.collidepoint(p.x, p.y) and self.on_hat_none:
                self.on_hat_none()

    def on_release(self, p, inside):
        pass

    def tick(self, dt):
        self.appear.update(dt)
        self.visible = self.appear.visible
        super().tick(dt)
        if not self.visible:
            return
        self._layout()
        self.hover = None
        for p in self.ctx.input.pointers:
            for cr, it in self.cells:
                if cr.collidepoint(p.x, p.y):
                    self.hover = it
        for cr, it in self.cells:
            v = self._hov.get(it.id, 0.0)
            self._hov[it.id] = v + ((1.0 if self.hover is it else 0.0) - v) * min(1.0, dt * 16.0)

    def contains(self, x, y):
        return self.visible and self.rect.collidepoint(x, y)

    def _hit_rect(self):
        return self.rect

    # ---- desenho ----
    def draw(self, surf):
        if not self.visible:
            return
        e, t = self.appear.e, self.appear.t
        a = int(255 * min(1.0, t * 1.8))
        dy = int((1.0 - ease_out_cubic(t)) * 40)
        r = self.rect.move(0, dy)
        shade = pygame.Surface((surf.get_width(), surf.get_height()), pygame.SRCALPHA)
        shade.fill((2, 4, 14, int(110 * t)))
        surf.blit(shade, (0, 0))
        draw.glass(surf, r, 22, (10, 14, 34, int(215 * min(1, t * 1.5))), (*T.GLASS_BORDER[:3], int(120 * t)), accent=T.CYAN)
        draw.spaced(surf, "CATÁLOGO", (r.x + 22, r.y + 18), 20, T.TEXT, True, 5, "tl", a)
        draw.text(surf, "Clique em um item para criá-lo na sua mão e arraste para lançar", (r.x + 22, r.y + 48), 14, T.MUTED, False, "tl", a)
        # fixar / fechar
        pin = pygame.Rect(r.right - 150, r.y + 14, 84, 40)
        draw.rrect(surf, pin, (*(T.ACCENT if self.pinned else (255, 255, 255)), 60 if not self.pinned else 160), 10)
        draw.text(surf, "Fixar" if not self.pinned else "Fixado", pin.center, 15, T.TEXT, True, "c", a)
        cl = pygame.Rect(r.right - 54, r.y + 14, 40, 40)
        draw.rrect(surf, cl, (255, 70, 90, 110), 10)
        icons.draw("cross", surf, cl.centerx, cl.centery, 9, T.TEXT)
        # categorias
        for i, tr in enumerate(self._tab_rects()):
            tr = tr.move(0, dy)
            cid, label, ic = self._cats()[i]
            sel = i == self.cat
            draw.rrect(surf, tr, (*T.ACCENT, 170) if sel else (255, 255, 255, 18), 12)
            if sel:
                draw.rrect(surf, tr, (*T.ACCENT_HI, 200), 12, 1)
            icons.draw(ic if ic != "crown" else "star", surf, tr.x + 28, tr.centery, 11, T.TEXT if sel else T.MUTED)
            draw.text(surf, label, (tr.x + 52, tr.centery), 17, T.TEXT if sel else T.MUTED, True, "ml", a)
            draw.text(surf, str(len(I.by_cat(cid))), (tr.right - 14, tr.centery), 13, T.DIM, True, "mr", a)
        # grade
        self._layout()
        fav = self.ctx.cfg.favorites
        cell = self.ctx.cfg.post["cell"]
        for n, (cr, it) in enumerate(self.cells):
            appear = max(0.0, min(1.0, (t * 1.6 - n * 0.025)))
            hv = self._hov.get(it.id, 0.0)
            c = cr.move(0, dy - int(4 * hv) + int((1 - ease_out_cubic(appear)) * 14)).inflate(int(6 * hv), int(6 * hv))
            draw.rrect(surf, c, (*T.mix((20, 26, 56), it.color, 0.28 * hv), int(190 * appear)), 14)
            draw.rrect(surf, c, (*T.mix(T.GLASS_BORDER[:3], it.color, hv), int(60 + 160 * hv)), 14, 1)
            icon = item_icon(it, cell - 12)
            icon.set_alpha(int(255 * appear))
            surf.blit(icon, icon.get_rect(center=c.center))
            if it.id == self.ctx.cfg.hat or it.id == self.ctx.cfg.accessory:
                draw.rrect(surf, c, (*T.GREEN, 220), 14, 3)
            star = (c.right - 12, c.y + 12)
            icons.draw("star", surf, star[0], star[1], 6, T.AMBER if it.id in fav else (130, 140, 180), 1 if it.id not in fav else 2)
        # rodapé
        foot = pygame.Rect(r.x + 196, r.bottom - 58, r.w - 196 - 28 - 130, 40)
        if self.hover is not None:
            draw.text(surf, self.hover.name, (foot.x, foot.y + 2), 18, T.TEXT, True, "tl", a)
            draw.text(surf, self.hover.desc, (foot.x, foot.y + 24), 14, T.MUTED, False, "tl", a)
        else:
            draw.text(surf, "Passe o cursor sobre um item · ★ marca como favorito (barra rápida)", (foot.x, foot.y + 12), 14, T.DIM, False, "tl", a)
        if self._cats()[min(self.cat, len(self._cats()) - 1)][0] == "chapeus" and self.on_hat_none:
            nb = pygame.Rect(r.right - 262, r.bottom - 52, 120, 36)
            draw.rrect(surf, nb, (255, 255, 255, 30), 10)
            draw.text(surf, "Remover", nb.center, 15, T.TEXT, True, "c", a)


class RadialMenu(Widget):
    """Roda de favoritos aberta no ponto da mão/cursor. Fora da roda fecha; no centro abre o catálogo."""

    def __init__(self, ctx, on_pick, on_catalog):
        super().__init__((0, 0, ctx.W, ctx.H))
        self.ctx, self.on_pick, self.on_catalog = ctx, on_pick, on_catalog
        self.appear = Appear(7.0)
        self.center = (ctx.W // 2, ctx.H // 2)
        self.visible = False
        self.sp = [Spring(0.0, 220.0, 20.0) for _ in range(8)]
        self.hover_idx = -1
        self.ring = 150

    @property
    def is_open(self):
        return self.appear.open

    def open(self, x, y):
        pad = 210
        self.center = (max(pad, min(self.ctx.W - pad, x)), max(pad, min(self.ctx.H - pad, y)))
        self.appear.open = True
        self.visible = True
        for s in self.sp:
            s.snap(0.0)
        self.ctx.audio.play("whoosh", 0.4)

    def close(self):
        self.appear.open = False

    def _fav_items(self):
        return [I.ITEMS[f] for f in self.ctx.cfg.favorites if f in I.ITEMS][:8]

    def _slot_at(self, x, y):
        cx, cy = self.center
        d = math.hypot(x - cx, y - cy)
        if d < 58:
            return -2
        if d > 275:
            return -3
        n = max(1, len(self._fav_items()))
        a = (math.atan2(y - cy, x - cx) + math.pi / 2 + math.pi / n) % math.tau
        return int(a / (math.tau / n)) % n

    def on_press(self, p):
        idx = self._slot_at(p.x, p.y)
        items = self._fav_items()
        if idx == -3:
            self.close()
        elif idx == -2:
            self.close()
            self.on_catalog()
        elif 0 <= idx < len(items):
            self.on_pick(items[idx], p)
            self.close()

    def tick(self, dt):
        self.appear.update(dt)
        self.visible = self.appear.visible
        super().tick(dt)
        if not self.visible:
            return
        self.hover_idx = -1
        for p in self.ctx.input.pointers:
            self.hover_idx = self._slot_at(p.x, p.y)
            break
        for i, s in enumerate(self.sp):
            s.target = 1.0 if self.appear.open else 0.0
            s.update(dt * (1.0 if i < 8 else 1))

    def draw(self, surf):
        if not self.visible:
            return
        t = self.appear.t
        cx, cy = self.center
        shade = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        shade.fill((2, 4, 14, int(95 * t)))
        surf.blit(shade, (0, 0))
        items = self._fav_items()
        n = max(1, len(items))
        a = int(255 * min(1.0, t * 1.8))
        draw.glow(surf, (cx, cy), 230 * min(1.0, t * 1.3), T.ACCENT, 0.18)
        draw.ring(surf, (cx, cy), self.ring * ease_out_back(t) + 4, T.ACCENT_HI, 2, int(110 * t))
        for i, it in enumerate(items):
            ang = -math.pi / 2 + i * math.tau / n
            grow = max(0.0, self.sp[i].x - i * 0.0)
            rr = self.ring * min(1.15, grow)
            x, y = cx + math.cos(ang) * rr, cy + math.sin(ang) * rr
            hot = i == self.hover_idx
            R = 44 + (12 if hot else 0)
            if hot:
                draw.glow(surf, (x, y), 90, it.color, 0.7)
            pygame.draw.circle(surf, (*T.mix((16, 22, 50), it.color, 0.3 if hot else 0.08),), (int(x), int(y)), R)
            draw.ring(surf, (x, y), R, it.color if hot else T.GLASS_BORDER[:3], 2, 255 if hot else 120)
            icon = item_icon(it, 72)
            icon.set_alpha(a)
            surf.blit(icon, icon.get_rect(center=(int(x), int(y))))
            if hot:
                draw.text(surf, it.name, (cx, cy + self.ring + 78), 20, T.TEXT, True, "c", 255, True)
        hot_c = self.hover_idx == -2
        pygame.draw.circle(surf, (*T.mix((16, 22, 50), T.ACCENT, 0.5 if hot_c else 0.15),), (cx, cy), int(52 * min(1.0, t * 1.4)))
        draw.ring(surf, (cx, cy), 52 * min(1.0, t * 1.4), T.ACCENT_HI, 2, 220)
        icons.draw("sliders", surf, cx, cy - 8, 12, T.TEXT)
        draw.text(surf, "Catálogo", (cx, cy + 20), 13, T.TEXT, True, "c", a)

    def contains(self, x, y):
        return self.visible

    def _hit_rect(self):
        return self.rect


class Hotbar(Widget):
    """Barra rápida (8 favoritos). Fica escondida e sobe quando o cursor/mão chega perto do rodapé (ou ao apertar 1-8)."""

    def __init__(self, ctx, on_pick):
        super().__init__((0, 0, 10, 10))
        self.ctx, self.on_pick = ctx, on_pick
        self.sp = [Spring(0.0, 260.0, 22.0) for _ in range(8)]
        self.rev = Spring(0.0, 190.0, 24.0)
        self.force = 0.0
        self.dy = 0
        self.last = -1
        self._relayout()

    def _relayout(self):
        cell = 58 if self.ctx.cfg.posture == "sentado" else 68
        w = 8 * cell + 7 * 8 + 24
        self.cell = cell
        self.rect = pygame.Rect((self.ctx.W - w) // 2, self.ctx.H - cell - 26, w, cell + 18)

    def slot_rect(self, i):
        return pygame.Rect(self.rect.x + 12 + i * (self.cell + 8), self.rect.y + 9 + self.dy, self.cell, self.cell)

    def _items(self):
        return [I.ITEMS.get(f) for f in self.ctx.cfg.favorites][:8]

    def _hit_rect(self):
        return self.rect.move(0, self.dy) if self.rev.x > 0.5 else pygame.Rect(-10, -10, 1, 1)

    def contains(self, x, y):
        return self.visible and self._hit_rect().collidepoint(x, y)

    def on_press(self, p):
        for i, it in enumerate(self._items()):
            if it and self.slot_rect(i).collidepoint(p.x, p.y):
                self.last = i
                self.on_pick(it, p)

    def tick(self, dt):
        self._relayout()
        super().tick(dt)
        self.force = max(0.0, self.force - dt)
        near = any(p.y > self.ctx.H - 150 and abs(p.x - self.ctx.W / 2) < self.rect.w / 2 + 120 for p in self.ctx.input.pointers)
        self.rev.target = 1.0 if (near or self.force > 0) else 0.0
        self.rev.update(dt)
        self.dy = int((1.0 - max(0.0, min(1.0, self.rev.x))) * (self.cell + 44))
        for i, s in enumerate(self.sp):
            hov = self.rev.x > 0.5 and any(self.slot_rect(i).collidepoint(p.x, p.y) for p in self.ctx.input.pointers)
            s.target = 1.0 if hov else 0.0
            s.update(dt)

    def draw(self, surf):
        if self.dy < self.cell + 40:
            draw.glass(surf, self.rect.move(0, self.dy), 16, (10, 14, 34, 150), accent=T.ACCENT_HI)
            for i, it in enumerate(self._items()):
                r = self.slot_rect(i)
                k = max(0.0, self.sp[i].x)
                r = r.move(0, -int(8 * k)).inflate(int(8 * k), int(8 * k))
                draw.rrect(surf, r, (*T.mix((22, 28, 60), (it.color if it else T.DIM), 0.3 * k), 190), 12)
                draw.rrect(surf, r, (*T.GLASS_BORDER[:3], int(60 + 150 * k)), 12, 1)
                if it:
                    icon = item_icon(it, self.cell - 10)
                    surf.blit(icon, icon.get_rect(center=r.center))
                draw.text(surf, str(i + 1), (r.x + 6, r.y + 3), 12, T.MUTED, True)
        if self.dy > 20:      # dica discreta quando escondida
            icons.draw("up", surf, self.ctx.W // 2, self.ctx.H - 14, 6, T.DIM, 2)
