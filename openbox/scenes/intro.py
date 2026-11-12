"""Intro: toca o vídeo da Khyros Studio (pulável por tecla, clique ou pinça)."""
from __future__ import annotations

import cv2
import pygame

from .. import theme as T
from ..core.scene import Scene
from ..paths import VIDEO
from ..ui import draw


class IntroScene(Scene):
    name = "intro"
    cursors = False

    def enter(self, **kw):
        self.t = 0.0
        self.cap = None
        self.surf = None
        self.frame_i = -1
        self.done = False
        self.fps, self.dur = 30.0, 3.0
        try:
            cap = cv2.VideoCapture(str(VIDEO / "khyros-intro.mp4"))
            if cap.isOpened():
                self.cap = cap
                self.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                n = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                self.dur = (n / self.fps) if n > 0 else 8.0
        except Exception as exc:
            print(f"[intro] vídeo indisponível: {exc!r}")
        self.ctx.audio.play("boot")

    def exit(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def finish(self):
        if not self.done:
            self.done = True
            self.ctx.scenes.go("hub")

    def event(self, e):
        if e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.finish()

    def update(self, dt):
        self.t += dt
        if any(p.pressed for p in self.ctx.input.pointers):
            self.finish()
        if self.t >= self.dur:
            self.finish()
        if self.cap is not None and not self.done:
            target = int(self.t * self.fps)
            while self.frame_i < target - 1:
                if not self.cap.grab():
                    break
                self.frame_i += 1
            if self.frame_i < target:
                ok, frame = self.cap.read()
                self.frame_i += 1
                if ok:
                    rgb = cv2.cvtColor(cv2.resize(frame, (self.ctx.W, self.ctx.H), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
                    self._buf = rgb.tobytes()
                    self.surf = pygame.image.frombuffer(self._buf, (self.ctx.W, self.ctx.H), "RGB")

    def draw(self, surf):
        surf.fill((0, 0, 0))
        if self.surf is not None:
            surf.blit(self.surf, (0, 0))
        elif self.ctx.logo is not None:      # sem vídeo: logo com fade
            a = min(1.0, self.t / 0.8)
            logo = self.ctx.logo
            sc = 0.9 + 0.1 * a
            img = pygame.transform.smoothscale(logo, (int(logo.get_width() * sc), int(logo.get_height() * sc)))
            img.set_alpha(int(255 * a))
            surf.blit(img, img.get_rect(center=(self.ctx.W // 2, self.ctx.H // 2)))
        alpha = min(1.0, self.t * 0.9) * 0.6
        draw.text(surf, "Pressione qualquer tecla ou faça uma pinça para pular", (self.ctx.W // 2, self.ctx.H - 34), 15, T.MUTED, False, "c", int(255 * alpha))
