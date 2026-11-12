"""Widgets (botão, toggle, slider, seletor, abas, painel) + gerenciador de UI.
Tudo funciona igual com mão (pinça = clique, apontar parado = clique por permanência) e com mouse."""
from __future__ import annotations

import time

import pygame

from .. import theme as T
from . import draw, icons


class Widget:
    interactive = True
    blocking = True
    dwellable = False

    def __init__(self, rect, tooltip: str | None = None):
        self.rect = pygame.Rect(rect)
        self.visible = True
        self.enabled = True
        self.tooltip = tooltip
        self.hovered = False
        self.captured = None
        self.h = 0.0       # animação de hover 0..1
        self.press = 0.0   # animação de pressionado 0..1
        self.ui = None

    def contains(self, x, y):
        return self.visible and self._hit_rect().collidepoint(x, y)

    def _hit_rect(self):
        pad = self.ui.ctx.cfg.post["hit_pad"] if (self.ui is not None and self.interactive) else 0
        return self.rect.inflate(pad * 2, pad * 2) if pad else self.rect

    def tick(self, dt):
        self.h += ((1.0 if self.hovered else 0.0) - self.h) * min(1.0, dt * 14.0)
        self.press += ((1.0 if self.captured else 0.0) - self.press) * min(1.0, dt * 22.0)

    def on_press(self, p): ...
    def on_drag(self, p): ...
    def on_release(self, p, inside): ...
    def click(self, p=None): ...
    def draw(self, surf): ...

    def _sound(self, name):
        if self.ui is not None:
            self.ui.ctx.audio.play(name)


class Panel(Widget):
    interactive = False

    def __init__(self, rect, title: str | None = None, accent=T.ACCENT_HI, tint=T.GLASS, radius=18):
        super().__init__(rect)
        self.title, self.accent, self.tint, self.radius = title, accent, tint, radius

    def draw(self, surf):
        draw.glass(surf, self.rect, self.radius, self.tint, accent=self.accent)
        if self.title:
            draw.text(surf, self.title.upper(), (self.rect.x + 18, self.rect.y + 14), 15, T.MUTED, True)


class Label(Widget):
    interactive = False
    blocking = False

    def __init__(self, pos, s, size=18, color=T.TEXT, bold=False, anchor="tl", width=None):
        super().__init__((pos[0], pos[1], width or 10, size))
        self.s, self.size, self.color, self.bold, self.anchor, self.width = s, size, color, bold, anchor, width

    def draw(self, surf):
        s = self.s() if callable(self.s) else self.s
        if self.width:
            for i, line in enumerate(draw.wrap(s, self.size, self.width, self.bold)):
                draw.text(surf, line, (self.rect.x, self.rect.y + i * int(self.size * 1.35)), self.size, self.color, self.bold)
        else:
            draw.text(surf, s, (self.rect.x, self.rect.y), self.size, self.color, self.bold, self.anchor)


class Button(Widget):
    dwellable = True

    def __init__(self, rect, label="", on_click=None, icon=None, style="ghost", size=19, tooltip=None, icon_size=None):
        super().__init__(rect, tooltip)
        self.label, self.on_click, self.icon, self.style, self.size = label, on_click, icon, style, size
        self.icon_size = icon_size
        self.active = False
        self.badge = None
        self.ripples: list = []

    def on_press(self, p):
        if self.ui is not None and self.ui.ctx.cfg.ui_anim:
            self.ripples.append([p.x, p.y, 0.0])

    def on_release(self, p, inside):
        if inside and self.enabled:
            self.click(p)

    def click(self, p=None):
        now = time.monotonic()
        if now - getattr(self, "_last_click", 0.0) < 0.2:      # anti clique duplo
            return
        self._last_click = now
        self._sound("click")
        if p is not None and not self.ripples and self.ui is not None and self.ui.ctx.cfg.ui_anim:
            self.ripples.append([p.x, p.y, 0.0])
        if self.on_click:
            self.on_click()

    def tick(self, dt):
        super().tick(dt)
        for rp in self.ripples:
            rp[2] += dt * 2.2
        self.ripples = [rp for rp in self.ripples if rp[2] < 1.0]

    def draw(self, surf):
        k = int(3 * self.press) - int(2 * self.h)
        r = self.rect.inflate(-k * 2, -k * 2)
        if self.style == "primary":
            tint = (*T.ACCENT, int(190 + 40 * self.h))
            border = (*T.ACCENT_HI, 230)
        elif self.style == "danger":
            tint = (*T.RED, int(110 + 60 * self.h))
            border = (*T.RED, 200)
        else:
            tint = T.GLASS_HI if (self.h > 0.3 or self.active) else T.GLASS
            border = T.GLASS_BORDER_HI if (self.h > 0.3 or self.active) else T.GLASS_BORDER
        if self.active:
            tint = (*T.ACCENT, 170)
        draw.glass(surf, r, 12, tint, border)
        if self.h > 0.02 and self.enabled:
            draw.glow(surf, r.center, max(r.w, r.h) * 0.75, T.ACCENT, 0.28 * self.h)
        col = T.TEXT if self.enabled else T.DIM
        isz = self.icon_size or min(r.h * 0.28, 14)
        lab = self.label() if callable(self.label) else self.label
        if self.icon and lab:
            icons.draw(self.icon, surf, r.x + 22, r.centery, isz, col)
            draw.text(surf, lab, (r.x + 44, r.centery), self.size, col, True, "ml")
        elif self.icon:
            icons.draw(self.icon, surf, r.centerx, r.centery, isz, col)
        else:
            draw.text(surf, lab, r.center, self.size, col, True, "c")
        for rx, ry, t in self.ripples:     # onda de clique
            draw.ring(surf, (max(r.x, min(r.right, rx)), max(r.y, min(r.bottom, ry))), 6 + t * max(r.w, r.h) * 0.6, T.ACCENT_HI, 2, int(200 * (1 - t)))
        if self.badge:
            draw.text(surf, self.badge, (r.right - 10, r.y + 8), 13, T.MUTED, True, "tr")


class Toggle(Widget):
    dwellable = True

    def __init__(self, rect, label, get, set_, tooltip=None):
        super().__init__(rect, tooltip)
        self.label, self.get, self.set = label, get, set_
        self.k = 1.0 if get() else 0.0

    def on_release(self, p, inside):
        if inside:
            self.click(p)

    def click(self, p=None):
        self._sound("click")
        self.set(not self.get())

    def tick(self, dt):
        super().tick(dt)
        self.k += ((1.0 if self.get() else 0.0) - self.k) * min(1.0, dt * 16.0)

    def draw(self, surf):
        r = self.rect
        draw.glass(surf, r, 12, T.GLASS_HI if self.h > 0.3 else T.GLASS, T.GLASS_BORDER_HI if self.h > 0.3 else T.GLASS_BORDER)
        draw.text(surf, self.label, (r.x + 16, r.centery), 18, T.TEXT, False, "ml")
        pill = pygame.Rect(r.right - 62, r.centery - 12, 46, 24)
        draw.rrect(surf, pill, (*T.mix(T.DIM, T.ACCENT, self.k), 230), 12)
        draw.rrect(surf, pill, T.GLASS_BORDER, 12, 1)
        cx = pill.x + 12 + int(22 * self.k)
        draw.glow(surf, (cx, pill.centery), 18, T.ACCENT_HI, 0.6 * self.k)
        pygame.draw.circle(surf, (245, 248, 255), (cx, pill.centery), 9)


class Slider(Widget):
    def __init__(self, rect, label, get, set_, lo=0.0, hi=1.0, fmt="{:.2f}", tooltip=None):
        super().__init__(rect, tooltip)
        self.label, self.get, self.set, self.lo, self.hi, self.fmt = label, get, set_, lo, hi, fmt

    @property
    def track(self):
        return pygame.Rect(self.rect.x + 14, self.rect.bottom - 20, self.rect.w - 28, 6)

    def _apply(self, p):
        t = self.track
        frac = max(0.0, min(1.0, (p.x - t.x) / max(1, t.w)))
        self.set(self.lo + (self.hi - self.lo) * frac)

    def on_press(self, p):
        self._apply(p)

    def on_drag(self, p):
        self._apply(p)

    def draw(self, surf):
        r = self.rect
        draw.glass(surf, r, 12, T.GLASS_HI if (self.h > 0.3 or self.captured) else T.GLASS, T.GLASS_BORDER)
        draw.text(surf, self.label, (r.x + 16, r.y + 11), 17, T.TEXT)
        draw.text(surf, self.fmt.format(self.get()), (r.right - 16, r.y + 11), 17, T.CYAN, True, "tr")
        t = self.track
        frac = (self.get() - self.lo) / (self.hi - self.lo) if self.hi != self.lo else 0.0
        frac = max(0.0, min(1.0, frac))
        draw.rrect(surf, t, (255, 255, 255, 40), 3)
        draw.rrect(surf, (t.x, t.y, max(4, int(t.w * frac)), t.h), (*T.ACCENT_HI, 255), 3)
        kx = t.x + int(t.w * frac)
        draw.glow(surf, (kx, t.centery), 22, T.ACCENT_HI, 0.5 + 0.5 * max(self.h, self.press))
        pygame.draw.circle(surf, (245, 248, 255), (kx, t.centery), 8 + int(2 * self.press))


class Selector(Widget):
    dwellable = True

    def __init__(self, rect, label, options, get_idx, set_idx, tooltip=None):
        super().__init__(rect, tooltip)
        self.label, self.options, self.get_idx, self.set_idx = label, options, get_idx, set_idx
        self._last_x = rect[0] + rect[2]

    def on_release(self, p, inside):
        if inside:
            self.click(p)

    def click(self, p=None):
        x = p.x if p is not None else self.rect.right
        step = -1 if x < self.rect.centerx + self.rect.w * 0.1 else 1
        self._sound("click")
        self.set_idx((self.get_idx() + step) % len(self.options))

    def draw(self, surf):
        r = self.rect
        draw.glass(surf, r, 12, T.GLASS_HI if self.h > 0.3 else T.GLASS, T.GLASS_BORDER_HI if self.h > 0.3 else T.GLASS_BORDER)
        draw.text(surf, self.label, (r.x + 16, r.centery), 18, T.TEXT, False, "ml")
        cx = r.right - 108
        icons.draw("left", surf, cx - 84, r.centery, 8, T.MUTED)
        icons.draw("right", surf, cx + 84, r.centery, 8, T.MUTED)
        draw.text(surf, self.options[self.get_idx()], (cx, r.centery), 18, T.CYAN, True, "c")


class Tabs(Widget):
    dwellable = True

    def __init__(self, rect, names, get, set_):
        super().__init__(rect)
        self.names, self.get, self.set = names, get, set_
        self._ind = None

    def tick(self, dt):
        super().tick(dt)
        w = self.rect.w / len(self.names)
        tx = self.rect.x + self.get() * w
        if self._ind is None or not (self.ui and self.ui.ctx.cfg.ui_anim):
            self._ind = tx
        else:
            self._ind += (tx - self._ind) * min(1.0, dt * 14.0)

    def _idx_at(self, x):
        return max(0, min(len(self.names) - 1, int((x - self.rect.x) / (self.rect.w / len(self.names)))))

    def on_release(self, p, inside):
        if inside:
            self.click(p)

    def click(self, p=None):
        if p is not None:
            self._sound("click")
            self.set(self._idx_at(p.x))

    def draw(self, surf):
        w = self.rect.w / len(self.names)
        ix = int(self._ind if self._ind is not None else self.rect.x)
        draw.rrect(surf, (ix + 3, self.rect.y + 3, int(w) - 6, self.rect.h - 6), (*T.ACCENT, 150), 10)
        for i, n in enumerate(self.names):
            x = int(self.rect.x + i * w)
            sel = i == self.get()
            draw.text(surf, n, (x + w / 2, self.rect.centery), 17, T.TEXT if sel else T.MUTED, True, "c")


class Chip(Widget):
    """Pílula de status (não interativa)."""
    interactive = False
    blocking = False

    def __init__(self, pos, text, color=T.GREEN, size=15):
        super().__init__((pos[0], pos[1], 10, 10))
        self.text, self.color, self.size = text, color, size

    def draw(self, surf):
        s = self.text() if callable(self.text) else self.text
        col = self.color() if callable(self.color) else self.color
        w = draw.text_width(s, self.size, True) + 34
        r = pygame.Rect(self.rect.x, self.rect.y, w, self.size + 14)
        draw.rrect(surf, r, (0, 0, 0, 110), r.h // 2)
        pygame.draw.circle(surf, col, (r.x + 15, r.centery), 4)
        draw.text(surf, s, (r.x + 26, r.centery), self.size, T.TEXT, True, "ml")
        self.rect.size = r.size


class UI:
    def __init__(self, ctx):
        self.ctx = ctx
        self.widgets: list = []
        self._cap: dict = {}
        self._last_hover: dict = {}
        self._dwell: dict = {}
        self._hover_time = 0.0
        self._tip = None

    def add(self, w):
        w.ui = self
        self.widgets.append(w)
        return w

    def clear(self):
        self.widgets.clear()
        self._cap.clear()

    def update(self, dt, pointers):
        for w in self.widgets:
            w.hovered = False
        tip_w = None
        for p in pointers:
            p.hover = None
            cap = self._cap.get(p.id)
            if cap is not None:
                p.over_ui = True
                p.hover = cap
                inside = cap.contains(p.x, p.y) or (p.kind == "hand" and cap._hit_rect().inflate(64, 64).collidepoint(p.x, p.y))   # tolera o tremor da pinça
                cap.hovered = inside
                if p.down:
                    cap.on_drag(p)
                else:
                    cap.captured = None
                    cap.on_release(p, inside)
                    del self._cap[p.id]
                continue
            target, blocked = None, False
            for w in reversed(self.widgets):
                if w.visible and w.blocking and w._hit_rect().collidepoint(p.x, p.y):
                    blocked = True
                    if w.interactive and w.enabled:
                        target = w
                    break
            if target is None and p.kind == "hand":          # ímã de mira: gruda no botão mais próximo (até 28 px)
                best, bd = None, 1e9
                for w in self.widgets:
                    if w.visible and w.interactive and w.enabled and w.blocking:
                        r = w._hit_rect()
                        d = max(r.left - p.x, 0, p.x - r.right) ** 2 + max(r.top - p.y, 0, p.y - r.bottom) ** 2
                        if d < bd:
                            best, bd = w, d
                if best is not None and bd <= 28 * 28:
                    target, blocked = best, True
            p.over_ui, p.hover = blocked, target
            if target is not None:
                target.hovered = True
                tip_w = target
            if target is not self._last_hover.get(p.id):
                self._last_hover[p.id] = target
                self._dwell[p.id] = 0.0
                if target is not None:
                    self.ctx.audio.play("tick")
            if p.pressed and target is not None:
                target.captured = p.id
                self._cap[p.id] = target
                target.on_press(p)
                continue
            # clique por permanência: apontar (indicador) parado sobre o alvo
            p.dwell = 0.0
            cfg = self.ctx.cfg
            if (cfg.dwell_click and p.kind == "hand" and target is not None and target.dwellable
                    and p.gesture == "POINT" and not p.down and p.speed < 380):
                d = self._dwell.get(p.id, 0.0) + dt
                need = cfg.dwell_ms / 1000.0
                if d >= need:
                    target.click(p)
                    d = -0.7   # recarga
                self._dwell[p.id] = d
                p.dwell = max(0.0, min(1.0, d / need))
            else:
                self._dwell[p.id] = min(0.0, self._dwell.get(p.id, 0.0))
        for w in self.widgets:
            w.tick(dt)
        if tip_w is not None and tip_w.tooltip:
            self._hover_time = self._hover_time + dt if tip_w is self._tip else 0.0
        else:
            self._hover_time = 0.0
        self._tip = tip_w

    def draw(self, surf):
        for w in self.widgets:
            if w.visible:
                w.draw(surf)
        if self._tip is not None and self._tip.tooltip and self._hover_time > 0.45:
            s = self._tip.tooltip
            w = draw.text_width(s, 15) + 24
            r = pygame.Rect(0, 0, w, 32)
            r.midtop = (self._tip.rect.centerx, self._tip.rect.bottom + 8)
            r.clamp_ip(surf.get_rect().inflate(-10, -10))
            draw.glass(surf, r, 8, (6, 8, 20, 230), T.GLASS_BORDER_HI)
            draw.text(surf, s, r.center, 15, T.TEXT, False, "c")


class Toasts:
    """Notificações empilhadas no topo."""
    COLORS = {"info": T.ACCENT_HI, "ok": T.GREEN, "warn": T.AMBER, "error": T.RED}

    def __init__(self):
        self.items: list = []

    def push(self, text, kind="info", life=3.2):
        self.items.append([str(text), kind, life, life])
        self.items = self.items[-4:]

    def update(self, dt):
        for it in self.items:
            it[2] -= dt
        self.items = [i for i in self.items if i[2] > 0]

    def draw(self, surf):
        y = 82
        for text, kind, life, total in self.items:
            a = min(1.0, life / 0.4, (total - life) / 0.25 + 0.01)
            w = draw.text_width(text, 18, True) + 64
            r = pygame.Rect(0, 0, w, 42)
            slide = (1.0 - min(1.0, (total - life) / 0.28)) ** 2 * 34
            r.midtop = (surf.get_width() // 2, int(y - slide - (1.0 - min(1.0, life / 0.4)) * 10))
            col = self.COLORS.get(kind, T.ACCENT_HI)
            draw.glass(surf, r, 12, (8, 12, 30, int(200 * a)), (*col, int(200 * a)))
            pygame.draw.circle(surf, col, (r.x + 20, r.centery), 5)
            draw.text(surf, text, (r.x + 38, r.centery), 18, T.TEXT, True, "ml", int(255 * a))
            y += 50
