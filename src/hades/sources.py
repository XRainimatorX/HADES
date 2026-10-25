"""Video input (work package A): picam, webcam and video-file sources."""

from __future__ import annotations

from typing import Optional

from hades.contracts import FramePacket


class VideoSource:
    """Implements ``contracts.Source`` for a camera or video file."""

    def open(self) -> None:
        """Connect to the camera or open the video file."""
        raise NotImplementedError

    def read(self) -> Optional[FramePacket]:
        """Return the newest frame, or None when the input has stopped."""
        raise NotImplementedError

    def close(self) -> None:
        """Release the camera or file; safe to call more than once."""
        raise NotImplementedError
