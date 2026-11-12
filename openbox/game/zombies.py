"""Zumbis e diretor de ondas (modo Sobrevivência) — lógica pura, sem pygame."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class ZType:
    id: str
    name: str
    hp: float
    speed: float
    dps: float      # dano por segundo na base
    cost: int       # custo no orçamento da onda
    value: int      # moedas ao morrer
    item: str       # id do item/criatura


ZTYPES = {z.id: z for z in [
    ZType("walker", "Zumbi", 30, 55, 8, 1, 10, "zombie"),
    ZType("runner", "Corredor", 20, 125, 6, 2, 15, "zombie_runner"),
    ZType("brute", "Brutamontes", 120, 40, 20, 5, 40, "zombie_brute"),
    ZType("boss", "Tanque", 650, 34, 45, 25, 250, "zombie_brute"),
]}


class WaveDirector:
    """Estados: break (intervalo) → spawning (entrando) → fighting (aguarda abate) → break..."""

    BREAK = 7.0

    def __init__(self, diff: dict, rng=random):
        self.diff, self.rng = diff, rng
        self.wave = 0
        self.state = "break"
        self.timer = 4.0
        self.queue: List[Tuple[str, int]] = []
        self.spawn_t = 0.0
        self.total = 0

    def budget(self, n: int) -> int:
        return int((6 + 4 * n) * self.diff["count"])

    def build(self, n: int) -> List[Tuple[str, int]]:
        pts, q = self.budget(n), []
        if n % 5 == 0:
            q.append(("boss", self.rng.choice((-1, 1))))
            pts = max(0, pts - ZTYPES["boss"].cost)
        while pts > 0:
            opts = ["walker"]
            if n >= 2 and pts >= 2:
                opts += ["runner"] * (1 + n // 3)
            if n >= 3 and pts >= 5:
                opts += ["brute"] * (1 + n // 5)
            z = self.rng.choice(opts)
            q.append((z, self.rng.choice((-1, 1))))
            pts -= ZTYPES[z].cost
        self.rng.shuffle(q)
        return q

    def hp_scale(self) -> float:
        return self.diff["hp"] * (1.0 + 0.06 * max(0, self.wave - 1))

    def start_wave(self):
        self.wave += 1
        self.queue = self.build(self.wave)
        self.total = len(self.queue)
        self.state, self.spawn_t = "spawning", 0.5

    def update(self, dt: float, alive: int) -> List[Tuple[str, int]]:
        """Retorna ordens de spawn [(tipo, lado)] neste passo."""
        out: List[Tuple[str, int]] = []
        if self.state == "break":
            self.timer -= dt
            if self.timer <= 0:
                self.start_wave()
        elif self.state == "spawning":
            self.spawn_t -= dt
            if self.spawn_t <= 0 and self.queue:
                out.append(self.queue.pop(0))
                self.spawn_t = max(0.35, 1.4 - 0.05 * self.wave)
            if not self.queue:
                self.state = "fighting"
        elif self.state == "fighting":
            if alive == 0:
                self.state, self.timer = "break", self.BREAK
        return out

    def remaining(self, alive: int) -> int:
        return len(self.queue) + alive

    @property
    def clear_bonus(self) -> int:
        return 50 + 25 * self.wave
