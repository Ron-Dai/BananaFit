"""Abstract interface all gym-equipment detector backends must implement."""

from abc import ABC, abstractmethod

from equipment.registry import EQUIPMENT


class EquipmentDetector(ABC):
    """Contract for a gym-equipment detector backend.

    equipment/recognizer.py's EquipmentRecognizer (COCO-trained SSD
    MobileNetV2) and equipment/yolo_recognizer.py's YoloWorldRecognizer
    (open-vocabulary YOLO-World) both implement this — main.py/server.py
    only need `scan()`, `best_tag()`, and `describe()` to drive either one
    interchangeably. A future third backend only needs to subclass this and
    implement `scan()`; `best_tag()` and `describe()` come for free.
    """

    @abstractmethod
    def scan(self, frame_bgr):
        """Detect equipment in one BGR frame.

        Must return a list of (tag, confidence, box) tuples, where `tag` is
        a key into equipment/registry.py's EQUIPMENT dict, `confidence` is a
        float in [0, 1], and `box` is (x, y, w, h) in pixels. Return an empty
        list when nothing is recognized.
        """
        raise NotImplementedError

    def best_tag(self, frame_bgr):
        """Return the single highest-confidence recognized equipment tag, or 'unknown'."""
        matches = self.scan(frame_bgr)
        if not matches:
            return 'unknown'
        return max(matches, key=lambda m: m[1])[0]

    def describe(self, tag):
        """Look up registry metadata (label, muscles, description) for an equipment tag."""
        return EQUIPMENT.get(tag, EQUIPMENT['unknown'])
