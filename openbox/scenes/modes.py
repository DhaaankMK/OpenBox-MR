"""Regras dos modos de jogo: Sandbox, Practice, Tutorial e Sobrevivência (zumbis + armas)."""
from __future__ import annotations

import math
import random

import pygame

from .. import theme as T
from ..game import items as I
from ..game.creatures import PERSONALITY
from ..game.state import POWERUP_NAMES, POWERUP_TYPES
from ..game.tutorial import STEPS, Tutorial
from ..game.weapons import WEAPON_ORDER, WEAPONS
from ..game.zombies import ZTYPES, WaveDirector
from ..ui import draw, icons
from ..ui.anim import ease_out_back
from ..ui.widgets import Button, Panel, Selector

POWERUP_COLORS = {"slowmo": (100, 200, 255), "freeze": (150, 220, 255), "magnet": (255, 100, 200), "big": (255, 200, 50)}
POWERUP_ICONS = {"slowmo": "clock", "freeze": "orb", "magnet": "bolt", "big": "up"}


class Mode:
    name = ""
    sub = ""
    allow_spawn = True
    allow_gravity_toggle = True
    show_inspector = False
    show_help = True

    def __init__(self, scene):
        self.s = scene
        self.ctx = scene.ctx
        self.widgets: list = []

    # ---- ciclo ----
    def build(self, ui): ...
    def widget_visible(self, w): return True
    def enter(self): ...
    def exit(self): ...
    def update(self, dt): ...
    def draw_back(self, surf): ...
    def draw_world_overlay(self, surf): ...
    def draw_hud(self, surf): ...
    def on_event(self, name, **kw): ...
    def on_kill(self, b, source="player", head=False): ...
    def on_destroy(self, b, by_player=True): ...

    # ---- ganchos de regras ----
    def env_target(self, b):
        if b.brain is not None and b.brain.hostile:       # zumbis fora da Sobrevivência perseguem a mão/cursor
            ptrs = self.ctx.input.pointers
            if ptrs:
                return (ptrs[0].x, ptrs[0].y)
        return None

    def zombie_speed(self, b): return 1.0
    def player_damage_mult(self): return 1.0
    def can_equip(self, wid): return True
    def dmg_mult(self): return 1.0
    def rate_mult(self): return 1.0
    def default_weapon(self): return "pistol"

    # ---- utilidades ----
    def reach_points(self):
        pts = []
        for hv in self.ctx.hands.visible():
            if not hv.stale and hv.disp is not None:
                pts += [tuple(hv.palm), tuple(hv.mid), tuple(hv.index_tip)]
        m = self.ctx.input.mouse
        if m in self.ctx.input.pointers:
            pts.append((m.x, m.y))
        return pts

    def draw_score(self, surf, extra=""):
        ctx, gs = self.ctx, self.s.gs
        r = pygame.Rect(ctx.W // 2 - 190, 78, 380, 70)
        draw.glass(surf, r, 16, accent=T.CYAN)
        draw.text(surf, "PONTOS", (r.x + 18, r.y + 10), 13, T.MUTED, True)
        draw.text(surf, f"{gs.score:,}".replace(",", "."), (r.x + 18, r.y + 26), 34, T.TEXT, True)
        draw.text(surf, "MELHOR", (r.right - 18, r.y + 10), 13, T.MUTED, True, "tr")
        draw.text(surf, f"{gs.best:,}".replace(",", "."), (r.right - 18, r.y + 26), 22, T.AMBER, True, "tr")
        if gs.combo > 1:
            col = T.AMBER if gs.combo < 10 else T.RED
            draw.text(surf, f"COMBO x{gs.combo}", (r.centerx + 10, r.y + 14), 18, col, True, "c")
            draw.rrect(surf, (r.centerx - 55, r.y + 34, 130, 6), (255, 255, 255, 40), 3)
            draw.rrect(surf, (r.centerx - 55, r.y + 34, max(3, int(130 * gs.combo_timer / 2.5)), 6), (*col, 255), 3)
        if extra:
            draw.text(surf, extra, (r.centerx, r.bottom - 12), 13, T.MAGENTA, True, "c")
        x = ctx.W // 2 - 190
        for kind in POWERUP_TYPES:
            t = gs.timers[kind]
            if t > 0:
                s = f"{POWERUP_NAMES[kind]} {t:.1f}s"
                w = draw.text_width(s, 14, True) + 34
                pill = pygame.Rect(x, 156, w, 28)
                draw.rrect(surf, pill, (0, 0, 0, 120), 14)
                pygame.draw.circle(surf, POWERUP_COLORS[kind], (pill.x + 14, pill.centery), 5)
                draw.text(surf, s, (pill.x + 26, pill.centery), 14, T.TEXT, True, "ml")
                x += w + 8

    def score_for_destroy(self, b, by_player):
        s, gs = self.s, self.s.gs
        if not by_player:
            return
        if "target" in b.tags:
            gs.unlock("bullseye")
        gained = gs.add_score(50 if "target" in b.tags else 20)
        if gained:
            self.ctx.fx.popup(b.x, b.y, f"+{gained}", (255, 255, 100), 30)
        gs.bump_combo()
        if gs.destroyed >= 25:
            gs.unlock("kills25")


# ====================================================================== Sandbox
class SandboxMode(Mode):
    name = "sandbox"
    sub = "Crie, agarre, arremesse, atire e destrua — tudo é permitido"
    show_inspector = True

    def enter(self):
        s = self.s
        W, H = self.ctx.W, self.ctx.H
        for kind, dx in (("orb", -240), ("crate", -80), ("robot", 100), ("slime", 260)):
            s.spawn_kind(kind, at=(W / 2 + dx, H / 2), quiet=True)
        self.ctx.toast("Tab: catálogo · gesto ROCK (1 s) ou botão direito: menu radial", "info")

    def on_destroy(self, b, by_player=True):
        self.score_for_destroy(b, by_player)

    def on_kill(self, b, source="player", head=False):
        gs = self.s.gs
        gs.add_score(30)
        gs.bump_combo()

    def draw_hud(self, surf):
        self.draw_score(surf)


# ====================================================================== Practice
class PracticeMode(Mode):
    name = "practice"
    sub = "Treino de pontaria: acerte os alvos com arremessos, tiros e punhos"

    VARIANTS = ["Pontaria", "Ondas"]

    def __init__(self, scene):
        super().__init__(scene)
        self.variant = 0
        self.timer = 0.0
        self.wave = 1
        self.powerups: list = []
        self.pu_timer = 0.0

    def build(self, ui):
        W = self.ctx.W
        self.widgets = [
            ui.add(Panel((W - 316, 80, 300, 176), "Practice", T.MAGENTA, radius=18)),
            ui.add(Selector((W - 306, 118, 280, 46), "Variante", self.VARIANTS, lambda: self.variant, self._set_variant)),
        ]

    def _set_variant(self, i):
        self.variant = i
        self.s.restart()

    def enter(self):
        self.timer, self.wave, self.pu_timer = 1.0, 1, 0.0
        self.powerups.clear()
        self.s.equip("pistol")
        self.s.gs.wave = 1

    def update(self, dt):
        s, gs = self.s, self.s.gs
        targets = [b for b in s.world.bodies if "target" in b.tags and not b.dead]
        W, H = self.ctx.W, self.ctx.H
        if self.variant == 0:
            self.timer -= dt
            if self.timer <= 0:
                if len(targets) < 10:
                    s.spawn_kind("target", at=(random.randint(240, W - 380), random.randint(160, H - 260)))
                self.timer = 2.5
        elif not targets:
            self.timer -= dt
            if self.timer <= 0:
                for _ in range(min(self.wave + 1, 8)):
                    b = s.spawn_kind("target", at=(random.randint(240, W - 380), random.randint(120, H - 300)))
                    b.hp = b.max_hp = 2 + self.wave // 2
                self.ctx.toast(f"ONDA {self.wave}", "warn")
                self.wave += 1
                gs.wave = self.wave
                self.timer = 2.0
        self.pu_timer += dt
        if self.pu_timer > 12 and len(self.powerups) < 3:
            self.pu_timer = 0.0
            self.powerups.append(dict(x=random.randint(200, W - 380), y=random.randint(160, H - 200), kind=random.choice(POWERUP_TYPES), t=0.0, life=12.0))
        pts = self.reach_points()
        for p in self.powerups[:]:
            p["t"] += dt
            p["life"] -= dt
            py = p["y"] + math.sin(p["t"] * 3) * 10
            if p["life"] <= 0:
                self.powerups.remove(p)
            elif any(math.hypot(x - p["x"], y - py) < 55 for x, y in pts):
                gs.activate(p["kind"])
                gs.powerups += 1
                gs.add_score(25)
                col = POWERUP_COLORS[p["kind"]]
                self.ctx.audio.play("power")
                self.ctx.fx.popup(p["x"], py - 30, POWERUP_NAMES[p["kind"]], col, 26)
                self.ctx.fx.burst(p["x"], py, col, 26, 380, 4)
                if gs.powerups >= 5:
                    gs.unlock("powerup5")
                self.powerups.remove(p)
        if gs.active("freeze"):
            k = 0.9 ** (dt * 60)
            for b in s.world.bodies:
                if not b.held_by:
                    b.vx *= k
                    b.vy *= k
        if gs.active("magnet"):
            for hv in self.ctx.hands.visible():
                if hv.stale or hv.disp is None:
                    continue
                for b in s.world.bodies:
                    if b.held_by:
                        continue
                    dx, dy = hv.palm[0] - b.x, hv.palm[1] - b.y
                    d = math.hypot(dx, dy) + 1.0
                    if d < 350:
                        b.vx += dx / d * 800 * dt
                        b.vy += dy / d * 800 * dt

    def on_destroy(self, b, by_player=True):
        self.score_for_destroy(b, by_player)

    def on_kill(self, b, source="player", head=False):
        self.s.gs.add_score(30)

    def draw_world_overlay(self, surf):
        for p in self.powerups:
            col = POWERUP_COLORS[p["kind"]]
            y = p["y"] + math.sin(p["t"] * 3) * 10
            pulse = 1.0 + math.sin(p["t"] * 6) * 0.12
            draw.glow(surf, (p["x"], y), 64 * pulse, col, 0.7)
            draw.ring(surf, (p["x"], y), 26 * pulse, col, 3, 255)
            icons.draw(POWERUP_ICONS[p["kind"]], surf, p["x"], y, 12, (255, 255, 255), 2)

    def draw_hud(self, surf):
        self.draw_score(surf, f"ONDA {max(1, self.wave - 1)}" if self.variant == 1 else "")
        r = self.widgets[0].rect
        txt = ("Um alvo novo a cada 2,5 s. Acerte com arremessos, tiros (dedo-pistola) ou esmague com o punho." if self.variant == 0
               else "Ondas de alvos cada vez mais resistentes. Elimine todos para a próxima.")
        for i, line in enumerate(draw.wrap(txt, 14, r.w - 24)):
            draw.text(surf, line, (r.x + 14, r.y + 74 + i * 18), 14, T.MUTED)


# ====================================================================== Tutorial
class TutorialMode(Mode):
    name = "tutorial"
    sub = "Aprenda os gestos passo a passo"
    show_help = False

    def build(self, ui):
        self.panel = ui.add(Panel((108, 80, 410, 430), None, T.GREEN, radius=18))
        self.b_skip = ui.add(Button((120, 520, 190, 42), "Pular passo", self._skip, icon="right", size=16))
        self.b_exit = ui.add(Button((320, 520, 190, 42), "Sair", lambda: self.ctx.scenes.go("hub"), icon="home", size=16))
        self.widgets = [self.panel, self.b_skip, self.b_exit]
        self.pulse = 0.0

    def _skip(self):
        t = self.s.tut
        if t and not t.finished:
            t.skip()

    def enter(self):
        s = self.s
        s.tut = Tutorial(on_step=self._on_step, on_finish=self._on_finish)
        s.weapon_id, s.wstate = None, None
        self.pulse = 0.0
        self.respawn_t = 0.0
        self._fill()

    def exit(self):
        self.s.tut = None

    def _fill(self):
        s, W, H = self.s, self.ctx.W, self.ctx.H
        have = {b.kind for b in s.world.bodies if not b.dead}
        if "orb" not in have:
            s.spawn_kind("orb", at=(W * 0.66, H * 0.55), quiet=True)
        if "crate" not in have:
            s.spawn_kind("crate", at=(W * 0.80, H * 0.60), quiet=True)
        if "target" not in have:
            b = s.spawn_kind("target", at=(W * 0.72, H * 0.28), quiet=True, vel=(0, 0))
            b.gscale = 0.0

    def _on_step(self, step):
        ctx = self.ctx
        ctx.audio.play("sucesso", 0.8)
        ctx.fx.burst(310, 140, T.GREEN, 28, 420, 4, 0.9)
        ctx.fx.popup(310, 120, step.title, T.GREEN, 24)
        self.pulse = 1.0
        nxt = STEPS[min(self.s.tut.idx + 1, len(STEPS) - 1)]
        if nxt.id == "shoot":
            self.s.equip("pistol")
            self._fill()
        if nxt.id == "hat" and not self.ctx.faces.visible():
            self.ctx.toast("Mostre o rosto para ver o chapéu (ou pule o passo)", "info")

    def _on_finish(self):
        cfg = self.ctx.cfg
        cfg.tutorial_done = True
        self.s.gs.unlock("tutorial")
        for col in (T.GREEN, T.CYAN, T.AMBER, T.MAGENTA):
            self.ctx.fx.burst(self.ctx.W / 2, self.ctx.H / 2, col, 36, 520, 5, 1.2)
        self.ctx.toast("Tutorial concluído!", "ok")
        cfg.save()

    def update(self, dt):
        s, t = self.s, self.s.tut
        self.pulse = max(0.0, self.pulse - dt * 2.0)
        self.respawn_t += dt
        if self.respawn_t > 1.5:
            self.respawn_t = 0.0
            self._fill()
        if t is None:
            return
        if t.step.id == "push":
            fast = [c for c in self.ctx.hands.colliders() if math.hypot(c[3], c[4]) > 300]
            for b in s.world.bodies:
                if not b.held_by and math.hypot(b.vx, b.vy) > 220 and any(math.hypot(b.x - c[0], b.y - c[1]) < b.r + c[2] + 40 for c in fast):
                    s.emit("push")
                    break
        if t.step.id == "shoot" and s.weapon_id is None:
            s.equip("pistol")
        if t.step.id == "hat" and not self.ctx.cfg.face_tracking:
            t.skip_optional()
        self.b_skip.visible = not t.finished and self.s.mode is self
        if t.finished:
            self.b_skip.label = ""

    def widget_visible(self, w):
        t = self.s.tut
        if w is self.b_skip:
            return t is not None and not t.finished
        return True

    def draw_hud(self, surf):
        t = self.s.tut
        if t is None:
            return
        r = self.panel.rect
        st = t.step
        draw.text(surf, f"PASSO {min(t.idx + 1, len(STEPS))} DE {len(STEPS)}", (r.x + 22, r.y + 18), 13, T.GREEN, True)
        icons.draw(st.icon, surf, r.right - 44, r.y + 40, 18 + 4 * self.pulse, T.GREEN, 3)
        draw.glow(surf, (r.right - 44, r.y + 40), 52 + 30 * self.pulse, T.GREEN, 0.25 + 0.5 * self.pulse)
        draw.text(surf, st.title, (r.x + 22, r.y + 38), 28, T.TEXT, True)
        for i, line in enumerate(draw.wrap(st.text, 17, r.w - 44)):
            draw.text(surf, line, (r.x + 22, r.y + 82 + i * 24), 17, T.MUTED)
        if st.count > 1 and not t.finished:
            draw.text(surf, f"{t.progress}/{st.count}", (r.x + 22, r.y + 160), 16, T.AMBER, True)
        draw.rrect(surf, (r.x + 22, r.y + 186, r.w - 44, 6), (255, 255, 255, 36), 3)
        draw.rrect(surf, (r.x + 22, r.y + 186, max(4, int((r.w - 44) * t.fraction)), 6), (*T.GREEN, 255), 3)
        for i, s_ in enumerate(STEPS[:-1]):
            done = s_.id in t.done_ids
            cur = i == t.idx
            y = r.y + 206 + i * 19
            pygame.draw.circle(surf, T.GREEN if done else (T.AMBER if cur else T.DIM), (r.x + 30, y + 8), 5, 0 if done or cur else 2)
            draw.text(surf, s_.title + ("  (opcional)" if s_.optional else ""), (r.x + 46, y), 14, T.TEXT if cur else (T.MUTED if done else T.DIM), cur)
        if t.finished:
            draw.text(surf, "Concluído! Volte ao menu e escolha um modo.", (r.centerx, r.bottom - 22), 15, T.GREEN, True, "c")


# ====================================================================== Sobrevivência
class ShopButton(Button):
    def __init__(self, rect, label_fn, on_click, enabled_fn, icon=None):
        super().__init__(rect, "", on_click, icon=icon, size=15)
        self.label_fn, self.enabled_fn = label_fn, enabled_fn

    def tick(self, dt):
        self.label = self.label_fn()
        self.enabled = self.enabled_fn()
        super().tick(dt)


class SurvivalMode(Mode):
    name = "survival"
    sub = "Proteja o reator: atire, arremesse e esmague os zumbis"
    allow_spawn = False
    allow_gravity_toggle = False

    def build(self, ui):
        W, H = self.ctx.W, self.ctx.H
        px = W - 316
        self.shop = ui.add(Panel((px, 80, 300, 560), None, T.AMBER, radius=18))
        self.widgets = [self.shop]
        y = 124
        self.wbtns = {}
        for wid in WEAPON_ORDER:
            w = WEAPONS[wid]
            b = ui.add(ShopButton((px + 10, y, 280, 44), (lambda wid=wid: self._weapon_label(wid)), (lambda wid=wid: self._buy_or_equip(wid)),
                                  (lambda wid=wid: True), icon="bolt"))
            self.widgets.append(b)
            y += 50
        y += 12
        self.widgets += [
            ui.add(ShopButton((px + 10, y, 280, 44), lambda: f"Dano +20%  (Nv {self.dmg_lvl})  ·  {self._cost('dmg')}", self._up_dmg, lambda: self.coins >= self._cost("dmg"), icon="up")),
            ui.add(ShopButton((px + 10, y + 50, 280, 44), lambda: f"Cadência +15%  (Nv {self.rate_lvl})  ·  {self._cost('rate')}", self._up_rate, lambda: self.coins >= self._cost("rate"), icon="up")),
            ui.add(ShopButton((px + 10, y + 100, 280, 44), lambda: f"Reparar reator +40  ·  100", self._repair, lambda: self.coins >= 100 and self.base_hp < self.base_max, icon="heart")),
        ]
        self.b_retry = ui.add(Button((W // 2 - 160, 440, 320, 52), "Jogar de novo", self.s.restart, icon="refresh", style="primary"))
        self.b_menu = ui.add(Button((W // 2 - 160, 504, 320, 52), "Menu principal", lambda: self.ctx.scenes.go("hub"), icon="home"))
        self.widgets += [self.b_retry, self.b_menu]
        self._init_state()

    def _init_state(self):
        self.base_max = 100.0
        self.base_hp = 100.0
        self.coins = 0
        self.kills = 0
        self.score = 0
        self.owned = {"pistol"}
        self.dmg_lvl = self.rate_lvl = 0
        self.over = False
        self.director = None
        self.flash_t = 0.0
        self.groan_t = 3.0
        self.banner = ("", 0.0)

    def widget_visible(self, w):
        if w in (self.b_retry, self.b_menu):
            return self.over
        return not self.over

    # ---- loja ----
    def _cost(self, what):
        return int(150 * (1 + (self.dmg_lvl if what == "dmg" else self.rate_lvl) * 0.8))

    def _weapon_label(self, wid):
        w = WEAPONS[wid]
        if wid not in self.owned:
            return f"{w.name}  ·  {w.cost}"
        return f"{w.name}  ·  " + ("EQUIPADA" if self.s.weapon_id == wid else "equipar")

    def _buy_or_equip(self, wid):
        w = WEAPONS[wid]
        if wid not in self.owned:
            if self.coins < w.cost:
                self.ctx.toast(f"Faltam {w.cost - self.coins} moedas", "warn")
                self.ctx.audio.play("erro", 0.7)
                return
            self.coins -= w.cost
            self.owned.add(wid)
            self.ctx.audio.play("power")
        self.s.equip(wid)

    def _refresh_weapon(self):
        if self.s.wstate:
            self.s.wstate.dmg_mult, self.s.wstate.rate_mult = self.dmg_mult(), self.rate_mult()

    def _up_dmg(self):
        c = self._cost("dmg")
        if self.coins >= c:
            self.coins -= c
            self.dmg_lvl += 1
            self._refresh_weapon()
            self.ctx.audio.play("power")

    def _up_rate(self):
        c = self._cost("rate")
        if self.coins >= c:
            self.coins -= c
            self.rate_lvl += 1
            self._refresh_weapon()
            self.ctx.audio.play("power")

    def _repair(self):
        if self.coins >= 100 and self.base_hp < self.base_max:
            self.coins -= 100
            self.base_hp = min(self.base_max, self.base_hp + 40)
            self.ctx.audio.play("power")

    # ---- regras ----
    def can_equip(self, wid):
        if wid in self.owned:
            return True
        self.ctx.toast("Compre esta arma na loja", "warn")
        return False

    def dmg_mult(self): return 1.0 + 0.2 * self.dmg_lvl
    def rate_mult(self): return 1.0 + 0.15 * self.dmg_lvl * 0 + 0.15 * self.rate_lvl
    def default_weapon(self): return [w for w in WEAPON_ORDER if w in self.owned][-1]

    def player_damage_mult(self):
        return 1.0

    def env_target(self, b):
        return (self.ctx.W / 2.0, self.ctx.H - 40.0) if b.brain is not None and b.brain.hostile else None

    def zombie_speed(self, b):
        z = ZTYPES.get(b.extra.get("z", "walker"), ZTYPES["walker"])
        base = PERSONALITY.get(b.kind, PERSONALITY["zombie"])["walk"]
        wave = self.director.wave if self.director else 1
        return z.speed / base * (1.0 + 0.012 * wave)

    def enter(self):
        s, cfg = self.s, self.ctx.cfg
        self._old_gravity = cfg.gravity
        if cfg.gravity < 800:
            cfg.gravity = 1400.0
        self._init_state()
        self.director = WaveDirector(cfg.diff)
        s.equip("pistol")
        s.help = True
        s.help_t = 0.0
        self.ctx.toast("Segure o reator! Dedo-pistola: levante o polegar e abaixe para atirar", "info")

    def exit(self):
        self.ctx.cfg.gravity = getattr(self, "_old_gravity", self.ctx.cfg.gravity)

    def spawn_zombie(self, zid, side):
        s, W, H = self.s, self.ctx.W, self.ctx.H
        z = ZTYPES[zid]
        item = I.ITEMS[z.item]
        r = 58 if zid == "boss" else item.r
        b = s.spawn_item(item, at=(46 if side < 0 else W - 46, H - r - 2), vel=(0, 0), radius=r, quiet=True)
        b.hp = b.max_hp = z.hp * self.director.hp_scale()
        b.extra["z"] = zid
        b.brain.face = 1 if side < 0 else -1
        if zid == "boss":
            self.ctx.toast("CHEFE: TANQUE!", "error")
            self.ctx.shake = 14
            self.ctx.audio.play("groan", 1.0)
        return b

    def update(self, dt):
        s, ctx, cfg = self.s, self.ctx, self.ctx.cfg
        if self.over:
            return
        d = self.director
        prev_state, prev_wave = d.state, d.wave
        alive = len([b for b in s.world.bodies if b.brain is not None and b.brain.hostile and not b.dead])
        for zid, side in d.update(dt, alive):
            self.spawn_zombie(zid, side)
        if d.wave != prev_wave:
            self.banner = (f"ONDA {d.wave}", 2.2)
            ctx.audio.play("power")
            if d.wave >= 5:
                s.gs.unlock("wave5")
            if d.wave >= 10:
                s.gs.unlock("wave10")
        if prev_state != "break" and d.state == "break":
            bonus = d.clear_bonus
            self.score += bonus
            self.coins += int(bonus * 0.4)
            ctx.toast(f"Onda {d.wave} concluída! +{bonus} pontos", "ok")
            ctx.audio.play("sucesso")
        self.banner = (self.banner[0], max(0.0, self.banner[1] - dt))
        # zumbis atacam o reator
        for b in s.world.bodies:
            if b.brain is not None and b.brain.hostile and b.brain.attacking and not b.dead:
                z = ZTYPES.get(b.extra.get("z", "walker"), ZTYPES["walker"])
                self.base_hp -= z.dps * dt * cfg.diff["dmg"]
                self.flash_t = 0.15
        self.flash_t = max(0.0, self.flash_t - dt)
        if self.flash_t > 0 and random.random() < dt * 3:
            ctx.audio.play("hit", 0.5)
            ctx.shake = min(10.0, ctx.shake + 2)
        # moedas e corações (tocar com a mão)
        pts = self.reach_points()
        for b in s.world.bodies:
            if b.dead or b.kind not in ("coin", "heart"):
                continue
            if any(math.hypot(x - b.x, y - b.y) < b.r + 36 for x, y in pts):
                b.dead = True
                if b.kind == "coin":
                    v = b.extra.get("value", 10)
                    self.coins += v
                    ctx.audio.play("coin")
                    ctx.fx.popup(b.x, b.y - 20, f"+{v}", T.AMBER, 20)
                else:
                    self.base_hp = min(self.base_max, self.base_hp + 20)
                    ctx.audio.play("power")
                    ctx.fx.popup(b.x, b.y - 20, "+20 reator", T.GREEN, 20)
                ctx.fx.burst(b.x, b.y, b.color, 10, 260, 3, 0.5)
        # gemidos
        self.groan_t -= dt
        if self.groan_t <= 0 and alive:
            ctx.audio.play("groan", 0.35)
            self.groan_t = random.uniform(2.5, 6.0)
        if self.base_hp <= 0:
            self.base_hp, self.over = 0.0, True
            ctx.audio.play("over")
            ctx.shake = 20
            ctx.fx.burst(ctx.W / 2, ctx.H - 70, T.AMBER, 60, 700, 6, 1.4)
            ctx.fx.flash((255, 120, 60), 140)
            best = cfg.highscores.get("survival", 0)
            if self.score > best:
                cfg.highscores["survival"] = int(self.score)
            cfg.highscores["survival_onda"] = max(int(cfg.highscores.get("survival_onda", 0)), d.wave)
            cfg.save()

    def on_kill(self, b, source="player", head=False):
        if b.brain is None or not b.brain.hostile:
            return
        s, ctx, cfg = self.s, self.ctx, self.ctx.cfg
        z = ZTYPES.get(b.extra.get("z", "walker"), ZTYPES["walker"])
        pts = int(z.value * 10 * (1.5 if head else 1.0) * (1.25 if source == "impact" else 1.0))
        self.score += pts
        self.kills += 1
        s.gs.unlock("first_kill")
        ctx.fx.popup(b.x, b.y - b.r * 2.4, f"+{pts}", (255, 255, 100), 26)
        for _ in range(random.randint(1, 3) if z.id != "boss" else 8):
            c = s.spawn_kind("coin", at=(b.x + random.uniform(-20, 20), b.y - 10), vel=(random.uniform(-250, 250), random.uniform(-600, -200)), quiet=True)
            c.extra["value"] = max(5, int(z.value * cfg.diff["coins"] / 2))
            c.extra["ttl"] = 12.0
        if random.random() < 0.08:
            h = s.spawn_kind("heart", at=(b.x, b.y - 10), vel=(random.uniform(-120, 120), -350), quiet=True)
            h.extra["ttl"] = 12.0

    def on_destroy(self, b, by_player=True):
        pass

    # ---- desenho ----
    def draw_back(self, surf):
        ctx = self.ctx
        W, H = ctx.W, ctx.H
        hp = self.base_hp / self.base_max
        col = T.mix(T.RED, T.CYAN, hp)
        x, y = W // 2, H - 64
        draw.glow(surf, (x, y - 30), 150, col, 0.35 + 0.1 * math.sin(ctx.now * 3))
        pygame.draw.rect(surf, (28, 34, 60), (x - 54, y + 22, 108, 26), border_radius=6)
        pygame.draw.polygon(surf, (*T.mix(col, (255, 255, 255), 0.3),), [(x, y - 70), (x + 26, y - 20), (x, y + 24), (x - 26, y - 20)])
        pygame.draw.polygon(surf, (255, 255, 255), [(x, y - 70), (x + 26, y - 20), (x, y + 24), (x - 26, y - 20)], 2)
        draw.ring(surf, (x, y - 20), 62 + 4 * math.sin(ctx.now * 4), col, 2, int(60 + 120 * hp))
        pygame.draw.line(surf, T.mix(col, (0, 0, 0), 0.4), (0, H - 3), (W, H - 3), 4)

    def draw_hud(self, surf):
        ctx, d, s = self.ctx, self.director, self.s
        W, H = ctx.W, ctx.H
        r = pygame.Rect(W // 2 - 250, 78, 500, 64)
        draw.glass(surf, r, 16, accent=T.RED)
        alive = len([b for b in s.world.bodies if b.brain is not None and b.brain.hostile and not b.dead])
        draw.text(surf, "ONDA", (r.x + 20, r.y + 8), 13, T.MUTED, True)
        draw.text(surf, str(max(1, d.wave)), (r.x + 20, r.y + 22), 32, T.TEXT, True)
        draw.text(surf, "ZUMBIS", (r.x + 130, r.y + 8), 13, T.MUTED, True)
        draw.text(surf, str(d.remaining(alive)) if d.state != "break" else "—", (r.x + 130, r.y + 22), 32, T.RED, True)
        draw.text(surf, "MOEDAS", (r.x + 260, r.y + 8), 13, T.MUTED, True)
        draw.text(surf, str(self.coins), (r.x + 260, r.y + 22), 32, T.AMBER, True)
        draw.text(surf, "PONTOS", (r.right - 20, r.y + 8), 13, T.MUTED, True, "tr")
        draw.text(surf, str(self.score), (r.right - 20, r.y + 22), 28, T.TEXT, True, "tr")
        if d.state == "break" and not self.over:
            draw.text(surf, f"Próxima onda em {max(0, d.timer):.0f}s — compre melhorias na loja", (W // 2, 160), 17, T.CYAN, True, "c", 230, True)
        # barra do reator
        bw = 440
        bx, by = (W - bw) // 2, H - 30
        draw.rrect(surf, (bx, by, bw, 12), (255, 255, 255, 40), 6)
        hp = self.base_hp / self.base_max
        draw.rrect(surf, (bx, by, max(4, int(bw * hp)), 12), (*T.mix(T.RED, T.GREEN, hp), 255), 6)
        draw.text(surf, f"REATOR {int(self.base_hp)}/{int(self.base_max)}", (W // 2, by - 14), 14, T.TEXT, True, "c", 255, True)
        # arma
        ws = s.wstate
        if ws:
            draw.text(surf, ws.w.name.upper(), (110, H - 74), 15, ws.w.color, True)
            frac = ws.ammo / ws.w.mag if not ws.reloading else 1.0 - ws.reload_t / max(0.01, ws.w.reload)
            draw.rrect(surf, (110, H - 52, 150, 8), (255, 255, 255, 40), 4)
            draw.rrect(surf, (110, H - 52, max(3, int(150 * frac)), 8), (*(T.AMBER if ws.reloading else ws.w.color), 255), 4)
            draw.text(surf, "RECARREGANDO" if ws.reloading else f"{int(ws.ammo)}/{ws.w.mag}", (110, H - 40), 13, T.MUTED, True)
        if self.banner[1] > 0:
            a = int(255 * min(1.0, self.banner[1] / 0.6))
            draw.text(surf, self.banner[0], (W // 2, H // 2 - 60), 64, T.RED, True, "c", a, True)
        if self.over:
            shade = pygame.Surface((W, H), pygame.SRCALPHA)
            shade.fill((20, 0, 4, 150))
            surf.blit(shade, (0, 0))
            p = pygame.Rect(W // 2 - 220, 190, 440, 230)
            draw.glass(surf, p, 20, (20, 8, 16, 220), (255, 90, 100, 160), accent=T.RED)
            draw.text(surf, "O REATOR CAIU", (p.centerx, p.y + 20), 28, T.RED, True, "tc")
            draw.text(surf, f"Onda {d.wave}  ·  {self.kills} zumbis  ·  {self.score} pontos", (p.centerx, p.y + 70), 18, T.TEXT, True, "tc")
            best = ctx.cfg.highscores.get("survival", 0)
            draw.text(surf, f"Recorde: {best} pontos · melhor onda {ctx.cfg.highscores.get('survival_onda', 0)}", (p.centerx, p.y + 104), 15, T.AMBER, True, "tc")
        else:
            r = self.shop.rect
            draw.text(surf, "LOJA", (r.x + 18, r.y + 14), 15, T.AMBER, True)
            draw.text(surf, f"{self.coins} moedas", (r.right - 18, r.y + 14), 15, T.AMBER, True, "tr")


def make_modes(scene):
    return {"sandbox": SandboxMode(scene), "practice": PracticeMode(scene), "tutorial": TutorialMode(scene), "survival": SurvivalMode(scene)}
