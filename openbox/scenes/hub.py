"""Hub principal: cartões animados para cada modo (pinça, apontar parado, swipe ou mouse)."""
from __future__ import annotations

import math
import random

import pygame

from .. import APP_NAME, STUDIO, __version__
from .. import theme as T
from ..config import POSTURE_ORDER
from ..core.scene import Scene
from ..ui import draw, icons
from ..ui.anim import ease_out_back, ease_out_cubic
from ..ui.hud import hint_bar
from ..ui.widgets import Button, Widget


class Card(Widget):
    dwellable = True

    def __init__(self, rect, icon, title, desc, accent, on_click, index, mode):
        super().__init__(rect)
        self.icon, self.title, self.desc, self.accent, self.on_click, self.index, self.mode = icon, title, desc, accent, on_click, index, mode
        self.focus = False
        self.t = 0.0
        self.tilt = [0.0, 0.0]

    def tick(self, dt):
        super().tick(dt)
        self.t += dt
        tx = ty = 0.0
        for p in self.ui.ctx.input.pointers:
            if self.rect.inflate(60, 60).collidepoint(p.x, p.y):
                tx = (p.x - self.rect.centerx) / (self.rect.w / 2)
                ty = (p.y - self.rect.centery) / (self.rect.h / 2)
        k = min(1.0, dt * 9)
        self.tilt[0] += (tx - self.tilt[0]) * k
        self.tilt[1] += (ty - self.tilt[1]) * k

    def on_release(self, p, inside):
        if inside:
            self.click(p)

    def click(self, p=None):
        self._sound("click")
        self.on_click()

    def _best(self):
        cfg = self.ui.ctx.cfg
        if self.mode == "tutorial":
            return "CONCLUÍDO" if cfg.tutorial_done else ""
        if self.mode == "survival":
            b = cfg.highscores.get("survival", 0)
            return f"RECORDE {b} · ONDA {cfg.highscores.get('survival_onda', 0)}" if b else ""
        b = cfg.highscores.get(self.mode, 0)
        return f"RECORDE {b}" if b and self.mode != "sandbox" else ""

    def draw(self, surf):
        anim = self.ui.ctx.cfg.ui_anim
        appear = max(0.0, min(1.0, (self.t - 0.08 * self.index) / 0.55)) if anim else 1.0
        if appear <= 0:
            return
        ease = ease_out_back(appear) if anim else 1.0
        e1 = ease_out_cubic(appear)
        lift = 10 * self.h
        r = self.rect.move(0, int((1 - min(1.0, ease)) * 46 - lift)).inflate(int(10 * self.h), int(10 * self.h))
        hot = self.h > 0.3 or self.focus
        tint = (*T.mix((10, 14, 34), self.accent, 0.24 if hot else 0.07), int(180 * e1))
        border = (*self.accent, int((220 if hot else 80) * e1))
        draw.glass(surf, r, 20, tint, border, accent=self.accent)
        cx = r.centerx + self.tilt[0] * 9 * self.h
        cy = r.y + 116 + self.tilt[1] * 6 * self.h + math.sin(self.t * 2.0 + self.index) * 3
        pulse = 1.0 + 0.06 * math.sin(self.t * 3 + self.index)
        draw.glow(surf, (cx, cy), 100 * pulse, self.accent, 0.22 + 0.34 * self.h)
        draw.ring(surf, (cx, cy), 62 + 8 * self.h + 3 * math.sin(self.t * 2), self.accent, 2, int(60 + 100 * self.h))
        icons.draw(self.icon, surf, cx, cy, 44 * pulse, self.accent, 4)
        draw.text(surf, self.title, (r.centerx, r.y + 204), 25, T.TEXT, True, "c", int(255 * e1))
        for i, line in enumerate(draw.wrap(self.desc, 16, r.w - 44)):
            draw.text(surf, line, (r.centerx, r.y + 240 + i * 22), 16, T.MUTED, False, "c", int(255 * e1))
        best = self._best()
        if best:
            draw.text(surf, best, (r.centerx, r.bottom - 50), 13, T.AMBER if "RECORDE" in best else T.GREEN, True, "c", int(255 * e1))
        a = int(255 * max(self.h, 0.35 if self.focus else 0.0))
        if a:
            draw.text(surf, "JOGAR", (r.centerx, r.bottom - 26), 14, self.accent, True, "c", a)


class HubScene(Scene):
    name = "hub"

    def __init__(self, ctx):
        super().__init__(ctx)
        W = ctx.W
        go = ctx.scenes.go
        spec = [
            ("hand", "TUTORIAL", "Aprenda cada gesto passo a passo: pinça, tiro, menu, chapéus e mais.", T.GREEN, "tutorial"),
            ("cube", "SANDBOX", "Crie objetos, bots e armas. Agarre, arremesse e destrua sem regras.", T.CYAN, "sandbox"),
            ("target", "PRACTICE", "Treino de pontaria: acerte alvos com arremessos e tiros, junte combos.", T.MAGENTA, "practice"),
            ("bomb", "SOBREVIVÊNCIA", "Zumbis em ondas! Defenda o reator com armas, mãos e o que achar.", T.RED, "survival"),
        ]
        cw, ch, gap = 270, 340, 24
        x0 = (W - (cw * 4 + gap * 3)) // 2
        self.cards = [self.ui.add(Card((x0 + i * (cw + gap), 190, cw, ch), ic, t, d, ac, (lambda m=m: go("play", mode=m)), i, m))
                      for i, (ic, t, d, ac, m) in enumerate(spec)]
        self.ui.add(Button((W - 76, 26, 48, 48), icon="cross", style="danger", tooltip="Sair", on_click=ctx.app.quit))
        self.ui.add(Button((W - 136, 26, 48, 48), icon="gear", tooltip="Ajustes", on_click=lambda: go("settings")))
        self.ui.add(Button((W - 196, 26, 48, 48), icon="hand", tooltip="Calibrar a pinça", on_click=lambda: go("calibration")))
        self.posture_btn = self.ui.add(Button((W // 2 - 150, 548, 300, 44), lambda: f"Postura: {ctx.cfg.post['label']}", self._toggle_posture, icon="refresh", size=16,
                                              tooltip="Sentado ou em pé: ajusta alcance, tamanho dos botões e sensibilidade"))
        self.retry = self.ui.add(Button((W // 2 - 110, 604, 220, 40), "Tentar câmera de novo", self._retry, icon="refresh", size=15))
        self.focus = 0
        self.dots = [[random.uniform(0, W), random.uniform(0, ctx.H), random.uniform(8, 28), random.uniform(0.3, 1.0)] for _ in range(46)]

    def _toggle_posture(self):
        cfg = self.ctx.cfg
        cfg.posture = POSTURE_ORDER[(POSTURE_ORDER.index(cfg.posture) + 1) % len(POSTURE_ORDER)]
        cfg.save()
        if cfg.posture == "em_pe":
            self.ctx.toast("Em pé: afaste-se ~1,5–2 m da câmera, mostre o corpo todo e use gestos amplos", "info")
        else:
            self.ctx.toast("Sentado: fique a ~60–90 cm da câmera, com as mãos à vista", "info")

    def _retry(self):
        self.ctx.camera.reconfigure()
        self.ctx.toast("Reabrindo câmera...", "info")

    def enter(self, **kw):
        for c in self.cards:
            c.t = 0.0
        self.focus = 0

    def event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_RIGHT:
                self.focus = (self.focus + 1) % 4
            elif e.key == pygame.K_LEFT:
                self.focus = (self.focus - 1) % 4
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.cards[self.focus].click()
            elif e.key == pygame.K_ESCAPE:
                self.ctx.app.quit()

    def update(self, dt):
        for _slot, name in list(self.ctx.hands.swipes):
            self.focus = (self.focus + (1 if name == "swipe_right" else -1)) % 4
            self.ctx.audio.play("whoosh", 0.6)
        self.ui.update(dt, self.ctx.input.pointers)
        for i, c in enumerate(self.cards):
            c.focus = i == self.focus
            if c.hovered:
                self.focus = i
        self.retry.visible = self.ctx.camera.state == "error"
        for d in self.dots:
            d[1] -= d[2] * dt
            if d[1] < -10:
                d[0], d[1] = random.uniform(0, self.ctx.W), self.ctx.H + 10

    def draw(self, surf):
        ctx = self.ctx
        ctx.draw_background(surf)
        for x, y, _v, k in self.dots:
            draw.glow(surf, (x, y), 6, T.ACCENT_HI, 0.35 * k)
        px, py = ctx.parallax()
        if ctx.logo is not None:
            lg = ctx.logo
            h = 52
            img = pygame.transform.smoothscale(lg, (int(lg.get_width() * h / lg.get_height()), h))
            surf.blit(img, (34 + px * 4, 24 + py * 3))
        title = APP_NAME.upper().replace(" MR", "")
        total = draw.spaced(surf, title, (ctx.W // 2 - 22, 74 + py * 3), 54, T.TEXT, True, 14, "tc")
        draw.text(surf, "MR", (ctx.W // 2 - 22 + total // 2 + 18, 96 + py * 3), 24, T.ACCENT_HI, True)
        draw.text(surf, "MIXED REALITY ENGINE", (ctx.W // 2, 142), 15, T.ACCENT_HI, True, "c")
        draw.text(surf, "Pince para clicar  ·  deslize a palma para trocar  ·  aponte parado para selecionar", (ctx.W // 2, 164), 15, T.MUTED, False, "c")
        self.ui.draw(surf)
        if ctx.camera.state == "error":
            draw.text(surf, f"{ctx.camera.info or 'Câmera indisponível'} — o mouse funciona como ponteiro.", (ctx.W // 2, 590), 16, T.AMBER, True, "c")
        elif ctx.camera.ready and not ctx.hands.visible():
            a = int(140 + 100 * math.sin(ctx.now * 3))
            draw.text(surf, "Mostre a mão para a câmera", (ctx.W // 2, 606), 18, T.CYAN, True, "c", a)
        if ctx.camera.ready and ctx.tracker.snapshot.brightness < 55:
            draw.text(surf, "Pouca luz: o rastreamento fica bem melhor com o ambiente mais claro", (ctx.W // 2, 640), 14, T.AMBER, True, "c")
        hint_bar(surf, ctx, [("hand", "Pinça: clicar"), ("right", "Deslizar: trocar"), ("target", "Apontar parado: selecionar"), ("camera", "F12: captura")], y=ctx.H - 62)
        draw.text(surf, f"v{__version__}  ·  {STUDIO}", (24, ctx.H - 24), 13, T.DIM, False, "bl")
        ctx.draw_hands(surf)
