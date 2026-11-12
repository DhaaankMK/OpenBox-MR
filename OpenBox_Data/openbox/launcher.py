"""OpenBox MR Launcher — diagnóstico, câmeras com pré-visualização e todas as configurações (Configurações.json)."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading
import time

import cv2
import numpy as np
import pygame

from . import APP_NAME, STUDIO, __version__
from . import theme as T
from .config import Config
from .core.audio import Audio
from .core.camera import _open_capture, probe_cameras
from .core.input import Pointer
from .paths import BRAND, CONFIG_FILE, MODELS, ROOT, SOUNDS
from .scenes.loading import draw_open_box
from .ui import draw
from .ui.settings_pages import build_pages, layout
from .ui.widgets import UI, Button, Panel, Tabs, Toasts

LW, LH = 1240, 680
NEWS = [
    "Modos: Tutorial, Sandbox, Practice e Sobrevivência (zumbis + armas)",
    "Mais de 60 itens: objetos, bots, armas, chapéus e ferramentas",
    "Rastreamento de mãos e rosto reforçado; dedo-pistola com gatilho",
    "Menus de criação: radial (gesto ROCK / botão direito) e catálogo",
]


class LCtx:
    def __init__(self, cfg):
        self.cfg = cfg
        self.audio = Audio(cfg)


def check_system():
    rows = []
    py_ok = (3, 9) <= sys.version_info[:2] <= (3, 12)
    rows.append(("Python", sys.version_info >= (3, 9), f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}" +
                 ("" if py_ok else "  (recomendado 3.10–3.12)")))
    for label, mod in (("Pygame", "pygame"), ("OpenCV", "cv2"), ("MediaPipe", "mediapipe"), ("NumPy", "numpy")):
        if importlib.util.find_spec(mod) is None:
            rows.append((label, False, "não instalado"))
            continue
        try:
            m = __import__(mod)
            rows.append((label, True, str(getattr(m, "__version__", getattr(m, "ver", "ok")))))
        except Exception as exc:
            rows.append((label, False, f"erro: {type(exc).__name__}"))
    for f in ("hand_landmarker.task", "face_landmarker.task"):
        p = MODELS / f
        rows.append((f"Modelo {f.split('_')[0]}", p.exists(), f"{p.stat().st_size / 1e6:.1f} MB" if p.exists() else "ausente (será baixado)"))
    ok = all((SOUNDS / n).exists() for n in ("click.mp3", "erro.mp3", "sucesso.mp3", "notificacao.wav")) and (BRAND / "khyros-logo.png").exists()
    rows.append(("Sons e imagens", ok, "ok" if ok else "faltando em OpenBox_Data/assets"))
    rows.append(("Configurações.json", True, "encontrado" if CONFIG_FILE.exists() else "será criado ao salvar"))
    return rows


class CamPreview:
    """Pré-visualização da webcam (thread própria) — só roda quando você pede, para não segurar a câmera."""

    def __init__(self):
        self.frame = None
        self.running = False
        self.error = ""
        self._stop = threading.Event()
        self._thread = None

    def start(self, index, w, h):
        self.stop()
        self._stop.clear()
        self.running = True
        self.error = ""
        self._thread = threading.Thread(target=self._run, args=(index, w, h), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self.running = False
        self.frame = None

    def _run(self, index, w, h):
        cap = _open_capture(index, w, h, 30)
        if cap is None:
            self.error = f"Câmera #{index} indisponível"
            self.running = False
            return
        while not self._stop.is_set():
            ok, f = cap.read()
            if ok:
                self.frame = cv2.resize(f, (480, 270), interpolation=cv2.INTER_AREA)
            else:
                time.sleep(0.02)
        cap.release()


class Launcher:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        pygame.display.set_caption(f"{APP_NAME} — Launcher")
        try:
            pygame.display.set_icon(pygame.transform.smoothscale(pygame.image.load(str(BRAND / "khyros-logo.png")), (64, 64)))
        except Exception:
            pass
        self.screen = pygame.display.set_mode((LW, LH))
        self.clock = pygame.time.Clock()
        self.cfg = Config.load()
        self.ctx = LCtx(self.cfg)
        self.ui = UI(self.ctx)
        self.toasts = Toasts()
        self.ptr = Pointer("mouse", "mouse")
        self._prev_down = False
        self.running = True
        self.launching = 0.0
        self.t = 0.0
        self.tab = 0
        self.checks = []
        self.busy = ""
        self.log = ""
        self.preview = CamPreview()
        self._prev_surf = None
        self._prev_buf = None
        self.logo = None
        try:
            from .core.app import load_logo
            self.logo = load_logo()
        except Exception:
            pass
        self.bg = self._make_bg()
        import random
        self.dots = [[random.uniform(0, LW), random.uniform(0, LH), random.uniform(6, 26), random.uniform(0.3, 1.0)] for _ in range(70)]
        self._build()
        self.run_checks()

    def _make_bg(self):
        s = pygame.Surface((LW, LH))
        for y in range(0, LH, 2):
            s.fill(T.mix((4, 6, 16), (10, 16, 44), y / LH), (0, y, LW, 2))
        for x in range(0, LW, 50):
            pygame.draw.line(s, (12, 18, 40), (x, 0), (x, LH))
        for y in range(0, LH, 50):
            pygame.draw.line(s, (12, 18, 40), (0, y), (LW, y))
        return s

    # ------------------------------------------------------------------ interface
    def _build(self):
        a = self.ui.add
        a(Button((28, 336, 272, 66), "JOGAR", self.play, icon="play", style="primary", size=24, icon_size=14))
        a(Button((28, 412, 272, 46), "Jogar sem câmera (mouse)", lambda: self.play(["--no-camera"]), icon="hand", size=15))
        a(Button((28, 466, 272, 46), "Abrir o tutorial", lambda: self.play(["--mode", "tutorial"]), icon="star", size=15))
        a(Button((28, 520, 272, 46), "Calibrar a pinça", self.calibrate, icon="sliders", size=15))
        a(Button((28, 574, 272, 46), "Sair", self.quit, icon="cross", size=15))
        a(Panel((324, 24, 892, 632), None, T.ACCENT_HI, radius=20))
        actions = dict(detect=self.detect, preview=self.toggle_preview, test_sound=lambda: self.ctx.audio.play("sucesso"))
        pages = build_pages(self.cfg, actions, launcher=True)
        self.page_names = [n for n, _ in pages] + ["Sistema"]
        a(Tabs((340, 38, 860, 44), self.page_names, lambda: self.tab, self._set_tab))
        self.groups = []
        for name, widgets in pages:
            layout(widgets, 352, 104)
            for w in widgets:
                a(w)
            self.groups.append(widgets)
        sys_w = [Button((352, 520, 200, 48), "Verificar", self.run_checks, icon="refresh", size=15),
                 Button((564, 520, 230, 48), "Reparar dependências", self.install, icon="bolt", size=15, tooltip="Reinstala o que estiver em requirements.txt"),
                 Button((806, 520, 190, 48), "Abrir pasta", self.open_folder, icon="home", size=15),
                 Button((1008, 520, 190, 48), "Padrões", self.reset, icon="trash", style="danger", size=15, tooltip="Restaura Configurações.json (mantém recordes)")]
        for w in sys_w:
            a(w)
        self.groups.append(sys_w)

    def _set_tab(self, i):
        self.tab = i
        if self.page_names[i] != "Câmera":
            self.preview.stop()

    # ------------------------------------------------------------------ tarefas
    def run_checks(self):
        def work():
            self.busy = "Verificando..."
            self.checks = check_system()
            self.busy = ""
        threading.Thread(target=work, daemon=True).start()

    def detect(self):
        if self.busy:
            return

        def work():
            self.busy = "Procurando câmeras..."
            self.preview.stop()
            try:
                found = probe_cameras(5)
            except Exception:
                found = []
            self.busy = ""
            if found:
                if self.cfg.camera_index not in found:
                    self.cfg.camera_index = found[0]
                self.toasts.push("Câmeras encontradas: " + ", ".join(f"#{i}" for i in found), "ok")
            else:
                self.toasts.push("Nenhuma câmera encontrada", "error")
        threading.Thread(target=work, daemon=True).start()

    def toggle_preview(self):
        if self.preview.running:
            self.preview.stop()
        else:
            self.preview.start(self.cfg.camera_index, 640, 480)

    def install(self):
        if self.busy:
            return
        req = ROOT / "OpenBox_Data" / "requirements.txt"

        def work():
            self.busy = "Instalando dependências..."
            try:
                subprocess.call([sys.executable, "-m", "pip", "uninstall", "-y", "pygame"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                proc = subprocess.Popen([sys.executable, "-m", "pip", "install", "-r", str(req)], stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    self.log = line.strip()[:70]
                proc.wait()
                ok = proc.returncode == 0
            except Exception as exc:
                ok, self.log = False, str(exc)[:70]
            self.busy = ""
            self.toasts.push("Dependências instaladas" if ok else "Falha ao instalar (veja o terminal)", "ok" if ok else "error")
            self.checks = check_system()
        threading.Thread(target=work, daemon=True).start()

    def open_folder(self):
        try:
            if os.name == "nt":
                os.startfile(str(ROOT))   # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(ROOT)])
            else:
                subprocess.Popen(["xdg-open", str(ROOT)])
        except Exception as exc:
            self.toasts.push(f"Não foi possível abrir: {exc}", "error")

    def reset(self):
        self.cfg.reset_to_defaults()
        self.cfg.save()
        self.toasts.push("Configurações restauradas (recordes mantidos)", "ok")

    # ------------------------------------------------------------------ ações
    def play(self, extra=None):
        if self.launching:
            return
        self.preview.stop()
        self.cfg.save()
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--game"]
        else:
            cmd = [sys.executable, str(ROOT / "OpenBox.py"), "--game"]
        try:
            subprocess.Popen(cmd + (extra or []), cwd=str(ROOT))
            self.launching = time.monotonic()
            self.toasts.push("Iniciando OpenBox MR...", "ok")
            self.ctx.audio.play("sucesso")
        except Exception as exc:
            self.toasts.push(f"Falha ao iniciar: {exc}", "error")

    def calibrate(self):
        self.play(["--no-intro", "--mode", "menu"])

    def quit(self):
        self.running = False

    # ------------------------------------------------------------------ loop
    def _pointer(self):
        p = self.ptr
        x, y = pygame.mouse.get_pos()
        down = bool(pygame.mouse.get_pressed()[0])
        p.pressed, p.released = down and not self._prev_down, (not down) and self._prev_down
        p.x, p.y, p.down, p.over_ui = float(x), float(y), down, False
        self._prev_down = down

    def run(self):
        try:
            while self.running:
                dt = min(self.clock.tick(60) / 1000.0, 0.05)
                self.t += dt
                for e in pygame.event.get():
                    if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                        self.running = False
                    elif e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.play()
                for i, grp in enumerate(self.groups):
                    for w in grp:
                        w.visible = i == self.tab
                self._pointer()
                self.ui.update(dt, [self.ptr])
                self.toasts.update(dt)
                if self.launching and time.monotonic() - self.launching > 1.8:
                    self.running = False
                for d in self.dots:
                    d[1] -= d[2] * dt
                    if d[1] < -10:
                        d[1] = LH + 10
                self._draw()
                pygame.display.flip()
        finally:
            self.preview.stop()
            self.cfg.save()
            pygame.quit()

    def _draw(self):
        s = self.screen
        s.blit(self.bg, (0, 0))
        for x, y, _v, k in self.dots:
            draw.glow(s, (x, y), 6, T.ACCENT_HI, 0.35 * k)
        draw_open_box(s, 164, 92, 40, self.t)
        draw.spaced(s, "OPENBOX", (28, 156), 34, T.TEXT, True, 8)
        draw.text(s, "MR", (232, 190), 18, T.ACCENT_HI, True)
        draw.text(s, "MIXED REALITY ENGINE", (30, 198), 13, T.ACCENT_HI, True)
        draw.text(s, f"v{__version__}  ·  {STUDIO}", (30, 220), 13, T.MUTED)
        for i, line in enumerate(draw.wrap("Sua webcam vira um espaço de realidade mista controlado pelas mãos e pelo rosto.", 14, 266)):
            draw.text(s, line, (30, 252 + i * 19), 14, T.MUTED)
        cfg = self.cfg
        draw.text(s, f"{cfg.post['label']} · {cfg.diff['label']} · {'direto' if cfg.skip_launcher else 'com launcher'}", (30, 312), 12, T.DIM)
        self.ui.draw(s)
        name = self.page_names[self.tab]
        if name == "Câmera":
            self._draw_camera_tab()
        elif name == "Sistema":
            self._draw_system_tab()
        elif name == "Geral":
            r = pygame.Rect(352, 440, 840, 190)
            draw.text(s, "NOVIDADES", (r.x, r.y), 13, T.ACCENT_HI, True)
            for i, line in enumerate(NEWS):
                draw.text(s, "•  " + line, (r.x, r.y + 28 + i * 24), 15, T.MUTED)
            draw.text(s, "Tudo o que você muda aqui é salvo em Configurações.json, na pasta do jogo.", (r.x, r.y + 140), 14, T.DIM)
        draw.text(s, "© 2026 Khyros Studio · DUMP-L", (LW - 24, LH - 16), 12, T.DIM, False, "br")
        self.toasts.draw(s)
        if self.launching:
            a = min(1.0, (time.monotonic() - self.launching) / 1.2)
            veil = pygame.Surface((LW, LH))
            veil.set_alpha(int(160 * a))
            s.blit(veil, (0, 0))
            draw.text(s, "Iniciando...", (LW // 2, LH // 2), 36, T.TEXT, True, "c", int(255 * a))

    def _draw_camera_tab(self):
        s = self.screen
        box = pygame.Rect(352, 340, 480, 270)
        draw.rrect(s, box, (0, 0, 0, 160), 14)
        f = self.preview.frame
        if f is not None:
            rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
            self._prev_buf = rgb.tobytes()
            s.blit(pygame.image.frombuffer(self._prev_buf, (480, 270), "RGB"), box.topleft)
            br = float(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean())
            col = T.RED if br < 45 else T.AMBER if br < 80 else T.GREEN
            draw.text(s, f"Brilho médio: {br:.0f}/255  —  " + ("muito escuro" if br < 45 else "pouca luz" if br < 80 else "boa iluminação"), (box.right + 18, box.y + 8), 15, col, True)
        else:
            msg = self.preview.error or ("Carregando..." if self.preview.running else "Clique em «Pré-visualizar câmera» para ver a imagem e checar a luz")
            for i, line in enumerate(draw.wrap(msg, 15, 420)):
                draw.text(s, line, (box.centerx, box.centery - 12 + i * 20), 15, T.MUTED, False, "c")
        pygame.draw.rect(s, T.GLASS_BORDER[:3], box, 1, border_radius=14)
        tips = ["Boa iluminação frontal melhora muito o rastreamento.", "Evite contraluz (janela atrás de você).",
                "Sentado: ~60–90 cm da câmera. Em pé: ~1,5–2 m.", "Resoluções menores reduzem a latência."]
        for i, t in enumerate(tips):
            draw.text(s, "•  " + t, (box.right + 18, box.y + 44 + i * 26), 14, T.MUTED)

    def _draw_system_tab(self):
        s = self.screen
        y = 112
        draw.text(s, "DIAGNÓSTICO", (352, y - 6), 13, T.ACCENT_HI, True)
        y += 22
        for name, ok, detail in self.checks:
            pygame.draw.circle(s, T.GREEN if ok else T.RED, (362, y + 10), 5)
            draw.text(s, name, (380, y), 16, T.TEXT, True)
            draw.text(s, detail, (880, y), 15, T.MUTED if ok else T.AMBER, False, "tr")
            y += 30
        if self.busy:
            draw.text(s, self.busy + (f"  {self.log}" if self.log and "Instalando" in self.busy else ""), (352, 488), 14, T.AMBER, True)
        draw.text(s, f"Pasta do jogo: {ROOT}", (352, 592), 13, T.DIM)
