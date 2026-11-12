"""Configurações do OpenBox MR — tudo salvo em «Configurações.json» (na raiz, ao lado do OpenBox.py)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields

from .paths import CONFIG_FILE

# Perfis de qualidade: custo do rastreamento e dos efeitos. "auto" ajusta a resolução sozinho.
QUALITY = {
    "auto": dict(infer_w=640, particles=0.8, glow=True, adaptive=True),
    "performance": dict(infer_w=480, particles=0.5, glow=False, adaptive=False),
    "balanced": dict(infer_w=640, particles=0.8, glow=True, adaptive=False),
    "ultra": dict(infer_w=960, particles=1.0, glow=True, adaptive=False),
}
QUALITY_ORDER = ["auto", "performance", "balanced", "ultra"]
RESOLUTIONS = [(640, 480), (1280, 720), (1920, 1080)]
SKELETON_STYLES = ["neon", "minimal", "solid", "off"]

POSTURES = {
    "sentado": dict(label="Sentado", hit_pad=0, cell=64, grab_reach=1.0, smooth_bias=0.0, pinch_bias=0.0,
                    collider_min=9.0, cursor=1.0, infer_min=480),
    "em_pe": dict(label="Em pé", hit_pad=10, cell=78, grab_reach=1.45, smooth_bias=0.15, pinch_bias=0.04,
                  collider_min=16.0, cursor=1.3, infer_min=800),
}
POSTURE_ORDER = ["sentado", "em_pe"]

DIFFICULTIES = {
    "facil": dict(label="Fácil", hp=0.75, count=0.75, dmg=0.7, coins=1.2),
    "normal": dict(label="Normal", hp=1.0, count=1.0, dmg=1.0, coins=1.0),
    "dificil": dict(label="Difícil", hp=1.4, count=1.35, dmg=1.4, coins=0.9),
}
DIFFICULTY_ORDER = ["facil", "normal", "dificil"]

DEFAULT_FAVORITES = ["orb", "basketball", "crate", "barrel", "robot", "slime", "zombie", "pistol"]


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


@dataclass
class Config:
    # --- câmera
    camera_index: int = 0
    cam_width: int = 1280
    cam_height: int = 720
    cam_fps: int = 30
    mirror: bool = True
    # --- rastreamento das mãos
    quality: str = "auto"
    smoothing: float = 0.55
    prediction: float = 0.55
    pinch_engage: float = 0.30
    pinch_release: float = 0.46
    fist_grab: bool = False
    detect_conf: float = 0.55
    track_conf: float = 0.5
    # --- rosto / chapéus
    face_tracking: bool = True
    head_parallax: bool = True
    hat: str = "none"
    accessory: str = "none"
    # --- jogo
    posture: str = "sentado"
    difficulty: str = "normal"
    gravity: float = 1400.0
    bounce: float = 0.72
    air_drag: float = 0.35
    time_scale: float = 1.0
    bots_immortal: bool = True
    hand_colliders: bool = True
    trigger_mode: str = "polegar"          # "polegar" (gatilho de dedo) | "pinca"
    favorites: list = field(default_factory=lambda: list(DEFAULT_FAVORITES))
    # --- interação
    dwell_click: bool = True
    dwell_ms: int = 900
    mouse_fallback: bool = True
    # --- visual
    camera_dim: float = 0.28
    skeleton_style: str = "neon"
    show_fps: bool = True
    particles: bool = True
    trails: bool = True
    fullscreen: bool = False
    target_fps: int = 60
    ui_anim: bool = True
    vignette: bool = True
    hand_color_0: str = "#00E4FF"
    hand_color_1: str = "#FF54D6"
    # --- áudio
    volume: float = 0.7
    sfx: bool = True
    # --- launcher
    skip_launcher: bool = False
    skip_intro: bool = False
    start_mode: str = "menu"            # menu | tutorial | sandbox | practice | survival
    # --- progresso
    highscores: dict = field(default_factory=dict)
    achievements: list = field(default_factory=list)
    tutorial_done: bool = False

    # ---- derivados ----
    @property
    def q(self) -> dict:
        return QUALITY.get(self.quality, QUALITY["balanced"])

    @property
    def post(self) -> dict:
        return POSTURES.get(self.posture, POSTURES["sentado"])

    @property
    def diff(self) -> dict:
        return DIFFICULTIES.get(self.difficulty, DIFFICULTIES["normal"])

    def hand_color(self, slot: int):
        s = (self.hand_color_0 if slot == 0 else self.hand_color_1).lstrip("#")
        try:
            return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return (0, 228, 255) if slot == 0 else (255, 84, 214)

    def clamp(self) -> "Config":
        self.camera_index = int(_clamp(self.camera_index, 0, 9))
        self.cam_width = int(_clamp(self.cam_width, 320, 3840))
        self.cam_height = int(_clamp(self.cam_height, 240, 2160))
        self.cam_fps = int(_clamp(self.cam_fps, 15, 120))
        self.smoothing = _clamp(float(self.smoothing), 0.0, 1.0)
        self.prediction = _clamp(float(self.prediction), 0.0, 1.0)
        self.pinch_engage = _clamp(float(self.pinch_engage), 0.10, 0.60)
        self.pinch_release = _clamp(float(self.pinch_release), self.pinch_engage + 0.06, 0.95)
        self.detect_conf = _clamp(float(self.detect_conf), 0.2, 0.9)
        self.track_conf = _clamp(float(self.track_conf), 0.2, 0.9)
        self.camera_dim = _clamp(float(self.camera_dim), 0.0, 0.85)
        self.volume = _clamp(float(self.volume), 0.0, 1.0)
        self.dwell_ms = int(_clamp(self.dwell_ms, 400, 2500))
        self.bounce = _clamp(float(self.bounce), 0.0, 1.1)
        self.air_drag = _clamp(float(self.air_drag), 0.0, 3.0)
        self.time_scale = _clamp(float(self.time_scale), 0.2, 2.0)
        self.gravity = _clamp(float(self.gravity), -1500.0, 3000.0)
        self.target_fps = int(_clamp(self.target_fps, 30, 240))
        for name, table, default in (("quality", QUALITY, "auto"), ("posture", POSTURES, "sentado"),
                                     ("difficulty", DIFFICULTIES, "normal")):
            if getattr(self, name) not in table:
                setattr(self, name, default)
        if self.skeleton_style not in SKELETON_STYLES:
            self.skeleton_style = "neon"
        if self.start_mode not in ("menu", "tutorial", "sandbox", "practice", "survival"):
            self.start_mode = "menu"
        if self.trigger_mode not in ("polegar", "pinca"):
            self.trigger_mode = "polegar"
        if not isinstance(self.highscores, dict):
            self.highscores = {}
        if not isinstance(self.achievements, list):
            self.achievements = []
        if not isinstance(self.favorites, list) or not self.favorites:
            self.favorites = list(DEFAULT_FAVORITES)
        self.favorites = [str(x) for x in self.favorites][:8]
        return self

    # ---- persistência (arquivo organizado em seções, com chaves em português) ----
    SECTIONS = {
        "camera": [("camera_index", "indice"), ("cam_width", "largura"), ("cam_height", "altura"), ("cam_fps", "fps"), ("mirror", "espelhar")],
        "rastreamento": [("quality", "qualidade"), ("smoothing", "suavizacao"), ("prediction", "compensacao_latencia"),
                         ("pinch_engage", "pinca_fechar"), ("pinch_release", "pinca_abrir"), ("fist_grab", "punho_agarra"),
                         ("detect_conf", "confianca_deteccao"), ("track_conf", "confianca_rastreio")],
        "rosto": [("face_tracking", "ativo"), ("head_parallax", "paralaxe"), ("hat", "chapeu"), ("accessory", "acessorio")],
        "jogo": [("posture", "postura"), ("difficulty", "dificuldade"), ("gravity", "gravidade"), ("bounce", "quique"),
                 ("air_drag", "resistencia_ar"), ("time_scale", "escala_tempo"), ("bots_immortal", "bots_imortais"),
                 ("hand_colliders", "maos_empurram"), ("trigger_mode", "gatilho"), ("favorites", "favoritos")],
        "interacao": [("dwell_click", "clique_permanencia"), ("dwell_ms", "tempo_permanencia_ms"), ("mouse_fallback", "mouse_como_ponteiro")],
        "visual": [("camera_dim", "escurecer_camera"), ("skeleton_style", "estilo_esqueleto"), ("show_fps", "mostrar_fps"),
                   ("particles", "particulas"), ("trails", "rastros"), ("fullscreen", "tela_cheia"), ("target_fps", "fps_alvo"),
                   ("ui_anim", "animacoes"), ("vignette", "vinheta"), ("hand_color_0", "cor_mao_1"), ("hand_color_1", "cor_mao_2")],
        "audio": [("volume", "volume"), ("sfx", "efeitos")],
        "launcher": [("skip_launcher", "pular_launcher"), ("skip_intro", "pular_intro"), ("start_mode", "iniciar_em")],
        "progresso": [("highscores", "recordes"), ("achievements", "conquistas"), ("tutorial_done", "tutorial_concluido")],
    }

    @staticmethod
    def path():
        return CONFIG_FILE

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        try:
            data = json.loads(cls.path().read_text(encoding="utf-8"))
            for section, pairs in cls.SECTIONS.items():
                block = data.get(section, {})
                if not isinstance(block, dict):
                    continue
                for attr, key in pairs:
                    if key in block:
                        setattr(cfg, attr, block[key])
        except (OSError, ValueError):
            pass
        return cfg.clamp()

    def to_dict(self) -> dict:
        self.clamp()
        out = {"versao": 2, "aviso": "Gerado pelo OpenBox MR. Pode editar com o jogo fechado."}
        for section, pairs in self.SECTIONS.items():
            out[section] = {key: getattr(self, attr) for attr, key in pairs}
        return out

    def save(self) -> None:
        try:
            tmp = self.path().with_suffix(".tmp")
            tmp.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path())
        except OSError:
            pass

    def reset_to_defaults(self, keep_progress: bool = True) -> None:
        keep = (dict(self.highscores), list(self.achievements), self.tutorial_done)
        fresh = Config()
        for f in fields(Config):
            setattr(self, f.name, getattr(fresh, f.name))
        if keep_progress:
            self.highscores, self.achievements, self.tutorial_done = keep
