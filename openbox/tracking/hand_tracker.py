"""Rastreamento de mãos em thread própria: One-Euro, IDs estáveis (associação com predição),
hold com extrapolação, resolução adaptativa, medição de luz e gestos."""
from __future__ import annotations

import threading
import time
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional

import cv2
import numpy as np

from ..paths import MODELS
from .filters import OneEuro
from .gestures import GestureInfo, HandAnalyzer

MODEL_URLS = {
    "hand_landmarker.task": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
}
HOLD_SECONDS = 0.25   # mantém a mão "viva" após perder a detecção (evita soltar objetos por 1 frame ruim)


@dataclass
class Hand:
    slot: int
    label: str
    score: float
    n: np.ndarray            # (21,3) landmarks filtrados, normalizados
    size_n: float            # comprimento da palma como fração da largura do frame
    vel_n: np.ndarray        # (2,) velocidade da palma (normalizado/s)
    info: GestureInfo
    stale: bool = False


@dataclass
class Snapshot:
    seq: int = -1
    t: float = 0.0
    hands: List[Hand] = field(default_factory=list)
    head: Optional[tuple] = None    # compatibilidade (o rosto agora tem thread própria)
    infer_ms: float = 0.0
    fps: float = 0.0
    brightness: float = 128.0
    infer_w: int = 640


class _Track:
    def __init__(self, slot: int):
        self.slot = slot
        self.filt = OneEuro()
        self.analyzer = HandAnalyzer()
        self.wrist = np.zeros(2)
        self.last_seen = 0.0
        self.prev_palm = None
        self.prev_t = 0.0
        self.vel = np.zeros(2)
        self.hand: Optional[Hand] = None


def ensure_model(name: str):
    path = MODELS / name
    if path.exists():
        return path
    MODELS.mkdir(parents=True, exist_ok=True)
    print(f"[tracker] baixando {name}...")
    urllib.request.urlretrieve(MODEL_URLS[name], path)
    return path


class HandTracker(threading.Thread):
    def __init__(self, camera, cfg, bus=None):
        super().__init__(name="openbox-hands", daemon=True)
        self.camera, self.cfg, self.bus = camera, cfg, bus
        self.snapshot = Snapshot()
        self.state = "loading"
        self.error = ""
        self.events: deque = deque(maxlen=32)   # (slot, 'swipe_left' | 'swipe_right')
        self._stop_evt = threading.Event()
        self._tracks: dict = {}
        self._last_ts = 0
        self._infer_w = 640
        self._ema_ms = 10.0
        self._brightness = 128.0

    def stop(self):
        self._stop_evt.set()

    def _load(self):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self.mp = mp
        self.hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(ensure_model("hand_landmarker.task"))),
            running_mode=vision.RunningMode.VIDEO, num_hands=2,
            min_hand_detection_confidence=self.cfg.detect_conf,
            min_hand_presence_confidence=max(0.3, self.cfg.detect_conf - 0.05),
            min_tracking_confidence=self.cfg.track_conf))

    # ------------------------------------------------------------------ loop
    def run(self):
        try:
            self._load()
        except Exception as exc:
            self.state, self.error = "error", f"{type(exc).__name__}: {exc}"
            print(f"[tracker] falha ao iniciar: {self.error}")
            if self.bus:
                self.bus.emit("tracker_error", message=self.error)
            return
        self.state = "running"
        last_seq, n_frames, fps, t_fps, frame_i = -1, 0, 0.0, time.monotonic(), 0
        self._infer_w = max(self.cfg.q["infer_w"], self.cfg.post["infer_min"] if self.cfg.q["adaptive"] else 0)
        while not self._stop_evt.is_set():
            frame, seq, t_cap = self.camera.latest()
            if frame is None or seq == last_seq:
                time.sleep(0.002)
                continue
            last_seq = seq
            t0 = time.perf_counter()
            try:
                hands = self._process(frame, t_cap, frame_i)
            except Exception as exc:
                print(f"[tracker] erro no frame: {exc!r}")
                time.sleep(0.05)
                continue
            ms = (time.perf_counter() - t0) * 1000.0
            self._adapt(ms, frame_i)
            frame_i += 1
            n_frames += 1
            now = time.monotonic()
            if now - t_fps >= 1.0:
                fps, n_frames, t_fps = n_frames / (now - t_fps), 0, now
            self.snapshot = Snapshot(seq, t_cap, hands, None, ms, fps, self._brightness, self._infer_w)
        try:
            self.hands.close()
        except Exception:
            pass

    def _adapt(self, ms: float, frame_i: int):
        """Resolução adaptativa: sobe quando há folga, desce quando a inferência passa do orçamento."""
        q = self.cfg.q
        if not q["adaptive"]:
            self._infer_w = q["infer_w"]
            return
        self._ema_ms = 0.9 * self._ema_ms + 0.1 * ms
        if frame_i % 30 != 0:
            return
        lo = self.cfg.post["infer_min"]
        if self._ema_ms > 24 and self._infer_w > lo:
            self._infer_w = max(lo, self._infer_w - 80)
        elif self._ema_ms < 11 and self._infer_w < 960:
            self._infer_w = min(960, self._infer_w + 80)

    # --------------------------------------------------------------- processamento
    def _filter_params(self):
        s = min(1.0, self.cfg.smoothing + self.cfg.post["smooth_bias"])
        return 3.0 - 2.6 * s, 10.0   # min_cutoff (Hz), beta

    def _process(self, frame, t_cap, frame_i):
        ih, iw = frame.shape[:2]
        w = self._infer_w
        small = cv2.resize(frame, (w, int(ih * w / iw)), interpolation=cv2.INTER_AREA) if iw > w else frame
        if frame_i % 10 == 0:
            self._brightness = float(cv2.cvtColor(cv2.resize(small, (48, 27)), cv2.COLOR_BGR2GRAY).mean())
        rgb = np.ascontiguousarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        sh, sw = rgb.shape[:2]
        mp_img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        ts = max(self._last_ts + 1, int(t_cap * 1000))
        self._last_ts = ts
        res = self.hands.detect_for_video(mp_img, ts)
        dets = []
        for i, lms in enumerate(getattr(res, "hand_landmarks", []) or []):
            arr = np.array([[p.x, p.y, p.z] for p in lms], dtype=np.float64)
            cat = res.handedness[i][0] if res.handedness and res.handedness[i] else None
            dets.append((arr, cat.category_name if cat else "?", float(cat.score) if cat else 0.0))
        return self._update_tracks(dets, t_cap, sw, sh)

    def _update_tracks(self, dets, t, sw, sh) -> List[Hand]:
        # 1) associação gulosa pela distância ao pulso PREVISTO (pulso + velocidade * dt)
        pairs = []
        for di, det in enumerate(dets):
            for slot, tr in self._tracks.items():
                pred = tr.wrist + tr.vel * min(0.2, max(0.0, t - tr.last_seen))
                pairs.append((float(np.hypot(*(det[0][0, :2] - pred))), di, slot))
        pairs.sort(key=lambda p: p[0])
        used_d, used_t, assign = set(), set(), {}
        for dist, di, slot in pairs:
            if dist > 0.4 or di in used_d or slot in used_t:
                continue
            assign[di] = slot
            used_d.add(di)
            used_t.add(slot)
        for di in range(len(dets)):
            if di not in assign:
                free = [s for s in (0, 1) if s not in self._tracks and s not in used_t]
                if not free:
                    continue
                self._tracks[free[0]] = _Track(free[0])
                assign[di] = free[0]
                used_t.add(free[0])

        out: List[Hand] = []
        min_c, beta = self._filter_params()
        bias = self.cfg.post["pinch_bias"]
        engage, release = self.cfg.pinch_engage + bias, self.cfg.pinch_release + bias
        for di, slot in assign.items():
            arr, label, score = dets[di]
            tr = self._tracks[slot]
            tr.filt.min_cutoff, tr.filt.beta = min_c, beta
            n = tr.filt(arr, t)
            tr.wrist = n[0, :2].copy()
            tr.last_seen = t
            P = n * np.array([sw, sh, sw])
            palm = n[[0, 5, 9, 13, 17], :2].mean(axis=0)
            if tr.prev_palm is not None and t > tr.prev_t:
                v = (palm - tr.prev_palm) / (t - tr.prev_t)
                tr.vel = 0.6 * v + 0.4 * tr.vel
            tr.prev_palm, tr.prev_t = palm, t
            info = tr.analyzer.update(P, palm, t, engage, release, self.cfg.fist_grab)
            if info.swipe:
                self.events.append((slot, f"swipe_{info.swipe}"))
            tr.hand = Hand(slot, label, score, n, info.size / sw, tr.vel.copy(), info)
            out.append(tr.hand)

        # 2) não detectadas: mantém por HOLD_SECONDS, extrapolando com velocidade amortecida
        for slot in list(self._tracks):
            if slot in used_t:
                continue
            tr = self._tracks[slot]
            age = t - tr.last_seen
            if age > HOLD_SECONDS or tr.hand is None:
                del self._tracks[slot]
                continue
            h = tr.hand
            shift = tr.vel * age * 0.6 * (1.0 - age / HOLD_SECONDS)
            n = h.n.copy()
            n[:, 0] += shift[0]
            n[:, 1] += shift[1]
            out.append(Hand(h.slot, h.label, h.score, n, h.size_n, h.vel_n, h.info, stale=True))
        out.sort(key=lambda h: h.slot)
        return out
