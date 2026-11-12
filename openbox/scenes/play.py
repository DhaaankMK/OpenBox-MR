"""Cena de jogo do OpenBox MR: Sandbox, Practice, Tutorial e Sobrevivência (regras em scenes/modes.py).

Mãos:  pinça agarra/arremessa · dedo-pistola atira (levante o polegar e abaixe) · palma aberta empurra ·
punho esmaga · ROCK (1 s) abre o menu radial · joinha = slow motion · palmas juntas = onda de choque ·
duas mãos no mesmo objeto ampliam e giram.   Mouse: arrastar agarra/arremessa · botão direito = menu radial."""
from __future__ import annotations

import math
import random
from collections import deque

import pygame

from .. import theme as T
from ..config import SKELETON_STYLES
from ..core.scene import Scene
from ..game import items as I
from ..game.creatures import Brain, Env
from ..game.state import ACHIEVEMENTS, MODE_LABELS, GameState
from ..game.weapons import WEAPONS, WeaponState, ray_hits, spread_dir
from ..physics.world import World
from ..tracking.gestures import GESTURE_NAMES
from ..tracking.manager import fit_velocity
from ..ui import creature_draw, draw, hats, icons, sprites
from ..ui.catalog import CatalogPanel, Hotbar, RadialMenu
from ..ui.hud import TopBar
from ..ui.widgets import Button, Panel, Selector, Slider, Tabs, Toggle, Widget

MAX_THROW = 3800.0
MUZZLE = {"pistol": 52, "smg": 68, "shotgun": 96, "sniper": 116, "laser": 62, "rocket_launcher": 98}
BLAST = {"barrel": (210, 55), "tnt": (260, 80), "bomb": (230, 60), "grenade": (190, 55)}


def _attr(obj, name):
    return (lambda: getattr(obj, name)), (lambda v: setattr(obj, name, v))


class Shade(Widget):
    interactive = False

    def draw(self, surf):
        r = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        r.fill((2, 4, 12, 170))
        surf.blit(r, self.rect.topleft)


class PlayScene(Scene):
    name = "play"

    def __init__(self, ctx):
        super().__init__(ctx)
        W, H, cfg = ctx.W, ctx.H, ctx.cfg
        self.world = World(W, H, cfg)
        self.gs = GameState(cfg, on_unlock=lambda n: ctx.toast(f"Conquista: {n}", "ok"),
                            on_milestone=lambda c: (ctx.audio.play("combo"), ctx.toast(f"Combo x{c}!", "warn")))
        self.t = 0.0
        self.paused = False
        self.show_hud = True
        self.help, self.help_t = True, 0.0
        self.spawn_scale = 1.0
        self.tab = 0
        self.panel_open = True
        self.holds, self.off, self.was, self.two = {}, {}, {}, {}
        self.msamples: deque = deque(maxlen=14)
        self.cool: dict = {}
        self.rock_t: dict = {}
        self.trig_prev: dict = {}
        self.weapon_id = None
        self.wstate = None
        self.flash: dict = {}
        self.tracers: list = []
        self.alarms: list = []            # (x, y, ttl): sustos para as criaturas
        self.tool = None
        self.slowmo_t = 0.0
        self.tut = None
        self.mode = None
        self._layer = pygame.Surface((W, H), pygame.SRCALPHA)
        from .modes import make_modes
        self.modes = make_modes(self)

        # ---- barra superior
        self.bar = self.ui.add(TopBar(ctx, "OPENBOX", "", left=76))
        self.menu_btn = self.ui.add(Button((24, 18, 44, 44), icon="sliders", tooltip="Menu (Esc)", on_click=self.pause))

        # ---- widgets específicos de cada modo
        for m in self.modes.values():
            m.build(self.ui)

        # ---- menus de criação
        self.hotbar = self.ui.add(Hotbar(ctx, self.pick_item))
        self.radial = self.ui.add(RadialMenu(ctx, self.pick_item, self.open_catalog))
        self.catalog = self.ui.add(CatalogPanel(ctx, self.pick_item, on_hat_none=self.remove_hat))

        # ---- MENU ÚNICO (pausa + ações + física + visual + ajuda + info) — por cima de tudo
        mx, my, mw, mh = W // 2 - 440, 84, 880, 560
        self.menu_shade = self.ui.add(Shade((0, 0, W, H)))
        self.menu_panel = self.ui.add(Panel((mx, my, mw, mh), None, T.ACCENT_HI, radius=20))
        self.menu_tabs = self.ui.add(Tabs((mx + 16, my + 14, mw - 32, 42), ["Jogo", "Física", "Visual", "Ajuda", "Info"], lambda: self.tab, self._set_tab))
        BW = 400

        def B(label, fn, **kw):
            return Button((0, 0, BW, 54), label, fn, size=17, **kw)
        self.btn_clear = B("Limpar tudo", lambda: (self.clear(), self.resume()), icon="trash")
        jogo = [B("Continuar", self.resume, icon="play", style="primary"),
                B("Catálogo de itens", lambda: (self.resume(), self.open_catalog()), icon="sliders"),
                B(lambda: "Guardar arma" if self.weapon_id else "Equipar arma", lambda: (self.resume(), self.toggle_weapon()), icon="bolt"),
                B("Reiniciar modo", self.restart, icon="refresh"),
                self.btn_clear,
                B("Tirar captura", lambda: (self.resume(), ctx.app.screenshot()), icon="camera"),
                Toggle((0, 0, BW, 50), "Gravidade ligada", lambda: cfg.gravity > 0, lambda v: setattr(cfg, "gravity", 1400.0 if v else 0.0)),
                Toggle((0, 0, BW, 50), "Mãos empurram objetos", *_attr(cfg, "hand_colliders")),
                Toggle((0, 0, BW, 50), "Rastros dos objetos", *_attr(cfg, "trails")),
                B("Menu principal", lambda: ctx.scenes.go("hub"), icon="home")]
        phys = [
            Slider((0, 0, BW, 56), "Gravidade", *_attr(cfg, "gravity"), 0, 2500, "{:.0f}"),
            Slider((0, 0, BW, 56), "Quique", *_attr(cfg, "bounce"), 0, 1.1, "{:.2f}"),
            Slider((0, 0, BW, 56), "Resistência do ar", *_attr(cfg, "air_drag"), 0, 2, "{:.2f}"),
            Slider((0, 0, BW, 56), "Velocidade do tempo", *_attr(cfg, "time_scale"), 0.2, 2.0, "{:.2f}x"),
            Slider((0, 0, BW, 56), "Tamanho ao criar", *_attr(self, "spawn_scale"), 0.6, 2.0, "{:.2f}x"),
            Toggle((0, 0, BW, 50), "Bots imortais", *_attr(cfg, "bots_immortal")),
        ]
        vis = [
            Toggle((0, 0, BW, 50), "Partículas", *_attr(cfg, "particles")),
            Toggle((0, 0, BW, 50), "Paralaxe da cabeça", *_attr(cfg, "head_parallax")),
            Selector((0, 0, BW, 50), "Esqueleto", [x.capitalize() for x in SKELETON_STYLES],
                     lambda: SKELETON_STYLES.index(cfg.skeleton_style), lambda i: setattr(cfg, "skeleton_style", SKELETON_STYLES[i])),
            Slider((0, 0, BW, 56), "Escurecer câmera", *_attr(cfg, "camera_dim"), 0, 0.85, "{:.2f}"),
            Toggle((0, 0, BW, 50), "Mostrar FPS", *_attr(cfg, "show_fps")),
        ]
        from ..ui.settings_pages import layout
        self.menu_groups = [jogo, phys, vis, [], []]
        for grp in self.menu_groups:
            layout(grp, mx + 30, my + 84)
            for w in grp:
                self.ui.add(w)

    # ================================================================== modos
    def enter(self, mode="sandbox", **kw):
        self.set_mode(mode, announce=False)
        self.paused = False
        self.help, self.help_t = True, 0.0

    def exit(self):
        for k in list(self.holds):
            self._drop(k, throw=False)
        if self.mode:
            self.mode.exit()
        self.ctx.cfg.save()

    def set_mode(self, name, announce=True):
        for k in list(self.holds):
            self._drop(k, throw=False)
        if self.mode:
            self.mode.exit()
        self.mode = self.modes[name]
        self.gs.mode = name
        self.gs.reset_run()
        self.world.clear()
        self.two.clear()
        self.tracers.clear()
        self.alarms.clear()
        self.tool = None
        self.weapon_id, self.wstate = None, None
        self.slowmo_t = 0.0
        self.bar.title_s = "OPENBOX · " + MODE_LABELS[name]
        self.bar.sub = self.mode.sub
        self._seen = 0.0
        self.mode.enter()
        if announce:
            self.ctx.fx.popup(self.ctx.W / 2, self.ctx.H / 2, MODE_LABELS[name], T.AMBER, 56)
            self.ctx.audio.play("power")

    def restart(self):
        self.set_mode(self.mode.name)
        self.resume()

    def pause(self):
        self.paused = True
        self.tab = 0

    def resume(self):
        self.paused = False

    # ================================================================== utilidades de UI
    def emit(self, name, **kw):
        if self.tut is not None:
            self.tut.event(name)
        self.mode.on_event(name, **kw)

    def _set_tab(self, i):
        self.tab = i

    def toggle_catalog(self):
        if self.catalog.is_open:
            self.catalog.close()
        else:
            self.open_catalog()

    def open_catalog(self, cat=None):
        if self.radial.is_open:
            self.radial.close()
        self.catalog.restrict = None if self.mode.allow_spawn else {"chapeus"}
        self.catalog.open(cat if cat else (None if self.mode.allow_spawn else "chapeus"))
        self.emit("menu_open")

    def toggle_gravity(self):
        self.ctx.cfg.gravity = 0.0 if self.ctx.cfg.gravity > 0 else 1400.0

    def toggle_trails(self):
        self.ctx.cfg.trails = not self.ctx.cfg.trails

    def toggle_colliders(self):
        self.ctx.cfg.hand_colliders = not self.ctx.cfg.hand_colliders

    def toggle_weapon(self):
        if self.weapon_id:
            self.weapon_id, self.wstate = None, None
            self.ctx.toast("Arma guardada", "info")
        else:
            self.equip(self.mode.default_weapon())

    def clear(self):
        if not self.mode.allow_spawn:
            return
        for k in list(self.holds):
            self._drop(k, throw=False)
        self.world.clear()
        self.ctx.audio.play("whoosh", 0.5)

    def remove_hat(self):
        self.ctx.cfg.hat = self.ctx.cfg.accessory = "none"
        self.ctx.toast("Chapéu removido", "info")

    def time_factor(self):
        return self.ctx.cfg.time_scale * (0.35 if (self.slowmo_t > 0 or self.gs.active("slowmo")) else 1.0)

    # ================================================================== equipar / criar
    def equip(self, wid):
        if wid is None or wid not in WEAPONS:
            return
        if not self.mode.can_equip(wid):
            return
        self.weapon_id = wid
        self.wstate = WeaponState(WEAPONS[wid], self.mode.dmg_mult(), self.mode.rate_mult())
        self.ctx.toast(f"Arma: {WEAPONS[wid].name} — dedo-pistola (levante o polegar e abaixe)", "info")

    def pick_item(self, item, pointer=None):
        """Chamado pelo catálogo/menu radial/barra rápida. Com ponteiro, o item nasce na mão e já é agarrado."""
        ctx, cfg = self.ctx, self.ctx.cfg
        if item.kind in ("body", "creature"):
            if not self.mode.allow_spawn:
                ctx.toast("Criação desativada neste modo", "warn")
                return
            at = (pointer.x, pointer.y) if pointer is not None else None
            b = self.spawn_item(item, at=at)
            if b is not None and pointer is not None and pointer.down:
                key = "m" if pointer.kind == "mouse" else pointer.id[-1]
                if key not in self.holds:
                    self._pick(key, b, (pointer.x, pointer.y))
                    self.was[key] = True
        elif item.kind == "weapon":
            self.equip(item.id)
        elif item.kind == "hat":
            cfg.hat = "none" if cfg.hat == item.id else item.id
            self.ctx.audio.play("power", 0.6)
            if cfg.hat != "none":
                self.gs.unlock("hat")
                self.emit("hat_equip")
                if not self.ctx.faces.visible():
                    ctx.toast("Chapéu equipado — mostre o rosto para a câmera", "info")
        elif item.kind == "accessory":
            cfg.accessory = "none" if cfg.accessory == item.id else item.id
            self.ctx.audio.play("power", 0.6)
            self.emit("hat_equip")
        elif item.kind == "tool":
            self.tool = item.id
            ctx.toast(f"Ferramenta: {item.name} — clique no mundo (Esc cancela)", "info")
        self.emit("spawn")

    def spawn_item(self, item, at=None, vel=None, radius=None, brain=True, quiet=False):
        ctx = self.ctx
        x, y = at if at else (random.randint(240, ctx.W - 380), random.randint(180, ctx.H // 2 + 60))
        r = radius or item.r * self.spawn_scale * (1.5 if self.gs.active("big") else 1.0)
        v = vel or (random.uniform(-120, 120), random.uniform(-120, 60))
        b = self.world.add(item.id, x, y, v[0], v[1], r)
        if item.kind == "creature" and brain:
            b.brain = Brain(item.id)
            b.hp = b.max_hp = float(item.hp)
        self.gs.spawned += 1
        if self.gs.spawned >= 10:
            self.gs.unlock("spawn10")
        if not quiet:
            ctx.audio.play("spawn")
            ctx.fx.ring(b.x, b.y, b.color, r * 2.4, 0.5)
            ctx.fx.burst(b.x, b.y, b.color, 12, 220, 3)
        return b

    def spawn_kind(self, kind, **kw):
        return self.spawn_item(I.ITEMS[kind], **kw)

    # ================================================================== eventos
    def event(self, e):
        ctx = self.ctx
        if e.type == pygame.MOUSEBUTTONDOWN and getattr(e, "button", 1) == 3 and not self.paused:
            if self.mode.allow_spawn and not self.catalog.is_open:
                m = ctx.input.mouse
                self.radial.open(m.x, m.y)
                self.emit("menu_open")
            return
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
        if k == pygame.K_ESCAPE:
            if self.radial.is_open:
                self.radial.close()
            elif self.catalog.is_open:
                self.catalog.close()
            elif self.tool:
                self.tool = None
            else:
                self.resume() if self.paused else self.pause()
            return
        if k == pygame.K_SPACE:
            self.resume() if self.paused else self.pause()
            return
        if self.paused:
            return
        if k == pygame.K_TAB:
            self.toggle_catalog()
        elif k == pygame.K_q and self.mode.allow_spawn:
            m = ctx.input.mouse
            self.radial.open(m.x, m.y)
        elif pygame.K_1 <= k <= pygame.K_8:
            self.hotbar.force = 2.5
            idx = k - pygame.K_1
            fav = ctx.cfg.favorites
            if idx < len(fav) and fav[idx] in I.ITEMS:
                self.pick_item(I.ITEMS[fav[idx]], None)
        elif k == pygame.K_x:
            self.toggle_weapon()
        elif k == pygame.K_r:
            self.restart()
        elif k == pygame.K_h:
            self.help, self.help_t = not self.help, 0.0
        elif k == pygame.K_F1:
            self.show_hud = not self.show_hud
        elif k == pygame.K_g:
            self.toggle_gravity()
        elif k == pygame.K_c:
            self.clear()
        elif k == pygame.K_t:
            self.toggle_trails()

    # ================================================================== atualização
    def _sync_visibility(self):
        m = self.mode
        for mm in self.modes.values():
            for w in mm.widgets:
                w.visible = (mm is m) and not self.paused and mm.widget_visible(w)
        for w in (self.menu_shade, self.menu_panel, self.menu_tabs):
            w.visible = self.paused
        for i, grp in enumerate(self.menu_groups):
            for w in grp:
                w.visible = self.paused and self.tab == i
        self.btn_clear.visible = self.paused and self.tab == 0 and m.allow_spawn
        self.hotbar.visible = m.allow_spawn and not self.paused
        self.menu_btn.visible = not self.paused

    def update(self, dt):
        ctx, cfg = self.ctx, self.ctx.cfg
        self._sync_visibility()
        self.ui.update(dt, ctx.input.pointers)
        if self.paused:
            return
        self.t += dt
        self.help_t += dt
        if self.help_t > 14:
            self.help = False
        self.gs.update(dt)
        self.slowmo_t = max(0.0, self.slowmo_t - dt)
        sdt = dt * self.time_factor()
        self.mode.update(sdt)
        self._update_holds(dt)
        self._gestures(dt)
        self._weapons(dt)
        self._creatures(sdt)
        self._fuses(sdt)
        self._maybe_hand_events(dt)
        colliders = ctx.hands.colliders() + ctx.faces.colliders()
        self.world.step(sdt, colliders)
        self._collisions()
        self._impacts()
        self._cleanup()
        for c in list(self.cool):
            self.cool[c] = max(0.0, self.cool[c] - dt)
        for k in list(self.flash):
            self.flash[k] = max(0.0, self.flash[k] - dt * 7)
        self.tracers = [[a, b, life - dt, col, w] for a, b, life, col, w in self.tracers if life - dt > 0]
        self.alarms = [(x, y, ttl - dt) for x, y, ttl in self.alarms if ttl - dt > 0]

    def _cleanup(self):
        for b in self.world.bodies:
            if b.dead:
                self._release_body(b)
        self.world.remove_dead()

    def _release_body(self, b):
        for key in [k for k, bb in self.holds.items() if bb is b]:
            self.holds.pop(key, None)
            self.off.pop(key, None)
        b.held_by.clear()
        self.two.pop(b.id, None)

    # ---------------------------------------------------------------- gestos extras das mãos
    def _gestures(self, dt):
        ctx, cfg = self.ctx, self.ctx.cfg
        hands = [hv for hv in ctx.hands.visible() if not hv.stale and hv.disp is not None]
        for hv in hands:
            key = f"g{hv.slot}"
            px, py = float(hv.palm[0]), float(hv.palm[1])
            g = hv.gesture
            if g == "OPEN" and not self.holds.get(str(hv.slot)):
                for b in self.world.bodies:
                    if b.held_by:
                        continue
                    dx, dy = b.x - px, b.y - py
                    d = math.hypot(dx, dy)
                    if 1 < d < 200:
                        force = (200 - d) * 3.2
                        b.vx += dx / d * force * dt
                        b.vy += dy / d * force * dt
                        if random.random() < 0.1:
                            ctx.fx.burst(b.x, b.y, (255, 200, 255), 1, 120, 2, 0.3)
                self.emit("push_open")
            elif g == "FIST" and not cfg.fist_grab and self.cool.get(key, 0.0) <= 0:
                hit = [b for b in self.world.bodies if not b.held_by and not b.dead and math.hypot(b.x - px, b.y - py) < max(120, hv.size_px * 1.0)]
                if hit:
                    for b in hit:
                        self.smash(b, px, py)
                    self.cool[key] = 0.35
                    self.emit("smash")
            if g == "ROCK":
                self.rock_t[hv.slot] = self.rock_t.get(hv.slot, 0.0) + dt
                if self.rock_t[hv.slot] > 0.8 and not self.radial.is_open and not self.catalog.is_open and self.mode.allow_spawn:
                    self.radial.open(px, py)
                    self.rock_t[hv.slot] = -1.5
                    self.emit("menu_open")
            else:
                self.rock_t[hv.slot] = 0.0
            if g == "THUMBS_UP" and self.slowmo_t <= 0 and self.cool.get("tu", 0.0) <= 0:
                self.slowmo_t = 5.0
                ctx.audio.play("power")
                ctx.toast("SLOW MOTION!", "info")
                self.cool["tu"] = 8.0
        # palmas juntas -> onda de choque
        if len(hands) == 2 and self.cool.get("clap", 0.0) <= 0:
            a, b = hands
            dist = math.hypot(a.palm[0] - b.palm[0], a.palm[1] - b.palm[1])
            rel = math.hypot(*(a.vel_pts[[0, 5, 9, 13, 17]].mean(axis=0) - b.vel_pts[[0, 5, 9, 13, 17]].mean(axis=0)))
            if dist < max(190, (a.size_px + b.size_px) * 0.9) and rel > 1100:
                mx, my = (a.palm[0] + b.palm[0]) / 2, (a.palm[1] + b.palm[1]) / 2
                self.shockwave(mx, my)
                self.cool["clap"] = 6.0
                ctx.toast("Palmas! Onda de choque", "info")

    def smash(self, b, px, py):
        """Esmagar: objetos quebram; criaturas levam dano e são arremessadas."""
        if b.brain:
            d = max(1.0, math.hypot(b.x - px, b.y - py))
            self.damage_body(b, 25, ((b.x - px) / d * 700, (b.y - py) / d * 500 - 250))
            return
        self.destroy(b)

    def shockwave(self, x, y, radius=430.0, power=1900.0, damage=14.0):
        ctx = self.ctx
        self.world.explode(x, y, radius, power)
        for b in self.world.bodies:
            if b.brain and math.hypot(b.x - x, b.y - y) < radius:
                self.damage_body(b, damage, (0, 0), source="shockwave")
        ctx.fx.ring(x, y, T.CYAN, radius, 0.6)
        ctx.fx.ring(x, y, T.ACCENT_HI, radius * 0.7, 0.45)
        ctx.fx.flash((120, 200, 255), 70)
        ctx.audio.play("boom", 0.8)
        ctx.shake = min(22.0, ctx.shake + 10)

    def _maybe_hand_events(self, dt):
        for hv in self.ctx.hands.visible():
            if not hv.stale:
                self._seen = getattr(self, "_seen", 0.0) + dt / max(1, len(self.ctx.hands.visible()))
                if self._seen > 0.8:
                    self.emit("hand_seen")
                    self._seen = -999
            key = f"p{hv.slot}"
            if hv.pinching and not self.was.get(key):
                self.emit("pinch")
            self.was[key] = hv.pinching

    # ---------------------------------------------------------------- criaturas
    def _threats(self):
        ctx = self.ctx
        th = []
        for (x, y, r, vx, vy) in ctx.hands.colliders():
            sp = math.hypot(vx, vy)
            if sp > 380:
                th.append((x, y, r, sp))
        for b in self.world.bodies:
            if b.brain is None and not b.dead:
                sp = math.hypot(b.vx, b.vy)
                if sp > 650 or (b.held_by and b.r > 20):
                    th.append((b.x, b.y, b.r, max(sp, 700.0)))
        th.extend((x, y, 30, 900.0) for x, y, _ in self.alarms)
        return th

    def _creatures(self, dt):
        ctx, cfg = self.ctx, self.ctx.cfg
        creatures = [b for b in self.world.bodies if b.brain is not None and not b.dead]
        if not creatures:
            return
        threats = self._threats()
        interest = [(p.x, p.y) for p in ctx.input.pointers] + [(float(hv.index_tip[0]), float(hv.index_tip[1])) for hv in ctx.hands.visible() if hv.disp is not None]
        for b in creatures:
            bt = b.brain
            env = Env(self.world.w, self.world.h, threats=[t for t in threats if abs(t[0] - b.x) + abs(t[1] - b.y) > 2], interest=interest,
                      target=self.mode.env_target(b), immortal=cfg.bots_immortal, speed_mult=self.mode.zombie_speed(b),
                      attack_range=70 + b.r)
            for ev in bt.think(b, dt, env):
                if ev == "die":
                    self.kill(b, "impact", False)
                elif ev == "hurt":
                    if self.cool.get("ow", 0.0) <= 0:
                        ctx.audio.play("hit", 0.7)
                        self.cool["ow"] = 0.2
                    ctx.fx.burst(b.x, b.y, b.color, 6, 200, 3, 0.4)
                elif ev == "jump" and bt.hostile is False:
                    pass

    def damage_body(self, b, dmg, kb=(0.0, 0.0), head=False, source="player"):
        """Dano unificado: criaturas, alvos, barris explosivos, caixotes, balões..."""
        if b.dead:
            return
        ctx, cfg = self.ctx, self.ctx.cfg
        m = max(0.5, b.mass ** 0.5)
        b.vx += kb[0] / m
        b.vy += kb[1] / m
        b.flash = 1.0
        if b.brain is not None:
            mortal = b.brain.hostile or not cfg.bots_immortal
            amount = dmg * (2.0 if head else 1.0) * (self.mode.player_damage_mult() if b.brain.hostile else 1.0)
            if mortal:
                b.hp -= amount
            b.brain.stun(0.25 if dmg < 30 else 0.8)
            ctx.fx.popup(b.x, b.y - b.r * 1.8, f"{int(amount)}{'!' if head else ''}", T.AMBER if head else (255, 255, 255), 24 if head else 18)
            ctx.fx.burst(b.x, b.y - b.r * 0.4, (110, 230, 90) if b.brain.hostile else (255, 255, 255), 6 if not head else 12, 240, 3, 0.5)
            if mortal and b.hp <= 0:
                self.kill(b, source, head)
            return
        tags = b.tags
        if "target" in tags:
            if b.hit_cd <= 0:
                b.hp -= 1
                b.hit_cd = 0.15
                ctx.fx.burst(b.x, b.y, (255, 255, 100), 8, 260, 3)
                if b.hp <= 0:
                    self.destroy(b)
                else:
                    ctx.audio.play("pop")
        elif "explosive" in tags:
            b.hp -= 1
            if b.hp <= 0:
                self.detonate(b)
        elif "breakable" in tags:
            b.hp -= 1
            ctx.fx.burst(b.x, b.y, b.color, 8, 260, 3)
            if b.hp <= 0:
                self.destroy(b)
        elif "pops" in tags:
            self.destroy(b)

    def kill(self, b, source="player", head=False):
        if b.dead:
            return
        b.dead = True
        self._release_body(b)
        ctx = self.ctx
        ctx.fx.burst(b.x, b.y, (110, 230, 90) if b.brain and b.brain.hostile else b.color, 26, 420, 4, 0.7)
        ctx.fx.ring(b.x, b.y, T.AMBER, b.r * 2.5, 0.4)
        ctx.audio.play("boom", 0.45)
        ctx.shake = min(14.0, ctx.shake + 3)
        self.gs.destroyed += 1
        self.mode.on_kill(b, source, head)

    def destroy(self, b, by_player=True):
        if b.dead:
            return
        if b.item and "explosive" in b.tags:
            self.detonate(b)
            return
        b.dead = True
        self._release_body(b)
        ctx, gs = self.ctx, self.gs
        ctx.fx.burst(b.x, b.y, b.color, 24, 420, 4, 0.7)
        ctx.fx.burst(b.x, b.y, (255, 255, 255), 8, 500, 3, 1.0)
        ctx.audio.play("pop" if "pops" in b.tags else "boom", 0.7)
        ctx.shake = min(12.0, ctx.shake + 4)
        gs.destroyed += 1
        self.mode.on_destroy(b, by_player)

    def detonate(self, b):
        if b.dead:
            return
        b.dead = True
        self._release_body(b)
        rad, dmg = BLAST.get(b.kind, (200, 50))
        if b.kind == "missile":
            rad, dmg = b.extra.get("blast", 150), b.extra.get("dmg", 55)
        self.explode(b.x, b.y, rad, rad * 8.0, dmg, ignore=b)
        self.mode.on_destroy(b, True)

    def explode(self, x, y, radius=200.0, power=1500.0, damage=50.0, ignore=None, source="explosion"):
        ctx = self.ctx
        self.world.explode(x, y, radius, power, ignore=ignore)
        for b in self.world.bodies:
            if b is ignore or b.dead:
                continue
            d = math.hypot(b.x - x, b.y - y) - b.r
            if d >= radius:
                continue
            k = 1.0 - max(0.0, d) / radius
            if b.brain:
                self.damage_body(b, damage * k, (0, 0), source=source)
            elif "explosive" in b.tags and b.fuse is None:
                b.fuse = 0.08 + random.random() * 0.14
            elif "target" in b.tags or "breakable" in b.tags or "pops" in b.tags:
                self.damage_body(b, 1)
        ctx.fx.burst(x, y, (255, 180, 60), 40, 600, 5, 0.8)
        ctx.fx.burst(x, y, (255, 90, 40), 24, 380, 6, 0.9)
        ctx.fx.ring(x, y, T.AMBER, radius, 0.55)
        ctx.fx.ring(x, y, (255, 255, 255), radius * 0.5, 0.35)
        ctx.fx.flash((255, 160, 60), 100)
        ctx.audio.play("boom")
        ctx.shake = min(26.0, ctx.shake + 14)
        self.alarms.append((x, y, 1.2))

    def _fuses(self, dt):
        ctx = self.ctx
        for b in self.world.bodies:
            if b.dead:
                continue
            if b.kind == "missile":
                b.fuse = (b.fuse if b.fuse is not None else 3.0) - dt
                ctx.fx.burst(b.x, b.y, (255, 190, 80), 1, 80, 3, 0.4)
                if b.hit_speed > 150 or b.fuse <= 0:
                    self.detonate(b)
                continue
            ttl = b.extra.get("ttl")
            if ttl is not None:
                b.extra["ttl"] = ttl - dt
                if b.extra["ttl"] <= 0:
                    b.dead = True
                    continue
            if b.fuse is None:
                continue
            if not b.held_by:
                b.fuse -= dt
            if "rocket" in b.tags and b.extra.get("lit"):
                b.vy -= 1200 * dt
                b.vx += math.sin(self.t * 9 + b.id) * 90 * dt
                ctx.fx.burst(b.x, b.y + b.r, (255, 200, 90), 1, 120, 3, 0.35)
            if b.fuse <= 0:
                if "rocket" in b.tags:
                    self.fireworks(b)
                elif "explosive" in b.tags:
                    self.detonate(b)
            elif "timed" in b.tags and b.fuse < 1.0 and int(b.fuse * 8) % 2 == 0:
                b.flash = 1.0

    def fireworks(self, b):
        ctx = self.ctx
        b.dead = True
        self._release_body(b)
        for col in ((255, 90, 90), (90, 255, 160), (110, 160, 255), (255, 230, 90), (255, 120, 230)):
            ctx.fx.burst(b.x, b.y, col, 18, random.uniform(300, 520), 4, 1.0)
        ctx.fx.ring(b.x, b.y, (255, 255, 255), 140, 0.6)
        ctx.audio.play("pop")
        ctx.audio.play("boom", 0.4)

    # ---------------------------------------------------------------- colisões entre corpos
    def _collisions(self):
        for a, b, speed in self.world.pair_hits:
            for proj, other in ((a, b), (b, a)):
                if other.dead or other.brain is not None:
                    continue
                if "target" in other.tags and "target" not in proj.tags and speed > 300 and other.hit_cd <= 0:
                    self.damage_body(other, 1)
                elif "explosive" in other.tags and other.kind != "grenade" and speed > (650 if other.kind == "bomb" else 800):
                    self.detonate(other)
                elif "breakable" in other.tags and speed > 520 and other.hit_cd <= 0:
                    other.hit_cd = 0.2
                    self.damage_body(other, 1)
                elif "pops" in other.tags and speed > 150:
                    self.destroy(other)
            if (a.brain or b.brain) and speed > 650 and (a.held_by or b.held_by or a.brain and b.brain):
                self.gs.bump_combo()
        self.world.pair_hits.clear()
        for (x, y, r, vx, vy) in self.ctx.hands.colliders():          # dedo/palma em alta velocidade acerta alvos
            if math.hypot(vx, vy) < 800:
                continue
            for b in self.world.bodies:
                if not b.dead and ("target" in b.tags) and math.hypot(b.x - x, b.y - y) < b.r + r and b.hit_cd <= 0:
                    self.damage_body(b, 1)

    def _impacts(self):
        ctx, n = self.ctx, 0
        for x, y, speed, _k in self.world.impacts:
            if speed > 420 and n < 3:
                n += 1
                ctx.audio.play("thud", min(1.0, speed / 1800))
                ctx.fx.burst(x, y, T.ACCENT_HI, int(6 + speed / 120), 200 + speed * 0.2, 2.5, 0.5)
                if speed > 1000:
                    ctx.fx.ring(x, y, T.CYAN, 60 + speed * 0.04, 0.4)
        self.world.impacts.clear()

    # ---------------------------------------------------------------- armas
    def _muzzle_base(self, hv):
        scale = max(0.6, min(1.7, hv.size_px / 90.0))
        base = hv.palm + hv.aim * hv.size_px * 0.15
        return base, scale

    def _targets(self):
        out = []
        for b in self.world.bodies:
            if b.dead or b.held_by or b.kind in ("coin",) or b.kind == "missile":
                continue
            head = None
            if b.brain and b.kind not in ("slime", "ghost", "chick"):
                head = (b.x + math.sin(b.angle) * b.r * 1.35, b.y - math.cos(b.angle) * b.r * 1.35, b.r * 0.52)
            out.append((b, b.x, b.y, b.r * 1.05, head))
        return out

    def _weapons(self, dt):
        ctx, cfg, ws = self.ctx, self.ctx.cfg, self.wstate
        if ws is None:
            return
        any_beam = False
        for hv in ctx.hands.visible():
            if hv.stale or hv.disp is None:
                continue
            key = str(hv.slot)
            trig = hv.trigger if cfg.trigger_mode == "polegar" else (hv.pinching and hv.gesture == "PINCH")
            edge = trig and not self.trig_prev.get(key, False)
            self.trig_prev[key] = trig
            base, scale = self._muzzle_base(hv)
            muz = base + hv.aim * MUZZLE.get(ws.w.id, 60) * scale
            d = (float(hv.aim[0]), float(hv.aim[1]))
            if ws.w.beam:
                if trig and ws.drain_beam(dt):
                    any_beam = True
                    self._beam(muz, d, ws, dt)
                    self.flash[key] = 0.6
            elif (ws.w.auto and trig and ws.can_fire()) or (edge and ws.can_fire()):
                if ws.fire():
                    self.fire(key, (float(muz[0]), float(muz[1])), d)
        m = ctx.input.mouse
        if m in ctx.input.pointers and self.tool is None and not m.over_ui:
            origin = (ctx.W / 2.0, ctx.H - 30.0)
            d = (m.x - origin[0], m.y - origin[1])
            trig = m.down
            edge = m.pressed
            if ws.w.beam:
                if trig and ws.drain_beam(dt):
                    any_beam = True
                    self._beam(origin, d, ws, dt)
            elif (ws.w.auto and trig and ws.can_fire()) or (edge and ws.can_fire()):
                if ws.fire():
                    self.fire("m", origin, d)
        ws.update(dt, firing=any_beam)

    def _beam(self, origin, d, ws, dt):
        hits = ray_hits(origin[0], origin[1], d[0], d[1], self._targets(), ws.w.range)
        n = math.hypot(*d) or 1.0
        end = (origin[0] + d[0] / n * ws.w.range, origin[1] + d[1] / n * ws.w.range)
        if hits:
            h = hits[0]
            end = h.point
            self.damage_body(h.target, ws.damage * dt, (d[0] / n * 40, d[1] / n * 40), h.head)
            self.ctx.fx.burst(end[0], end[1], ws.w.color, 1, 200, 2, 0.3)
        self.tracers.append([origin, end, 0.05, ws.w.color, 4])
        if self.cool.get("beam", 0.0) <= 0:
            self.ctx.audio.play("shot_laser", 0.5)
            self.cool["beam"] = 0.18

    def fire(self, key, origin, d):
        ctx, ws = self.ctx, self.wstate
        w = ws.w
        n = math.hypot(*d) or 1.0
        dx, dy = d[0] / n, d[1] / n
        self.flash[key] = 1.0
        ctx.audio.play(w.sound)
        self.alarms.append((origin[0], origin[1], 0.35))
        self.emit("shoot")
        self.gs.bump_combo(0)
        if w.blast:
            b = self.world.add("missile", origin[0], origin[1], dx * 1250, dy * 1250)
            b.fuse = 3.0
            b.extra["blast"], b.extra["dmg"] = w.blast, ws.damage
            b.angle = math.atan2(dy, dx)
            ctx.shake = min(12.0, ctx.shake + 5)
            return
        targets = self._targets()
        for _ in range(w.pellets):
            sdx, sdy = spread_dir(dx, dy, w.spread) if w.spread else (dx, dy)
            hits = ray_hits(origin[0], origin[1], sdx, sdy, targets, w.range)[: w.pierce]
            end = (origin[0] + sdx * min(w.range, 2200), origin[1] + sdy * min(w.range, 2200))
            for i, h in enumerate(hits):
                end = h.point
                dmg = ws.damage * (0.7 ** i)
                self.damage_body(h.target, dmg, (sdx * w.kb, sdy * w.kb), h.head)
                if h.head and h.target.brain and h.target.brain.hostile:
                    self.gs.unlock("headshot")
                ctx.fx.burst(h.point[0], h.point[1], w.color, 5, 240, 2.5, 0.35)
            self.tracers.append([origin, end, 0.07, w.color, 3 if w.pellets == 1 else 2])
        ctx.fx.burst(origin[0], origin[1], (255, 220, 140), 4, 180, 2.5, 0.2)

    # ---------------------------------------------------------------- agarrar / arremessar
    def _sources(self):
        ctx, cfg, src = self.ctx, self.ctx.cfg, {}
        shooting_pinch = self.wstate is not None and cfg.trigger_mode == "pinca"
        for slot, hv in ctx.hands.views.items():
            p = ctx.input.hand_ptrs.get(slot)
            grab = bool(hv.visible and hv.grabbing and hv.disp is not None) and not shooting_pinch
            pt = (float(hv.grab_point[0]), float(hv.grab_point[1])) if hv.disp is not None else (0.0, 0.0)
            reach = max(52.0, hv.size_px * 0.5) * cfg.post["grab_reach"] if hv.pinching else max(64.0, hv.size_px * 0.6) * cfg.post["grab_reach"]
            src[str(slot)] = dict(grab=grab, pt=pt, over=bool(p and p.over_ui), reach=reach, vel=lambda hv=hv: hv.throw_velocity(0.12, ctx.now))
        m = ctx.input.mouse
        active = m in ctx.input.pointers
        if active:
            self.msamples.append((ctx.now, m.x, m.y))
        else:
            self.msamples.clear()
        src["m"] = dict(grab=bool(active and m.down) and self.wstate is None, pt=(m.x, m.y), over=m.over_ui, reach=50.0,
                        vel=lambda: fit_velocity(self.msamples, 0.12, ctx.now))
        return src

    def _src_pt(self, key):
        if key == "m":
            return (self.ctx.input.mouse.x, self.ctx.input.mouse.y)
        hv = self.ctx.hands.views[int(key)]
        return (float(hv.grab_point[0]), float(hv.grab_point[1]))

    def _update_holds(self, dt):
        ctx = self.ctx
        src = self._sources()
        for key, s in src.items():
            edge = s["grab"] and not self.was.get(key, False)
            self.was[key] = s["grab"]
            if edge and not s["over"] and key not in self.holds:
                if self.tool is not None:
                    self.use_tool(self.tool, s["pt"])
                    continue
                b = self.world.nearest(s["pt"][0], s["pt"][1], s["reach"])
                if b is not None:
                    self._pick(key, b, s["pt"])
            elif key in self.holds and not s["grab"]:
                self._drop(key, s["vel"]())
        done = set()
        for key, b in list(self.holds.items()):
            if b.id in done:
                continue
            done.add(b.id)
            keys = [k for k, bb in self.holds.items() if bb is b]
            pts = []
            for k in keys:
                ox, oy = self.off.get(k, (0.0, 0.0))
                decay = math.exp(-dt * 7.0)
                self.off[k] = (ox * decay, oy * decay)
                px, py = src[k]["pt"]
                pts.append((px + self.off[k][0], py + self.off[k][1]))
            b.target = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
            if len(keys) == 2 and b.id in self.two:
                t0 = self.two[b.id]
                (ax, ay), (bx, by) = src[keys[0]]["pt"], src[keys[1]]["pt"]
                d = max(math.hypot(bx - ax, by - ay), 1.0)
                b.target_r = max(b.base_r * 0.5, min(b.base_r * 2.6, t0["r0"] * d / t0["d0"]))
                b.angle = t0["a0"] + (math.atan2(by - ay, bx - ax) - t0["h0"])
                b.w = 0.0
                if abs(b.target_r / max(b.base_r, 1) - 1.0) > 0.35:
                    self.emit("scale")

    def _pick(self, key, b, pt):
        ctx, gs = self.ctx, self.gs
        self.holds[key] = b
        b.held_by.add(key)
        self.off[key] = (b.x - pt[0], b.y - pt[1])
        if len(b.held_by) == 2:
            k1, k2 = list(b.held_by)
            (ax, ay), (bx, by) = self._src_pt(k1), self._src_pt(k2)
            self.two[b.id] = dict(d0=max(math.hypot(bx - ax, by - ay), 40.0), r0=b.r, a0=b.angle, h0=math.atan2(by - ay, bx - ax))
            ctx.toast("Duas mãos: afaste para ampliar, gire para rotacionar", "info")
        ctx.audio.play("grab")
        ctx.fx.ring(b.x, b.y, T.GREEN, b.r * 1.8, 0.35)
        gs.grabs += 1
        gs.unlock("first_grab")
        gained = gs.add_score(5)
        if gained:
            gs.bump_combo()
            ctx.fx.popup(b.x, b.y - 40, f"+{gained}", T.GREEN, 20)
        self.emit("grab")

    def _drop(self, key, vel=(0.0, 0.0), throw=True):
        b = self.holds.pop(key, None)
        self.off.pop(key, None)
        if b is None:
            return
        b.held_by.discard(key)
        self.two.pop(b.id, None)
        b.base_r = b.target_r = b.r
        if b.held_by:
            return
        if "timed" in b.tags and b.fuse is None:
            b.fuse = 2.5
            self.ctx.audio.play("tick")
        if "rocket" in b.tags and not b.extra.get("lit"):
            b.extra["lit"], b.fuse = True, 1.6
            self.ctx.audio.play("whoosh")
        if not throw:
            b.vx = b.vy = 0.0
            return
        vx, vy = vel[0] * 1.05, vel[1] * 1.05
        sp = math.hypot(vx, vy)
        if sp > MAX_THROW:
            vx, vy, sp = vx * MAX_THROW / sp, vy * MAX_THROW / sp, MAX_THROW
        b.vx, b.vy = vx, vy
        if b.brain is None:
            b.w += vx * 0.002
        else:
            b.w = vx * 0.004
        ctx, gs = self.ctx, self.gs
        if sp > 300:
            gs.throws += 1
            gs.unlock("first_throw")
            gained = gs.add_score(int(sp / 50))
            if gained:
                gs.bump_combo()
                ctx.fx.popup(b.x, b.y - 40, f"+{gained}", (255, 200, 100), 20)
            if sp > 500:
                self.emit("throw")
                if b.brain is not None:
                    gs.unlock("bot_throw")
        if sp > 700:
            ctx.audio.play("whoosh", min(1.0, sp / 2500))
            ctx.fx.burst(b.x, b.y, b.color, 10, 160, 3)
        else:
            ctx.audio.play("release", 0.7)

    def use_tool(self, tool, pt):
        ctx = self.ctx
        x, y = pt
        if tool == "explosion":
            self.explode(x, y, 190, 1700, 60)
        elif tool == "lightning":
            ctx.fx.flash((200, 220, 255), 130)
            self.tracers.append([(x + random.uniform(-60, 60), 0), (x, y), 0.18, (200, 225, 255), 5])
            self.tracers.append([(x + random.uniform(-90, 90), 0), (x, y), 0.14, (255, 255, 255), 3])
            ctx.audio.play("boom", 0.8)
            ctx.shake = min(20.0, ctx.shake + 9)
            ctx.fx.ring(x, y, (200, 225, 255), 120, 0.4)
            for b in list(self.world.bodies):
                if math.hypot(b.x - x, b.y - y) < 110 + b.r:
                    if b.brain:
                        self.damage_body(b, 60, (0, -300), source="raio")
                    else:
                        self.destroy(b)
        elif tool == "shockwave":
            self.shockwave(x, y)
        elif tool == "eraser":
            b = self.world.nearest(x, y, 30)
            if b is not None:
                b.dead = True
                self._release_body(b)
                ctx.fx.burst(b.x, b.y, b.color, 14, 260, 3)
                ctx.audio.play("pop", 0.6)

    # ================================================================== desenho
    def draw(self, surf):
        ctx = self.ctx
        ctx.draw_background(surf)
        self.mode.draw_back(surf)
        self._draw_world(surf)
        ctx.draw_hands(surf, held_slots={int(k) for k in self.holds if k != "m"})
        self._draw_weapons(surf)
        self._draw_holds(surf)
        self.mode.draw_world_overlay(surf)
        self.ui.draw(surf)
        if self.show_hud:
            self.mode.draw_hud(surf)
        if self.paused and self.tab == 4:
            self._draw_info(surf)
        elif self.paused and self.tab == 3:
            self._draw_help_tab(surf)
        if self.help and not self.paused and self.mode.show_help:
            self._draw_help(surf)
        if self.tool and not self.paused:
            it = I.ITEMS[self.tool]
            draw.text(surf, f"Ferramenta: {it.name} — clique no mundo · Esc cancela", (ctx.W // 2, ctx.H - 112), 17, T.AMBER, True, "c", 240, True)
        if self.paused:
            draw.text(surf, "Esc ou Espaço para continuar", (ctx.W // 2, 656), 14, T.MUTED, False, "c")

    def _draw_world(self, surf):
        ctx, cfg = self.ctx, self.ctx.cfg
        layer = self._layer
        layer.fill((0, 0, 0, 0))
        now = ctx.now
        # rostos: acessórios e chapéus
        for fv in ctx.faces.visible():
            if fv.stale or fv.pts is None:
                continue
            if cfg.accessory != "none":
                hats.draw_accessory(layer, cfg.accessory, fv, now)
            if cfg.hat != "none" and fv.hat_pos is not None:
                hats.draw_hat(layer, cfg.hat, (float(fv.hat_pos[0]), float(fv.hat_pos[1])), fv.width, fv.roll, now, fv.yaw, fv.hat_tilt)
        px, py = ctx.parallax()
        for b in self.world.bodies:
            sx, sy = -px * 26, 30 + py * 12
            if b.kind not in ("missile",):
                pygame.draw.ellipse(layer, (0, 0, 0, 46), pygame.Rect(b.x - b.r * 0.9 + sx, min(b.y + b.r * 0.55, self.world.h - 8) + sy * 0.3, b.r * 1.8, b.r * 0.45))
            if cfg.trails and len(b.trail) > 3 and not b.brain:
                sp = math.hypot(b.vx, b.vy)
                if sp > 140:
                    n = len(b.trail)
                    for i, (tx, ty) in enumerate(b.trail):
                        k = i / n
                        pygame.draw.circle(layer, (*b.color, int(60 * k)), (int(tx), int(ty)), max(2, int(b.r * 0.42 * k)))
        for b in self.world.bodies:
            if b.brain is not None:
                creature_draw.draw_creature(layer, b, now)
                if b.flash > 0.4:
                    pygame.draw.circle(layer, (255, 255, 255, int(110 * b.flash)), (int(b.x), int(b.y)), int(b.r * 1.1))
            else:
                img = sprites.body_image(b, now)
                layer.blit(img, img.get_rect(center=(int(b.x), int(b.y))))
        surf.blit(layer, (0, 0))
        for b in self.world.bodies:
            held = bool(b.held_by)
            g = 0.26 + 0.5 * b.flash + (0.25 if held else 0.0)
            if b.kind in ("blackhole", "magnet"):
                g += 0.4
            draw.glow(surf, (b.x, b.y), b.r * (2.6 if b.kind == "blackhole" else 2.1), T.GREEN if held else b.color, g)
            if b.kind == "target" and b.hp < b.max_hp:
                bw = int(b.r * 2)
                pygame.draw.rect(surf, (40, 40, 50), (int(b.x - b.r), int(b.y - b.r) - 14, bw, 7), border_radius=3)
                pygame.draw.rect(surf, T.RED, (int(b.x - b.r), int(b.y - b.r) - 14, int(bw * b.hp / b.max_hp), 7), border_radius=3)
            elif b.brain is not None and b.brain.hostile and b.hp < b.max_hp:
                bw = int(b.r * 1.6)
                y0 = int(b.y - b.r * 2.2)
                pygame.draw.rect(surf, (30, 36, 40), (int(b.x - bw / 2), y0, bw, 5), border_radius=2)
                pygame.draw.rect(surf, (110, 230, 90), (int(b.x - bw / 2), y0, int(bw * max(0.0, b.hp) / max(1.0, b.max_hp)), 5), border_radius=2)
            elif b.kind == "bomb" and int(now * 6) % 2 == 0:
                draw.glow(surf, (b.x, b.y), b.r * 1.3, (255, 70, 60), 0.5)
            if b.fuse is not None and "timed" in b.tags:
                draw.text(surf, f"{max(0.0, b.fuse):.1f}", (b.x, b.y - b.r - 14), 16, T.AMBER, True, "c", 230, True)
        for a, bb, life, col, w in self.tracers:
            k = max(0.0, min(1.0, life / 0.07))
            pygame.draw.line(surf, T.mix(col, (255, 255, 255), 0.6), (int(a[0]), int(a[1])), (int(bb[0]), int(bb[1])), max(1, int(w)))
            draw.glow(surf, bb, 22 * k + 6, col, 0.6 * k)

    def _draw_weapons(self, surf):
        ws, ctx = self.wstate, self.ctx
        if ws is None:
            return
        layer = self._layer
        layer.fill((0, 0, 0, 0))
        for hv in ctx.hands.visible():
            if hv.disp is None:
                continue
            ready = hv.gesture in ("GUN", "POINT") or hv.armed or hv.trigger or (ctx.cfg.trigger_mode == "pinca" and hv.pinching)
            if not ready:
                continue
            base, scale = self._muzzle_base(hv)
            ang = math.atan2(float(hv.aim[1]), float(hv.aim[0]))
            hats.draw_weapon(layer, ws.w.id, float(base[0]), float(base[1]), ang, self.flash.get(str(hv.slot), 0.0), scale)
            # mira / indicador de munição
            bar_w = 70
            r = pygame.Rect(int(hv.palm[0]) - bar_w // 2, int(hv.palm[1]) + int(hv.size_px * 0.75), bar_w, 6)
            pygame.draw.rect(layer, (255, 255, 255, 60), r, border_radius=3)
            frac = ws.ammo / ws.w.mag if not ws.reloading else 1.0 - ws.reload_t / max(0.01, ws.w.reload)
            pygame.draw.rect(layer, (*(T.AMBER if ws.reloading else ws.w.color), 230), (r.x, r.y, max(2, int(bar_w * frac)), 6), border_radius=3)
            if hv.armed and not hv.trigger:
                pygame.draw.circle(layer, (*T.GREEN, 200), (int(hv.palm[0]), int(hv.palm[1]) - int(hv.size_px * 0.9)), 5)
        surf.blit(layer, (0, 0))

    def _draw_holds(self, surf):
        groups: dict = {}
        for k, b in self.holds.items():
            groups.setdefault(b.id, (b, []))[1].append(k)
        for b, keys in groups.values():
            draw.ring(surf, (b.x, b.y), b.r + 10, T.GREEN, 2, 200)
            pts = [self._src_pt(k) for k in keys]
            for p in pts:
                pygame.draw.line(surf, T.GREEN, (int(p[0]), int(p[1])), (int(b.x), int(b.y)), 1)
            if len(pts) == 2:
                pygame.draw.line(surf, T.GREEN, (int(pts[0][0]), int(pts[0][1])), (int(pts[1][0]), int(pts[1][1])), 2)
                draw.text(surf, f"x{b.r / b.base_r:.2f}", ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2 - 18), 18, T.GREEN, True, "c", 255, True)

    def _draw_help(self, surf):
        ctx = self.ctx
        rows = [("hand", "PINÇA", "agarrar e arremessar"), ("bolt", "DEDO-PISTOLA", "polegar sobe e desce = tiro"),
                ("up", "PALMA ABERTA", "empurra à distância"), ("fist", "PUNHO", "esmaga o que estiver perto"),
                ("gear", "ROCK (1 s)", "abre o menu de criação"), ("clock", "JOINHA", "slow motion")]
        a = int(255 * min(1.0, (14 - self.help_t) / 1.5))
        r = pygame.Rect(ctx.W // 2 - 340, ctx.H - 250, 680, 128)
        draw.glass(surf, r, 16, (10, 14, 34, int(150 * a / 255)), (*T.GLASS_BORDER[:3], int(80 * a / 255)))
        for i, (ic, k, v) in enumerate(rows):
            cx, cy = r.x + 26 + (i // 3) * 340, r.y + 24 + (i % 3) * 30
            icons.draw(ic, surf, cx + 10, cy, 10, T.CYAN)
            draw.text(surf, k, (cx + 32, cy), 15, T.TEXT, True, "ml", a)
            draw.text(surf, v, (cx + 170, cy), 14, T.MUTED, False, "ml", a)
        draw.text(surf, "Tab catálogo · Q/botão direito menu radial · 1-8 barra rápida · X arma · Esc pausa · H ajuda", (r.centerx, r.bottom - 14), 13, T.DIM, False, "c", a)

    def _draw_help_tab(self, surf):
        r = self.menu_panel.rect
        rows = [("hand", "PINÇA", "agarrar, arremessar e clicar"), ("bolt", "DEDO-PISTOLA", "levante o polegar e abaixe = tiro"),
                ("up", "PALMA ABERTA", "empurra objetos à distância"), ("fist", "PUNHO", "esmaga o que estiver perto"),
                ("gear", "ROCK (1 s)", "abre o menu radial de criação"), ("clock", "JOINHA", "slow motion"),
                ("orb", "DUAS MÃOS", "ampliam e giram um objeto"), ("star", "PALMAS JUNTAS", "onda de choque")]
        for i, (ic, k, v) in enumerate(rows):
            cx, cy = r.x + 40 + (i // 4) * 430, r.y + 96 + (i % 4) * 46
            icons.draw(ic, surf, cx + 10, cy, 11, T.CYAN)
            draw.text(surf, k, (cx + 34, cy - 10), 16, T.TEXT, True)
            draw.text(surf, v, (cx + 34, cy + 9), 14, T.MUTED)
        draw.text(surf, "Mouse: arrastar agarra · botão direito/Q menu radial · Tab catálogo · 1-8 barra rápida (sobe quando o cursor vai ao rodapé) · X arma · Esc menu",
                  (r.centerx, r.bottom - 40), 14, T.DIM, False, "c")

    def _draw_info(self, surf):
        ctx, gs, r = self.ctx, self.gs, self.menu_panel.rect
        y = r.y + 90
        rows = [("Objetos", f"{len(self.world.bodies)}/{World.MAX_BODIES}"), ("Câmera", f"{ctx.camera.info or '—'} @ {ctx.camera.fps:.0f}"),
                ("Mãos", f"{ctx.hands.fps:.0f} fps · {ctx.hands.infer_ms:.0f} ms"), ("Rosto", f"{ctx.faces.fps:.0f} fps"),
                ("Latência", f"{ctx.hands.latency * 1000:.0f} ms"), ("Postura", ctx.cfg.post["label"]),
                ("Agarres / arremessos", f"{gs.grabs} / {gs.throws}"), ("Conquistas", f"{len(ctx.cfg.achievements)}/{len(ACHIEVEMENTS)}")]
        for k, v in rows:
            draw.text(surf, k, (r.x + 36, y), 16, T.MUTED)
            draw.text(surf, v, (r.x + 420, y), 16, T.TEXT, True, "tr")
            y += 27
        y += 8
        draw.text(surf, "MÃOS", (r.x + 22, y), 13, T.ACCENT_HI, True)
        y += 24
        hands = ctx.hands.visible()
        if not hands:
            draw.text(surf, "Nenhuma mão detectada", (r.x + 22, y), 15, T.DIM)
        for hv in hands:
            draw.text(surf, f"Mão {hv.slot + 1}", (r.x + 22, y), 16, hv.color, True)
            draw.text(surf, f"{GESTURE_NAMES.get(hv.gesture, '—')} · pinça {hv.pinch_ratio:.2f}", (r.right - 22, y), 15, T.TEXT, False, "tr")
            y += 26
