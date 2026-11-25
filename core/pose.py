"""Pose backends. They all return {"left_knee": (x_px, y_px, visibility), ...}.

MediaPipe Tasks API (PoseLandmarker). The .task model file is downloaded once on first
use into ./models/. To swap in another model (YOLO-pose, ViTPose, RTMPose from Hugging
Face), implement the same `detect(bgr_image) -> dict` and pass it to the processor.
"""
from __future__ import annotations

import os
import time
import urllib.request
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

# MediaPipe BlazePose landmark indices for the joints we use
LANDMARKS = {
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13, "right_elbow": 14,
    "left_wrist": 15, "right_wrist": 16,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
}

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_URLS = {
    "lite": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
    "full": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
    "heavy": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task",
}


class PoseBackend(Protocol):
    def detect(self, bgr: np.ndarray) -> dict: ...


def ensure_model(variant: str = "lite") -> str:
    path = MODEL_DIR / f"pose_landmarker_{variant}.task"
    if not path.exists() or path.stat().st_size < 1_000_000:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(MODEL_URLS[variant], tmp)
        os.replace(tmp, path)
    return str(path)


class MediaPipePose:
    """Single-person pose landmarks from a BGR frame."""

    def __init__(self, variant: str = "lite", detect_width: int = 640):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        self._w = detect_width
        self._last_ts = 0
        opts = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(
                model_asset_buffer=Path(ensure_model(variant)).read_bytes(),
                delegate=mp_python.BaseOptions.Delegate.CPU,
            ),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._lm = vision.PoseLandmarker.create_from_options(opts)

    def detect(self, bgr: np.ndarray) -> dict:
        h, w = bgr.shape[:2]
        small = bgr if w <= self._w else cv2.resize(bgr, (self._w, int(h * self._w / w)))
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        mp_img = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        ts = max(int(time.monotonic() * 1000), self._last_ts + 1)   # must strictly increase
        self._last_ts = ts
        res = self._lm.detect_for_video(mp_img, ts)
        if not res.pose_landmarks:
            return {}
        lms = res.pose_landmarks[0]
        return {
            name: (lms[i].x * w, lms[i].y * h, float(lms[i].visibility or 0.0))
            for name, i in LANDMARKS.items()
        }
