"""Ponto de entrada interno (chamado pelo OpenBox.py já dentro do ambiente virtual)."""
from __future__ import annotations

import argparse
import sys


def selftest(light: bool) -> int:
    from . import APP_NAME, __version__
    from .config import Config
    from .paths import ASSETS, MODELS, SOUNDS
    problems = []
    for f in (MODELS / "hand_landmarker.task", MODELS / "face_landmarker.task", SOUNDS / "click.mp3", ASSETS / "brand" / "khyros-logo.png"):
        if not f.exists():
            problems.append(f"ausente: {f}")
    Config.load()
    if not light:
        import cv2, mediapipe, numpy, pygame  # noqa: F401, E401
        from .scenes import hub, loading, modes, play, settings  # noqa: F401
    print(f"{APP_NAME} v{__version__} — autoteste " + ("FALHOU: " + "; ".join(problems) if problems else "OK"))
    return 1 if problems else 0


def run(argv) -> int:
    ap = argparse.ArgumentParser(prog="OpenBox.py", description="OpenBox MR — Khyros Studio")
    ap.add_argument("--game", action="store_true", help="abre o jogo direto (uso interno do launcher)")
    ap.add_argument("--launcher", action="store_true", help="força a abertura do launcher")
    ap.add_argument("--no-camera", action="store_true", help="não abre a webcam (usa o mouse)")
    ap.add_argument("--no-intro", action="store_true", help="pula a intro da Khyros")
    ap.add_argument("--camera", type=int, default=None, help="índice da câmera")
    ap.add_argument("--mode", choices=["menu", "tutorial", "sandbox", "practice", "survival"], default=None)
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--windowed", action="store_true")
    ap.add_argument("--reset-config", action="store_true", help="restaura as configurações padrão")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--selftest-light", action="store_true")
    ap.add_argument("--reinstall", action="store_true")      # tratado pelo OpenBox.py
    ap.add_argument("--console", action="store_true")        # tratado pelo OpenBox.py
    args = ap.parse_args(argv)

    if args.selftest or args.selftest_light:
        return selftest(args.selftest_light)

    from .config import Config
    cfg = Config.load()
    if args.reset_config:
        cfg.reset_to_defaults()
        cfg.save()
    if args.camera is not None:
        cfg.camera_index = args.camera
    if args.fullscreen:
        cfg.fullscreen = True
    if args.windowed:
        cfg.fullscreen = False

    if args.launcher or (not args.game and not cfg.skip_launcher):
        from .launcher import Launcher
        Launcher().run()
        return 0

    from .core.app import App
    App(cfg, no_camera=args.no_camera, no_intro=args.no_intro, start_mode=args.mode).run()
    return 0
