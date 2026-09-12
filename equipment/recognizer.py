import os

import cv2

from equipment.registry import EQUIPMENT, DETECTOR_CLASS_TO_TAG

_MODEL_DIR   = os.path.dirname(__file__)
_MODEL_PATH  = os.path.join(_MODEL_DIR, 'frozen_inference_graph.pb')
_CONFIG_PATH = os.path.join(_MODEL_DIR, 'ssd_mobilenet_v2_coco_2018_03_29.pbtxt')

_INPUT_SIZE   = (320, 320)
_INPUT_SCALE  = 1.0 / 127.5
_INPUT_MEAN   = (127.5, 127.5, 127.5)
_DEFAULT_CONFIDENCE = 0.5

# The standard 90-slot MS-COCO id -> class name map (mscoco_label_map.pbtxt from
# the TF Object Detection API). IDs skip several numbers by design; this is the
# label space the SSD MobileNetV2 COCO model below was trained on.
COCO_CLASSES = {
    1: 'person', 2: 'bicycle', 3: 'car', 4: 'motorcycle', 5: 'airplane',
    6: 'bus', 7: 'train', 8: 'truck', 9: 'boat', 10: 'traffic light',
    11: 'fire hydrant', 13: 'stop sign', 14: 'parking meter', 15: 'bench',
    16: 'bird', 17: 'cat', 18: 'dog', 19: 'horse', 20: 'sheep', 21: 'cow',
    22: 'elephant', 23: 'bear', 24: 'zebra', 25: 'giraffe', 27: 'backpack',
    28: 'umbrella', 31: 'handbag', 32: 'tie', 33: 'suitcase', 34: 'frisbee',
    35: 'skis', 36: 'snowboard', 37: 'sports ball', 38: 'kite',
    39: 'baseball bat', 40: 'baseball glove', 41: 'skateboard', 42: 'surfboard',
    43: 'tennis racket', 44: 'bottle', 46: 'wine glass', 47: 'cup', 48: 'fork',
    49: 'knife', 50: 'spoon', 51: 'bowl', 52: 'banana', 53: 'apple',
    54: 'sandwich', 55: 'orange', 56: 'broccoli', 57: 'carrot', 58: 'hot dog',
    59: 'pizza', 60: 'donut', 61: 'cake', 62: 'chair', 63: 'couch',
    64: 'potted plant', 65: 'bed', 67: 'dining table', 70: 'toilet', 72: 'tv',
    73: 'laptop', 74: 'mouse', 75: 'remote', 76: 'keyboard', 77: 'cell phone',
    78: 'microwave', 79: 'oven', 80: 'toaster', 81: 'sink', 82: 'refrigerator',
    84: 'book', 85: 'clock', 86: 'vase', 87: 'scissors', 88: 'teddy bear',
    89: 'hair drier', 90: 'toothbrush',
}


def _ensure_model_files():
    missing = [p for p in (_MODEL_PATH, _CONFIG_PATH) if not os.path.exists(p)]
    if not missing:
        return
    raise FileNotFoundError(
        "Equipment recognizer model files are missing:\n"
        + "\n".join(f"  {p}" for p in missing) + "\n\n"
        "This isn't auto-downloaded (no reliably pinned URL). Get both files "
        "for the 'ssd_mobilenet_v2_coco_2018_03_29' TensorFlow Object "
        "Detection Model Zoo network and place them in "
        f"{_MODEL_DIR}:\n"
        "  1. frozen_inference_graph.pb — extracted from that model's .tar.gz\n"
        "  2. ssd_mobilenet_v2_coco_2018_03_29.pbtxt — the matching OpenCV DNN "
        "text graph (ships alongside this network in OpenCV's own dnn test data)"
    )


class EquipmentRecognizer:
    """Runs a COCO-trained SSD MobileNetV2 detector and maps hits to equipment tags.

    COCO has no gym-equipment classes, so this only recognizes the handful of
    COCO objects listed in equipment/registry.py's DETECTOR_CLASS_TO_TAG as
    rough proxies (e.g. a COCO 'bench') — everything else reports 'unknown'.
    """

    def __init__(self, confidence_threshold=_DEFAULT_CONFIDENCE):
        """Load the SSD MobileNetV2 (COCO) detection model via OpenCV's DNN module."""
        _ensure_model_files()
        self._confidence_threshold = confidence_threshold
        self._net = cv2.dnn_DetectionModel(_MODEL_PATH, _CONFIG_PATH)
        self._net.setInputSize(*_INPUT_SIZE)
        self._net.setInputScale(_INPUT_SCALE)
        self._net.setInputMean(_INPUT_MEAN)
        self._net.setInputSwapRB(True)

    def scan(self, frame_bgr):
        """Detect objects in one frame.

        Returns a list of (tag, confidence, box) for every detection whose
        COCO class maps to a known equipment tag; box is (x, y, w, h) in
        pixels. Detections that don't map to any tag are dropped.
        """
        class_ids, confidences, boxes = self._net.detect(
            frame_bgr, confThreshold=self._confidence_threshold)

        results = []
        for class_id, confidence, box in zip(
                class_ids.flatten() if len(class_ids) else [],
                confidences.flatten() if len(confidences) else [],
                boxes if len(boxes) else []):
            class_name = COCO_CLASSES.get(int(class_id))
            tag = DETECTOR_CLASS_TO_TAG.get(class_name)
            if tag is not None:
                results.append((tag, float(confidence), tuple(int(v) for v in box)))
        return results

    def best_tag(self, frame_bgr):
        """Return the single highest-confidence recognized equipment tag, or 'unknown'."""
        matches = self.scan(frame_bgr)
        if not matches:
            return 'unknown'
        return max(matches, key=lambda m: m[1])[0]

    def describe(self, tag):
        """Look up registry metadata (label, muscles, description) for an equipment tag."""
        return EQUIPMENT.get(tag, EQUIPMENT['unknown'])
