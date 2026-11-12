"""Teste de fumaça sem janela: percorre TODAS as cenas e modos com mãos/rosto sintéticos e câmera falsa para pegar
erros de código (nomes, tipos, fluxo). Uso: python tests/smoke_headless.py  (usa tests/fake_pygame.py)."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_pygame

pg = fake_pygame.install()
import numpy as np

from test_core import make_hand
from openbox.config import Config
from openbox.core.app import App
from openbox.game import items as I
from openbox.tracking.face_tracker import KEYS, Face, FaceSnapshot
from openbox.tracking.gestures import HandAnalyzer
from openbox.tracking.hand_tracker import Hand, Snapshot


def synth_hand(slot, cx, cy, gesture, an, seq, thumb_up=False):
    ext = {"OPEN": (True,) * 5, "FIST": (False,) * 5, "POINT": (False, True, False, False, False), "GUN": (False, True, False, False, False),
           "PEACE": (False, True, True, False, False), "PINCH": (True,) * 5, "THUMBS_UP": (True, False, False, False, False), "ROCK": (False, True, False, False, True)}[gesture]
    P = make_hand(pinch=0.15 if gesture == "PINCH" else 0.9, ext=ext, scale=60.0, thumb_up=thumb_up)
    n = np.zeros((21, 3))
    n[:, 0] = cx + P[:, 0] / 1280.0
    n[:, 1] = cy + P[:, 1] / 720.0
    info = an.update(P, (cx, cy), seq / 30.0, 0.30, 0.46, False)
    return Hand(slot, "Right", 0.9, n, info.size / 1280.0, np.array([0.1, 0.0]), info)


def synth_face(cx=0.5, cy=0.45):
    n = np.zeros((len(KEYS), 3)) + [cx, cy, 0]
    pos = dict(top=(0, -0.12), chin=(0, 0.12), left=(-0.07, 0), right=(0.07, 0), nose=(0, 0.01), bridge=(0, -0.03),
               eye_l_o=(-0.05, -0.03), eye_l_i=(-0.02, -0.03), eye_r_i=(0.02, -0.03), eye_r_o=(0.05, -0.03),
               mouth_l=(-0.03, 0.06), mouth_r=(0.03, 0.06), lip_up=(0, 0.05), lip_lo=(0, 0.07), brow_l=(-0.04, -0.06), brow_r=(0.04, -0.06))
    for k, (dx, dy) in pos.items():
        n[KEYS.index(k)] = (cx + dx, cy + dy, 0)
    return Face(0, n, 0.14, 0.1, 0.1, 0.0, 0.2)


def run_frames(app, frames, per_frame=None, gestures=("OPEN",), two_hands=True, face=True):
    ctx, cam = app.ctx, app.camera
    an = [HandAnalyzer(), HandAnalyzer()]
    frame = (np.random.rand(720, 1280, 3) * 255).astype(np.uint8)
    for k in range(frames):
        run_frames.i += 1
        i = run_frames.i
        cam._frame, cam._seq, cam._t = frame, i, time.monotonic()
        g = gestures[(k // 10) % len(gestures)]
        cx, cy = 0.3 + 0.4 * ((k % 60) / 60.0), 0.5 + 0.1 * np.sin(k / 10.0)
        hands = [synth_hand(0, cx, cy, g, an[0], i, thumb_up=(g == "GUN" and (k % 10) < 5))]
        if two_hands and k % 40 > 20:
            hands.append(synth_hand(1, 1 - cx, cy, "PINCH" if g == "PINCH" else "OPEN", an[1], i))
        app.tracker.snapshot = Snapshot(i, time.monotonic(), hands, None, 8.0, 30.0, 120.0, 640)
        app.face_tracker.snapshot = FaceSnapshot(i, time.monotonic(), [synth_face(0.5 + 0.05 * np.sin(k / 15.0))] if face else [], 5.0, 20.0)
        ctx.now = time.monotonic()
        ctx.hands.update(1 / 60, ctx.now)
        ctx.faces.update(1 / 60, ctx.now)
        ctx.input.update(1 / 60, ctx.now, True)
        if per_frame:
            per_frame(k)
        app.scenes.update(1 / 60)
        ctx.fx.update(1 / 60)
        ctx.toasts.update(1 / 60)
        ctx.hands.swipes.clear()
        app.scenes.draw(app.screen)
        ctx.fx.draw(app.screen)
        ctx.toasts.draw(app.screen)
        app._apply_shake(1 / 60)
        time.sleep(0.003)


run_frames.i = 0


def main():
    cfg = Config()
    cfg.highscores, cfg.achievements = {}, []
    cfg.save = lambda: None
    app = App(cfg, no_camera=True, no_intro=True)
    ctx = app.ctx
    app.camera.state = "ready"
    app.camera.info = "1280x720"

    # ---- carregamento -> (pula intro) -> hub
    run_frames(app, 240, gestures=("OPEN",))
    print("ok: loading ->", app.scenes.current.name)

    run_frames(app, 40)
    app.scenes.go("hub")
    run_frames(app, 40)
    print("ok: hub")

    # ---- play: todos os modos
    p = None
    for mode in ("sandbox", "practice", "tutorial", "survival"):
        app.scenes.go("play", mode=mode)
        run_frames(app, 20)
        p = app.scenes.get("play")

        def actions(k, mode=mode):
            if k == 5:                                          # cria TODOS os itens do catálogo
                for it in I._ALL:
                    if it.kind in ("body", "creature"):
                        p.spawn_item(it, at=(150 + (hash(it.id) % 900), 300), quiet=True)
            if k == 10:
                p.catalog.open()
                p.radial.open(600, 360)
            if k == 40:
                p.catalog.close(); p.radial.close()
                for wid in ("pistol", "smg", "shotgun", "sniper", "laser", "rocket_launcher"):
                    if mode == "survival":
                        p.modes["survival"].owned.add(wid)
                    p.equip(wid)
                    p.fire("0", (300, 400), (1, -0.1))
                    p.wstate.ammo = p.wstate.w.mag
                    p.wstate.cool = 0
            if k == 90:
                for b in list(p.world.bodies)[:12]:
                    p.detonate(b) if "explosive" in b.tags else p.damage_body(b, 500, (300, -300), True)
                for tool in ("explosion", "lightning", "shockwave", "eraser"):
                    p.use_tool(tool, (500, 400))
            if mode == "survival" and k == 100:
                p.modes["survival"].director.timer = 0
            if mode == "tutorial" and k % 8 == 0:
                for name in ("hand_seen", "pinch", "grab", "throw", "push", "smash", "scale", "menu_open", "spawn", "shoot", "hat_equip"):
                    if k % 24 == 0:
                        p.emit(name)
            if k == 150 and mode == "survival":
                p.modes["survival"].base_hp = 0
        run_frames(app, 260, actions, gestures=("OPEN", "GUN", "PINCH", "PINCH", "FIST", "ROCK", "POINT", "THUMBS_UP"))
        print(f"ok: play {mode} — corpos={len(p.world.bodies)} score={p.gs.score}")

    # ---- hats / acessórios
    for it in I.by_cat("chapeus"):
        p.pick_item(it, None)
        run_frames(app, 3)
    p.ctx.cfg.hat = "none"
    print("ok: hats + acessórios")

    # ---- demais cenas
    for scene in ("calibration", "settings", "intro", "loading", "hub"):
        app.scenes.go(scene)
        run_frames(app, 60)
        print("ok:", scene)
    print("SMOKE OK — frames:", run_frames.i)


if __name__ == "__main__":
    main()
