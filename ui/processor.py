"""streamlit-webrtc video processor: camera frame -> pose -> engine -> overlay -> frame."""
from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Optional

import av
import cv2
from streamlit_webrtc import VideoProcessorBase

from core.engine import CoachEngine, FrameState
from exercises.configs import EXERCISES
from ui.overlay import draw_overlay

logger = logging.getLogger(__name__)


class CoachProcessor(VideoProcessorBase):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.engine: Optional[CoachEngine] = None
        self.paused = False
        self.mirror = True
        self.tracker = None                     # created lazily in the video thread
        self.model_error: Optional[str] = None
        self.last_state = FrameState()

    # called from the Streamlit script thread
    def configure(self, exercise_key: str, reps: int, sets: int, rest_s: int) -> None:
        with self._lock:
            if self.engine is None or self.engine.ex.key != exercise_key:
                self.engine = CoachEngine(EXERCISES[exercise_key], reps, sets, rest_s)

    def snapshot(self) -> Optional[dict]:
        with self._lock:
            return self.engine.summary() if self.engine else None

    def _ensure_tracker(self) -> bool:
        if self.tracker is None and self.model_error is None:
            try:
                from core.pose import MediaPipePose
                self.tracker = MediaPipePose("lite")
            except Exception as e:              # e.g. model download blocked
                logger.exception("Failed to initialize MediaPipePose")
                self.model_error = f"{type(e).__name__}: {e}"
                print(f"Pose model error: {self.model_error}", file=sys.stderr, flush=True)
        return self.tracker is not None

    # called from the video thread, once per frame
    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        if self.mirror:
            img = cv2.flip(img, 1)

        with self._lock:
            engine, paused = self.engine, self.paused

        if engine is None:
            return av.VideoFrame.from_ndarray(img, format="bgr24")

        if not self._ensure_tracker():
            cv2.putText(img, "Pose model unavailable", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            if self.model_error:
                cv2.putText(img, self.model_error[:90], (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 1)
            return av.VideoFrame.from_ndarray(img, format="bgr24")

        pts = self.tracker.detect(img)
        with self._lock:
            if paused:
                st = FrameState(set_no=engine.set_no, sets_total=engine.sets,
                                reps_in_set=engine.reps_in_set, reps_target=engine.reps_per_set)
            else:
                st = engine.process(pts, time.monotonic())
            self.last_state = st
        draw_overlay(img, st, engine.ex, pts, paused)
        return av.VideoFrame.from_ndarray(img, format="bgr24")
