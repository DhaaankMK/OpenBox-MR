"""Cérebro das criaturas (bots/zumbis): passear, pular, sentir medo, tontura e ataque — lógica pura."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

TAU = math.tau

PERSONALITY = {
    #            caminhar  pulo  raio_medo  pânico  curioso  voa    pula_sempre
    "robot":    dict(walk=95, jump=640, fear=230, panic=1.5, curious=0.25, fly=False, hop=False),
    "slime":    dict(walk=70, jump=560, fear=180, panic=1.2, curious=0.70, fly=False, hop=True),
    "chick":    dict(walk=150, jump=470, fear=320, panic=1.9, curious=0.45, fly=False, hop=False),
    "alien":    dict(walk=80, jump=760, fear=210, panic=1.6, curious=0.30, fly=True, hop=False),
    "ghost":    dict(walk=75, jump=0, fear=280, panic=1.4, curious=0.35, fly=True, hop=False),
    "skeleton": dict(walk=90, jump=600, fear=170, panic=1.3, curious=0.20, fly=False, hop=False),
    "ninja":    dict(walk=140, jump=980, fear=110, panic=1.1, curious=0.15, fly=False, hop=False),
    "zombie":   dict(walk=55, jump=0, fear=0, panic=1.0, curious=0.0, fly=False, hop=False, hostile=True),
    "zombie_runner": dict(walk=125, jump=420, fear=0, panic=1.0, curious=0.0, fly=False, hop=False, hostile=True),
    "zombie_brute": dict(walk=40, jump=0, fear=0, panic=1.0, curious=0.0, fly=False, hop=False, hostile=True),
}


@dataclass
class Env:
    w: float
    h: float
    threats: List[Tuple[float, float, float, float]] = field(default_factory=list)   # x, y, raio, velocidade
    interest: List[Tuple[float, float]] = field(default_factory=list)                # mãos/cursor (para olhar/seguir)
    target: Optional[Tuple[float, float]] = None                                     # alvo dos hostis (base)
    immortal: bool = True
    speed_mult: float = 1.0
    attack_range: float = 80.0


class Brain:
    def __init__(self, kind: str, rng=random):
        self.kind = kind
        self.p = PERSONALITY.get(kind, PERSONALITY["robot"])
        self.rng = rng
        self.mode = "idle"
        self.dir = rng.choice((-1, 1))
        self.timer = rng.uniform(0.3, 1.5)
        self.fear = 0.0
        self.stun_t = 0.0
        self.jump_cd = rng.uniform(0.5, 2.0)
        self.t = rng.uniform(0, 10)
        self.look = (0.0, 0.0)
        self.face = self.dir
        self.attacking = False
        self.expr = "normal"
        self.walk_phase = 0.0
        self.squash = 0.0
        self.speed_mult = 1.0
        self.dead = False
        self.events: List[str] = []

    @property
    def hostile(self) -> bool:
        return bool(self.p.get("hostile"))

    def stun(self, t: float):
        self.stun_t = max(self.stun_t, t)

    def think(self, b, dt: float, env: Env) -> List[str]:
        """Atualiza a velocidade/estado do corpo `b`. Retorna eventos: 'hurt', 'die', 'jump', 'land'."""
        ev: List[str] = []
        self.t += dt
        p = self.p
        # dano por impacto (a física grava a maior velocidade de impacto do frame em b.hit_speed)
        hs = getattr(b, "hit_speed", 0.0)
        b.hit_speed = 0.0
        if hs > 650 and not b.held_by:
            self.stun(min(2.4, hs / 900.0))
            if not (env.immortal and not self.hostile):
                b.hp -= (hs - 500) / 28.0
                ev.append("hurt")
            else:
                ev.append("hurt")
        if b.hp <= 0 and not (env.immortal and not self.hostile):
            self.dead = True
            ev.append("die")
            self.expr = "dead"
            return ev
        if b.hp <= 0:
            b.hp = 1

        self.squash *= math.exp(-dt * 10)
        # olhar para o interesse mais próximo
        if env.interest:
            ix, iy = min(env.interest, key=lambda q: (q[0] - b.x) ** 2 + (q[1] - b.y) ** 2)
            d = math.hypot(ix - b.x, iy - b.y) or 1.0
            self.look = ((ix - b.x) / d, (iy - b.y) / d)
        else:
            self.look = (self.dir * 0.6, 0.0)

        if b.held_by:
            self.mode, self.expr = "held", "held"
            self.fear = 1.0
            return ev
        if self.stun_t > 0:
            self.stun_t -= dt
            self.mode, self.expr = "stunned", "dizzy"
            if b.grounded:
                b.vx *= math.exp(-dt * 5)
                self._upright(b, dt, slow=True)
            return ev

        grounded = b.grounded
        flying = p["fly"]

        # ------------------------------------------------ medo
        near_d, near = 1e9, None
        for (tx, ty, tr, ts) in env.threats:
            d = math.hypot(tx - b.x, ty - b.y) - tr
            weight = 1.0 + min(2.0, ts / 700.0)         # coisas rápidas assustam de mais longe
            if d / weight < near_d:
                near_d, near = d / weight, (tx, ty)
        fear_r = p["fear"]
        if near is not None and near_d < fear_r:
            self.fear = min(1.0, self.fear + dt * 4.0)
        else:
            self.fear = max(0.0, self.fear - dt * 0.8)
        self.expr = "scared" if self.fear > 0.35 else "normal"

        want_vx = 0.0
        self.attacking = False
        if self.hostile and env.target is not None:
            dx = env.target[0] - b.x
            self.dir = 1 if dx > 0 else -1
            if abs(dx) < env.attack_range:
                self.attacking, want_vx, self.mode, self.expr = True, 0.0, "attack", "angry"
            else:
                want_vx = self.dir * p["walk"] * env.speed_mult
                self.mode, self.expr = "chase", "angry"
                if p["jump"] and grounded and self.jump_cd <= 0 and self.rng.random() < dt * 0.6:
                    b.vy = -p["jump"]
                    self.jump_cd = 2.0
                    ev.append("jump")
        elif self.fear > 0.35 and near is not None:
            self.mode = "flee"
            self.dir = -1 if near[0] > b.x else 1
            want_vx = self.dir * p["walk"] * p["panic"]
            if p["jump"] and grounded and self.jump_cd <= 0 and near_d < fear_r * 0.5:
                b.vy = -p["jump"] * 0.9
                self.jump_cd = 0.9
                ev.append("jump")
        else:
            self.timer -= dt
            if self.timer <= 0:
                r = self.rng.random()
                if env.interest and r < p["curious"]:
                    ix, iy = min(env.interest, key=lambda q: abs(q[0] - b.x))
                    self.dir = 1 if ix > b.x else -1
                    self.mode, self.timer = "walk", self.rng.uniform(0.8, 2.0)
                elif r < 0.55:
                    self.mode, self.timer = "walk", self.rng.uniform(1.0, 3.0)
                    self.dir = self.rng.choice((-1, 1))
                else:
                    self.mode, self.timer = "idle", self.rng.uniform(0.6, 2.2)
            if self.mode == "walk":
                want_vx = self.dir * p["walk"] * 0.7
            if p["hop"] and grounded and self.jump_cd <= 0:
                b.vy = -p["jump"] * self.rng.uniform(0.6, 1.0)
                if self.mode != "idle":
                    b.vx = self.dir * p["walk"] * 1.6
                self.jump_cd = self.rng.uniform(0.5, 1.3)
                ev.append("jump")
            elif p["jump"] and grounded and self.jump_cd <= 0 and self.rng.random() < dt * 0.25:
                b.vy = -p["jump"] * 0.8
                self.jump_cd = self.rng.uniform(1.5, 3.5)
                ev.append("jump")
        self.jump_cd -= dt

        # bordas da tela
        if b.x < 60 and self.dir < 0 or b.x > env.w - 60 and self.dir > 0:
            if not self.hostile:
                self.dir *= -1
                want_vx = -want_vx
        self.face = self.dir if self.dir else self.face

        if flying:
            hover = env.h - 190 - 50 * math.sin(self.t * 1.7 + b.id)
            if self.fear > 0.35 and near is not None:
                hover = max(120.0, min(env.h - 120.0, b.y + (-1 if near[1] > b.y else 1) * 200))
            b.vy += (hover - b.y) * 2.4 * dt - b.vy * 1.8 * dt
            b.vx += (want_vx - b.vx) * min(1.0, dt * 2.5)
            b.angle *= math.exp(-dt * 6)
            b.w *= math.exp(-dt * 6)
        elif grounded:
            b.vx += (want_vx - b.vx) * min(1.0, dt * 9.0)
            self._upright(b, dt)
            self.walk_phase += abs(b.vx) * dt * 0.075
            if not getattr(self, "_was_grounded", True):
                self.squash = 0.35
                ev.append("land")
        else:
            b.vx += (want_vx - b.vx) * min(1.0, dt * 0.8)
        self._was_grounded = grounded
        return ev

    @staticmethod
    def _upright(b, dt, slow=False):
        target = round(b.angle / TAU) * TAU
        b.angle += (target - b.angle) * min(1.0, dt * (3.0 if slow else 10.0))
        b.w *= math.exp(-dt * 12)
