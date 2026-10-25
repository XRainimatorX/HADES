"""Detector interface and implementations (work package B)."""

from __future__ import annotations

from hades.contracts import DetectionPacket, FramePacket


class ModelDetector:
    """Implements ``contracts.Detector``."""

    def load(self, model_path: str) -> None:
        """Load the model file once before detection starts."""
        raise NotImplementedError

    def detect(self, frame: FramePacket) -> DetectionPacket:
        """Run the model on one frame."""
        raise NotImplementedError
