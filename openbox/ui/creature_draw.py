"""Desenho procedural das criaturas (bots e zumbis): humanoides, slime, fantasma e pintinho.
Reagem ao estado do cérebro: andar, pular, medo, tontura, raiva e quando são segurados."""
from __future__ import annotations

import math

import pygame

from .. import theme as T

OUT = (8, 10, 22, 210)

STYLES = {
    "robot": dict(skin=(150, 176, 210), cloth=(86, 118, 172), dark=(52, 70, 104), head="box", eye=(90, 255, 255)),
    "zombie": dict(skin=(122, 178, 98), cloth=(78, 88, 124), dark=(48, 54, 80), head="round", eye=(255, 70, 70), fwd=True),
    "zombie_runner": dict(skin=(164, 202, 104), cloth=(150, 76, 64), dark=(96, 46, 40), head="round", eye=(255, 90, 60), fwd=True),
    "zombie_brute": dict(skin=(96, 140, 98), cloth=(62, 64, 76), dark=(38, 40, 50), head="round", eye=(255, 50, 50), fwd=True, scale=1.0, wide=1.35),
    "alien": dict(skin=(132, 255, 172), cloth=(130, 140, 170), dark=(80, 90, 120), head="alien", eye=(10, 14, 20)),
    "skeleton": dict(skin=(238, 236, 224), cloth=(238, 236, 224), dark=(170, 168, 156), head="skull", eye=(20, 20, 30), bones=True),
    "ninja": dict(skin=(42, 42, 58), cloth=(36, 36, 52), dark=(22, 22, 34), head="ninja", eye=(255, 255, 255), band=(224, 42, 62)),
}


def draw_creature(layer, b, now: float):
    br = b.brain
    if br is None:
        return
    if b.kind == "slime":
        _slime(layer, b, now)
    elif b.kind == "ghost":
        _ghost(layer, b, now)
    elif b.kind == "chick":
        _chick(layer, b, now)
    else:
        _humanoid(layer, b, now, STYLES.get(b.kind, STYLES["robot"]))
    if br.expr == "dizzy":
        _stars(layer, b, now)


class _Pen:
    """Transformação local (unidades do raio, x espelhado pela direção) -> tela."""

    def __init__(self, layer, b):
        self.layer, self.b = layer, b
        self.u = b.r
        self.f = b.brain.face or 1
        self.ca, self.sa = math.cos(b.angle), math.sin(b.angle)

    def P(self, px, py):
        lx, ly = px * self.f * self.u, py * self.u
        return (self.b.x + lx * self.ca - ly * self.sa, self.b.y + lx * self.sa + ly * self.ca)

    def limb(self, a, b, w, col):
        pa, pb = self.P(*a), self.P(*b)
        w = max(3, int(w * self.u))
        pygame.draw.line(self.layer, OUT, pa, pb, w + 3)
        pygame.draw.line(self.layer, (*col, 255), pa, pb, w)
        pygame.draw.circle(self.layer, (*col, 255), (int(pb[0]), int(pb[1])), w // 2)

    def poly(self, pts, col, outline=True):
        ps = [self.P(*p) for p in pts]
        pygame.draw.polygon(self.layer, (*col, 255), ps)
        if outline:
            pygame.draw.lines(self.layer, OUT, True, ps, 2)

    def circle(self, c, r, col, outline=True):
        p = self.P(*c)
        rr = max(2, int(r * self.u))
        pygame.draw.circle(self.layer, (*col, 255), (int(p[0]), int(p[1])), rr)
        if outline:
            pygame.draw.circle(self.layer, OUT, (int(p[0]), int(p[1])), rr, 2)

    def line(self, a, b, col, w=2):
        pygame.draw.line(self.layer, col, self.P(*a), self.P(*b), w)


def _eyes(pen, st, cx, cy, br, now, spacing=0.22, size=0.14):
    expr = br.expr
    lx, ly = br.look
    lx = lx * br.face
    for sd in (-1, 1):
        c = (cx + sd * spacing, cy)
        if expr == "dizzy":
            p = pen.P(*c)
            s = max(3, int(size * pen.u * 1.2))
            col = (30, 30, 40, 255)
            pygame.draw.line(pen.layer, col, (p[0] - s, p[1] - s), (p[0] + s, p[1] + s), 2)
            pygame.draw.line(pen.layer, col, (p[0] - s, p[1] + s), (p[0] + s, p[1] - s), 2)
            continue
        big = 1.55 if expr in ("scared", "held") else 1.0
        if st.get("head") in ("box", "ninja") and expr not in ("scared", "held"):
            pen.circle(c, size * 0.9, st["eye"], False)
            continue
        pen.circle(c, size * big, (250, 250, 255), True)
        pen.circle((c[0] + lx * size * 0.5, c[1] + ly * size * 0.5), size * (0.4 if big > 1 else 0.62), st["eye"] if st.get("head") != "alien" else (10, 14, 20), False)
    if expr == "angry":
        pen.line((cx - spacing - 0.16, cy - 0.2), (cx - 0.04, cy - 0.1), (10, 10, 20, 255), 3)
        pen.line((cx + spacing + 0.16, cy - 0.2), (cx + 0.04, cy - 0.1), (10, 10, 20, 255), 3)
    elif expr in ("scared", "held"):
        pen.line((cx - spacing - 0.14, cy - 0.12 - 0.22), (cx - 0.05, cy - 0.3), (10, 10, 20, 255), 2)
        pen.line((cx + spacing + 0.14, cy - 0.12 - 0.22), (cx + 0.05, cy - 0.3), (10, 10, 20, 255), 2)


def _humanoid(layer, b, now, st):
    br, pen = b.brain, _Pen(layer, b)
    skin, cloth, dark = st["skin"], st["cloth"], st["dark"]
    wide = st.get("wide", 1.0)
    moving = abs(b.vx) > 14 and b.grounded
    swing = math.sin(br.walk_phase * 2.0) * 0.75 if moving else 0.0
    airborne = not b.grounded and not b.held_by
    held = bool(b.held_by)
    sq = 1.0 - br.squash * 0.25
    tremble = math.sin(now * 55) * 0.05 if br.expr in ("scared", "held") else 0.0

    # pernas
    for side, sgn in ((-1, 1), (1, -1)):
        a = swing * sgn
        if held:
            a = math.sin(now * 9 + side) * 0.45
        elif airborne:
            a = 0.55 * sgn if abs(b.vy) < 300 else 0.25 * sgn
        foot = (side * 0.22 * wide + math.sin(a) * 0.8, 0.3 + math.cos(a) * 0.72 * sq)
        pen.limb((side * 0.2 * wide, 0.3), foot, 0.3 * wide, dark if not st.get("bones") else skin)
    # corpo
    t = 0.4 * wide
    pen.poly([(-t, -0.8), (t, -0.8), (t * 0.9, 0.38), (-t * 0.9, 0.38)], cloth)
    if st["head"] == "box":                                  # luz no peito
        pen.circle((0, -0.3), 0.14, st["eye"], False)
        pen.line((-0.25, 0.05), (0.25, 0.05), (*dark, 255), 3)
    elif st.get("bones"):
        for yy in (-0.6, -0.4, -0.2, 0.0):
            pen.line((-0.26, yy), (0.26, yy), (*dark, 255), 2)
        pen.line((0, -0.8), (0, 0.3), (*dark, 255), 2)
    elif st.get("band"):
        pen.poly([(-t, -0.8), (-t - 0.4, -0.5 + math.sin(now * 6) * 0.08), (-t - 0.3, -0.35)], st["band"], False)
    elif st.get("fwd"):
        pen.line((-0.2, -0.5), (0.1, -0.2), (*dark, 255), 3)
        pen.line((0.15, -0.6), (0.3, -0.3), (*dark, 255), 3)
    # braços
    for side, sgn in ((-1, -1), (1, 1)):
        sh = (side * 0.42 * wide, -0.66)
        if br.expr == "scared" or (held and br.expr == "held"):
            end = (side * 0.62 + math.sin(now * 17 + side) * 0.12, -1.5 + tremble * 3)
        elif st.get("fwd") and br.expr in ("angry", "normal"):
            end = (0.9, -0.62 + side * 0.07 + math.sin(now * 4 + side) * 0.05)
        else:
            a = swing * sgn * 0.9
            end = (side * 0.5 + math.sin(a) * 0.25, -0.66 + math.cos(a) * 0.72)
        pen.limb(sh, end, 0.24 * wide, skin if not st.get("bones") else skin)
    # cabeça
    hx, hy = tremble, -1.34
    kind = st["head"]
    if kind == "box":
        pen.poly([(hx - 0.5, hy - 0.45), (hx + 0.5, hy - 0.45), (hx + 0.5, hy + 0.42), (hx - 0.5, hy + 0.42)], skin)
        pen.line((hx, hy - 0.45), (hx, hy - 0.8), (*dark, 255), 3)
        pen.circle((hx, hy - 0.86), 0.1, T.RED if br.expr != "normal" else st["eye"], False)
    elif kind == "alien":
        pen.poly([(hx - 0.5, hy - 0.2), (hx - 0.3, hy - 0.62), (hx + 0.3, hy - 0.62), (hx + 0.5, hy - 0.2), (hx + 0.34, hy + 0.35), (hx, hy + 0.5), (hx - 0.34, hy + 0.35)], skin)
        pen.line((hx - 0.25, hy - 0.6), (hx - 0.4, hy - 1.0), (*dark, 255), 2)
        pen.line((hx + 0.25, hy - 0.6), (hx + 0.4, hy - 1.0), (*dark, 255), 2)
        pen.circle((hx - 0.4, hy - 1.02), 0.08, (255, 230, 90), False)
        pen.circle((hx + 0.4, hy - 1.02), 0.08, (255, 230, 90), False)
    else:
        pen.circle((hx, hy), 0.58, skin)
        if kind == "ninja":
            pen.poly([(hx - 0.58, hy - 0.22), (hx + 0.58, hy - 0.22), (hx + 0.58, hy + 0.12), (hx - 0.58, hy + 0.12)], st["band"] and (36, 36, 52), False)
            pen.line((hx - 0.58, hy - 0.2), (hx + 0.58, hy - 0.2), (*st["band"], 255), 5)
        if kind == "skull":
            pen.poly([(hx - 0.3, hy + 0.35), (hx + 0.3, hy + 0.35), (hx + 0.22, hy + 0.62), (hx - 0.22, hy + 0.62)], skin)
            for k in (-0.1, 0.0, 0.1):
                pen.line((hx + k, hy + 0.4), (hx + k, hy + 0.6), (*dark, 255), 1)
    # olhos e boca
    if kind == "alien":
        _eyes(pen, st, hx, hy + 0.02, br, now, 0.24, 0.17)
    elif kind == "ninja":
        _eyes(pen, st, hx, hy + 0.0, br, now, 0.24, 0.1)
    else:
        _eyes(pen, st, hx, hy - 0.02, br, now, 0.22, 0.14)
    if kind in ("round", "skull") and br.expr != "dizzy":
        if br.expr in ("angry",):
            pen.line((hx - 0.25, hy + 0.3), (hx + 0.25, hy + 0.3), (40, 10, 14, 255), 3)
        elif br.expr in ("scared", "held"):
            pen.circle((hx, hy + 0.34), 0.1, (40, 10, 20), False)
        elif kind == "round":
            pen.line((hx - 0.2, hy + 0.32), (hx + 0.2, hy + 0.32 + (0.02 if br.mode == "walk" else 0)), (40, 20, 30, 255), 2)
    if st.get("fwd") and br.expr != "dizzy":     # rasgo/cicatriz
        pen.line((hx + 0.2, hy - 0.4), (hx + 0.4, hy - 0.15), (120, 40, 50, 255), 2)


def _slime(layer, b, now):
    br = b.brain
    u = b.r
    squash = br.squash * 0.35 + (0.15 * math.sin(now * 5) if b.grounded else 0.0)
    stretch = min(0.35, abs(b.vy) / 1800.0) if not b.grounded else 0.0
    w, h = u * (1.15 + squash - stretch * 0.4), u * (0.95 - squash + stretch)
    cx, cy = b.x, b.y + (u - h)
    col = (90, 232, 122)
    rect = pygame.Rect(cx - w, cy - h, w * 2, h * 2)
    pygame.draw.ellipse(layer, OUT, rect.inflate(5, 5))
    pygame.draw.ellipse(layer, (*col, 215), rect)
    pygame.draw.ellipse(layer, (*T.mix(col, (255, 255, 255), 0.5), 200), (cx - w * 0.6, cy - h * 0.75, w * 0.7, h * 0.5))
    pygame.draw.ellipse(layer, (50, 160, 80, 255), rect, 2)
    lx, ly = br.look
    scared = br.expr in ("scared", "held")
    for sd in (-1, 1):
        ex, ey = cx + sd * w * 0.35, cy - h * 0.15
        if br.expr == "dizzy":
            pygame.draw.line(layer, (20, 40, 30, 255), (ex - 4, ey - 4), (ex + 4, ey + 4), 2)
            pygame.draw.line(layer, (20, 40, 30, 255), (ex - 4, ey + 4), (ex + 4, ey - 4), 2)
            continue
        r_ = int(u * (0.26 if scared else 0.2))
        pygame.draw.circle(layer, (255, 255, 255, 255), (int(ex), int(ey)), r_)
        pygame.draw.circle(layer, (20, 30, 30, 255), (int(ex + lx * r_ * 0.4), int(ey + ly * r_ * 0.4)), max(2, r_ // 2))
    if scared:
        pygame.draw.circle(layer, (30, 60, 40, 255), (int(cx), int(cy + h * 0.35)), max(2, int(u * 0.1)), 2)
    else:
        pygame.draw.arc(layer, (30, 70, 40, 255), pygame.Rect(cx - w * 0.25, cy + h * 0.05, w * 0.5, h * 0.4), 3.4, 6.0, 2)


def _ghost(layer, b, now):
    br, u = b.brain, b.r
    fade = 150 if br.expr in ("scared", "held") else 215
    x, y = b.x, b.y
    top = y - u * 1.1
    pts = [(x - u * 0.95, y + u * 0.9)]
    for i in range(9):
        a = i / 8
        pts.append((x - u * 0.95 + a * u * 1.9, y + u * (0.9 + (0.22 if i % 2 else -0.05) * (1 + 0.25 * math.sin(now * 6 + i)))))
    pts.append((x + u * 0.95, y + u * 0.9))
    arc = [(x + math.cos(t) * u * 0.95, y - u * 0.1 + math.sin(t) * u * 1.0) for t in [math.pi + k * math.pi / 10 for k in range(11)]]
    body = arc + list(reversed(pts))
    pygame.draw.polygon(layer, (225, 236, 255, fade), body)
    pygame.draw.lines(layer, (160, 190, 255, 255), True, body, 2)
    lx, ly = br.look
    for sd in (-1, 1):
        ex, ey = x + sd * u * 0.36, y - u * 0.15
        pygame.draw.ellipse(layer, (20, 24, 50, 255), (ex - u * 0.12, ey - u * 0.2, u * 0.24, u * 0.4 * (1.4 if br.expr == "scared" else 1.0)))
        pygame.draw.circle(layer, (255, 255, 255, 255), (int(ex + lx * 2), int(ey - u * 0.08 + ly * 2)), max(1, int(u * 0.05)))
    if br.expr in ("scared", "held"):
        pygame.draw.ellipse(layer, (20, 24, 50, 255), (x - u * 0.1, y + u * 0.2, u * 0.2, u * 0.3))
    for sd in (-1, 1):
        pygame.draw.circle(layer, (210, 225, 255, fade), (int(x + sd * u * 1.0), int(y + u * 0.2 + math.sin(now * 5 + sd) * 4)), int(u * 0.2))


def _chick(layer, b, now):
    br, pen = b.brain, _Pen(layer, b)
    moving = abs(b.vx) > 14 and b.grounded
    sw = math.sin(br.walk_phase * 3.0) * 0.5 if moving else 0.0
    for side in (-1, 1):
        foot = (side * 0.28 + sw * side * 0.4, 1.0)
        pen.limb((side * 0.2, 0.55), foot, 0.14, (255, 150, 40))
    pen.circle((0, 0.0), 1.0, (255, 214, 70))
    pen.circle((-0.25, 0.1), 0.4, (255, 190, 50), False)
    pen.poly([(0.85, -0.2), (1.35, -0.05), (0.85, 0.1)], (255, 140, 30))
    tuft = [(-0.1, -0.95), (0.0, -1.3 + math.sin(now * 8) * 0.05), (0.15, -0.95)]
    pen.poly(tuft, (255, 200, 60))
    scared = br.expr in ("scared", "held")
    pen.circle((0.4, -0.3), 0.26 if scared else 0.18, (255, 255, 255), True)
    lx, ly = br.look
    pen.circle((0.4 + lx * 0.07 * br.face, -0.3 + ly * 0.07), 0.1 if scared else 0.09, (20, 20, 30), False)


def _stars(layer, b, now):
    for i in range(3):
        a = now * 5 + i * math.tau / 3
        x, y = b.x + math.cos(a) * b.r * 0.7, b.y - b.r * 1.9 + math.sin(a) * b.r * 0.18
        pts = [(x + math.cos(-math.pi / 2 + k * math.pi / 5) * (6 if k % 2 == 0 else 2.6),
                y + math.sin(-math.pi / 2 + k * math.pi / 5) * (6 if k % 2 == 0 else 2.6)) for k in range(10)]
        pygame.draw.polygon(layer, (255, 230, 80, 255), pts)
