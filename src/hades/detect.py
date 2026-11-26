"""Detector interface and implementations (work package B)."""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

from hades.contracts import (
    CLASS_NAMES,
    SCHEMA_VERSION,
    Detection,
    DetectionPacket,
    FramePacket,
)


class ModelDetector:
    """Implements ``contracts.Detector``."""

    def load(self, model_path: str) -> None:
        """Load the model file once before detection starts."""
        raise NotImplementedError

    def detect(self, frame: FramePacket) -> DetectionPacket:
        """Run the model on one frame."""
        raise NotImplementedError


def _is_valid_image(image: Any) -> bool:
    """True for a non-empty height x width x 3 uint8 array."""
    return (
        isinstance(image, np.ndarray)
        and image.dtype == np.uint8
        and image.ndim == 3
        and image.shape[2] == 3
        and image.shape[0] > 0
        and image.shape[1] > 0
    )


def _clamp_box(coords: list[float], width: int, height: int) -> Optional[tuple[float, ...]]:
    """Clamp a box into the image; None if it is not four finite numbers or has no area."""
    if len(coords) != 4 or not all(math.isfinite(float(c)) for c in coords):
        return None
    x1, y1, x2, y2 = (float(c) for c in coords)
    x1, x2 = min(max(0.0, x1), float(width)), min(max(0.0, x2), float(width))
    y1, y2 = min(max(0.0, y1), float(height)), min(max(0.0, y2), float(height))
    if x1 >= x2 or y1 >= y2:
        return None
    return (x1, y1, x2, y2)


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
        from ultralytics import YOLO  # type: ignore[attr-defined,unused-ignore]  # pylint: disable=import-outside-toplevel

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
            class_id for class_id, name in model_names.items() if name in CLASS_NAMES
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
        if not _is_valid_image(image):
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

        detections = self._convert(result, image.shape[1], image.shape[0])
        return DetectionPacket(
            frame_id=frame.frame_id,
            detections=detections,
            inference_ms=inference_ms,
            timestamp=frame.timestamp,
            schema_version=SCHEMA_VERSION,
            t_detect=time.monotonic_ns(),
        )

    def _convert(self, result: Any, width: int, height: int) -> tuple[Detection, ...]:
        """Keep approved, confident, valid boxes as plain-Python ``Detection`` objects."""
        if result.boxes is None:
            return ()
        box_coords = result.boxes.xyxy.cpu().tolist()
        box_scores = result.boxes.conf.cpu().tolist()
        box_classes = result.boxes.cls.cpu().tolist()
        if not len(box_coords) == len(box_scores) == len(box_classes):
            raise RuntimeError("YOLO boxes, scores and classes have inconsistent lengths")

        detections: list[Detection] = []
        for coords, score_raw, class_raw in zip(box_coords, box_scores, box_classes):
            class_id = int(class_raw)
            score = float(score_raw)
            if class_id not in self._approved_ids:
                continue
            if not math.isfinite(score) or not self.min_confidence <= score <= 1:
                continue
            box = _clamp_box(coords, width, height)
            if box is None:
                continue
            detections.append(
                Detection(
                    bbox=(box[0], box[1], box[2], box[3]),
                    class_name=self._class_names[class_id],  # type: ignore[arg-type]
                    confidence=score,
                )
            )
        return tuple(detections)
