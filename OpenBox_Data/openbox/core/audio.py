"""Áudio: sons do Pack + efeitos sintetizados (sem arquivos extras)."""
from __future__ import annotations

import math

import numpy as np
import pygame

from ..paths import SOUNDS

SR = 44100
FILES = {"click": "click.mp3", "erro": "erro.mp3", "notificacao": "notificacao.wav", "sucesso": "sucesso.mp3"}


def _make(wave: np.ndarray, vol: float = 0.5):
    wave = np.clip(wave, -1.0, 1.0)
    init = pygame.mixer.get_init()
    ch = init[2] if init and len(init) > 2 else 2
    data = wave if ch == 1 else np.repeat(wave[:, None], ch, axis=1)
    arr = np.ascontiguousarray((data * 32767 * vol).astype(np.int16))
    return pygame.sndarray.make_sound(arr)


def _tone(freq, dur, sweep=0.0, decay=7.0, harm=0.0, attack=0.004):
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    f = freq + sweep * (t / dur)
    ph = 2 * math.pi * np.cumsum(f) / SR
    w = np.sin(ph) + harm * np.sin(2 * ph)
    env = np.exp(-decay * t / dur) * (1 - np.exp(-t / attack))
    return w * env


def _noise(dur, decay=6.0, smooth=24):
    n = int(SR * dur)
    x = np.random.uniform(-1, 1, n)
    k = np.ones(smooth) / smooth
    x = np.convolve(x, k, mode="same")
    t = np.linspace(0, 1, n)
    return x * np.exp(-decay * t) * 4.0


class Audio:
    def __init__(self, cfg):
        self.cfg = cfg
        self.sounds: dict = {}
        self.ok = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(SR, -16, 2, 512)
            self.ok = True
        except Exception as exc:
            print(f"[audio] mixer indisponível: {exc!r}")
            return
        for name, fname in FILES.items():
            try:
                self.sounds[name] = pygame.mixer.Sound(str(SOUNDS / fname))
            except Exception as exc:
                print(f"[audio] não carregou {fname}: {exc!r}")
        try:
            self._synth()
        except Exception as exc:
            print(f"[audio] síntese falhou: {exc!r}")

    def _synth(self):
        S = self.sounds
        S["tick"] = _make(_tone(1900, 0.035, decay=9), 0.16)
        S["grab"] = _make(_tone(420, 0.09, sweep=260, decay=6, harm=0.3), 0.35)
        S["release"] = _make(_tone(640, 0.11, sweep=-300, decay=6, harm=0.2), 0.30)
        S["thud"] = _make(_tone(110, 0.16, sweep=-50, decay=7, harm=0.5), 0.55)
        S["whoosh"] = _make(_noise(0.28, decay=5.0, smooth=40), 0.30)
        S["pop"] = _make(_tone(900, 0.12, sweep=900, decay=8, harm=0.2), 0.40)
        S["spawn"] = _make(_tone(300, 0.2, sweep=700, decay=5, harm=0.25), 0.35)
        S["count"] = _make(_tone(660, 0.14, decay=6), 0.40)
        S["go"] = _make(_tone(990, 0.28, decay=4, harm=0.3), 0.45)
        S["boot"] = _make(_tone(70, 1.1, sweep=60, decay=3, harm=0.6) + 0.4 * _tone(280, 1.1, sweep=280, decay=4), 0.55)
        S["boom"] = _make(_tone(90, 0.42, sweep=-60, decay=5, harm=0.8) + 0.5 * _noise(0.42, decay=4.0, smooth=30), 0.6)
        S["power"] = _make(_tone(420, 0.3, sweep=800, decay=4, harm=0.25), 0.4)
        S["combo"] = _make(_tone(1000, 0.18, sweep=900, decay=6, harm=0.2), 0.4)
        S["shot_pistol"] = _make(_noise(0.12, decay=9.0, smooth=6) * 0.7 + _tone(190, 0.12, sweep=-120, decay=8, harm=0.4), 0.55)
        S["shot_smg"] = _make(_noise(0.08, decay=10.0, smooth=5) * 0.6 + _tone(240, 0.08, sweep=-100, decay=9, harm=0.3), 0.4)
        S["shot_shotgun"] = _make(_noise(0.32, decay=6.0, smooth=18) + _tone(85, 0.32, sweep=-40, decay=6, harm=0.6), 0.7)
        S["shot_sniper"] = _make(_noise(0.5, decay=5.0, smooth=10) * 0.9 + _tone(70, 0.5, sweep=-40, decay=4, harm=0.5), 0.75)
        S["shot_laser"] = _make(_tone(1500, 0.2, sweep=-1000, decay=4.5, harm=0.5), 0.35)
        S["shot_rocket"] = _make(_noise(0.55, decay=3.5, smooth=40) * 0.8 + _tone(120, 0.55, sweep=60, decay=3, harm=0.5), 0.7)
        S["hit"] = _make(_tone(170, 0.1, sweep=-80, decay=7, harm=0.6), 0.45)
        S["groan"] = _make(_tone(95, 0.7, sweep=-30, decay=2.6, harm=1.0) * 0.8, 0.45)
        S["coin"] = _make(_tone(1500, 0.16, sweep=400, decay=7, harm=0.3), 0.4)
        S["over"] = _make(_tone(440, 0.6, sweep=-300, decay=4, harm=0.4), 0.45)

    def play(self, name: str, vol: float = 1.0):
        if not self.ok or not self.cfg.sfx:
            return
        snd = self.sounds.get(name)
        if snd is not None:
            snd.set_volume(max(0.0, min(1.0, vol * self.cfg.volume)))
            snd.play()
