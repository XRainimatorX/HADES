"""Tracking and filtering (work package I)."""

from __future__ import annotations

from hades.contracts import DetectionPacket, TrackingPacket


class DroneTracker:
    """Implements ``contracts.Tracker``."""

    def update(self, det: DetectionPacket) -> TrackingPacket:
        """Match new detections with existing tracks."""
        raise NotImplementedError

    def reset(self) -> None:
        """Clear all tracks."""
        raise NotImplementedError
