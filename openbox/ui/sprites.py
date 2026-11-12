"""Sprites dos objetos: esferas sombreadas (numpy), cubos isométricos e formas facetadas.
Renderizados uma vez por (tipo, raio) e reaproveitados (rotação em cache por faixas de ângulo)."""
from __future__ import annotations

import math

import numpy as np
import pygame

from .. import theme as T
from . import draw

_cache: dict = {}
_rot_cache: dict = {}
WHITE = (255, 255, 255)


def _rgba(arr):
    h, w = arr.shape[:2]
    return pygame.image.frombuffer(arr.tobytes(), (w, h), "RGBA").convert_alpha()


def _mul(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def _canvas(n):
    return pygame.Surface((int(n), int(n)), pygame.SRCALPHA)


# ------------------------------------------------------------------ esfera sombreada
def sphere(r, color, pattern=None, glass=False, spec=0.85, ambient=0.30, pad=3):
    n = int(r * 2) + pad * 2
    c = n / 2.0
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    nx, ny = (xx - c + 0.5) / r, (yy - c + 0.5) / r
    d2 = nx * nx + ny * ny
    mask = np.clip((1.0 - np.sqrt(d2)) * r + 0.5, 0.0, 1.0)
    nz = np.sqrt(np.clip(1.0 - d2, 0.0, 1.0))
    L = np.array([-0.45, -0.6, 0.66], dtype=np.float32)
    L /= np.linalg.norm(L)
    diff = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0.0, 1.0)
    base = np.empty((n, n, 3), dtype=np.float32)
    base[:] = np.array(color, dtype=np.float32)
    if pattern is not None:
        base = pattern(nx, ny, base)
    rgb = base * (ambient + (1.0 - ambient) * diff)[..., None]
    rgb += ((diff ** 26) * 255.0 * spec)[..., None]
    rgb += ((1.0 - nz) ** 2.6 * 70.0)[..., None] * (np.array(color, dtype=np.float32) / 255.0 + 0.3)
    alpha = mask * 255.0
    if glass:
        alpha = np.maximum(alpha * (0.22 + 0.78 * (1.0 - nz) ** 1.5), (diff ** 26) * 255.0 * mask)
    arr = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha, 0, 255)]).astype(np.uint8)
    return _rgba(arr)


def _dark(mask_arr, base, k=0.12):
    base[mask_arr] = base[mask_arr] * k
    return base


def pat_basketball(nx, ny, base):
    line = (np.abs(nx) < 0.05) | (np.abs(ny) < 0.05)
    line |= np.abs(np.hypot(nx - 1.15, ny) - 0.85) < 0.045
    line |= np.abs(np.hypot(nx + 1.15, ny) - 0.85) < 0.045
    return _dark(line, base)


def pat_soccer(nx, ny, base):
    base[:] = np.array([244, 244, 248], dtype=np.float32)
    dark = np.hypot(nx, ny) < 0.30
    for k in range(5):
        a = k * math.tau / 5 + 0.3
        dark |= np.hypot(nx - math.cos(a) * 0.78, ny - math.sin(a) * 0.78) < 0.2
    return _dark(dark, base, 0.10)


def pat_bowling(nx, ny, base):
    holes = np.zeros(nx.shape, bool)
    for hx, hy in ((-0.30, -0.45), (0.05, -0.50), (-0.10, -0.18)):
        holes |= np.hypot(nx - hx, ny - hy) < 0.10
    return _dark(holes, base, 0.05)


def pat_beach(nx, ny, base):
    ang = np.arctan2(ny, nx)
    seg = (np.floor((ang + math.pi) / (math.tau / 6)) % 6).astype(int)
    pal = np.array([(255, 80, 110), (255, 255, 255), (70, 170, 255), (255, 255, 255), (255, 215, 60), (255, 255, 255)], dtype=np.float32)
    return pal[seg]


def pat_pumpkin(nx, ny, base):
    ridge = np.abs(np.sin(nx * math.pi * 2.6)) < 0.14
    return _dark(ridge, base, 0.62)


def pat_magnet(nx, ny, base):
    out = base.copy()
    out[nx < 0] = np.array([230, 60, 70], dtype=np.float32)
    out[nx >= 0] = np.array([70, 110, 235], dtype=np.float32)
    tip = np.abs(ny) > 0.62
    out[tip] = np.array([215, 220, 232], dtype=np.float32)
    return out


# ------------------------------------------------------------------ cubo isométrico
def iso_cube(r, top, left, right, edge, alpha=255, scale=0.95, canvas=None):
    n = int(r * 2.5) + 6
    S = canvas or _canvas(n)
    c = S.get_width() / 2.0
    h = r * scale
    k = 0.866
    P = {"t": (c, c - h), "ur": (c + k * h, c - h / 2), "lr": (c + k * h, c + h / 2), "b": (c, c + h),
         "ll": (c - k * h, c + h / 2), "ul": (c - k * h, c - h / 2), "c": (c, c)}
    faces = [("top", [P["t"], P["ur"], P["c"], P["ul"]], top), ("left", [P["ul"], P["c"], P["b"], P["ll"]], left),
             ("right", [P["ur"], P["lr"], P["b"], P["c"]], right)]
    for _, pts, col in faces:
        pygame.draw.polygon(S, (*col, alpha), pts)
    for _, pts, _col in faces:
        pygame.draw.lines(S, (*edge, min(255, alpha + 40)), True, pts, 2)
    return S, {name: pts for name, pts, _ in faces}     # (pygame.Surface não aceita atributos extras)


def _center(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


# ------------------------------------------------------------------ renderizadores
def r_orb(r, c):
    S = sphere(r, c, glass=True)
    n = S.get_width()
    pygame.draw.circle(S, (*WHITE, 110), (n // 2, n // 2), int(r * 0.62), 1)
    pygame.draw.circle(S, (*WHITE, 240), (n // 2 + int(r * 0.62), n // 2), max(3, int(r * 0.11)))
    return S


def _plain_sphere(pattern=None, **kw):
    return lambda r, c: sphere(r, c, pattern, **kw)


def r_cube(r, c):
    return iso_cube(r, T.mix(c, WHITE, 0.45), _mul(c, 0.78), _mul(c, 0.5), T.mix(c, WHITE, 0.7), alpha=205)[0]


def r_crate(r, c):
    S, f = iso_cube(r, (206, 158, 96), (160, 112, 62), (120, 82, 44), (60, 38, 20))
    for name in ("left", "right"):
        p = f[name]
        pygame.draw.line(S, (70, 44, 22, 255), p[0], p[2], 3)
        pygame.draw.line(S, (70, 44, 22, 255), p[1], p[3], 3)
    t = f["top"]
    pygame.draw.line(S, (110, 76, 40, 255), _center([t[0], t[3]]), _center([t[1], t[2]]), 2)
    return S


def r_dice(r, c):
    S, f = iso_cube(r, (250, 250, 252), (222, 224, 232), (190, 194, 208), (80, 84, 100))
    pip = lambda p, rad: pygame.draw.circle(S, (30, 34, 50, 255), (int(p[0]), int(p[1])), rad)
    pip(_center(f["top"]), max(2, int(r * 0.11)))
    lc = _center(f["left"])
    for dx, dy in ((-0.2, -0.12), (0.2, 0.12)):
        pip((lc[0] + dx * r, lc[1] + dy * r), max(2, int(r * 0.09)))
    rc = _center(f["right"])
    for dx, dy in ((-0.24, 0.0), (0.0, 0.0), (0.24, 0.0)):
        pip((rc[0] + dx * r, rc[1] - dx * r * 0.45 + dy), max(2, int(r * 0.09)))
    return S


def r_ice(r, c):
    return iso_cube(r, (225, 248, 255), (150, 215, 245), (110, 180, 225), (240, 252, 255), alpha=170)[0]


def r_tnt(r, c):
    S, f = iso_cube(r, (240, 90, 80), (205, 50, 50), (150, 32, 38), (255, 190, 180))
    rc = _center(f["right"])
    lab = pygame.Rect(0, 0, int(r * 0.9), int(r * 0.4))
    lab.center = (int(rc[0]), int(rc[1]))
    pygame.draw.rect(S, (245, 240, 225, 255), lab, border_radius=3)
    draw.text(S, "TNT", lab.center, max(9, int(r * 0.34)), (150, 30, 30), True, "c")
    t = f["top"]
    pygame.draw.line(S, (40, 30, 20, 255), _center(t), (_center(t)[0] + r * 0.2, _center(t)[1] - r * 0.35), 3)
    return S


def r_anvil(r, c):
    n = int(r * 2.5) + 6
    S, cx = _canvas(n), n / 2
    pts = [(-1.0, -0.35), (0.5, -0.45), (1.1, -0.2), (0.55, -0.1), (0.35, 0.15), (0.6, 0.55), (-0.6, 0.55), (-0.35, 0.15), (-0.55, -0.1)]
    poly = [(cx + x * r * 0.95, cx + y * r * 1.1) for x, y in pts]
    pygame.draw.polygon(S, (*c, 255), poly)
    pygame.draw.polygon(S, (*_mul(c, 0.55), 255), [poly[4], poly[5], poly[6], poly[7]])
    pygame.draw.lines(S, (30, 34, 46, 255), True, poly, 2)
    pygame.draw.line(S, (*T.mix(c, WHITE, 0.6), 255), poly[0], poly[1], 3)
    return S


def r_barrel(r, c):
    n = int(r * 2.5) + 6
    S, cx = _canvas(n), n / 2
    w, h = r * 1.4, r * 1.75
    body = pygame.Rect(0, 0, int(w), int(h))
    body.center = (int(cx), int(cx))
    pygame.draw.rect(S, (*c, 255), body, border_radius=int(r * 0.3))
    for yy in (0.22, 0.78):
        pygame.draw.rect(S, (110, 25, 25, 255), (body.x, body.y + int(h * yy) - 3, body.w, 7))
    top = pygame.Rect(body.x, body.y - int(r * 0.12), body.w, int(r * 0.4))
    pygame.draw.ellipse(S, (255, 140, 120, 255), top)
    pygame.draw.ellipse(S, (120, 30, 30, 255), top, 2)
    tri = [(cx, cx - r * 0.38), (cx + r * 0.32, cx + r * 0.2), (cx - r * 0.32, cx + r * 0.2)]
    pygame.draw.polygon(S, (255, 210, 40, 255), tri)
    pygame.draw.lines(S, (40, 30, 20, 255), True, tri, 2)
    pygame.draw.line(S, (255, 255, 255, 90), (body.x + 6, body.y + 12), (body.x + 6, body.bottom - 12), 3)
    pygame.draw.rect(S, (60, 14, 14, 255), body, 2, border_radius=int(r * 0.3))
    return S


def r_bomb(r, c):
    S = sphere(r * 0.92, (36, 40, 58), spec=0.9)
    n = S.get_width()
    big = _canvas(int(r * 2.5) + 6)
    cx = big.get_width() // 2
    big.blit(S, S.get_rect(center=(cx, cx + int(r * 0.12))))
    pygame.draw.line(big, (210, 190, 150, 255), (cx + r * 0.45, cx - r * 0.72), (cx + r * 0.85, cx - r * 1.12), 4)
    pygame.draw.circle(big, (255, 200, 60, 255), (int(cx + r * 0.88), int(cx - r * 1.16)), max(3, int(r * 0.13)))
    pygame.draw.circle(big, (255, 90, 60, 220), (int(cx - r * 0.05), int(cx + r * 0.12)), max(3, int(r * 0.2)), 2)
    return big


def r_grenade(r, c):
    n = int(r * 2.5) + 6
    S, cx = _canvas(n), n / 2
    body = pygame.Rect(0, 0, int(r * 1.45), int(r * 1.75))
    body.center = (int(cx), int(cx + r * 0.1))
    pygame.draw.ellipse(S, (*c, 255), body)
    for k in (-0.35, 0.0, 0.35):
        pygame.draw.line(S, (40, 70, 36, 255), (cx + k * r * 1.1, body.y + 4), (cx + k * r * 1.1, body.bottom - 4), 1)
    for yy in (-0.3, 0.25):
        pygame.draw.line(S, (40, 70, 36, 255), (body.x + 4, cx + yy * r * 1.2), (body.right - 4, cx + yy * r * 1.2), 1)
    pygame.draw.ellipse(S, (22, 40, 22, 255), body, 2)
    pygame.draw.rect(S, (150, 150, 160, 255), (cx - r * 0.25, body.y - r * 0.3, r * 0.5, r * 0.34), border_radius=3)
    pygame.draw.circle(S, (230, 200, 70, 255), (int(cx + r * 0.42), int(body.y - r * 0.12)), int(r * 0.2), 2)
    pygame.draw.ellipse(S, (255, 255, 255, 80), (body.x + r * 0.2, body.y + r * 0.2, r * 0.4, r * 0.55))
    return S


def r_rocket(r, c):
    n = int(r * 3.6) + 6
    S, cx = _canvas(n), n / 2
    body = pygame.Rect(0, 0, int(r * 0.9), int(r * 2.1))
    body.center = (int(cx), int(cx))
    pygame.draw.rect(S, (*c, 255), body, border_radius=4)
    pygame.draw.polygon(S, (250, 250, 250, 255), [(body.x, body.y), (body.right, body.y), (cx, body.y - r * 0.9)])
    pygame.draw.polygon(S, (70, 150, 255, 255), [(body.x, body.bottom - 4), (body.x - r * 0.5, body.bottom + 6), (body.x, body.bottom - r * 0.6)])
    pygame.draw.polygon(S, (70, 150, 255, 255), [(body.right, body.bottom - 4), (body.right + r * 0.5, body.bottom + 6), (body.right, body.bottom - r * 0.6)])
    pygame.draw.rect(S, (255, 220, 70, 255), (body.x, body.y + int(r * 0.7), body.w, int(r * 0.25)))
    pygame.draw.polygon(S, (255, 160, 40, 220), [(cx - r * 0.25, body.bottom), (cx + r * 0.25, body.bottom), (cx, body.bottom + r * 0.7)])
    return S


def r_missile(r, c):
    S = r_rocket(r * 0.8, (230, 90, 60))
    return pygame.transform.rotate(S, -90)


def _star_pts(cx, cy, ro, ri, n=5, rot=-math.pi / 2):
    return [(cx + math.cos(rot + i * math.pi / n) * (ro if i % 2 == 0 else ri),
             cy + math.sin(rot + i * math.pi / n) * (ro if i % 2 == 0 else ri)) for i in range(n * 2)]


def r_star(r, c):
    n = int(r * 2.4) + 6
    S, cx = _canvas(n), n / 2
    pts = _star_pts(cx, cx, r * 1.05, r * 0.45)
    for i in range(5):
        o, i1, i2 = pts[2 * i], pts[2 * i - 1], pts[2 * i + 1]
        pygame.draw.polygon(S, (*(T.mix(c, WHITE, 0.45) if i % 2 == 0 else _mul(c, 0.8)), 255), [o, i1, (cx, cx)])
        pygame.draw.polygon(S, (*(_mul(c, 0.7) if i % 2 == 0 else T.mix(c, WHITE, 0.2)), 255), [o, i2, (cx, cx)])
    pygame.draw.lines(S, (140, 90, 10, 255), True, pts, 2)
    return S


def _heart_pts(cx, cy, r, k=1.0):
    pts = []
    for i in range(40):
        t = i / 40 * math.tau
        pts.append((cx + 16 * math.sin(t) ** 3 / 17 * r * 1.1 * k,
                    cy - (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 17 * r * 1.1 + r * 0.08))
    return pts


def r_heart(r, c):
    n = int(r * 2.5) + 6
    S, cx = _canvas(n), n / 2
    pts = _heart_pts(cx, cx, r)
    pygame.draw.polygon(S, (*_mul(c, 0.8), 255), pts)
    half = [p for p in pts if p[0] <= cx + 0.5]
    if len(half) > 3:
        pygame.draw.polygon(S, (*T.mix(c, WHITE, 0.2), 255), half + [(cx, cx + r * 0.98)])
    pygame.draw.lines(S, (150, 20, 60, 255), True, pts, 2)
    pygame.draw.ellipse(S, (255, 255, 255, 150), (cx - r * 0.6, cx - r * 0.7, r * 0.45, r * 0.3))
    return S


def r_coin(r, c):
    n = int(r * 2) + 6
    S, cx = _canvas(n), n / 2
    pygame.draw.circle(S, (*_mul(c, 0.75), 255), (int(cx), int(cx)), int(r))
    pygame.draw.circle(S, (*T.mix(c, WHITE, 0.35), 255), (int(cx), int(cx)), int(r * 0.86))
    pygame.draw.circle(S, (*_mul(c, 0.8), 255), (int(cx), int(cx)), int(r * 0.62), 2)
    pygame.draw.polygon(S, (*_mul(c, 0.7), 255), _star_pts(cx, cx, r * 0.45, r * 0.2))
    pygame.draw.arc(S, (255, 255, 255, 200), pygame.Rect(cx - r * 0.8, cx - r * 0.8, r * 1.6, r * 1.6), 1.9, 2.8, 3)
    return S


def r_gem(r, c):
    n = int(r * 2.5) + 6
    S, cx = _canvas(n), n / 2
    tl, tr_, ml, mr = (cx - r * 0.55, cx - r * 0.55), (cx + r * 0.55, cx - r * 0.55), (cx - r, cx - r * 0.1), (cx + r, cx - r * 0.1)
    bot = (cx, cx + r * 1.0)
    for pts, k in (([tl, tr_, (cx + r * 0.3, cx - r * 0.1), (cx - r * 0.3, cx - r * 0.1)], 1.0),
                   ([tl, ml, (cx - r * 0.3, cx - r * 0.1)], 0.8), ([tr_, mr, (cx + r * 0.3, cx - r * 0.1)], 0.6),
                   ([ml, (cx - r * 0.3, cx - r * 0.1), bot], 0.7), ([mr, (cx + r * 0.3, cx - r * 0.1), bot], 0.5),
                   ([(cx - r * 0.3, cx - r * 0.1), (cx + r * 0.3, cx - r * 0.1), bot], 0.9)):
        pygame.draw.polygon(S, (*T.mix(_mul(c, k), WHITE, 0.15 * k), 235), pts)
    pygame.draw.lines(S, (230, 250, 255, 255), True, [tl, tr_, mr, bot, ml], 2)
    return S


def r_balloon(r, c):
    n = int(r * 3.9) + 6
    S, cx = _canvas(n), n / 2
    sph = sphere(r, c, spec=0.9)
    S.blit(sph, sph.get_rect(center=(int(cx), int(cx))))
    pygame.draw.polygon(S, (*_mul(c, 0.7), 255), [(cx - r * 0.12, cx + r * 0.98), (cx + r * 0.12, cx + r * 0.98), (cx, cx + r * 1.14)])
    pygame.draw.lines(S, (220, 220, 230, 220), False, [(cx, cx + r * 1.12), (cx - r * 0.12, cx + r * 1.4), (cx + r * 0.1, cx + r * 1.7), (cx, cx + r * 1.95)], 2)
    return S


def r_duck(r, c):
    n = int(r * 2.6) + 6
    S, cx = _canvas(n), n / 2
    pygame.draw.ellipse(S, (*c, 255), (cx - r * 0.95, cx - r * 0.1, r * 1.8, r * 1.0))
    pygame.draw.circle(S, (*c, 255), (int(cx + r * 0.35), int(cx - r * 0.4)), int(r * 0.52))
    pygame.draw.polygon(S, (255, 140, 30, 255), [(cx + r * 0.8, cx - r * 0.42), (cx + r * 1.3, cx - r * 0.3), (cx + r * 0.8, cx - r * 0.2)])
    pygame.draw.circle(S, (30, 30, 40, 255), (int(cx + r * 0.5), int(cx - r * 0.55)), max(2, int(r * 0.09)))
    pygame.draw.ellipse(S, (*_mul(c, 0.8), 255), (cx - r * 0.7, cx + r * 0.1, r * 0.9, r * 0.45))
    pygame.draw.ellipse(S, (255, 255, 255, 120), (cx - r * 0.5, cx - r * 0.0, r * 0.7, r * 0.22))
    return S


def r_blackhole(r, c):
    n = int(r * 3.2) + 6
    S, cx = _canvas(n), n / 2
    for k, a in ((1.55, 40), (1.3, 70), (1.12, 110)):
        pygame.draw.circle(S, (*c, a), (int(cx), int(cx)), int(r * k), max(2, int(r * 0.16)))
    pygame.draw.circle(S, (8, 4, 20, 255), (int(cx), int(cx)), int(r))
    pygame.draw.circle(S, (*T.mix(c, WHITE, 0.4), 255), (int(cx), int(cx)), int(r), 2)
    pygame.draw.arc(S, (255, 255, 255, 200), pygame.Rect(cx - r * 0.75, cx - r * 0.75, r * 1.5, r * 1.5), 0.2, 1.4, 3)
    return S


def r_target(r, c):
    n = int(r * 2) + 8
    S, cx = _canvas(n), n // 2
    for k, col in ((1.0, c), (0.78, (250, 250, 250)), (0.56, c), (0.34, (250, 250, 250)), (0.14, c)):
        pygame.draw.circle(S, (*col, 255), (cx, cx), int(r * k))
    pygame.draw.circle(S, (60, 14, 20, 255), (cx, cx), int(r), 3)
    pygame.draw.arc(S, (255, 255, 255, 170), pygame.Rect(cx - r * 0.9, cx - r * 0.9, r * 1.8, r * 1.8), 1.9, 2.7, 4)
    return S


def r_spring(r, c):
    S = sphere(r, c)
    n = S.get_width()
    for k in (-0.45, 0.0, 0.45):
        pygame.draw.arc(S, (20, 100, 40, 200), pygame.Rect(n / 2 - r * 0.95, n / 2 + k * r - r * 0.3, r * 1.9, r * 0.6), 3.3, 6.1, 3)
    return S


RENDER = {
    "orb": r_orb,
    "basketball": _plain_sphere(pat_basketball),
    "soccer": _plain_sphere(pat_soccer),
    "bowling": _plain_sphere(pat_bowling),
    "beachball": _plain_sphere(pat_beach),
    "spring": r_spring,
    "pumpkin": _plain_sphere(pat_pumpkin),
    "cube": r_cube, "crate": r_crate, "dice": r_dice, "ice": r_ice, "tnt": r_tnt, "anvil": r_anvil,
    "barrel": r_barrel, "bomb": r_bomb, "grenade": r_grenade, "rocket": r_rocket, "missile": r_missile,
    "star": r_star, "heart": r_heart, "coin": r_coin, "gem": r_gem, "balloon": r_balloon, "duck": r_duck,
    "magnet": _plain_sphere(pat_magnet), "blackhole": r_blackhole, "target": r_target,
}
NO_ROTATE = {"balloon", "duck"}


def base_sprite(kind, r, color):
    key = (kind, int(round(r / 3.0)) * 3)
    s = _cache.get(key)
    if s is None:
        if len(_cache) > 600:
            _cache.clear()
            _rot_cache.clear()
        fn = RENDER.get(kind)
        s = fn(key[1], color) if fn else sphere(key[1], color)
        _cache[key] = s
    return s


def _tinted(s, flash, held):
    if flash <= 0.25 and not held:
        return s
    t = s.copy()
    if held:
        t.fill((0, 70, 24), special_flags=pygame.BLEND_RGB_ADD)
    if flash > 0.25:
        k = int(80 * flash)
        t.fill((k, k, k), special_flags=pygame.BLEND_RGB_ADD)
    return t


def body_image(b, now=0.0):
    """Imagem pronta (já rotacionada) do corpo `b`. Retorna Surface centrada no corpo."""
    held, flash = bool(b.held_by), b.flash
    if b.kind == "coin":                                         # moeda gira: largura varia com cos
        base = base_sprite("coin", b.r, b.color)
        wdt = max(4, int(base.get_width() * abs(math.cos(b.angle * 2.0))))
        key = ("coinw", base.get_width(), wdt, held, flash > 0.25)
        img = _rot_cache.get(key)
        if img is None:
            img = pygame.transform.smoothscale(_tinted(base, flash, held), (wdt, base.get_height()))
            _rot_cache[key] = img
        return img
    base = base_sprite(b.kind, b.r, b.color)
    ang = 0.0 if b.kind in NO_ROTATE else b.angle
    if b.kind in NO_ROTATE:
        ang = max(-0.4, min(0.4, b.vx * 0.0006))
    deg = int(round(-math.degrees(ang) / 6.0)) * 6 % 360
    key = (b.kind, base.get_width(), deg, held, flash > 0.25)
    img = _rot_cache.get(key)
    if img is None:
        if len(_rot_cache) > 3000:
            _rot_cache.clear()
        t = _tinted(base, flash, held)
        img = pygame.transform.rotate(t, deg) if deg else t
        _rot_cache[key] = img
    return img
