"""Armas e matemática de raio (hitscan) para tiros."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Weapon:
    id: str
    name: str
    damage: float
    rate: float            # tiros/s
    mag: int
    reload: float
    spread: float          # graus
    pellets: int = 1
    range: float = 1500.0
    pierce: int = 1
    auto: bool = False
    beam: bool = False
    kb: float = 120.0      # empurrão (px/s)
    cost: int = 0
    color: Tuple[int, int, int] = (255, 255, 255)
    blast: float = 0.0     # raio de explosão (projétil)
    sound: str = "shot_pistol"


WEAPONS = {w.id: w for w in [
    Weapon("pistol", "Pistola", 12, 3.5, 12, 1.0, 1.5, kb=130, color=(200, 220, 255), sound="shot_pistol"),
    Weapon("smg", "Submetralhadora", 6, 11.0, 30, 1.4, 4.0, auto=True, kb=60, cost=150, color=(255, 200, 80), sound="shot_smg"),
    Weapon("shotgun", "Escopeta", 7, 1.1, 6, 1.6, 9.0, pellets=7, range=720, kb=230, cost=250, color=(255, 140, 60), sound="shot_shotgun"),
    Weapon("sniper", "Rifle de Precisão", 60, 0.9, 5, 1.8, 0.0, range=3000, pierce=3, kb=420, cost=400, color=(120, 255, 190), sound="shot_sniper"),
    Weapon("laser", "Raio Laser", 30, 1.0, 100, 1.5, 0.0, range=950, auto=True, beam=True, kb=0, cost=600, color=(255, 70, 110), sound="shot_laser"),
    Weapon("rocket_launcher", "Lança-Foguetes", 55, 0.8, 4, 2.0, 0.0, kb=0, cost=800, color=(255, 170, 50), blast=150, sound="shot_rocket"),
]}
WEAPON_ORDER = ["pistol", "smg", "shotgun", "sniper", "laser", "rocket_launcher"]


@dataclass
class Hit:
    target: object
    dist: float
    point: Tuple[float, float]
    head: bool = False


def ray_circle(ox, oy, dx, dy, cx, cy, r) -> Optional[float]:
    """Distância ao longo do raio (d unitário) até entrar no círculo; None se errar."""
    fx, fy = cx - ox, cy - oy
    t = fx * dx + fy * dy
    d2 = fx * fx + fy * fy - t * t
    if d2 > r * r:
        return None
    th = math.sqrt(r * r - d2)
    t0 = t - th
    if t + th < 0:
        return None
    return max(t0, 0.0)


def ray_hits(ox, oy, dx, dy, targets, max_range=1500.0) -> List[Hit]:
    """targets: iterável de (ref, cx, cy, r, head) com head = (hx, hy, hr) ou None. Retorna acertos ordenados."""
    n = math.hypot(dx, dy) or 1.0
    dx, dy = dx / n, dy / n
    hits: List[Hit] = []
    for ref, cx, cy, r, head in targets:
        tb = ray_circle(ox, oy, dx, dy, cx, cy, r)
        th = ray_circle(ox, oy, dx, dy, head[0], head[1], head[2]) if head else None
        cands = [t for t in (tb, th) if t is not None and t <= max_range]
        if not cands:
            continue
        t = min(cands)
        hits.append(Hit(ref, t, (ox + dx * t, oy + dy * t), head=th is not None and (tb is None or th <= tb + 4)))
    hits.sort(key=lambda h: h.dist)
    return hits


def spread_dir(dx, dy, spread_deg, rng=random):
    n = math.hypot(dx, dy) or 1.0
    a = math.atan2(dy, dx) + math.radians(rng.uniform(-spread_deg, spread_deg))
    return math.cos(a), math.sin(a)


class WeaponState:
    """Munição, cadência e recarga de uma arma equipada."""

    def __init__(self, weapon: Weapon, dmg_mult: float = 1.0, rate_mult: float = 1.0):
        self.w = weapon
        self.dmg_mult, self.rate_mult = dmg_mult, rate_mult
        self.ammo = float(weapon.mag)
        self.cool = 0.0
        self.reload_t = 0.0

    @property
    def reloading(self) -> bool:
        return self.reload_t > 0.0

    def update(self, dt: float, firing: bool = False):
        self.cool = max(0.0, self.cool - dt)
        if self.reload_t > 0:
            self.reload_t -= dt
            if self.reload_t <= 0:
                self.reload_t, self.ammo = 0.0, float(self.w.mag)
        elif self.w.beam and not firing and self.ammo < self.w.mag:
            self.ammo = min(self.w.mag, self.ammo + 25.0 * dt)   # laser recarrega a energia sozinho
        if self.ammo <= 0 and not self.reloading:
            self.reload_t = self.w.reload

    def can_fire(self) -> bool:
        return self.cool <= 0 and not self.reloading and self.ammo > 0

    def fire(self) -> bool:
        if not self.can_fire():
            return False
        self.ammo -= 1
        self.cool = 1.0 / (self.w.rate * self.rate_mult)
        return True

    def drain_beam(self, dt: float) -> bool:
        if self.reloading or self.ammo <= 0:
            return False
        self.ammo = max(0.0, self.ammo - 22.0 * dt)
        return True

    @property
    def damage(self) -> float:
        return self.w.damage * self.dmg_mult
