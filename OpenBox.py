#!/usr/bin/env python3
"""OpenBox MR — Khyros Studio.   ▶ Execute este arquivo (python OpenBox.py ou dois cliques).

Na primeira execução ele cria sozinho o ambiente virtual (OpenBox_Data/.venv) e instala as dependências.
Nas seguintes, só abre o launcher (ou o jogo direto, se você marcou isso). Os arquivos do jogo ficam na pasta OpenBox_Data (visível e aberta: nada escondido).

Opções úteis:  --launcher  --game  --no-camera  --mode tutorial|sandbox|practice|survival
               --reinstall (refaz a instalação)  --console (mantém o terminal visível)  --reset-config
"""
import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
HERE = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
DATA = HERE / "OpenBox_Data"
VENV = DATA / ".venv"
REQ = DATA / "requirements.txt"
STAMP = VENV / "OpenBox_Data_ok"
LOG = DATA / "ultimo.log"


def say(msg=""):
    print(msg, flush=True)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def in_venv() -> bool:
    try:
        return Path(sys.prefix).resolve() == VENV.resolve()
    except OSError:
        return False


def wanted_stamp() -> str:
    h = hashlib.sha256()
    h.update(REQ.read_bytes() if REQ.exists() else b"")
    h.update(f"{sys.version_info.major}.{sys.version_info.minor}".encode())
    return h.hexdigest()


def console(show: bool):
    if os.name != "nt":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 5 if show else 0)
    except Exception:
        pass


def pause(msg="Pressione Enter para fechar..."):
    try:
        if sys.stdin and sys.stdin.isatty() or os.name == "nt":
            input(msg)
    except Exception:
        pass


def find_compatible_python():
    """Se o Python atual for muito novo (>=3.13), tenta achar um 3.12/3.11/3.10 para criar a .venv."""
    if sys.version_info < (3, 13):
        return None
    cands = ([["py", f"-3.{v}"] for v in (12, 11, 10)] if os.name == "nt" else [[f"python3.{v}"] for v in (12, 11, 10)])
    for c in cands:
        try:
            out = subprocess.check_output(c + ["-c", "import sys;print(sys.version_info[:2])"], stderr=subprocess.DEVNULL, text=True)
            if out.strip():
                return c
        except Exception:
            continue
    return None


def ensure_env(force: bool = False) -> bool:
    """Cria a .venv e instala as dependências quando necessário. Retorna True se precisou instalar algo."""
    did = False
    if not venv_python().exists():
        say("╭──────────────────────────────────────────────╮")
        say("│  OpenBox MR — primeira execução              │")
        say("│  Criando o ambiente (só acontece uma vez)... │")
        say("╰──────────────────────────────────────────────╯")
        if sys.version_info >= (3, 13):
            say("Aviso: o MediaPipe funciona melhor com Python 3.10–3.12. Se a instalação falhar, use essas versões.")
        try:
            alt = find_compatible_python()
            if alt:
                say(f"Usando {' '.join(alt)} (o MediaPipe ainda não suporta o Python {sys.version_info.major}.{sys.version_info.minor}).")
                subprocess.check_call(alt + ["-m", "venv", str(VENV)])
            else:
                venv.EnvBuilder(with_pip=True, clear=False).create(str(VENV))
        except Exception as exc:
            say(f"Não foi possível criar o ambiente virtual: {exc}")
            say("No Linux, instale o pacote 'python3-venv' (ex.: sudo apt install python3-venv).")
            pause()
            sys.exit(1)
        did = True
    if force and STAMP.exists():
        STAMP.unlink()
    if os.environ.get("OPENBOX_SKIP_INSTALL") == "1":
        return did
    if not STAMP.exists() or STAMP.read_text().strip() != wanted_stamp():
        say("Instalando dependências (pygame, opencv, mediapipe, numpy)... pode levar alguns minutos.")
        py = str(venv_python())
        try:
            subprocess.check_call([py, "-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip"])
            # o pygame "puro" conflita com o pygame-ce (mesmo nome de módulo): remove se existir
            subprocess.call([py, "-m", "pip", "uninstall", "-y", "pygame"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.check_call([py, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQ)])
        except subprocess.CalledProcessError:
            say("\nFalha ao instalar as dependências. Verifique a internet e tente de novo (ou use --reinstall).")
            pause()
            sys.exit(1)
        STAMP.write_text(wanted_stamp())
        did = True
        say("Pronto! Abrindo o OpenBox MR...\n")
    return did


def main():
    args = sys.argv[1:]

    if FROZEN or in_venv():                         # dentro do ambiente (ou futuro .exe): roda de verdade
        sys.path.insert(0, str(DATA))
        from openbox.main import run
        sys.exit(run([a for a in args if a not in ("--reinstall", "--console")]))

    first = ensure_env(force="--reinstall" in args)
    keep_console = first or "--console" in args or "--selftest" in args or "--selftest-light" in args
    if not keep_console:
        console(False)

    env = {**os.environ, "OPENBOX_CHILD": "1"}
    cmd = [str(venv_python()), str(Path(__file__).resolve()), *[a for a in args if a != "--reinstall"]]
    if keep_console or os.name != "nt":
        rc = subprocess.call(cmd, env=env)
    else:                                            # Windows sem console: registra a saída em OpenBox_Data/ultimo.log
        with open(LOG, "w", encoding="utf-8", errors="replace") as log:
            rc = subprocess.call(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000)
        if rc != 0:
            console(True)
            say("O OpenBox MR fechou com erro. Últimas linhas do registro:\n")
            try:
                say("".join(LOG.read_text(encoding="utf-8", errors="replace").splitlines(True)[-25:]))
            except OSError:
                pass
            pause()
    sys.exit(rc)


if __name__ == "__main__":
    main()
