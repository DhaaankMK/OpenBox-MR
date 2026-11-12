import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openbox.config import DIFFICULTIES, Config
from openbox.game import items
from openbox.game.creatures import Brain, Env, PERSONALITY
from openbox.game.tutorial import STEPS, Tutorial
from openbox.game.weapons import WEAPONS, WeaponState, ray_circle, ray_hits
from openbox.game.zombies import WaveDirector, ZTYPES


class Dummy:
    _n = 0

    def __init__(self, x=500, y=600, grounded=True):
        Dummy._n += 1
        self.id = Dummy._n
        self.x, self.y, self.vx, self.vy, self.angle, self.w = x, y, 0.0, 0.0, 0.0, 0.0
        self.hp, self.held_by, self.grounded, self.hit_speed = 50, set(), grounded, 0.0


class TestItems(unittest.TestCase):
    def test_catalog_integrity(self):
        ids = [i.id for i in items._ALL]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 60)
        for cat, _, _ in items.CATEGORIES:
            self.assertTrue(items.by_cat(cat), cat)
        for i in items.by_cat("criaturas"):
            self.assertIn(i.id, PERSONALITY)
        for i in items.by_cat("armas"):
            self.assertIn(i.id, WEAPONS)
        for f in Config().favorites:
            self.assertIn(f, items.ITEMS)


class TestWeapons(unittest.TestCase):
    def test_ray_hits_order_and_miss(self):
        t = [("a", 500, 0, 30, None), ("b", 300, 0, 30, None), ("c", 300, 200, 30, None)]
        hits = ray_hits(0, 0, 1, 0, t)
        self.assertEqual([h.target for h in hits], ["b", "a"])
        self.assertAlmostEqual(hits[0].dist, 270, places=3)
        self.assertIsNone(ray_circle(0, 0, 1, 0, 300, 100, 30))
        self.assertIsNone(ray_circle(0, 0, 1, 0, -300, 0, 30))     # atrás do atirador

    def test_headshot(self):
        hits = ray_hits(0, 0, 1, 0, [("z", 400, 40, 36, (400, 0, 20))])
        self.assertTrue(hits and hits[0].head)

    def test_ammo_rate_reload(self):
        ws = WeaponState(WEAPONS["pistol"])
        shots = 0
        for _ in range(600):
            ws.update(1 / 60)
            shots += ws.fire()
        self.assertGreater(shots, 12)            # recarregou ao menos uma vez
        self.assertLess(shots, 3.5 * 10 + 14)    # respeitou a cadência


class TestZombies(unittest.TestCase):
    def test_waves_scale_and_boss(self):
        d = WaveDirector(DIFFICULTIES["normal"], random.Random(1))
        cost = lambda n: sum(ZTYPES[z].cost for z, _ in d.build(n))
        self.assertGreater(cost(10), cost(1) * 3)
        self.assertIn("boss", [z for z, _ in d.build(5)])
        self.assertNotIn("boss", [z for z, _ in d.build(4)])

    def test_state_machine(self):
        d = WaveDirector(DIFFICULTIES["normal"], random.Random(2))
        spawned = []
        for _ in range(60 * 60):
            spawned += d.update(1 / 60, alive=len(spawned) and 0)
            if d.state == "fighting":
                break
        self.assertEqual(d.wave, 1)
        self.assertEqual(len(spawned), d.total)
        d.update(1 / 60, alive=0)
        self.assertEqual(d.state, "break")

    def test_difficulty_scales_hp(self):
        a = WaveDirector(DIFFICULTIES["facil"]); b = WaveDirector(DIFFICULTIES["dificil"])
        a.wave = b.wave = 3
        self.assertLess(a.hp_scale(), b.hp_scale())


class TestTutorial(unittest.TestCase):
    def test_flow(self):
        done = []
        t = Tutorial(on_finish=lambda: done.append(1))
        self.assertFalse(t.event("grab"))
        for s in STEPS[:-1]:
            for _ in range(s.count):
                t.event(s.need)
        self.assertTrue(t.finished and done)

    def test_skip_optional(self):
        t = Tutorial()
        while t.step.id != "hat":
            t.skip()
        t.skip_optional()
        self.assertEqual(t.step.id, "done")


class TestCreatures(unittest.TestCase):
    def run_brain(self, brain, b, env, secs=2.0):
        for _ in range(int(secs * 60)):
            brain.think(b, 1 / 60, env)
            b.x += b.vx / 60

    def test_flees_from_threat(self):
        b, br = Dummy(), Brain("robot", random.Random(3))
        env = Env(1280, 720, threats=[(400, 600, 30, 900.0)])
        self.run_brain(br, b, env)
        self.assertGreater(b.x, 520)                  # fugiu para a direita (ameaça à esquerda)
        self.assertEqual(br.expr, "scared")

    def test_zombie_chases_and_attacks(self):
        b, br = Dummy(x=100), Brain("zombie", random.Random(4))
        env = Env(1280, 720, target=(640, 650))
        self.run_brain(br, b, env, 12)
        self.assertTrue(br.attacking)
        self.assertGreater(b.x, 500)

    def test_hard_impact_stuns_and_hurts_mortal(self):
        b, br = Dummy(), Brain("zombie", random.Random(5))
        b.hit_speed = 1500
        ev = br.think(b, 1 / 60, Env(1280, 720, immortal=False))
        self.assertIn("hurt", ev)
        self.assertGreater(br.stun_t, 0)
        self.assertLess(b.hp, 50)

    def test_immortal_bot_survives(self):
        b, br = Dummy(), Brain("robot", random.Random(6))
        b.hp = 1
        b.hit_speed = 3000
        br.think(b, 1 / 60, Env(1280, 720, immortal=True))
        self.assertFalse(br.dead)

    def test_flyer_hovers_without_ground(self):
        b, br = Dummy(y=300, grounded=False), Brain("ghost", random.Random(7))
        env = Env(1280, 720)
        for _ in range(300):
            br.think(b, 1 / 60, env)
            b.y += b.vy / 60
        self.assertTrue(300 < b.y < 700)


class TestConfig(unittest.TestCase):
    def test_roundtrip_sections(self):
        import tempfile
        from pathlib import Path
        from openbox import config as C
        tmp = Path(tempfile.mkdtemp()) / "Configurações.json"
        old = C.CONFIG_FILE
        C.CONFIG_FILE = tmp
        try:
            Config.path = staticmethod(lambda: tmp)
            c = Config()
            c.posture, c.volume, c.hat = "em_pe", 0.3, "wizard"
            c.highscores = {"survival": 99}
            c.save()
            import json
            raw = json.loads(tmp.read_text(encoding="utf-8"))
            self.assertEqual(raw["jogo"]["postura"], "em_pe")
            self.assertEqual(raw["rosto"]["chapeu"], "wizard")
            c2 = Config.load()
            self.assertEqual((c2.posture, c2.volume, c2.hat, c2.highscores), ("em_pe", 0.3, "wizard", {"survival": 99}))
            tmp.write_text("{ quebrado", encoding="utf-8")
            self.assertEqual(Config.load().posture, "sentado")     # arquivo corrompido -> padrões
        finally:
            C.CONFIG_FILE = old
            Config.path = staticmethod(lambda: old)


if __name__ == "__main__":
    unittest.main()


class TestPhysicsExtra(unittest.TestCase):
    def setUp(self):
        from openbox.physics.world import World
        self.cfg = Config()
        self.cfg.gravity = 1400
        self.World = World

    def test_balloon_rises_and_ball_falls(self):
        w = self.World(1280, 720, self.cfg)
        b = w.add("balloon", 600, 500)
        c = w.add("anvil", 300, 100)
        for _ in range(240):
            w.step(1 / 60)
        self.assertLess(b.y, 200)
        self.assertGreater(c.y, 600)
        self.assertTrue(c.grounded)

    def test_magnet_pulls_neighbours(self):
        w = self.World(1280, 720, self.cfg)
        self.cfg.gravity = 0
        m = w.add("blackhole", 600, 360)
        o = w.add("orb", 800, 360)
        for _ in range(60):
            w.step(1 / 60)
        self.assertLess(o.x, 780)

    def test_hit_speed_recorded(self):
        w = self.World(1280, 720, self.cfg)
        b = w.add("orb", 600, 100, 0, 1500)
        for _ in range(60):
            w.step(1 / 60)
            if b.hit_speed > 0:
                break
        self.assertGreater(b.hit_speed, 260)
