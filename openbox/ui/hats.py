"""Chapéus e acessórios do rosto + sprites das armas. Tudo desenhado proceduralmente."""
from __future__ import annotations

import math

import pygame

from .. import theme as T

OUT = (10, 10, 20, 230)


class _Hat:
    """Sistema local: unidades da largura do rosto; origem na âncora (topo da cabeça); y negativo = acima."""

    def __init__(self, layer, anchor, s, rot, yaw=0.0):
        self.layer, self.A, self.s = layer, anchor, s
        self.c, self.sn = math.cos(rot), math.sin(rot)
        self.yaw = yaw

    def P(self, x, y):
        lx, ly = (x + self.yaw * 0.12) * self.s, y * self.s
        return (self.A[0] + lx * self.c - ly * self.sn, self.A[1] + lx * self.sn + ly * self.c)

    def poly(self, pts, col, line=OUT, w=2):
        ps = [self.P(*p) for p in pts]
        pygame.draw.polygon(self.layer, (*col, 255), ps)
        if line:
            pygame.draw.lines(self.layer, line, True, ps, w)

    def ell(self, cx, cy, rx, ry, col, line=OUT):
        pts = [self.P(cx + math.cos(t) * rx, cy + math.sin(t) * ry) for t in [i * math.tau / 24 for i in range(24)]]
        pygame.draw.polygon(self.layer, (*col, 255), pts)
        if line:
            pygame.draw.lines(self.layer, line, True, pts, 2)

    def circ(self, cx, cy, r, col, line=OUT):
        p = self.P(cx, cy)
        pygame.draw.circle(self.layer, (*col, 255), (int(p[0]), int(p[1])), max(2, int(r * self.s)))
        if line:
            pygame.draw.circle(self.layer, line, (int(p[0]), int(p[1])), max(2, int(r * self.s)), 2)

    def line(self, a, b, col, w=3):
        pygame.draw.line(self.layer, col, self.P(*a), self.P(*b), max(1, int(w)))


def _star(h, cx, cy, r, col):
    pts = [(cx + math.cos(-math.pi / 2 + i * math.pi / 5) * (r if i % 2 == 0 else r * 0.45),
            cy + math.sin(-math.pi / 2 + i * math.pi / 5) * (r if i % 2 == 0 else r * 0.45)) for i in range(10)]
    h.poly(pts, col, None)


def tophat(h, now):
    h.ell(0, -0.02, 0.62, 0.07, (24, 24, 32))
    h.poly([(-0.36, -0.02), (-0.34, -0.68), (0.34, -0.68), (0.36, -0.02)], (34, 34, 46))
    h.ell(0, -0.68, 0.34, 0.06, (52, 52, 68))
    h.poly([(-0.355, -0.14), (0.355, -0.14), (0.352, -0.02), (-0.358, -0.02)], (200, 40, 60), None)


def wizard(h, now):
    h.ell(0, -0.02, 0.7, 0.09, (80, 50, 170))
    h.poly([(-0.46, -0.02), (0.46, -0.02), (0.22, -0.55), (0.1 + math.sin(now * 2) * 0.03, -1.1), (-0.08, -0.62)], (112, 72, 214))
    h.poly([(-0.47, -0.1), (0.47, -0.1), (0.44, -0.02), (-0.44, -0.02)], (255, 210, 80), None)
    _star(h, -0.1, -0.35, 0.07, (255, 235, 120))
    _star(h, 0.14, -0.2, 0.05, (255, 235, 120))
    _star(h, 0.02, -0.62, 0.05, (255, 235, 120))


def crown(h, now):
    pts = [(-0.42, 0.0), (-0.42, -0.4), (-0.22, -0.2), (0.0, -0.5), (0.22, -0.2), (0.42, -0.4), (0.42, 0.0)]
    h.poly(pts, (255, 205, 60))
    h.poly([(-0.42, -0.08), (0.42, -0.08), (0.42, 0.0), (-0.42, 0.0)], (220, 160, 30), None)
    for x, c in ((-0.42, (255, 80, 90)), (0.0, (80, 190, 255)), (0.42, (90, 255, 150))):
        h.circ(x, -0.42 if x else -0.52, 0.045, c, None)
    h.circ(0.0, -0.04, 0.04, (255, 80, 90), None)


def cap(h, now):
    h.poly([(-0.5, 0.0), (-0.46, -0.3), (-0.2, -0.5), (0.2, -0.5), (0.46, -0.3), (0.5, 0.0)], (62, 124, 232))
    h.poly([(0.2, -0.02), (0.95, 0.0), (0.95, 0.07), (0.2, 0.06)], (40, 90, 190))
    h.circ(0.0, -0.5, 0.04, (240, 240, 250), None)


def pirate(h, now):
    h.poly([(-0.78, 0.0), (-0.5, -0.45), (-0.2, -0.62), (0.2, -0.62), (0.5, -0.45), (0.78, 0.0), (0.4, -0.14), (-0.4, -0.14)], (30, 30, 40))
    h.circ(0.0, -0.32, 0.07, (240, 240, 240), None)
    h.line((-0.1, -0.2), (0.1, -0.2), (240, 240, 240, 255), 2)
    h.line((-0.3, -0.45), (0.3, -0.18), (240, 240, 240, 255), 2)


def helmet(h, now):
    h.poly([(-0.52, 0.04), (-0.5, -0.32), (-0.26, -0.55), (0.26, -0.55), (0.5, -0.32), (0.52, 0.04)], (92, 122, 82))
    h.poly([(-0.56, 0.0), (0.56, 0.0), (0.56, 0.07), (-0.56, 0.07)], (60, 84, 54))
    h.poly([(-0.12, -0.55), (0.12, -0.55), (0.1, -0.08), (-0.1, -0.08)], (120, 150, 104), None)


def party(h, now):
    h.poly([(-0.3, 0.0), (0.3, 0.0), (0.02, -0.95)], (255, 90, 200))
    for i, y in enumerate((-0.15, -0.4, -0.65)):
        w = 0.3 * (1 + y / 1.0) * 0.9
        h.line((-w, y), (w, y), (255, 240, 120, 255), 3)
    h.circ(0.02, -0.97, 0.07, (120, 240, 255), None)


def horns(h, now):
    for sd in (-1, 1):
        h.poly([(sd * 0.28, 0.0), (sd * 0.4, -0.18), (sd * 0.42, -0.5), (sd * 0.34, -0.3), (sd * 0.2, -0.04)], (226, 48, 60))


def catears(h, now):
    for sd in (-1, 1):
        h.poly([(sd * 0.12, 0.0), (sd * 0.42, 0.02), (sd * 0.4, -0.52)], (58, 58, 70))
        h.poly([(sd * 0.2, -0.04), (sd * 0.38, -0.04), (sd * 0.37, -0.32)], (240, 140, 160), None)


def halo(h, now):
    y = -0.3 + math.sin(now * 2.5) * 0.02
    for k, a in ((0.12, 60), (0.08, 120)):
        pts = [h.P(math.cos(t) * 0.42, y + math.sin(t) * 0.1) for t in [i * math.tau / 24 for i in range(24)]]
        pygame.draw.lines(h.layer, (255, 235, 120, a), True, pts, max(2, int(k * h.s * 0.6)))
    pts = [h.P(math.cos(t) * 0.42, y + math.sin(t) * 0.1) for t in [i * math.tau / 24 for i in range(24)]]
    pygame.draw.lines(h.layer, (255, 250, 200, 255), True, pts, max(2, int(0.035 * h.s)))


def cowboy(h, now):
    h.poly([(-0.85, -0.12), (-0.6, 0.04), (0.0, 0.07), (0.6, 0.04), (0.85, -0.12), (0.5, -0.02), (-0.5, -0.02)], (176, 114, 62))
    h.poly([(-0.34, 0.0), (-0.3, -0.42), (-0.1, -0.4), (0.0, -0.3), (0.1, -0.4), (0.3, -0.42), (0.34, 0.0)], (190, 126, 70))
    h.poly([(-0.34, -0.08), (0.34, -0.08), (0.34, 0.0), (-0.34, 0.0)], (90, 56, 30), None)


def chef(h, now):
    h.poly([(-0.34, 0.0), (-0.3, -0.3), (0.3, -0.3), (0.34, 0.0)], (246, 246, 250))
    for cx, cy, r in ((-0.26, -0.42, 0.2), (0.0, -0.58, 0.24), (0.26, -0.42, 0.2)):
        h.circ(cx, cy, r, (250, 250, 252))
    h.poly([(-0.36, -0.08), (0.36, -0.08), (0.36, 0.0), (-0.36, 0.0)], (210, 214, 224), None)


def viking(h, now):
    helmet_col = (150, 152, 164)
    h.poly([(-0.5, 0.04), (-0.48, -0.3), (-0.24, -0.52), (0.24, -0.52), (0.48, -0.3), (0.5, 0.04)], helmet_col)
    h.poly([(-0.52, -0.06), (0.52, -0.06), (0.52, 0.04), (-0.52, 0.04)], (110, 112, 124), None)
    for sd in (-1, 1):
        h.poly([(sd * 0.45, -0.1), (sd * 0.62, -0.24), (sd * 0.66, -0.6), (sd * 0.55, -0.42), (sd * 0.42, -0.26)], (240, 236, 220))


def santa(h, now):
    h.poly([(-0.46, 0.0), (0.46, 0.0), (0.3, -0.45), (0.5 + math.sin(now * 3) * 0.04, -0.62), (-0.1, -0.7)], (222, 40, 50))
    h.poly([(-0.5, -0.1), (0.5, -0.1), (0.5, 0.04), (-0.5, 0.04)], (250, 250, 252))
    h.circ(0.52 + math.sin(now * 3) * 0.04, -0.65, 0.09, (250, 250, 252))


def bunny(h, now):
    for sd in (-1, 1):
        sway = math.sin(now * 3 + sd) * 0.06
        h.ell(sd * 0.22 + sway, -0.52, 0.11, 0.5, (250, 204, 224))
        h.ell(sd * 0.22 + sway, -0.5, 0.055, 0.38, (240, 130, 170), None)


def antennas(h, now):
    for sd in (-1, 1):
        tip = (sd * 0.3 + math.sin(now * 4 + sd) * 0.04, -0.62)
        h.line((sd * 0.12, 0.0), tip, (180, 190, 210, 255), 3)
        h.circ(tip[0], tip[1], 0.07, (120, 255, 200))


HATS = {"tophat": tophat, "wizard": wizard, "crown": crown, "cap": cap, "pirate": pirate, "helmet": helmet, "party": party,
        "horns": horns, "catears": catears, "halo": halo, "cowboy": cowboy, "chef": chef, "viking": viking, "santa": santa,
        "bunny": bunny, "antennas": antennas}


def draw_hat(layer, hat_id, anchor, width, roll, now, yaw=0.0, tilt=0.0):
    fn = HATS.get(hat_id)
    if fn:
        fn(_Hat(layer, anchor, width, roll + tilt, yaw), now)


def draw_accessory(layer, acc_id, fv, now):
    """Acessórios ancorados em olhos/nariz/boca do rosto (FaceView)."""
    w, roll = fv.width, fv.roll
    if acc_id == "sunglasses":
        mid = (fv.eye_l + fv.eye_r) / 2
        h = _Hat(layer, mid, w, roll)
        for sd in (-1, 1):
            h.ell(sd * 0.22, 0.0, 0.2, 0.14, (14, 14, 22))
            h.ell(sd * 0.22 - 0.05, -0.04, 0.06, 0.03, (120, 140, 190), None)
        h.line((-0.05, -0.02), (0.05, -0.02), (14, 14, 22, 255), 4)
        h.line((-0.42, -0.02), (-0.55, -0.06), (14, 14, 22, 255), 4)
        h.line((0.42, -0.02), (0.55, -0.06), (14, 14, 22, 255), 4)
    elif acc_id == "mustache":
        pt = fv.p("lip_up") + (fv.p("nose") - fv.p("lip_up")) * 0.35
        h = _Hat(layer, pt, w, roll)
        for sd in (-1, 1):
            h.poly([(0, -0.02), (sd * 0.22, -0.07), (sd * 0.3, 0.02), (sd * 0.2, 0.08), (0, 0.03)], (60, 40, 30))
    elif acc_id == "clownnose":
        p = fv.p("nose")
        h = _Hat(layer, p, w, roll)
        h.circ(0, 0, 0.085, (255, 50, 60))
        h.circ(-0.025, -0.03, 0.02, (255, 200, 200), None)


# ------------------------------------------------------------------ armas
def draw_weapon(layer, wid, x, y, ang, flash=0.0, scale=1.0):
    """Arma ao longo de `ang` (rad); (x, y) = empunhadura; cano em +x."""
    c, s = math.cos(ang), math.sin(ang)
    flip = -1 if abs(ang) > math.pi / 2 else 1

    def P(px, py):
        px, py = px * scale, py * scale * flip
        return (x + px * c - py * s, y + px * s + py * c)

    def poly(pts, col):
        ps = [P(*p) for p in pts]
        pygame.draw.polygon(layer, (*col, 255), ps)
        pygame.draw.lines(layer, OUT, True, ps, 2)

    metal, dark = (170, 180, 200), (70, 78, 96)
    if wid == "pistol":
        poly([(-6, -10), (46, -10), (46, 4), (-6, 4)], metal)
        poly([(-6, 4), (10, 4), (4, 28), (-10, 28)], dark)
        muzzle = 52
    elif wid == "smg":
        poly([(-10, -10), (62, -10), (62, 4), (-10, 4)], (200, 160, 70))
        poly([(10, 4), (24, 4), (22, 30), (8, 30)], dark)
        poly([(-8, 4), (6, 4), (0, 24), (-12, 24)], dark)
        muzzle = 68
    elif wid == "shotgun":
        poly([(-20, -9), (90, -9), (90, 2), (-20, 2)], (210, 130, 70))
        poly([(-20, 2), (30, 2), (30, 10), (-20, 10)], (110, 70, 40))
        muzzle = 96
    elif wid == "sniper":
        poly([(-24, -8), (110, -8), (110, 0), (-24, 0)], (110, 220, 170))
        poly([(10, -18), (46, -18), (46, -8), (10, -8)], dark)
        poly([(-24, 0), (0, 0), (-8, 18), (-30, 12)], dark)
        muzzle = 116
    elif wid == "laser":
        poly([(-8, -10), (54, -12), (60, -2), (54, 6), (-8, 6)], (255, 90, 130))
        poly([(0, 6), (14, 6), (8, 26), (-6, 26)], dark)
        pygame.draw.circle(layer, (255, 230, 240, 255), (int(P(52, -3)[0]), int(P(52, -3)[1])), 5)
        muzzle = 62
    else:   # rocket_launcher
        poly([(-30, -14), (80, -14), (80, 6), (-30, 6)], (120, 130, 110))
        poly([(78, -18), (96, -18), (96, 10), (78, 10)], (200, 150, 60))
        poly([(10, 6), (24, 6), (18, 26), (4, 26)], dark)
        muzzle = 98
    if flash > 0.05:
        mx, my = P(muzzle, -2)
        for k, a in ((26, 70), (16, 140), (8, 255)):
            pygame.draw.circle(layer, (255, 220, 120, int(a * flash)), (int(mx), int(my)), int(k * flash * scale))
    return P(muzzle, -2)
