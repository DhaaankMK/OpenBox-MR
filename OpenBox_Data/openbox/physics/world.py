"""Mundo físico 2D leve: corpos circulares dirigidos pelo catálogo de itens, paredes, colisões,
colisores cinemáticos (mãos), atratores (ímã/buraco negro) e explosões."""
from __future__ import annotations

import math
import random
from collections import deque
from typing import List, Tuple

from ..game.items import ITEMS, Item

MAX_SPEED = 4200.0
SUBSTEP = 1.0 / 120.0

INTERNAL = {"missile": Item("missile", "Míssil", "ferramentas", r=13, density=0.5, gscale=0.05, color=(255, 170, 60),
                            tags=frozenset({"missile", "round"}))}


class Body:
    _ids = 0

    def __init__(self, kind: str, x: float, y: float, radius: float | None = None):
        Body._ids += 1
        self.id = Body._ids
        self.kind = kind
        item = ITEMS.get(kind) or INTERNAL.get(kind)
        self.item = item
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.r = float(radius or (item.r if item else 32))
        self.base_r = self.target_r = self.r
        self.angle = random.uniform(0, math.tau)
        self.w = random.uniform(-1.5, 1.5)
        self.color = item.color if item else (255, 255, 255)
        self.density = item.density if item else 1.0
        self.gscale = item.gscale if item else 1.0
        self.bounce_mult = item.bounce if item else 1.0
        self.tags = item.tags if item else frozenset()
        self.hp = self.max_hp = float(item.hp if item else 1)
        self.held_by: set = set()
        self.target = (self.x, self.y)
        self.trail: deque = deque(maxlen=22)
        self.age = 0.0
        self.flash = 0.0
        self.hit_cd = 0.0
        self.dead = False
        self.grounded = False
        self.hit_speed = 0.0
        self.brain = None          # Brain (criaturas)
        self.fuse = None           # contagem regressiva (granada, foguete, míssil)
        self.extra: dict = {}

    @property
    def mass(self) -> float:
        return max(0.15, self.density * (self.r / 34.0) ** 2)

    def has(self, tag: str) -> bool:
        return tag in self.tags


class World:
    MAX_BODIES = 70

    def __init__(self, width: int, height: int, cfg):
        self.w, self.h, self.cfg = width, height, cfg
        self.bodies: List[Body] = []
        self.impacts: List[Tuple[float, float, float, str]] = []
        self.pair_hits: list = []

    # ---------------------------------------------------------------- gestão
    def add(self, kind: str, x: float, y: float, vx: float = 0.0, vy: float = 0.0, radius=None) -> Body:
        if len(self.bodies) >= self.MAX_BODIES:
            for b in self.bodies:
                if not b.held_by and "hostile" not in b.tags:
                    self.bodies.remove(b)
                    break
            else:
                self.bodies.pop(0)
        b = Body(kind, x, y, radius)
        b.vx, b.vy = vx, vy
        b.x = min(max(b.x, b.r), self.w - b.r)
        b.y = min(max(b.y, b.r), self.h - b.r)
        self.bodies.append(b)
        return b

    def clear(self):
        self.bodies.clear()
        self.pair_hits.clear()
        self.impacts.clear()

    def remove_dead(self):
        self.bodies = [b for b in self.bodies if not b.dead]

    def nearest(self, x: float, y: float, reach: float = 40.0, free_only: bool = False):
        best, best_d = None, 1e9
        for b in self.bodies:
            if free_only and b.held_by:
                continue
            d = math.hypot(b.x - x, b.y - y) - b.r
            if d < reach and d < best_d:
                best, best_d = b, d
        return best

    def explode(self, x, y, radius=230.0, power=1500.0, ignore=None):
        """Impulso radial."""
        for b in self.bodies:
            if b is ignore or b.held_by:
                continue
            dx, dy = b.x - x, b.y - y
            d = math.hypot(dx, dy) or 1.0
            if d < radius:
                k = (1.0 - d / radius) * power / max(0.6, b.mass ** 0.5)
                b.vx += dx / d * k
                b.vy += dy / d * k - 120 * (1.0 - d / radius)
                b.flash = 1.0
                b.hit_speed = max(b.hit_speed, k * 0.5)

    # ---------------------------------------------------------------- passo
    def step(self, dt: float, colliders=()):
        dt = min(dt, 0.05)
        self._attract(dt)
        n = max(1, int(math.ceil(dt / SUBSTEP)))
        h = dt / n
        for _ in range(n):
            self._substep(h, colliders)
        for b in self.bodies:
            b.age += dt
            b.flash = max(0.0, b.flash - dt * 3.0)
            b.hit_cd = max(0.0, b.hit_cd - dt)
            b.trail.append((b.x, b.y))

    def _attract(self, dt):
        for a in self.bodies:
            rng, force = a.item.attract if a.item else (0.0, 0.0)
            if rng <= 0 or a.held_by and False:
                continue
            for b in self.bodies:
                if b is a or b.held_by:
                    continue
                dx, dy = a.x - b.x, a.y - b.y
                d = math.hypot(dx, dy)
                if 1.0 < d < rng:
                    k = force * (1.0 - d / rng) * dt
                    b.vx += dx / d * k
                    b.vy += dy / d * k

    def _substep(self, h: float, colliders):
        g, drag = self.cfg.gravity, self.cfg.air_drag
        for b in self.bodies:
            b.grounded = False
            e = min(1.1, self.cfg.bounce * b.bounce_mult)
            if b.held_by:
                vx, vy = (b.target[0] - b.x) * 20.0, (b.target[1] - b.y) * 20.0
                sp = math.hypot(vx, vy)
                if sp > 7000:
                    vx, vy = vx * 7000 / sp, vy * 7000 / sp
                b.vx, b.vy = vx, vy
                b.r += (b.target_r - b.r) * min(1.0, h * 12.0)
            else:
                b.vy += g * b.gscale * h
                damp = max(0.0, 1.0 - drag * h)
                b.vx *= damp
                b.vy *= damp
                sp = math.hypot(b.vx, b.vy)
                if sp > MAX_SPEED:
                    b.vx, b.vy = b.vx * MAX_SPEED / sp, b.vy * MAX_SPEED / sp
            b.x += b.vx * h
            b.y += b.vy * h
            b.angle += b.w * h
            b.w *= max(0.0, 1.0 - 0.6 * h)
            self._walls(b, e, h)

        bodies = self.bodies
        for i in range(len(bodies)):
            a = bodies[i]
            for j in range(i + 1, len(bodies)):
                self._pair(a, bodies[j])
        if colliders:
            for c in colliders:
                for b in bodies:
                    if not b.held_by:
                        self._collider(b, c)

    def _walls(self, b: Body, e: float, h: float):
        hit = 0.0
        if b.x < b.r:
            b.x = b.r
            if b.vx < 0:
                hit = -b.vx
                b.vx = -b.vx * e
        elif b.x > self.w - b.r:
            b.x = self.w - b.r
            if b.vx > 0:
                hit = b.vx
                b.vx = -b.vx * e
        if b.y < b.r:
            b.y = b.r
            if b.vy < 0:
                hit = max(hit, -b.vy)
                b.vy = -b.vy * e
        elif b.y > self.h - b.r:
            b.y = self.h - b.r
            if b.vy > 0:
                hit = max(hit, b.vy)
                b.vy = -b.vy * e
        if b.y >= self.h - b.r - 1.5 and not b.held_by:
            b.grounded = True
            if b.brain is None:
                if "box" in b.tags:
                    b.vx *= max(0.0, 1.0 - 5.0 * h)
                    b.w *= max(0.0, 1.0 - 8.0 * h)
                else:
                    b.vx *= 0.995
                    b.w = b.w * 0.92 + (b.vx / max(b.r, 1.0)) * 0.08
        if hit > 260:
            self.impacts.append((b.x, b.y, hit, b.kind))
            b.flash = 1.0
            b.hit_speed = max(b.hit_speed, hit)

    def _pair(self, a: Body, b: Body):
        dx, dy = b.x - a.x, b.y - a.y
        rr = a.r + b.r
        d2 = dx * dx + dy * dy
        if d2 >= rr * rr or d2 < 1e-9:
            return
        d = math.sqrt(d2)
        nx, ny = dx / d, dy / d
        ia = 0.0 if a.held_by else 1.0 / a.mass
        ib = 0.0 if b.held_by else 1.0 / b.mass
        s = ia + ib
        if s == 0.0:
            return
        pen = rr - d
        a.x -= nx * pen * ia / s
        a.y -= ny * pen * ia / s
        b.x += nx * pen * ib / s
        b.y += ny * pen * ib / s
        rv = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
        if rv < 0:
            e = min(1.1, self.cfg.bounce * (a.bounce_mult + b.bounce_mult) / 2.0)
            j = -(1.0 + e) * rv / s
            a.vx -= j * ia * nx
            a.vy -= j * ia * ny
            b.vx += j * ib * nx
            b.vy += j * ib * ny
            tvx = (b.vx - a.vx) * -ny + (b.vy - a.vy) * nx
            if a.brain is None:
                a.w -= tvx * 0.004 * ia
            if b.brain is None:
                b.w += tvx * 0.004 * ib
            if -rv > 150:
                self.pair_hits.append((a, b, -rv))
            if -rv > 220:
                self.impacts.append(((a.x + b.x) / 2, (a.y + b.y) / 2, -rv, b.kind))
                a.flash = b.flash = 1.0
                a.hit_speed = max(a.hit_speed, -rv * (b.mass / (a.mass + b.mass)) * 1.6)
                b.hit_speed = max(b.hit_speed, -rv * (a.mass / (a.mass + b.mass)) * 1.6)

    def _collider(self, b: Body, c):
        """c = (x, y, raio, vx, vy): círculo cinemático (ponta de dedo / palma)."""
        cx, cy, cr, cvx, cvy = c
        dx, dy = b.x - cx, b.y - cy
        rr = b.r + cr
        d2 = dx * dx + dy * dy
        if d2 >= rr * rr or d2 < 1e-9:
            return
        d = math.sqrt(d2)
        nx, ny = dx / d, dy / d
        pen = rr - d
        b.x += nx * pen
        b.y += ny * pen
        rv = (b.vx - cvx) * nx + (b.vy - cvy) * ny
        if rv < 0:
            k = -(1.0 + 0.35) * rv
            b.vx += k * nx
            b.vy += k * ny
            if b.brain is None:
                b.w += ((cvx * -ny + cvy * nx) * 0.003)
            if k > 260:
                self.impacts.append((cx, cy, k, b.kind))
                b.flash = 1.0
                b.hit_speed = max(b.hit_speed, k * 0.5)
