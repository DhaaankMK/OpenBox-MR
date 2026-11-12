"""Testes sem dependência de janela/câmera: python -m unittest discover -s tests"""
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openbox.tracking.filters import OneEuro
from openbox.tracking.gestures import HandAnalyzer


def make_hand(pinch=0.9, ext=(True, True, True, True, True), scale=100.0, thumb_up=False):
    """Mão sintética apontando para cima. pinch = distância polegar-indicador / tamanho."""
    P = np.zeros((21, 3))
    P[0] = (0, 0, 0)
    # MCPs
    mcp_x = {5: -30, 9: -10, 13: 10, 17: 30}
    for i, x in mcp_x.items():
        P[i] = (x, -100, 0)
    P[1], P[2], P[3], P[4] = (-25, -20, 0), (-45, -45, 0), (-60, -65, 0), (-75, -90, 0)
    for (mcp, pip, tip), e in zip(((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20)), ext[1:]):
        x = P[mcp][0]
        P[pip] = (x, -135, 0)
        P[tip] = (x, -175 if e else -90, 0) if e else (x, -95, 0)
        if not e:
            P[pip] = (x, -135, 0)
            P[tip] = (x, -105, 0)
    if thumb_up:
        P[3], P[4] = (-100, -80, 0), (-130, -95, 0)
    if pinch < 0.9:
        P[8] = P[4] + np.array([pinch * 100.0, 0, 0])
    return P * (scale / 100.0)


class TestFilters(unittest.TestCase):
    def test_reduces_jitter(self):
        rng = np.random.default_rng(1)
        f = OneEuro(min_cutoff=0.5, beta=10)
        raw, out = [], []
        for i in range(200):
            x = 0.5 + rng.normal(0, 0.004)
            raw.append(x)
            out.append(float(f(np.array([x]), i / 30.0)[0]))
        self.assertLess(np.std(out[50:]), np.std(raw[50:]) * 0.6)

    def test_follows_fast_motion(self):
        f = OneEuro(min_cutoff=0.5, beta=10)
        y = 0.0
        for i in range(60):
            y = float(f(np.array([i * 0.02]), i / 30.0)[0])
        self.assertLess(abs(y - 59 * 0.02), 0.12)


class TestGestures(unittest.TestCase):
    def run_g(self, P, frames=4):
        a = HandAnalyzer()
        info = None
        for i in range(frames):
            info = a.update(P, (0.5, 0.5), i / 30.0, 0.30, 0.46)
        return info

    def test_open_palm(self):
        self.assertEqual(self.run_g(make_hand()).gesture, "OPEN")

    def test_fist(self):
        info = self.run_g(make_hand(ext=(False, False, False, False, False)))
        self.assertEqual(info.gesture, "FIST")
        self.assertTrue(info.grabbing)

    def test_point(self):
        info = self.run_g(make_hand(ext=(False, True, False, False, False)))
        self.assertEqual(info.gesture, "POINT")

    def test_pinch_hysteresis_and_scale_invariance(self):
        for scale in (50.0, 100.0, 400.0):
            a = HandAnalyzer()
            P = make_hand(pinch=0.2, scale=scale)
            self.assertTrue(a.update(P, (0.5, 0.5), 0.0, 0.30, 0.46).pinching)
            # 0.38 está entre engage e release: continua pinçando
            P2 = make_hand(pinch=0.38, scale=scale)
            self.assertTrue(a.update(P2, (0.5, 0.5), 0.03, 0.30, 0.46).pinching)
            P3 = make_hand(pinch=0.7, scale=scale)
            self.assertFalse(a.update(P3, (0.5, 0.5), 0.06, 0.30, 0.46).pinching)

    def test_gun_arm_and_trigger(self):
        a = HandAnalyzer()
        ext = (False, True, False, False, False)
        up, down = make_hand(ext=ext, thumb_up=True), make_hand(ext=ext, thumb_up=False)
        for i in range(4):
            info = a.update(up, (0.5, 0.5), i / 30.0, 0.30, 0.46)
        self.assertTrue(info.armed and not info.trigger)
        self.assertEqual(info.gesture, "GUN")
        for i in range(4, 7):
            info = a.update(down, (0.5, 0.5), i / 30.0, 0.30, 0.46)
        self.assertTrue(info.trigger)
        for i in range(7, 10):
            info = a.update(up, (0.5, 0.5), i / 30.0, 0.30, 0.46)
        self.assertFalse(info.trigger)
        self.assertTrue(info.armed)

    def test_thumb_tucked_point_never_fires_without_arming(self):
        a = HandAnalyzer()
        down = make_hand(ext=(False, True, False, False, False))
        for i in range(10):
            info = a.update(down, (0.5, 0.5), i / 30.0, 0.30, 0.46)
        self.assertFalse(info.trigger)

    def test_aim_direction_points_up(self):
        info = self.run_g(make_hand(ext=(False, True, False, False, False)))
        self.assertLess(info.aim[1], -0.9)

    def test_swipe(self):
        a = HandAnalyzer()
        P = make_hand()
        got = None
        for i in range(10):
            info = a.update(P, (0.2 + i * 0.05, 0.5), i * 0.03, 0.30, 0.46)
            got = got or info.swipe
        self.assertEqual(got, "right")


if __name__ == "__main__":
    unittest.main()


class TestPhysics(unittest.TestCase):
    def setUp(self):
        from openbox.config import Config
        from openbox.physics.world import World
        self.cfg = Config()
        self.World = World

    def test_stays_in_bounds_with_gravity(self):
        self.cfg.gravity = 1500
        w = self.World(1280, 720, self.cfg)
        b = w.add("orb", 640, 100)
        for _ in range(600):
            w.step(1 / 60)
        self.assertTrue(b.r <= b.y <= 720 - b.r + 1e-6)
        self.assertLess(math.hypot(b.vx, b.vy), 120)  # assentou

    def test_collision_separates(self):
        w = self.World(1280, 720, self.cfg)
        a = w.add("orb", 600, 360)
        c = w.add("orb", 610, 360)
        w.step(1 / 60)
        self.assertGreaterEqual(math.hypot(a.x - c.x, a.y - c.y), a.r + c.r - 1.0)

    def test_collider_pushes(self):
        w = self.World(1280, 720, self.cfg)
        b = w.add("orb", 600, 360)
        for _ in range(10):
            w.step(1 / 60, colliders=[(560, 360, 20, 900.0, 0.0)])
        self.assertGreater(b.vx, 100)

    def test_held_body_follows_target(self):
        w = self.World(1280, 720, self.cfg)
        b = w.add("cube", 300, 300)
        b.held_by.add(0)
        b.target = (800, 500)
        for _ in range(60):
            w.step(1 / 60)
        self.assertLess(math.hypot(b.x - 800, b.y - 500), 5)


class TestManager(unittest.TestCase):
    def test_edges_and_throw(self):
        from openbox.config import Config
        from openbox.core.view import CameraView
        from openbox.tracking.hand_tracker import Hand, Snapshot
        from openbox.tracking.manager import HandsManager

        class T:
            snapshot = Snapshot()
            events = []

        tr, cfg, view = T(), Config(), CameraView(1280, 720)
        mgr = HandsManager(tr, cfg, view)
        a = HandAnalyzer()

        def snap(seq, x, pinch):
            P = make_hand(pinch=0.2 if pinch else 0.9)
            n = np.zeros((21, 3))
            n[:, 0] = 0.5 + P[:, 0] / 2000.0 + x
            n[:, 1] = 0.5 + P[:, 1] / 2000.0
            info = a.update(P, (x + 0.5, 0.5), seq / 30.0, 0.30, 0.46)
            h = Hand(0, "Right", 0.9, n, 0.1, np.array([0.0, 0.0]), info)
            return Snapshot(seq, seq / 30.0, [h])

        downs, ups = 0, 0
        for i in range(30):
            tr.snapshot = snap(i, i * 0.01, pinch=(5 <= i < 20))
            mgr.update(1 / 60, i / 30.0 + 0.03)
            hv = mgr.views[0]
            downs += hv.pinch_down
            ups += hv.pinch_up
            hv.clear_edges()
        self.assertEqual((downs, ups), (1, 1))
        vx, vy = mgr.views[0].throw_velocity()
        self.assertGreater(vx, 300)       # 0.01*1280/(1/30) ≈ 384 px/s
        self.assertLess(abs(vy), 50)


class TestGameState(unittest.TestCase):
    def setUp(self):
        from openbox.config import Config
        from openbox.game.state import GameState
        self.cfg = Config()
        self.unlocked = []
        self.gs = GameState(self.cfg, on_unlock=self.unlocked.append)

    def test_combo_multiplies_and_expires(self):
        self.gs.bump_combo()
        self.gs.bump_combo()
        self.assertEqual(self.gs.add_score(50), 100)
        self.gs.update(3.0)
        self.assertEqual(self.gs.combo, 0)

    def test_achievement_unlocks_once(self):
        self.gs.unlock("bullseye")
        self.gs.unlock("bullseye")
        self.assertEqual(len(self.unlocked), 1)
        self.assertIn("bullseye", self.cfg.achievements)

    def test_tutorial_has_no_score_and_best_is_per_mode(self):
        self.gs.mode = "tutorial"
        self.assertEqual(self.gs.add_score(100), 0)
        self.gs.mode = "practice"
        self.gs.add_score(80)
        self.assertEqual(self.cfg.highscores["practice"], 80)

    def test_powerup_timers(self):
        self.gs.activate("slowmo")
        self.assertAlmostEqual(self.gs.time_factor, 0.35)
        self.gs.update(7.0)
        self.assertEqual(self.gs.time_factor, 1.0)


class TestFace(unittest.TestCase):
    def _pts(self, shift=0.0, tilt=0.0):
        import math as m
        base = dict(top=(0, -100), chin=(0, 100), left=(-80, 0), right=(80, 0), nose=(shift, 10), bridge=(0, -10),
                    eye_l_o=(-55, -20), eye_l_i=(-20, -20), eye_r_i=(20, -20), eye_r_o=(55, -20),
                    mouth_l=(-30, 60), mouth_r=(30, 60), lip_up=(0, 55), lip_lo=(0, 70), brow_l=(-40, -40), brow_r=(40, -40))
        c, s = m.cos(tilt), m.sin(tilt)
        return {k: np.array([x * c - y * s, x * s + y * c, 0.0]) for k, (x, y) in base.items()}

    def test_roll_yaw_scale(self):
        from openbox.tracking.face_tracker import face_pose
        p = face_pose(self._pts())
        self.assertAlmostEqual(p["roll"], 0.0, places=3)
        self.assertAlmostEqual(p["yaw"], 0.0, places=2)
        self.assertAlmostEqual(p["width"], 160.0, places=1)
        self.assertAlmostEqual(face_pose(self._pts(tilt=0.3))["roll"], 0.3, places=2)
        self.assertGreater(face_pose(self._pts(shift=30))["yaw"], 0.3)
        self.assertLess(face_pose(self._pts(shift=-30))["yaw"], -0.3)

    def test_hat_spring_follows_anchor(self):
        from openbox.core.view import CameraView
        from openbox.tracking.face_tracker import KEYS, Face
        from openbox.tracking.faces import FaceView
        fv, view = FaceView(0), CameraView(1280, 720)
        n = np.zeros((len(KEYS), 3)) + 0.5
        n[KEYS.index("top")] = (0.5, 0.3, 0)
        n[KEYS.index("chin")] = (0.5, 0.7, 0)
        fv.ingest(Face(0, n, 0.2), view)
        for _ in range(10):
            fv.advance(1 / 60)
        n2 = n.copy()
        n2[:, 0] += 0.2
        fv.ingest(Face(0, n2, 0.2), view)
        for _ in range(240):
            fv.advance(1 / 60)
        self.assertLess(float(np.hypot(*(fv.hat_pos - fv.anchor))), 3.0)
