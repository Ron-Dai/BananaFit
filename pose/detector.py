import os
import urllib.request

import cv2
import mediapipe as mp
import numpy as np

_MODEL_URL = (
    'https://storage.googleapis.com/mediapipe-models/'
    'pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task'
)
_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'pose_landmarker.task')


def _ensure_model():
    if not os.path.exists(_MODEL_PATH):
        print('Downloading pose landmarker model (~4 MB)...')
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        print('Model ready.')


class PoseDetector:
    def __init__(self):
        _ensure_model()
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=_MODEL_PATH),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
        )
        self._landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)

    def detect(self, frame_bgr):
        """Return MediaPipe PoseLandmarkerResult for the first person found."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        return self._landmarker.detect(mp_image)

    def get_landmarks(self, results, frame_shape):
        """Return (33, 4) float32 array [x_px, y_px, z_px, visibility] or None."""
        if not results.pose_landmarks:
            return None
        h, w = frame_shape[:2]
        return np.array(
            [[lm.x * w, lm.y * h, lm.z * w, lm.visibility]
             for lm in results.pose_landmarks[0]],
            dtype=np.float32,
        )

    def close(self):
        self._landmarker.close()
