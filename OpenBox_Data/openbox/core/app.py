"""Aplicativo principal: janela, contexto compartilhado e loop."""
from __future__ import annotations

import math
import time

import cv2
import numpy as np
import pygame

from .. import APP_NAME, STUDIO, __version__
from .. import theme as T
from ..paths import BRAND, screenshots_dir
from ..tracking.face_tracker import FaceTracker
from ..tracking.faces import FacesManager
from ..tracking.hand_tracker import HandTracker
from ..tracking.manager import HandsManager
from ..ui import draw
from ..ui.fx import FX
from ..ui.handfx import HandRenderer, draw_cursors
from ..ui.widgets import Toasts
from .audio import Audio
from .camera import Camera
from .events import EventBus
from .input import InputManager
from .scene import SceneManager
from .view import CameraView

W, H = 1280, 720
SCENE_NAMES = ("loading", "intro", "hub", "play", "calibration", "settings")


def load_logo():
    """Carrega o logo da Khyros (fundo preto) e converte em PNG translúcido, recortado."""
    try:
        img = pygame.image.load(str(BRAND / "khyros-logo.png"))
        rgb = pygame.surfarray.array3d(img).astype(np.float32)          # (w, h, 3)
        a = np.maximum(rgb.max(axis=2), 1.0)
        out = np.clip(rgb / a[..., None] * 255.0, 0, 255).astype(np.uint8)
        surf = pygame.Surface(img.get_size(), pygame.SRCALPHA)
        pygame.surfarray.pixels3d(surf)[:] = out
        pygame.surfarray.pixels_alpha(surf)[:] = a.astype(np.uint8)
        ys, xs = np.where(a.T > 12)
        box = pygame.Rect(int(xs.min()) - 8, int(ys.min()) - 8, int(xs.max() - xs.min()) + 16, int(ys.max() - ys.min()) + 16)
        return surf.subsurface(box.clip(surf.get_rect())).copy()
    except Exception as exc:
        print(f"[logo] {exc!r}")
        return None


class Context:
    """Tudo que as cenas precisam, num só lugar."""

    def __init__(self, app, cfg, screen, camera, tracker, face_tracker):
        self.app, self.cfg, self.screen = app, cfg, screen
        self.W, self.H = W, H
        self.camera, self.tracker, self.face_tracker = camera, tracker, face_tracker
        self.bus = EventBus()
        self.audio = Audio(cfg)
        self.view = CameraView(W, H)
        self.hands = HandsManager(tracker, cfg, self.view)
        self.faces = FacesManager(face_tracker, cfg, self.view)
        self.input = InputManager(cfg, self.hands)
        self.fx = FX(cfg)
        self.toasts = Toasts()
        self.renderer = HandRenderer(cfg)
        self.logo = load_logo()
        self.shake = 0.0
        self.scenes = None
        self.now = time.monotonic()
        self.debug = False
        self.start_mode = "menu"
        self._bg_seq = -1
        self._bg_surf = None
        self._bg_bytes = None
        self._dim = pygame.Surface((W, H))
        self._dim.fill((0, 0, 0))
        self._vignette = self._make_vignette()
        self._grid_t = 0.0

    # ------------------------------------------------------------------ helpers
    def toast(self, text, kind="info"):
        self.toasts.push(text, kind)
        if kind in ("ok", "info"):
            self.audio.play("notificacao", 0.5)
        elif kind == "error":
            self.audio.play("erro", 0.8)

    def pop_swipes(self):
        s, self.hands.swipes = self.hands.swipes, []
        return s

    def parallax(self):
        if self.cfg.head_parallax and self.faces.has_head:
            return self.faces.head
        return (0.0, 0.0)

    def _make_vignette(self):
        surf = pygame.Surface((W, H), pygame.SRCALPHA)
        xx, yy = np.meshgrid(np.linspace(-1, 1, W), np.linspace(-1, 1, H), indexing="ij")
        r = np.sqrt(xx * xx * 0.8 + yy * yy)
        a = (np.clip((r - 0.55) / 0.75, 0, 1) ** 1.6 * 170).astype(np.uint8)
        surf.fill((0, 0, 0, 255))
        pa = pygame.surfarray.pixels_alpha(surf)
        pa[:] = a
        del pa
        return surf

    # ------------------------------------------------------------------ fundo
    def draw_background(self, surf):
        frame, seq, _t = self.camera.latest()
        if frame is not None and self.camera.ready:
            if seq != self._bg_seq:
                self._bg_seq = seq
                fh, fw = frame.shape[:2]
                self.view.set_frame(fw, fh)
                cx, cy, cw, ch = self.view.crop()
                crop = frame[cy:cy + ch, cx:cx + cw]
                big = cv2.cvtColor(cv2.resize(crop, (W, H), interpolation=cv2.INTER_LINEAR), cv2.COLOR_BGR2RGB)
                self._bg_bytes = big.tobytes()
                self._bg_surf = pygame.image.frombuffer(self._bg_bytes, (W, H), "RGB")
                small = cv2.GaussianBlur(cv2.resize(crop, (96, 54), interpolation=cv2.INTER_AREA), (0, 0), 1.4)
                small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                bs = pygame.image.frombuffer(small.tobytes(), (96, 54), "RGB")
                blurred = pygame.transform.smoothscale(bs, (W, H)).convert_alpha()
                blurred.fill((175, 182, 210, 255), special_flags=pygame.BLEND_RGBA_MULT)
                draw.set_blur(blurred)
            surf.blit(self._bg_surf, (0, 0))
            self._dim.set_alpha(int(self.cfg.camera_dim * 255))
            surf.blit(self._dim, (0, 0))
            if self.cfg.vignette:
                surf.blit(self._vignette, (0, 0))
        else:
            self._draw_void(surf)

    def _draw_void(self, surf):
        """Fundo sem câmera: grade em perspectiva animada."""
        surf.fill(T.BG)
        draw.set_blur(None)
        self._grid_t = (self._grid_t + 1 / 60) % 1.0
        vx, vy = W / 2 + self.parallax()[0] * 40, H * 0.42
        for i in range(-12, 13):
            pygame.draw.line(surf, (18, 26, 62), (vx + i * 30, vy), (vx + i * 330, H), 1)
        for k in range(14):
            f = ((k + self._grid_t) / 14.0) ** 2.2
            y = vy + (H - vy) * f
            pygame.draw.line(surf, T.mix((10, 14, 34), (36, 52, 130), f), (0, y), (W, y), 1)
        surf.blit(self._vignette, (0, 0))
        msg = None
        if self.camera.state == "error":
            msg = self.camera.info or "Câmera indisponível"
        elif self.camera.state in ("idle", "opening"):
            msg = "Abrindo câmera..."
        if msg:
            draw.text(surf, msg, (W // 2, H - 56), 18, T.AMBER, True, "c", 220)

    def draw_hands(self, surf, held_slots=()):
        self.renderer.draw(surf, self.hands.visible(), held_slots)


class App:
    def __init__(self, cfg, no_camera=False, no_intro=False, start_mode=None, start_scene=None):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        pygame.display.set_caption(f"{APP_NAME} — {STUDIO}")
        try:
            icon = pygame.image.load(str(BRAND / "khyros-logo.png"))
            pygame.display.set_icon(pygame.transform.smoothscale(icon, (64, 64)))
        except Exception:
            pass
        flags = pygame.SCALED | (pygame.FULLSCREEN if cfg.fullscreen else pygame.RESIZABLE)
        try:
            self.screen = pygame.display.set_mode((W, H), flags, vsync=1)
        except Exception:
            self.screen = pygame.display.set_mode((W, H), flags)
        self.cfg = cfg
        self.clock = pygame.time.Clock()
        self.running = True
        self.no_camera = no_camera
        self.camera = Camera(cfg)
        self.tracker = HandTracker(self.camera, cfg)
        self.face_tracker = FaceTracker(self.camera, cfg)
        if not no_camera:
            self.camera.start()
            self.tracker.start()
            self.face_tracker.start()
        self.ctx = Context(self, cfg, self.screen, self.camera, self.tracker, self.face_tracker)
        self.tracker.bus = self.ctx.bus
        self.ctx.bus.on("tracker_error", lambda message: self.ctx.toast(f"Rastreamento falhou: {message[:60]}", "error"))
        self.scenes = SceneManager(self.ctx)
        self.ctx.scenes = self.scenes
        self._register_scenes()
        mode = start_mode or (cfg.start_mode if cfg.start_mode != "menu" else None)
        self.ctx.start_mode = mode or "menu"
        self.ctx.skip_intro = bool(cfg.skip_intro or no_intro)
        self.scenes.start(start_scene or "loading")

    def _register_scenes(self):
        from ..scenes.calibration import CalibrationScene
        from ..scenes.hub import HubScene
        from ..scenes.intro import IntroScene
        from ..scenes.loading import LoadingScene
        from ..scenes.play import PlayScene
        from ..scenes.settings import SettingsScene
        for name, cls in (("loading", LoadingScene), ("intro", IntroScene), ("hub", HubScene), ("play", PlayScene),
                          ("calibration", CalibrationScene), ("settings", SettingsScene)):
            self.scenes.register(name, cls)

    # ------------------------------------------------------------------ ações globais
    def quit(self):
        self.running = False

    def toggle_fullscreen(self):
        self.cfg.fullscreen = not self.cfg.fullscreen
        try:
            pygame.display.toggle_fullscreen()
        except Exception:
            pass

    def screenshot(self):
        path = screenshots_dir() / time.strftime("openbox_%Y%m%d_%H%M%S.png")
        try:
            pygame.image.save(self.screen, str(path))
            self.ctx.fx.flash((255, 255, 255), 120)
            self.ctx.toast(f"Captura salva: Capturas/{path.name}", "ok")
        except Exception as exc:
            self.ctx.toast(f"Falha ao salvar captura: {exc}", "error")

    # ------------------------------------------------------------------ loop
    def run(self):
        ctx = self.ctx
        try:
            while self.running:
                dt = min(self.clock.tick(self.cfg.target_fps) / 1000.0, 0.05)
                ctx.now = now = time.monotonic()
                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        self.running = False
                    elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                        self.toggle_fullscreen()
                    elif e.type == pygame.KEYDOWN and e.key == pygame.K_F12:
                        self.screenshot()
                    elif e.type == pygame.KEYDOWN and e.key == pygame.K_F3:
                        ctx.debug = not ctx.debug
                    else:
                        self.scenes.event(e)
                ctx.hands.update(dt, now)
                ctx.faces.update(dt, now)
                ctx.input.update(dt, now, self.camera.ready)
                self._guard(lambda: self.scenes.update(dt))
                ctx.fx.update(dt)
                ctx.toasts.update(dt)
                ctx.hands.swipes.clear()

                self._guard(lambda: self.scenes.draw(self.screen))
                self._apply_shake(dt)
                ctx.fx.draw(self.screen)
                ctx.toasts.draw(self.screen)
                cur = self.scenes.current
                if cur is not None and cur.cursors:
                    draw_cursors(self.screen, ctx.input.pointers, now)
                if ctx.debug:
                    self._draw_debug(dt)
                pygame.display.flip()
        finally:
            self.cfg.save()
            self.camera.stop()
            self.tracker.stop()
            self.face_tracker.stop()
            pygame.quit()

    def _guard(self, fn):
        """Se uma cena lançar erro, registra em OpenBox_Data/erros.log e segue (volta ao menu após erros repetidos)."""
        try:
            fn()
            self._errs = max(0, getattr(self, "_errs", 0) - 0.02)
        except Exception:
            import traceback
            from ..paths import DATA
            tb = traceback.format_exc()
            print(tb)
            try:
                with open(DATA / "erros.log", "a", encoding="utf-8") as f:
                    f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + tb + "\n")
            except OSError:
                pass
            self._errs = getattr(self, "_errs", 0) + 1
            if self._errs == 1:
                self.ctx.toast("Erro interno registrado em OpenBox_Data/erros.log", "error")
            if self._errs >= 6 and self.scenes.current is not None and self.scenes.current.name != "hub":
                self._errs = 0
                self.scenes.go("hub")

    def _apply_shake(self, dt):
        c = self.ctx
        if c.shake > 0.6:
            tmp = self.screen.copy()
            self.screen.fill((0, 0, 0))
            self.screen.blit(tmp, (int(math.sin(c.now * 90) * c.shake), int(math.cos(c.now * 77) * c.shake)))
            c.shake *= math.exp(-dt * 9.0)
        else:
            c.shake = 0.0

    def _draw_debug(self, dt):
        s, c = self.screen, self.ctx
        snap = self.tracker.snapshot
        lines = [
            f"{APP_NAME} v{__version__}  |  render {self.clock.get_fps():.0f} fps  |  câmera {self.camera.fps:.0f} fps ({self.camera.info})  |  luz {snap.brightness:.0f}/255",
            f"mãos {c.hands.fps:.0f} fps · {c.hands.infer_ms:.1f} ms · res {snap.infer_w}px · latência {c.hands.latency * 1000:.0f} ms · {self.tracker.state}   |   "
            f"rosto {c.faces.fps:.0f} fps · {c.faces.infer_ms:.1f} ms · {self.face_tracker.state}",
        ]
        for hv in c.hands.visible():
            lines.append(f"mão {hv.slot} [{hv.label}] gesto={hv.gesture} pinça={hv.pinch_ratio:.2f} tam={hv.size_px:.0f}px armada={hv.armed} gatilho={hv.trigger} stale={hv.stale}")
        for fv in c.faces.visible():
            lines.append(f"rosto {fv.slot} larg={fv.width:.0f}px roll={math.degrees(fv.roll):.0f}° yaw={fv.yaw:.2f} boca={fv.mouth_open:.2f}")
        r = pygame.Rect(10, self.screen.get_height() - 24 - 20 * len(lines), 1000, 20 * len(lines) + 12)
        draw.rrect(s, r, (0, 0, 0, 170), 8)
        for i, ln in enumerate(lines):
            draw.text(s, ln, (r.x + 10, r.y + 6 + i * 20), 14, T.GREEN)
