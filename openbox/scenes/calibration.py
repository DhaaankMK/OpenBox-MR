"""Calibração da pinça: mede a mão aberta e fechada e ajusta os limiares (engage/release) ao seu tamanho de mão."""
from __future__ import annotations

import statistics

import pygame

from .. import theme as T
from ..core.scene import Scene
from ..ui import draw
from ..ui.hud import TopBar
from ..ui.widgets import Button, Panel

STEP_TITLES = ["Mostre a mão", "Mão aberta", "Faça a pinça", "Resultado"]


class CalibrationScene(Scene):
    name = "calibration"

    def __init__(self, ctx):
        super().__init__(ctx)
        W = ctx.W
        self.ui.add(TopBar(ctx, "CALIBRAÇÃO", "Ajuste a pinça ao tamanho da sua mão"))
        self.ui.add(Button((24, 18, 44, 44), icon="home", tooltip="Voltar", on_click=lambda: ctx.scenes.go("hub")))
        self.panel = self.ui.add(Panel((W // 2 - 340, 120, 680, 330), None, T.GREEN, radius=20))
        self.b_apply = self.ui.add(Button((W // 2 - 200, 390, 190, 48), "Aplicar", self._apply, icon="check", style="primary"))
        self.b_retry = self.ui.add(Button((W // 2 + 10, 390, 190, 48), "Refazer", self.reset, icon="refresh"))
        self.b_default = self.ui.add(Button((W // 2 - 110, 470, 220, 44), "Restaurar padrão", self._default, size=16))
        self.reset()

    def reset(self):
        self.step, self.prog, self.hold = 0, 0.0, 0.0
        self.open_s, self.pinch_s = [], []
        self.open_r = 1.0
        self.calc = None

    def enter(self, **kw):
        self.reset()

    def exit(self):
        self.ctx.cfg.save()

    def _hand(self):
        hs = [h for h in self.ctx.hands.visible() if not h.stale and h.disp is not None]
        return max(hs, key=lambda h: h.size_px) if hs else None

    def _apply(self):
        if self.calc and self.calc["ok"]:
            self.ctx.cfg.pinch_engage = self.calc["engage"]
            self.ctx.cfg.pinch_release = self.calc["release"]
            self.ctx.cfg.clamp()
            self.ctx.cfg.save()
            self.ctx.toast("Pinça calibrada!", "ok")
            self.ctx.scenes.go("hub")

    def _default(self):
        self.ctx.cfg.pinch_engage, self.ctx.cfg.pinch_release = 0.30, 0.46
        self.ctx.cfg.save()
        self.ctx.toast("Limiares padrão restaurados", "info")

    def update(self, dt):
        self.ui.update(dt, self.ctx.input.pointers)
        hv = self._hand()
        self.b_apply.visible = self.b_retry.visible = self.step == 3
        self.b_apply.enabled = bool(self.calc and self.calc["ok"])
        self.b_default.visible = self.step != 3
        if self.step == 0:
            self.hold = self.hold + dt if hv else 0.0
            if self.hold > 1.0:
                self.step, self.prog, self.hold = 1, 0.0, 0.0
                self.ctx.audio.play("count")
        elif self.step == 1:
            if hv and hv.pinch_ratio > 0.5 and not hv.pinching:
                self.open_s.append(hv.pinch_ratio)
                self.prog += dt
            elif not hv:
                self.prog = max(0.0, self.prog - dt)
            if self.prog >= 2.0 and len(self.open_s) > 20:
                self.open_r = statistics.median(self.open_s)
                self.step, self.prog = 2, 0.0
                self.ctx.audio.play("count")
        elif self.step == 2:
            if hv and hv.pinch_ratio < self.open_r * 0.55:
                self.pinch_s.append(hv.pinch_ratio)
                self.prog += dt
            else:
                self.prog = max(0.0, self.prog - dt * 0.5)
            if self.prog >= 1.5 and len(self.pinch_s) > 15:
                self._finish()

    def _finish(self):
        closed = statistics.median(self.pinch_s)
        o = self.open_r
        ok = (o - closed) > 0.25
        self.calc = dict(closed=closed, open=o, ok=ok,
                         engage=closed + 0.30 * (o - closed), release=closed + 0.52 * (o - closed))
        self.step = 3
        self.ctx.audio.play("sucesso" if ok else "erro")

    def draw(self, surf):
        ctx = self.ctx
        ctx.draw_background(surf)
        ctx.draw_hands(surf)
        self.ui.draw(surf)
        r = self.panel.rect
        draw.text(surf, f"PASSO {min(self.step + 1, 4)} DE 4", (r.x + 28, r.y + 24), 13, T.GREEN, True)
        draw.text(surf, STEP_TITLES[self.step], (r.x + 28, r.y + 46), 30, T.TEXT, True)
        msgs = ["Coloque a mão na frente da câmera, com a palma voltada para ela.",
                "Mantenha a mão ABERTA e relaxada, sem pinçar.",
                "Junte a ponta do polegar e do indicador (pinça) e segure.",
                "Calibração concluída. Confira os valores e aplique."]
        for i, line in enumerate(draw.wrap(msgs[self.step], 18, r.w - 60)):
            draw.text(surf, line, (r.x + 28, r.y + 96 + i * 26), 18, T.MUTED)
        # progresso
        if self.step in (1, 2):
            need = 2.0 if self.step == 1 else 1.5
            draw.ring(surf, (r.right - 90, r.y + 100), 40, (255, 255, 255), 6, 40)
            draw.arc(surf, (r.right - 90, r.y + 100), 40, T.GREEN, self.prog / need, 6)
        elif self.step == 0 and self.hold > 0:
            draw.arc(surf, (r.right - 90, r.y + 100), 40, T.GREEN, self.hold / 1.0, 6)
        # medidor ao vivo
        hv = self._hand()
        gx, gy, gw = r.x + 28, r.y + 190, r.w - 56
        draw.text(surf, "RAZÃO DA PINÇA (polegar↔indicador ÷ tamanho da mão)", (gx, gy - 22), 12, T.DIM, True)
        draw.rrect(surf, (gx, gy + 10, gw, 14), (255, 255, 255, 36), 7)
        scale = 1.4
        for val, col, lab in ((ctx.cfg.pinch_engage, T.GREEN, "fecha"), (ctx.cfg.pinch_release, T.AMBER, "abre")):
            x = gx + int(gw * min(1.0, val / scale))
            pygame.draw.line(surf, col, (x, gy + 4), (x, gy + 30), 2)
            draw.text(surf, f"{lab} {val:.2f}", (x, gy + 34), 12, col, True, "tc")
        if hv:
            x = gx + int(gw * min(1.0, hv.pinch_ratio / scale))
            draw.glow(surf, (x, gy + 17), 26, T.CYAN, 0.8)
            pygame.draw.circle(surf, (255, 255, 255), (x, gy + 17), 8)
            draw.text(surf, f"{hv.pinch_ratio:.2f}", (x, gy - 6), 14, T.TEXT, True, "c")
        else:
            draw.text(surf, "Sem mão detectada", (gx, gy + 56), 14, T.AMBER)
        if self.step == 3 and self.calc:
            c = self.calc
            col = T.GREEN if c["ok"] else T.RED
            msg = (f"Aberta {c['open']:.2f} · fechada {c['closed']:.2f}  →  fecha em {c['engage']:.2f} · abre em {c['release']:.2f}"
                   if c["ok"] else "A diferença entre aberta e fechada foi pequena. Refaça com movimentos mais nítidos.")
            draw.text(surf, msg, (r.x + 28, r.y + 258), 16, col, True)
