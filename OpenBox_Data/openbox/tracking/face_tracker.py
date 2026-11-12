"""Rastreamento de rosto em thread própria (MediaPipe FaceLandmarker): posição, escala, inclinação (roll),
giro (yaw), cabeceio (pitch), boca aberta e piscadas — base para chapéus e acessórios."""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from .filters import OneEuro
from .hand_tracker import ensure_model

# landmarks usados (índices do modelo de 478 pontos)
FACE_IDX = dict(top=10, chin=152, left=234, right=454, nose=1, bridge=168, eye_l_o=33, eye_l_i=133,
                eye_r_i=362, eye_r_o=263, mouth_l=61, mouth_r=291, lip_up=13, lip_lo=14, brow_l=105, brow_r=334)
KEYS = list(FACE_IDX)
SEL = [FACE_IDX[k] for k in KEYS]
POS = {k: i for i, k in enumerate(KEYS)}
HOLD = 0.3


def face_pose(pts: Dict[str, np.ndarray]) -> dict:
    """Calcula pose/escala a partir dos pontos (dict nome -> (x, y[, z]) em unidades iguais para x e y)."""
    L, R = pts["left"][:2], pts["right"][:2]
    if L[0] > R[0]:
        L, R = R, L
    width = float(np.hypot(*(R - L))) or 1e-6
    top, chin, nose = pts["top"][:2], pts["chin"][:2], pts["nose"][:2]
    height = float(np.hypot(*(top - chin))) or 1e-6
    el = (pts["eye_l_o"][:2] + pts["eye_l_i"][:2]) / 2
    er = (pts["eye_r_o"][:2] + pts["eye_r_i"][:2]) / 2
    if el[0] > er[0]:
        el, er = er, el
    roll = math.atan2(er[1] - el[1], er[0] - el[0])
    mid_x = (L[0] + R[0]) / 2
    yaw = float(np.clip((nose[0] - mid_x) / width * 2.0, -1.0, 1.0))
    eye_mid_y = (el[1] + er[1]) / 2
    pitch = float(np.clip(((nose[1] - eye_mid_y) / height - 0.30) * 4.0, -1.0, 1.0))
    mouth = float(np.clip((np.hypot(*(pts["lip_up"][:2] - pts["lip_lo"][:2])) / height) * 9.0, 0.0, 1.0))
    return dict(width=width, height=height, roll=roll, yaw=yaw, pitch=pitch, mouth_open=mouth)


@dataclass
class Face:
    slot: int
    n: np.ndarray                      # (K,3) pontos filtrados, ordem KEYS (normalizados)
    width_n: float                     # largura do rosto / largura do frame
    roll: float = 0.0
    yaw: float = 0.0
    pitch: float = 0.0
    mouth_open: float = 0.0
    blink_l: float = 0.0
    blink_r: float = 0.0
    smile: float = 0.0
    stale: bool = False

    def pt(self, key: str) -> np.ndarray:
        return self.n[POS[key]]


@dataclass
class FaceSnapshot:
    seq: int = -1
    t: float = 0.0
    faces: List[Face] = field(default_factory=list)
    infer_ms: float = 0.0
    fps: float = 0.0


class _FTrack:
    def __init__(self, slot):
        self.slot = slot
        self.filt = OneEuro(min_cutoff=1.4, beta=9.0)
        self.nose = np.zeros(2)
        self.last = 0.0
        self.face: Optional[Face] = None
        self.sm = {"roll": 0.0, "yaw": 0.0, "pitch": 0.0, "mouth_open": 0.0}


class FaceTracker(threading.Thread):
    MAX_HZ = 24.0

    def __init__(self, camera, cfg, bus=None):
        super().__init__(name="openbox-face", daemon=True)
        self.camera, self.cfg, self.bus = camera, cfg, bus
        self.snapshot = FaceSnapshot()
        self.state = "loading"
        self.error = ""
        self._stop_evt = threading.Event()
        self._tracks: dict = {}
        self._last_ts = 0

    def stop(self):
        self._stop_evt.set()

    def _load(self):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self.mp = mp
        self.face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(ensure_model("face_landmarker.task"))),
            running_mode=vision.RunningMode.VIDEO, num_faces=2, output_face_blendshapes=True,
            min_face_detection_confidence=0.5, min_tracking_confidence=0.5))

    def run(self):
        import cv2
        try:
            self._load()
        except Exception as exc:
            self.state, self.error = "error", f"{type(exc).__name__}: {exc}"
            print(f"[face] indisponível: {self.error}")
            return
        self.state = "running"
        last_seq, n, fps, t_fps, last_run = -1, 0, 0.0, time.monotonic(), 0.0
        while not self._stop_evt.is_set():
            if not self.cfg.face_tracking:
                if self.snapshot.faces:
                    self.snapshot = FaceSnapshot(seq=self.snapshot.seq + 1, t=time.monotonic())
                self.state = "paused"
                time.sleep(0.1)
                continue
            self.state = "running"
            frame, seq, t_cap = self.camera.latest()
            now = time.monotonic()
            if frame is None or seq == last_seq or now - last_run < 1.0 / self.MAX_HZ:
                time.sleep(0.003)
                continue
            last_seq, last_run = seq, now
            t0 = time.perf_counter()
            try:
                ih, iw = frame.shape[:2]
                w = 480
                small = cv2.resize(frame, (w, int(ih * w / iw)), interpolation=cv2.INTER_AREA) if iw > w else frame
                rgb = np.ascontiguousarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
                ts = max(self._last_ts + 1, int(t_cap * 1000))
                self._last_ts = ts
                res = self.face.detect_for_video(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb), ts)
                faces = self._update(res, t_cap, rgb.shape[1], rgb.shape[0])
            except Exception as exc:
                print(f"[face] erro: {exc!r}")
                time.sleep(0.05)
                continue
            n += 1
            if now - t_fps >= 1.0:
                fps, n, t_fps = n / (now - t_fps), 0, now
            self.snapshot = FaceSnapshot(seq, t_cap, faces, (time.perf_counter() - t0) * 1000.0, fps)
        try:
            self.face.close()
        except Exception:
            pass

    def _update(self, res, t, sw, sh) -> List[Face]:
        dets = []
        for i, lms in enumerate(getattr(res, "face_landmarks", []) or []):
            arr = np.array([[lms[j].x, lms[j].y, lms[j].z] for j in SEL])
            bs = {}
            if getattr(res, "face_blendshapes", None) and i < len(res.face_blendshapes):
                bs = {c.category_name: c.score for c in res.face_blendshapes[i]}
            dets.append((arr, bs))
        pairs = sorted(((float(np.hypot(*(d[0][POS["nose"], :2] - tr.nose))), di, slot)
                        for di, d in enumerate(dets) for slot, tr in self._tracks.items()), key=lambda p: p[0])
        used_d, used_t, assign = set(), set(), {}
        for dist, di, slot in pairs:
            if dist > 0.35 or di in used_d or slot in used_t:
                continue
            assign[di] = slot
            used_d.add(di)
            used_t.add(slot)
        for di in range(len(dets)):
            if di not in assign:
                free = [s for s in (0, 1) if s not in self._tracks and s not in used_t]
                if free:
                    self._tracks[free[0]] = _FTrack(free[0])
                    assign[di] = free[0]
                    used_t.add(free[0])
        out = []
        for di, slot in assign.items():
            arr, bs = dets[di]
            tr = self._tracks[slot]
            n = tr.filt(arr, t)
            tr.nose, tr.last = n[POS["nose"], :2].copy(), t
            px = {k: np.array([n[POS[k]][0] * sw, n[POS[k]][1] * sh, 0.0]) for k in KEYS}   # x e y na mesma unidade
            p = face_pose(px)
            for key in ("roll", "yaw", "pitch"):
                tr.sm[key] += (p[key] - tr.sm[key]) * 0.55
            mouth = bs.get("jawOpen", p["mouth_open"])
            tr.sm["mouth_open"] += (mouth - tr.sm["mouth_open"]) * 0.5
            tr.face = Face(slot, n, p["width"] / sw, tr.sm["roll"], tr.sm["yaw"], tr.sm["pitch"], tr.sm["mouth_open"],
                           bs.get("eyeBlinkLeft", 0.0), bs.get("eyeBlinkRight", 0.0),
                           (bs.get("mouthSmileLeft", 0.0) + bs.get("mouthSmileRight", 0.0)) / 2)
            out.append(tr.face)
        for slot in list(self._tracks):
            if slot in used_t:
                continue
            tr = self._tracks[slot]
            if t - tr.last > HOLD or tr.face is None:
                del self._tracks[slot]
            else:
                f = tr.face
                out.append(Face(f.slot, f.n, f.width_n, f.roll, f.yaw, f.pitch, f.mouth_open, f.blink_l, f.blink_r, f.smile, True))
        out.sort(key=lambda f: f.slot)
        return out
