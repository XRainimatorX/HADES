"""Detector interface and implementations (work package B)."""

from __future__ import annotations

from hades.contracts import (
    SCHEMA_VERSION,
    Detection,
    DetectionPacket,
    FramePacket,
)

import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

class ModelDetector:
    """Implements ``contracts.Detector``."""

    def load(self, model_path: str) -> None:
        """Load the model file once before detection starts."""
        raise NotImplementedError

    def detect(self, frame: FramePacket) -> DetectionPacket:
        """Run the model on one frame."""
        raise NotImplementedError

class UltralyticsDetector(ModelDetector):
    """Detect approved HADES classes using a local Ultralytics YOLO model."""

    def __init__(self, min_confidence: float = 0.25, input_size: int = 640) -> None:
        """Configure the confidence floor and model input image size."""
        if not math.isfinite(min_confidence) or not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be finite and between 0 and 1")
        if isinstance(input_size, bool) or not isinstance(input_size, int) or input_size <= 0:
            raise ValueError("input_size must be a positive integer")

        self.min_confidence = float(min_confidence)
        self.input_size = input_size
        self._model: Any | None = None
        self._model_path: Path | None = None
        self._class_names: dict[int, str] = {}
        self._approved_ids: list[int] = []

    def load(self, model_path: str) -> None:
        """Load the local model once, then perform precisely one blank-frame warm-up."""
        path = Path(model_path).expanduser().resolve()
        if self._model is not None:
            if path == self._model_path:
                return
            raise RuntimeError("Model already loaded; use a new detector for different weights")
        if not path.is_file():
            raise FileNotFoundError(f"Model weights not found: {path}")

        # Local import: importing hades.detect must never load model weights.
        from ultralytics import YOLO  # pylint: disable=import-outside-toplevel

        classes_path = Path(__file__).resolve().parents[2] / "data" / "classes.yaml"
        with classes_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if not isinstance(data, dict) or not isinstance(data.get("names"), dict):
            raise ValueError(f"Invalid class configuration: {classes_path}")
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("data/classes.yaml uses an unsupported schema_version")
        allowed = {str(value) for value in data["names"].values()}

        candidate = YOLO(str(path))
        names = candidate.names
        if isinstance(names, dict):
            pairs = names.items()
        elif isinstance(names, (tuple, list)):
            pairs = enumerate(names)
        else:
            raise ValueError("YOLO model must expose its class names")

        model_names = {int(class_id): str(name) for class_id, name in pairs}
        approved_ids = sorted(
            class_id for class_id, name in model_names.items() if name in allowed
        )
        warmup = np.zeros((self.input_size, self.input_size, 3), dtype=np.uint8)
        candidate.predict(
            source=warmup,
            imgsz=self.input_size,
            conf=self.min_confidence,
            verbose=False,
            augment=False,
        )
        self._model = candidate
        self._model_path = path
        self._class_names = model_names
        self._approved_ids = approved_ids

    def detect(self, frame: FramePacket) -> DetectionPacket:
        """Return a standard packet without modifying the supplied FramePacket."""
        if self._model is None:
            raise RuntimeError("Call load(model_path) before detect(frame)")
        if frame.schema_version != SCHEMA_VERSION:
            raise ValueError("Unsupported FramePacket schema version")
        image = frame.image
        if (
            not isinstance(image, np.ndarray)
            or image.dtype != np.uint8
            or image.ndim != 3
            or image.shape[2] != 3
            or not image.shape[0]
            or not image.shape[1]
        ):
            raise ValueError("FramePacket.image must be nonempty HxWx3 BGR uint8")

        # The Ultralytics predictor handles internal resizing and preprocessing;
        # its xyxy output is converted back to input-image coordinates.
        working_image = np.ascontiguousarray(image).copy()
        results = self._model.predict(
            source=working_image,
            imgsz=self.input_size,
            conf=self.min_confidence,
            verbose=False,
            augment=False,
        )
        if len(results) != 1:
            raise RuntimeError("Expected exactly one YOLO result per FramePacket")
        result = results[0]
        inference_ms = float(result.speed["inference"])
        if not math.isfinite(inference_ms) or inference_ms <= 0:
            raise RuntimeError("Model must report positive inference time in milliseconds")

        detections: list[Detection] = []
        if result.boxes is not None:
            box_coords = result.boxes.xyxy.cpu().tolist()
            box_scores = result.boxes.conf.cpu().tolist()
            box_classes = result.boxes.cls.cpu().tolist()
            if not (len(box_coords) == len(box_scores) == len(box_classes)):
                raise RuntimeError("YOLO boxes, scores and classes have inconsistent lengths")

            height, width = image.shape[:2]
            for coords, score_raw, class_raw in zip(box_coords, box_scores, box_classes):
                class_id = int(class_raw)
                score = float(score_raw)
                if class_id not in self._approved_ids:
                    continue
                if not math.isfinite(score) or not self.min_confidence <= score <= 1:
                    continue
                if len(coords) != 4 or not all(math.isfinite(float(c)) for c in coords):
                    continue

                x1, y1, x2, y2 = (float(c) for c in coords)
                x1 = min(max(0.0, x1), float(width))
                x2 = min(max(0.0, x2), float(width))
                y1 = min(max(0.0, y1), float(height))
                y2 = min(max(0.0, y2), float(height))
                if x1 >= x2 or y1 >= y2:
                    continue
                detections.append(
                    Detection(
                        bbox=(x1, y1, x2, y2),
                        class_name=self._class_names[class_id],  # type: ignore[arg-type]
                        confidence=score,
                    )
                )

        # NOTE: Issue #4 requires tuple, but contracts.py currently annotates
        # detections as list[Detection]. Owner should resolve this discrepancy.
        # Keep the contract class and field names unchanged as required by WP-B.
        return DetectionPacket(
            frame_id=frame.frame_id,
            detections=tuple(detections),  # type: ignore[arg-type]
            inference_ms=inference_ms,
            timestamp=frame.timestamp,
            schema_version=SCHEMA_VERSION,
            t_detect=time.monotonic_ns(),
        )