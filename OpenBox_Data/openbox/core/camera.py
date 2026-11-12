"""Captura de webcam em thread própria (sempre entrega o frame mais recente, sem fila)."""
from __future__ import annotations

import os
import threading
import time

import cv2


def _open_capture(index: int, width: int, height: int, fps: int):
    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY] if os.name == "nt" else [cv2.CAP_ANY]
    for backend in backends:
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  # mais FPS em USB
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        ok, frame = cap.read()
        if ok and frame is not None:
            return cap
        cap.release()
    return None


def probe_cameras(max_index: int = 5):
    """Lista índices de câmeras que abrem (usado pelo launcher; pode demorar um pouco)."""
    found = []
    for i in range(max_index):
        cap = _open_capture(i, 640, 480, 30)
        if cap is not None:
            found.append(i)
            cap.release()
    return found


class Camera:
    IDLE, OPENING, READY, ERROR = "idle", "opening", "ready", "error"

    def __init__(self, cfg):
        self.cfg = cfg
        self.state = self.IDLE
        self.info = ""
        self.fps = 0.0
        self._lock = threading.Lock()
        self._frame = None
        self._seq = 0
        self._t = 0.0
        self._stop = threading.Event()
        self._reopen = threading.Event()
        self._thread = threading.Thread(target=self._run, name="openbox-camera", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def reconfigure(self):
        """Reabre a câmera com os valores atuais do config (índice/resolução)."""
        self._reopen.set()

    def latest(self):
        with self._lock:
            return self._frame, self._seq, self._t

    @property
    def ready(self) -> bool:
        return self.state == self.READY

    def _run(self):
        cap = None
        fails = 0
        frames, t_fps = 0, time.monotonic()
        while not self._stop.is_set():
            if cap is None or self._reopen.is_set():
                self._reopen.clear()
                if cap is not None:
                    cap.release()
                    cap = None
                self.state = self.OPENING
                cap = _open_capture(self.cfg.camera_index, self.cfg.cam_width, self.cfg.cam_height, self.cfg.cam_fps)
                if cap is None:
                    self.state = self.ERROR
                    self.info = f"Câmera {self.cfg.camera_index} indisponível"
                    time.sleep(1.5)
                    continue
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self.info = f"{w}x{h}"
                self.state = self.READY
                fails = 0
            ok, frame = cap.read()
            if not ok or frame is None:
                fails += 1
                time.sleep(0.01)
                if fails > 60:
                    cap.release()
                    cap = None
                    self.state = self.ERROR
                    self.info = "Sinal da câmera perdido"
                    time.sleep(1.0)
                continue
            fails = 0
            if self.cfg.mirror:
                frame = cv2.flip(frame, 1)
            with self._lock:
                self._frame, self._t = frame, time.monotonic()
                self._seq += 1
            frames += 1
            now = time.monotonic()
            if now - t_fps >= 1.0:
                self.fps = frames / (now - t_fps)
                frames, t_fps = 0, now
        if cap is not None:
            cap.release()
