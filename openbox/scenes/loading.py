"""Tela de carregamento: cubo aberto 3D animado, barra de progresso, etapas reais e dicas."""
from __future__ import annotations

import math
import random
import time

import pygame

from .. import APP_NAME, STUDIO, __version__
from .. import theme as T
from ..core.scene import Scene
from ..ui import draw
from ..ui.anim import ease_in_out, ease_out_cubic

TIPS = [
    "Dedo-pistola: aponte, LEVANTE o polegar e ABAIXE para atirar.",
    "Faça o gesto ROCK (indicador + mindinho) por 1 s para abrir o menu de criação.",
    "Agarre um objeto com as duas mãos e afaste-as para ampliá-lo.",
    "Experimente chapéus no Catálogo — o OpenBox rastreia o seu rosto.",
    "Boa iluminação melhora muito o rastreamento das mãos.",
    "Jogando em pé? Troque a postura para «Em pé» nos Ajustes.",
    "Joinha ativa o slow motion; palmas juntas disparam uma onda de choque.",
    "Bots têm medo de movimentos rápidos — arremesse-os se quiser!",
    "Nos Ajustes você pode trocar a cor das suas mãos.",
    "Em Sobrevivência, toque nas moedas com a mão para coletá-las.",
]
CUBE = [(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1), (-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1)]   # y negativo = topo


def _rot(p, yaw, pitch):
    x, y, z = p
    c, s = math.cos(yaw), math.sin(yaw)
    x, z = x * c + z * s, -x * s + z * c
    c, s = math.cos(pitch), math.sin(pitch)
    y, z = y * c - z * s, y * s + z * c
    return x, y, z


def draw_open_box(surf, cx, cy, size, t, alpha=255):
    """Cubo em arame com as abas do topo abrindo e fechando (marca «OpenBox»)."""
    yaw, pitch = t * 0.9, -0.45 + 0.12 * math.sin(t * 0.7)
    flap = 0.25 + 1.15 * (0.5 + 0.5 * math.sin(t * 1.3 - 0.6))

    def P(p):
        x, y, z = _rot(p, yaw, pitch)
        k = 3.6 / (3.6 + z * 0.55)
        return (cx + x * size * k, cy + y * size * k), z

    pts = [P(v) for v in CUBE]
    col = T.ACCENT_HI
    for a, b in [(4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]:
        pygame.draw.line(surf, (*T.mix(col, (255, 255, 255), 0.25),), pts[a][0], pts[b][0], 3)
    # abas (hinge nas arestas do topo, abrindo para fora)
    for i, j in [(0, 1), (1, 2), (2, 3), (3, 0)]:
        va, vb = CUBE[i], CUBE[j]
        mid = ((va[0] + vb[0]) / 2, 0, (va[2] + vb[2]) / 2)
        n = (mid[0], 0, mid[2])
        nl = math.hypot(n[0], n[2]) or 1
        out = (n[0] / nl, 0, n[2] / nl)
        d = (out[0] * math.sin(flap), -math.cos(flap), out[2] * math.sin(flap))
        quad = [va, vb, (vb[0] + d[0], vb[1] + d[1], vb[2] + d[2]), (va[0] + d[0], va[1] + d[1], va[2] + d[2])]
        proj = [P(q)[0] for q in quad]
        pygame.draw.polygon(surf, (*T.mix((20, 30, 90), T.CYAN, 0.35),), proj)
        pygame.draw.lines(surf, T.CYAN, True, proj, 2)
    for (p, z) in pts:
        draw.glow(surf, p, 16, T.CYAN, 0.7)
        pygame.draw.circle(surf, (255, 255, 255), (int(p[0]), int(p[1])), 3)
    # luz saindo da caixa
    draw.glow(surf, (cx, cy - size * 0.2), size * 1.6, T.ACCENT, 0.22 + 0.1 * math.sin(t * 2))


class LoadingScene(Scene):
    name = "loading"
    cursors = False

    def enter(self, **kw):
        self.t = 0.0
        self.progress = 0.0
        self.shown = 0.0
        self.label = "Iniciando..."
        self.tip_i = random.randrange(len(TIPS))
        self.tip_t = 0.0
        self.dots = [[random.uniform(0, self.ctx.W), random.uniform(0, self.ctx.H), random.uniform(10, 40), random.uniform(0.3, 1.0)] for _ in range(70)]
        self.steps = self._make_steps()
        self.idx = 0
        self.gen = None
        self.status = {"camera": None, "hands": None, "face": None}
        self.finished = False
        self.fin_t = 0.0
        self.t0 = time.monotonic()
        self.ctx.audio.play("boot")

    # ------------------------------------------------------------------ etapas (geradores: yield = ainda trabalhando)
    def _make_steps(self):
        return [("Preparando áudio e interface", self._s_ui, 0.6, False),
                ("Pré-renderizando objetos", self._s_sprites, 3.0, False),
                ("Montando o catálogo", self._s_icons, 3.0, False),
                ("Abrindo a câmera", self._s_camera, 2.0, True),
                ("Carregando rastreamento das mãos", self._s_hands, 2.5, True),
                ("Carregando rastreamento do rosto", self._s_face, 1.5, True),
                ("Tudo pronto!", self._s_done, 0.5, True)]

    def _s_ui(self):
        yield 0.5
        from ..ui import draw as d
        for s in (14, 16, 18, 20, 26, 34, 56):
            d.font(s, True)
            d.font(s, False)
        yield 1.0

    def _s_sprites(self):
        from ..game import items as I
        from ..ui import sprites
        bodies = [i for i in I._ALL if i.kind == "body"]
        for n, it in enumerate(bodies):
            for r in (it.r, it.r * 1.5):
                try:
                    sprites.base_sprite(it.id, r, it.color)
                except Exception as exc:
                    print(f"[loading] sprite {it.id}: {exc!r}")
            yield n / max(1, len(bodies))
        yield 1.0

    def _s_icons(self):
        from ..game import items as I
        from ..ui.catalog import item_icon
        sizes = (self.ctx.cfg.post["cell"] - 12, 58, 72)
        for n, it in enumerate(I._ALL):
            for sz in sizes:
                item_icon(it, sz)
            yield n / len(I._ALL)
        yield 1.0

    def _wait(self, cond, timeout, attr=None):
        t0 = time.monotonic()
        while not cond() and time.monotonic() - t0 < timeout:
            yield min(0.95, (time.monotonic() - t0) / timeout)
        yield 1.0

    def _s_camera(self):
        if self.ctx.app.no_camera:
            self.status["camera"] = "off"
            yield 1.0
            return
        yield from self._wait(lambda: self.ctx.camera.state in ("ready", "error"), 9.0)
        self.status["camera"] = self.ctx.camera.state

    def _s_hands(self):
        if self.ctx.app.no_camera:
            self.status["hands"] = "off"
            yield 1.0
            return
        yield from self._wait(lambda: self.ctx.tracker.state in ("running", "error"), 20.0)
        self.status["hands"] = self.ctx.tracker.state

    def _s_face(self):
        if self.ctx.app.no_camera or not self.ctx.cfg.face_tracking:
            self.status["face"] = "off"
            yield 1.0
            return
        yield from self._wait(lambda: self.ctx.face_tracker.state in ("running", "error", "paused"), 8.0)
        self.status["face"] = self.ctx.face_tracker.state

    def _s_done(self):
        t0 = time.monotonic()
        while time.monotonic() - t0 < 0.5:
            yield (time.monotonic() - t0) / 0.5
        yield 1.0

    # ------------------------------------------------------------------ ciclo
    def update(self, dt):
        self.t += dt
        self.tip_t += dt
        if self.tip_t > 3.6:
            self.tip_t = 0.0
            self.tip_i = (self.tip_i + 1) % len(TIPS)
        for d in self.dots:
            d[1] -= d[2] * dt
            if d[1] < -10:
                d[0], d[1] = random.uniform(0, self.ctx.W), self.ctx.H + 10
        if not self.finished:
            budget = time.perf_counter() + 0.008
            while self.idx < len(self.steps) and time.perf_counter() < budget:
                name, fn, _w, waiting = self.steps[self.idx]
                self.label = name
                if self.gen is None:
                    self.gen = fn()
                try:
                    self.part = next(self.gen)
                    if self.part < 1.0:
                        if waiting:
                            break                  # etapa de espera: volta no próximo frame
                        continue                   # etapa em blocos: segue até o orçamento de tempo do frame
                except StopIteration:
                    pass
                self.gen, self.part = None, 0.0
                self.idx += 1
            total = sum(st[2] for st in self.steps)
            done = sum(st[2] for st in self.steps[:self.idx])
            cur = self.steps[self.idx][2] * getattr(self, "part", 0.0) if self.idx < len(self.steps) else 0.0
            self.progress = min(1.0, (done + cur) / total)
            if self.idx >= len(self.steps):
                self.finished = True
                self.progress = 1.0
        self.shown += (self.progress - self.shown) * min(1.0, dt * 6.0)
        if self.finished and self.shown > 0.985:
            self.fin_t += dt
            if self.fin_t > 0.35:
                self._leave()

    def _leave(self):
        ctx = self.ctx
        if not self.ctx.camera.ready and not ctx.app.no_camera:
            ctx.toast("Câmera indisponível — o mouse funciona como ponteiro", "warn")
        if ctx.tracker.state == "error":
            ctx.toast("O rastreamento de mãos não iniciou (veja o terminal)", "error")
        if ctx.start_mode != "menu":
            ctx.scenes.go("play", mode=ctx.start_mode)
        elif getattr(ctx, "skip_intro", False):
            ctx.scenes.go("hub")
        else:
            ctx.scenes.go("intro")
        self.fin_t = -99

    def event(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.ctx.app.quit()

    def draw(self, surf):
        ctx, t = self.ctx, self.t
        W, H = ctx.W, ctx.H
        for y in range(0, H, 4):
            surf.fill(T.mix((4, 6, 18), (10, 18, 52), y / H), (0, y, W, 4))
        # grade em perspectiva
        vx, vy = W / 2, H * 0.50
        for i in range(-14, 15):
            pygame.draw.line(surf, (16, 24, 58), (vx + i * 26, vy), (vx + i * 330, H), 1)
        for k in range(12):
            f = ((k + (t * 0.35) % 1.0) / 12.0) ** 2.2
            pygame.draw.line(surf, T.mix((10, 14, 34), (34, 52, 130), f), (0, vy + (H - vy) * f), (W, vy + (H - vy) * f), 1)
        for x, y, _v, k in self.dots:
            draw.glow(surf, (x, y), 6, T.ACCENT_HI, 0.35 * k)
        appear = ease_out_cubic(min(1.0, t / 0.8))
        draw_open_box(surf, W // 2, 214, 92 * (0.85 + 0.15 * appear), t)
        # título com letras surgindo
        title = APP_NAME.upper().replace(" MR", "")
        widths = [draw.text_width(ch, 60, True) + 14 for ch in title]
        x = W // 2 - (sum(widths) - 14) // 2
        for i, (ch, w) in enumerate(zip(title, widths)):
            k = ease_out_cubic(min(1.0, max(0.0, (t - 0.25 - i * 0.07) / 0.45)))
            draw.text(surf, ch, (x, 336 + (1 - k) * 22), 60, T.TEXT, True, "tl", int(255 * k), True)
            x += w
        draw.text(surf, "MR", (W // 2 + (sum(widths) - 14) // 2 + 20, 366), 28, T.ACCENT_HI, True, "tl", int(255 * ease_out_cubic(min(1, max(0, (t - 0.9) / 0.4)))))
        draw.text(surf, "MIXED REALITY ENGINE", (W // 2, 414), 15, T.MUTED, True, "c", int(255 * ease_out_cubic(min(1, max(0, (t - 1.1) / 0.5)))))
        # barra de progresso
        bw, bh = 560, 12
        bx, by = (W - bw) // 2, 468
        draw.rrect(surf, (bx - 2, by - 2, bw + 4, bh + 4), (255, 255, 255, 30), 9)
        fill = max(0, int(bw * self.shown))
        if fill > 2:
            draw.rrect(surf, (bx, by, fill, bh), (*T.ACCENT, 255), 6)
            sheen = int((t * 220) % (bw + 120)) - 60
            sh = pygame.Rect(max(bx, bx + sheen - 40), by, 0, bh)
            sh.width = max(0, min(bx + fill, bx + sheen + 40) - sh.x)
            if sh.width > 2:
                draw.rrect(surf, sh, (255, 255, 255, 90), 6)
            draw.glow(surf, (bx + fill, by + bh / 2), 30, T.CYAN, 0.8)
        dots = "." * (int(t * 3) % 4)
        draw.text(surf, self.label + dots, (bx, by + 22), 16, T.TEXT, True)
        draw.text(surf, f"{int(self.shown * 100)}%", (bx + bw, by + 22), 16, T.CYAN, True, "tr")
        # estado dos módulos
        chips = [("Câmera", self.status["camera"], ("ready",)), ("Mãos", self.status["hands"], ("running",)), ("Rosto", self.status["face"], ("running", "paused"))]
        cx = W // 2 - 190
        for name, st, ok in chips:
            if st is None:
                col, sym = T.DIM, "…"
            elif st in ok:
                col, sym = T.GREEN, "ok"
            elif st == "off":
                col, sym = T.DIM, "off"
            else:
                col, sym = T.AMBER, "!"
            pill = pygame.Rect(cx, 540, 118, 28)
            draw.rrect(surf, pill, (0, 0, 0, 110), 14)
            pygame.draw.circle(surf, col, (pill.x + 14, pill.centery), 5)
            draw.text(surf, f"{name} · {sym}", (pill.x + 26, pill.centery), 14, T.TEXT, True, "ml")
            cx += 130
        # dica
        a = int(255 * min(1.0, self.tip_t / 0.4, (3.6 - self.tip_t) / 0.4))
        draw.text(surf, "DICA", (W // 2, 604), 12, T.ACCENT_HI, True, "c", a)
        draw.text(surf, TIPS[self.tip_i], (W // 2, 628), 17, T.MUTED, False, "c", a)
        # marca do estúdio
        if ctx.logo is not None:
            h = 34
            img = pygame.transform.smoothscale(ctx.logo, (int(ctx.logo.get_width() * h / ctx.logo.get_height()), h))
            img.set_alpha(int(180 * appear))
            surf.blit(img, (28, H - h - 22))
        draw.text(surf, f"v{__version__}  ·  {STUDIO}", (W - 24, H - 26), 13, T.DIM, False, "br")
