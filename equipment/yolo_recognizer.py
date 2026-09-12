from ultralytics import YOLO

from equipment.registry import EQUIPMENT, YOLO_WORLD_CLASSES

_MODEL_NAME = 'yolov8s-worldv2.pt'   # auto-downloaded by ultralytics on first use (~25 MB)
_DEFAULT_CONFIDENCE = 0.15            # open-vocabulary models score lower than closed-set ones


class YoloWorldRecognizer:
    """Open-vocabulary gym-equipment detector via YOLO-World (Ultralytics).

    Unlike EquipmentRecognizer (recognizer.py's COCO-trained SSD MobileNetV2),
    this detects the actual equipment classes in YOLO_WORLD_CLASSES directly —
    no proxy mapping through COCO's category set, since YOLO-World is prompted
    with the gym-equipment names themselves.
    """

    def __init__(self, classes=YOLO_WORLD_CLASSES, confidence_threshold=_DEFAULT_CONFIDENCE):
        """Load YOLO-World and set it to look for the given open-vocabulary classes."""
        self._model = YOLO(_MODEL_NAME)
        self._model.set_classes(classes)
        self._confidence_threshold = confidence_threshold

    def scan(self, frame_bgr):
        """Detect gym equipment in one frame.

        Returns a list of (label, confidence, box) — box is (x, y, w, h) in
        pixels — matching EquipmentRecognizer.scan()'s shape for drop-in use.
        """
        results = self._model.predict(frame_bgr, conf=self._confidence_threshold, verbose=False)[0]
        names = results.names
        out = []
        for box in results.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            label = names[int(box.cls[0])]
            confidence = float(box.conf[0])
            out.append((label, confidence, (int(x1), int(y1), int(x2 - x1), int(y2 - y1))))
        return out

    def best_tag(self, frame_bgr):
        """Return the single highest-confidence recognized equipment tag, or 'unknown'."""
        matches = self.scan(frame_bgr)
        if not matches:
            return 'unknown'
        return max(matches, key=lambda m: m[1])[0]

    def describe(self, tag):
        """Look up registry metadata (label, muscles, description) for an equipment tag."""
        return EQUIPMENT.get(tag, EQUIPMENT['unknown'])
