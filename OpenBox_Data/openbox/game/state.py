"""Estado de jogo (pontos, combo, power-ups, conquistas) — sem dependência de pygame."""
from __future__ import annotations

MODES = ("sandbox", "practice", "tutorial", "survival")
MODE_LABELS = {"sandbox": "SANDBOX", "practice": "PRACTICE", "tutorial": "TUTORIAL", "survival": "SOBREVIVÊNCIA"}

POWERUP_TYPES = ("slowmo", "freeze", "magnet", "big")
POWERUP_NAMES = {"slowmo": "SLOW MO", "freeze": "FREEZE", "magnet": "MAGNET", "big": "BIG MODE"}
POWERUP_DURATION = {"slowmo": 6.0, "freeze": 4.0, "magnet": 6.0, "big": 8.0}

ACHIEVEMENTS = {
    "first_grab": ("Primeira Pegada", "Agarre um objeto"),
    "first_throw": ("Arremessador", "Arremesse um objeto"),
    "bullseye": ("Na Mosca", "Destrua um alvo"),
    "combo10": ("Combo x10", "Alcance combo 10"),
    "combo50": ("Combo x50", "Alcance combo 50"),
    "spawn10": ("Criador", "Crie 10 objetos"),
    "powerup5": ("Colecionador", "Colete 5 power-ups"),
    "kills25": ("Destruidor", "Destrua 25 objetos"),
    "tutorial": ("Aluno Exemplar", "Conclua o tutorial"),
    "first_kill": ("Primeiro Sangue", "Abata um zumbi"),
    "headshot": ("Na Cabeça", "Acerte um tiro na cabeça"),
    "wave5": ("Sobrevivente", "Chegue à onda 5"),
    "wave10": ("Lenda Viva", "Chegue à onda 10"),
    "hat": ("Estiloso", "Use um chapéu"),
    "bot_throw": ("Arremesso de Bot", "Arremesse uma criatura"),
}
COMBO_WINDOW = 2.5


class GameState:
    def __init__(self, cfg, on_unlock=None, on_milestone=None):
        self.cfg = cfg
        self.on_unlock = on_unlock
        self.on_milestone = on_milestone
        self.mode = "sandbox"
        self.timers = {k: 0.0 for k in POWERUP_TYPES}
        self.reset_run()

    def reset_run(self):
        self.score = 0
        self.combo = 0
        self.combo_timer = 0.0
        self.max_combo = 0
        self.spawned = self.destroyed = self.grabs = self.throws = self.powerups = 0
        self.wave = 1
        self.wave_timer = 0.0
        self.elapsed = 0.0
        for k in self.timers:
            self.timers[k] = 0.0

    # ---- recorde por modo ----
    @property
    def best(self) -> int:
        return int(self.cfg.highscores.get(self.mode, 0))

    def _bump_best(self):
        if self.score > self.best:
            self.cfg.highscores[self.mode] = int(self.score)

    # ---- pontuação ----
    def add_score(self, base: int) -> int:
        if self.mode in ("tutorial",):
            return 0
        gained = int(base * max(1, self.combo))
        self.score += gained
        self._bump_best()
        return gained

    def bump_combo(self, amount: int = 1):
        self.combo += amount
        self.max_combo = max(self.max_combo, self.combo)
        self.combo_timer = COMBO_WINDOW
        if self.combo in (10, 25, 50, 100) and self.on_milestone:
            self.on_milestone(self.combo)
        if self.combo >= 10:
            self.unlock("combo10")
        if self.combo >= 50:
            self.unlock("combo50")

    def unlock(self, key: str):
        if key in ACHIEVEMENTS and key not in self.cfg.achievements:
            self.cfg.achievements.append(key)
            if self.on_unlock:
                self.on_unlock(ACHIEVEMENTS[key][0])

    # ---- tempo ----
    def update(self, dt: float):
        self.elapsed += dt
        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 0
        for k in self.timers:
            self.timers[k] = max(0.0, self.timers[k] - dt)

    def activate(self, kind: str):
        self.timers[kind] = POWERUP_DURATION[kind]

    def active(self, kind: str) -> bool:
        return self.timers[kind] > 0.0

    @property
    def time_factor(self) -> float:
        return 0.35 if self.active("slowmo") else 1.0
