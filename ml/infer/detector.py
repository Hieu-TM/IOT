"""Ultralytics YOLO wrapper. This is the ONLY module that imports ultralytics."""

from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image


@dataclass
class Detection:
    bbox_xywh: tuple  # (x, y, w, h), ints, top-left origin
    class_name: str
    confidence: float


@dataclass
class DetectionResult:
    detections: list
    image_width: int
    image_height: int


def _class_name(names, class_id):
    try:
        return names[class_id]
    except (KeyError, IndexError, TypeError):
        return str(class_id)


class Detector:
    def __init__(self, weights):
        from ultralytics import YOLO  # lazy: keep the heavy/optional dep here

        self.model = YOLO(str(weights))

    def run(self, image_bytes):
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        width, height = img.size
        return self.run_array(np.asarray(img), width, height)

    def run_array(self, rgb_array, width=None, height=None):
        if width is None or height is None:
            height, width = rgb_array.shape[:2]
        results = self.model.predict(rgb_array, verbose=False)
        names = self.model.names
        detections = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                detections.append(
                    Detection(
                        bbox_xywh=(x1, y1, x2 - x1, y2 - y1),
                        class_name=_class_name(names, int(box.cls[0].item())),
                        confidence=float(box.conf[0].item()),
                    )
                )
        return DetectionResult(detections=detections, image_width=width, image_height=height)
