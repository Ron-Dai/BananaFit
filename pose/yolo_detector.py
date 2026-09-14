"""CPU-safe pose adapter for browser camera frames.

Ultralytics pose models expose the COCO 17-keypoint layout. The rest of this
project consumes MediaPipe's 33-slot layout, so this adapter maps the joints
used by the existing angle and curl-tracking pipeline into those slots.
"""

import numpy as np
from ultralytics import YOLO


_MODEL_NAME = "yolo11n-pose.pt"

# destination MediaPipe index -> source COCO index
_COCO_TO_MEDIAPIPE = {
    0: 0,    # nose
    11: 5,   # left shoulder
    12: 6,   # right shoulder
    13: 7,   # left elbow
    14: 8,   # right elbow
    15: 9,   # left wrist
    16: 10,  # right wrist
    23: 11,  # left hip
    24: 12,  # right hip
    25: 13,  # left knee
    26: 14,  # right knee
    27: 15,  # left ankle
    28: 16,  # right ankle
}


class YoloPoseDetector:
    """Run pose estimation on CPU and expose the project's landmark contract."""

    def __init__(self, model_name: str = _MODEL_NAME):
        self._model = YOLO(model_name)

    def detect(self, frame_bgr):
        """Return the Ultralytics result for one frame."""
        return self._model.predict(frame_bgr, device="cpu", verbose=False)[0]

    def get_landmarks(self, result, _frame_shape):
        """Map the clearest detected person into a MediaPipe-shaped array."""
        if result.keypoints is None or len(result.keypoints) == 0:
            return None

        if result.boxes is not None and result.boxes.conf is not None:
            person_index = int(result.boxes.conf.argmax().item())
        else:
            person_index = 0

        points = result.keypoints.xy[person_index].cpu().numpy()
        confidence_tensor = result.keypoints.conf
        if confidence_tensor is None:
            confidence = np.ones(len(points), dtype=np.float32)
        else:
            confidence = confidence_tensor[person_index].cpu().numpy()

        landmarks = np.zeros((33, 4), dtype=np.float32)
        for destination, source in _COCO_TO_MEDIAPIPE.items():
            if source >= len(points):
                continue
            landmarks[destination, :2] = points[source]
            landmarks[destination, 3] = confidence[source]
        return landmarks

    def close(self):
        """Match the existing detector lifecycle contract."""

