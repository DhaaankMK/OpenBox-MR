"""Páginas de configuração compartilhadas entre o Launcher e os Ajustes dentro do jogo.
Tudo grava direto no objeto Config (e, portanto, em «Configurações.json»)."""
from __future__ import annotations

from ..config import (DIFFICULTIES, DIFFICULTY_ORDER, POSTURE_ORDER, POSTURES, QUALITY_ORDER, RESOLUTIONS, SKELETON_STYLES)
from ..game import items as I
from .widgets import Button, Selector, Slider, Toggle

COLW = 400
HAND_COLORS = [("Ciano", "#00E4FF"), ("Rosa", "#FF54D6"), ("Verde", "#70FF9A"), ("Âmbar", "#FFC446"), ("Vermelho", "#FF4860"), ("Branco", "#FFFFFF")]
START_MODES = [("menu", "Menu principal"), ("tutorial", "Tutorial"), ("sandbox", "Sandbox"), ("practice", "Practice"), ("survival", "Sobrevivência")]


def _a(obj, name):
    return (lambda: getattr(obj, name)), (lambda v: setattr(obj, name, v))


def _sel(label, labels, values, obj, attr, tooltip=None, after=None):
    def get():
        try:
            return values.index(getattr(obj, attr))
        except ValueError:
            return 0

    def set_(i):
        setattr(obj, attr, values[i])
        if after:
            after()
    return Selector((0, 0, COLW, 50), label, labels, get, set_, tooltip=tooltip)


def _slider(label, obj, attr, lo, hi, fmt="{:.2f}"):
    g, s = _a(obj, attr)
    return Slider((0, 0, COLW, 56), label, g, s, lo, hi, fmt)


def _toggle(label, obj, attr, tooltip=None):
    g, s = _a(obj, attr)
    return Toggle((0, 0, COLW, 50), label, g, s, tooltip=tooltip)


def layout(widgets, x, y, cols=2, gap=14, colw=COLW):
    ys = [y] * cols
    for i, w in enumerate(widgets):
        c = i % cols if len(widgets) > 5 else 0
        w.rect.x, w.rect.y = x + c * (colw + gap), ys[c]
        ys[c] += w.rect.h + 12


def build_pages(cfg, actions: dict, launcher: bool = False):
    """Retorna [(nome, [widgets])]. `actions`: apply_camera, calibrate, fullscreen, reset, test_sound, detect, preview."""
    act = lambda k: actions.get(k) or (lambda: None)
    pages = []

    if launcher:
        pages.append(("Geral", [
            _sel("Iniciar em", [l for _, l in START_MODES], [v for v, _ in START_MODES], cfg, "start_mode", "Modo aberto direto ao jogar"),
            _sel("Postura", [POSTURES[p]["label"] for p in POSTURE_ORDER], POSTURE_ORDER, cfg, "posture", "Sentado ou em pé"),
            _sel("Dificuldade", [DIFFICULTIES[d]["label"] for d in DIFFICULTY_ORDER], DIFFICULTY_ORDER, cfg, "difficulty"),
            _sel("FPS alvo", ["30", "60", "90", "120"], [30, 60, 90, 120], cfg, "target_fps"),
            _toggle("Tela cheia", cfg, "fullscreen"),
            _toggle("Pular a intro da Khyros", cfg, "skip_intro"),
            _toggle("Abrir direto o jogo (sem launcher)", cfg, "skip_launcher", "Na próxima vez, o OpenBox.py inicia o jogo sem mostrar o launcher. Use --launcher para voltar."),
        ]))

    cam = [
        Selector((0, 0, COLW, 50), "Câmera", [f"#{i}" for i in range(5)], lambda: min(4, cfg.camera_index), lambda i: setattr(cfg, "camera_index", i)),
        _sel("Resolução", [f"{w}x{h}" for w, h in RESOLUTIONS], RESOLUTIONS, _Res(cfg), "value"),
        _sel("FPS da câmera", ["15", "30", "60"], [15, 30, 60], cfg, "cam_fps", "60 só se a câmera suportar"),
        _toggle("Espelhar imagem", cfg, "mirror"),
    ]
    if launcher:
        cam.append(Button((0, 0, COLW, 50), "Detectar câmeras", act("detect"), icon="camera", size=16))
        cam.append(Button((0, 0, COLW, 50), "Pré-visualizar câmera", act("preview"), icon="eye", size=16))
    else:
        cam.append(Button((0, 0, COLW, 50), "Aplicar câmera", act("apply_camera"), icon="camera", style="primary"))
    pages.append(("Câmera", cam))

    pages.append(("Rastreio", [
        _sel("Qualidade", [q.capitalize() for q in QUALITY_ORDER], QUALITY_ORDER, cfg, "quality", "Auto ajusta a resolução sozinho"),
        _slider("Suavização", cfg, "smoothing", 0, 1),
        _slider("Compensação de latência", cfg, "prediction", 0, 1),
        _slider("Confiança na detecção", cfg, "detect_conf", 0.2, 0.9),
        _slider("Confiança no rastreio", cfg, "track_conf", 0.2, 0.9),
        _sel("Gatilho da arma", ["Polegar (dedo-pistola)", "Pinça"], ["polegar", "pinca"], cfg, "trigger_mode"),
        _toggle("Punho agarra (em vez de esmagar)", cfg, "fist_grab"),
        _toggle("Clique por permanência", cfg, "dwell_click", "Aponte o indicador parado sobre um botão"),
        _slider("Tempo de permanência", cfg, "dwell_ms", 400, 2500, "{:.0f} ms"),
        _toggle("Mouse como ponteiro", cfg, "mouse_fallback"),
    ] + ([Button((0, 0, COLW, 50), "Calibrar pinça", act("calibrate"), icon="hand")] if not launcher else [])))

    pages.append(("Jogo", [
        _sel("Postura", [POSTURES[p]["label"] for p in POSTURE_ORDER], POSTURE_ORDER, cfg, "posture", "Em pé: alcance maior, botões maiores, mais suavização"),
        _sel("Dificuldade", [DIFFICULTIES[d]["label"] for d in DIFFICULTY_ORDER], DIFFICULTY_ORDER, cfg, "difficulty"),
        _slider("Gravidade", cfg, "gravity", 0, 2500, "{:.0f}"),
        _slider("Quique", cfg, "bounce", 0, 1.1),
        _slider("Resistência do ar", cfg, "air_drag", 0, 2),
        _slider("Velocidade do tempo", cfg, "time_scale", 0.2, 2.0, "{:.2f}x"),
        _toggle("Bots imortais", cfg, "bots_immortal", "Criaturas não morrem por impacto no Sandbox"),
        _toggle("Mãos empurram objetos", cfg, "hand_colliders"),
    ]))

    hats = [i for i in I.by_cat("chapeus") if i.kind == "hat"]
    accs = [i for i in I.by_cat("chapeus") if i.kind == "accessory"]
    pages.append(("Rosto", [
        _toggle("Rastrear o rosto", cfg, "face_tracking", "Desligue para economizar CPU"),
        _toggle("Paralaxe da cabeça", cfg, "head_parallax"),
        _sel("Chapéu", ["Nenhum"] + [h.name for h in hats], ["none"] + [h.id for h in hats], cfg, "hat"),
        _sel("Acessório", ["Nenhum"] + [a.name for a in accs], ["none"] + [a.id for a in accs], cfg, "accessory"),
    ]))

    vis = [
        _sel("Esqueleto da mão", [s.capitalize() for s in SKELETON_STYLES], SKELETON_STYLES, cfg, "skeleton_style"),
        _sel("Cor da mão 1", [n for n, _ in HAND_COLORS], [h for _, h in HAND_COLORS], cfg, "hand_color_0"),
        _sel("Cor da mão 2", [n for n, _ in HAND_COLORS], [h for _, h in HAND_COLORS], cfg, "hand_color_1"),
        _slider("Escurecer câmera", cfg, "camera_dim", 0, 0.85),
        _toggle("Vinheta", cfg, "vignette"),
        _toggle("Animações da interface", cfg, "ui_anim"),
        _toggle("Mostrar FPS", cfg, "show_fps"),
        _toggle("Partículas", cfg, "particles"),
        _toggle("Rastros dos objetos", cfg, "trails"),
    ]
    if not launcher:
        vis.append(Toggle((0, 0, COLW, 50), "Tela cheia (F11)", lambda: cfg.fullscreen, lambda v: act("fullscreen")() if v != cfg.fullscreen else None))
    pages.append(("Visual", vis))

    pages.append(("Áudio", [
        _slider("Volume", cfg, "volume", 0, 1),
        _toggle("Efeitos sonoros", cfg, "sfx"),
        Button((0, 0, COLW, 50), "Testar som", act("test_sound"), icon="play"),
    ]))
    return pages


class _Res:
    """Adaptador: resolução (largura, altura) como um único atributo."""

    def __init__(self, cfg):
        self.cfg = cfg

    @property
    def value(self):
        cur = (self.cfg.cam_width, self.cfg.cam_height)
        return cur if cur in RESOLUTIONS else RESOLUTIONS[1]

    @value.setter
    def value(self, v):
        self.cfg.cam_width, self.cfg.cam_height = v
