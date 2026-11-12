"""Caminhos do projeto.

Layout:   <raiz>/OpenBox.py · <raiz>/Configurações.json · <raiz>/OpenBox_Data/(openbox, assets, .venv)
"""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent
DATA = PKG.parent                      # OpenBox_Data
ROOT = DATA.parent                     # pasta onde está o OpenBox.py
if getattr(sys, "frozen", False):      # futuro .exe (PyInstaller)
    ROOT = Path(sys.executable).resolve().parent
    DATA = Path(getattr(sys, "_MEIPASS", ROOT / "OpenBox_Data"))

ASSETS = DATA / "assets"
MODELS = ASSETS / "models"
SOUNDS = ASSETS / "sounds"
BRAND = ASSETS / "brand"
VIDEO = ASSETS / "video"
CONFIG_FILE = ROOT / "Configurações.json"


def screenshots_dir() -> Path:
    d = ROOT / "Capturas"
    d.mkdir(parents=True, exist_ok=True)
    return d
