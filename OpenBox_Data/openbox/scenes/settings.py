"""Ajustes dentro do jogo (mesmas páginas do launcher) + Sobre e conquistas."""
from __future__ import annotations

import pygame

from .. import APP_NAME, AUTHOR, STUDIO, __version__
from .. import theme as T
from ..core.scene import Scene
from ..game.state import ACHIEVEMENTS
from ..ui import draw
from ..ui.hud import TopBar
from ..ui.settings_pages import build_pages, layout
from ..ui.widgets import Button, Panel, Tabs


class SettingsScene(Scene):
    name = "settings"

    def __init__(self, ctx):
        super().__init__(ctx)
        W, cfg = ctx.W, ctx.cfg
        self.tab = 0
        self.ui.add(TopBar(ctx, "AJUSTES", "Tudo é salvo em Configurações.json"))
        self.ui.add(Button((24, 18, 44, 44), icon="home", tooltip="Voltar", on_click=lambda: ctx.scenes.go("hub")))
        px, py, pw, ph = W // 2 - 440, 88, 880, 600
        self.px, self.py = px, py
        self.ui.add(Panel((px, py, pw, ph), None, T.ACCENT_HI, radius=20))
        actions = dict(apply_camera=self._apply_camera, calibrate=lambda: ctx.scenes.go("calibration"),
                       fullscreen=ctx.app.toggle_fullscreen, test_sound=lambda: ctx.audio.play("sucesso"))
        pages = build_pages(cfg, actions)
        names = [n for n, _ in pages] + ["Sobre"]
        self.ui.add(Tabs((px + 16, py + 14, pw - 32, 42), names, lambda: self.tab, self._set_tab))
        self.groups = []
        for name, widgets in pages:
            layout(widgets, px + 30, py + 80)
            for w in widgets:
                self.ui.add(w)
            self.groups.append(widgets)
        reset = Button((px + 30, py + ph - 76, 400, 50), "Restaurar padrões", self._reset, icon="refresh", style="danger")
        self.ui.add(reset)
        self.groups.append([reset])

    def _set_tab(self, i):
        self.tab = i

    def _apply_camera(self):
        self.ctx.camera.reconfigure()
        self.ctx.toast("Reabrindo a câmera com as novas opções...", "info")

    def _reset(self):
        self.ctx.cfg.reset_to_defaults()
        self.ctx.toast("Padrões restaurados", "ok")

    def exit(self):
        self.ctx.cfg.save()

    def event(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.ctx.scenes.go("hub")

    def update(self, dt):
        for i, grp in enumerate(self.groups):
            for w in grp:
                w.visible = i == self.tab
        self.ui.update(dt, self.ctx.input.pointers)

    def draw(self, surf):
        ctx = self.ctx
        ctx.draw_background(surf)
        self.ui.draw(surf)
        x, y = self.px + 30, self.py + 80
        if self.tab == 0:
            st = {"ready": ("Câmera ativa", T.GREEN), "opening": ("Abrindo...", T.AMBER), "error": ("Indisponível", T.RED), "idle": ("Parada", T.DIM)}[ctx.camera.state]
            draw.text(surf, f"Estado: {st[0]}  ·  {ctx.camera.info or '—'}  ·  {ctx.camera.fps:.0f} fps", (x + 414, y + 6), 15, st[1], True)
            for i, line in enumerate(draw.wrap("Escolha índice, resolução e FPS e toque em Aplicar câmera. Resoluções menores reduzem a latência do rastreamento.", 14, 400)):
                draw.text(surf, line, (x + 414, y + 36 + i * 19), 14, T.MUTED)
        elif self.tab == len(self.groups) - 1:
            draw.text(surf, f"{APP_NAME} v{__version__}", (x, y), 26, T.TEXT, True)
            draw.text(surf, f"Desenvolvido por {STUDIO}  ·  autor: {AUTHOR}", (x, y + 36), 16, T.ACCENT_HI, True)
            for i, line in enumerate(draw.wrap("Licença DUMP-L v1.0: uso pessoal, educacional e de entretenimento. É proibido modificar, remover créditos ou comercializar sem autorização. Veja LICENSE.txt.", 14, 400)):
                draw.text(surf, line, (x, y + 70 + i * 19), 14, T.MUTED)
            draw.text(surf, "Tecnologias: MediaPipe · OpenCV · Pygame · NumPy", (x, y + 160), 14, T.DIM)
            ax = x + 430
            draw.text(surf, "CONQUISTAS", (ax, y), 13, T.ACCENT_HI, True)
            for i, (k, (name, desc)) in enumerate(ACHIEVEMENTS.items()):
                got = k in ctx.cfg.achievements
                yy = y + 24 + i * 31
                pygame.draw.circle(surf, T.GREEN if got else T.DIM, (ax + 8, yy + 9), 6, 0 if got else 2)
                draw.text(surf, name, (ax + 26, yy), 15, T.TEXT if got else T.MUTED, True)
                draw.text(surf, desc, (ax + 26, yy + 16), 12, T.DIM)
