"""Video input (work package A): webcam, video-file and virtual Pi camera sources.

Every source turns an image source into ``FramePacket`` objects through the same three
functions (``open``, ``read``, ``close``), so nothing downstream depends on where an image
came from. The capture time of a frame is ``time.monotonic_ns()`` taken immediately after
the image is obtained.

Live sources (webcam, virtual Pi camera) run one camera thread that keeps reading and holds
only the newest frame; ``read()`` returns that frame. Importing this module opens nothing and
starts nothing (Issue 0).
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Any, Optional

import cv2
import numpy as np

from hades.contracts import FramePacket, SourceType

_NS_PER_S = 1_000_000_000
_DEFAULT_FPS = 30.0
_WAIT_FOR_FRAME_S = 1.0


class VideoSource:
    """Common part of every source: the frame counter and packet construction.

    Implements ``contracts.Source``; the subclasses supply ``open``, ``read`` and ``close``.
    """

    source_type: SourceType = "video"

    def __init__(self) -> None:
        self._frame_id = 0
        self._opened_once = False

    def open(self) -> None:
        """Connect to the camera or open the video file."""
        raise NotImplementedError

    def read(self) -> Optional[FramePacket]:
        """Return the newest frame, or None when the input has stopped."""
        raise NotImplementedError

    def close(self) -> None:
        """Release the camera or file; safe to call more than once."""
        raise NotImplementedError

    def _require_opened_once(self, name: str) -> None:
        """Raise if ``read()`` is called on a source that was never opened.

        A source that was opened and then closed has stopped; its ``read()`` returns None.
        """
        if not self._opened_once:
            raise RuntimeError(f"{name}.read() called before open()")

    def _packet(self, image: np.ndarray, timestamp: int) -> FramePacket:
        """Wrap an image in the next FramePacket; ``frame_id`` rises by one per packet."""
        packet = FramePacket(
            frame_id=self._frame_id,
            timestamp=timestamp,
            image=image,
            source_type=self.source_type,
        )
        self._frame_id += 1
        return packet


def _open_capture(target: Any, what: str) -> Any:
    """Open an OpenCV capture or raise ``RuntimeError`` with a clear message."""
    capture = cv2.VideoCapture(target)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"Could not open {what}")
    return capture


class VideoFileSource(VideoSource):
    """Frames from a video file.

    With ``realtime=True`` frames are released at the file's own rate and the newest one is
    returned: a slow reader skips ahead instead of queuing. With ``realtime=False`` every
    frame is returned in order, as fast as it is read.
    """

    source_type: SourceType = "video"

    def __init__(self, path: str, realtime: bool = True) -> None:
        super().__init__()
        self.path = path
        self.realtime = realtime
        self._capture: Any = None
        self._period_ns = int(_NS_PER_S / _DEFAULT_FPS)
        self._start_ns = 0
        self._index = 0

    def open(self) -> None:
        """Open the file; raises ``RuntimeError`` if it cannot be opened."""
        self.close()
        self._capture = _open_capture(self.path, f"video file '{self.path}'")
        self._opened_once = True
        fps = float(self._capture.get(cv2.CAP_PROP_FPS) or 0.0)
        self._period_ns = int(_NS_PER_S / (fps if fps > 0 else _DEFAULT_FPS))
        self._frame_id = 0
        self._index = 0
        self._start_ns = 0

    def read(self) -> Optional[FramePacket]:
        """Return the next frame, or None at the end of the file or when it cannot be read."""
        if self._capture is None:
            self._require_opened_once("VideoFileSource")
            return None
        if self.realtime and not self._wait_until_due():
            return None
        ok, image = self._capture.read()
        timestamp = time.monotonic_ns()
        if not ok or image is None:
            return None
        self._index += 1
        return self._packet(image, timestamp)

    def _wait_until_due(self) -> bool:
        """Sleep until the next frame is due, or skip frames the reader was too slow for.

        Returns False if the file ended while skipping.
        """
        now = time.monotonic_ns()
        if self._start_ns == 0:
            self._start_ns = now
        due = (now - self._start_ns) // self._period_ns
        if self._index > due:
            time.sleep((self._start_ns + self._index * self._period_ns - now) / _NS_PER_S)
            return True
        while self._index < due:
            if not self._capture.grab():
                return False
            self._index += 1
        return True

    def close(self) -> None:
        """Release the file; safe to call more than once."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None


class _CameraThread:
    """One thread that keeps reading images and holds only the newest one."""

    def __init__(self, grab: Any, period_s: float) -> None:
        self._grab = grab  # returns an image, or None when the source is lost
        self._period_s = period_s
        self._condition = threading.Condition()
        self._latest: Optional[tuple[np.ndarray, int]] = None
        self._delivered = False
        self._lost = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="hades-camera", daemon=True)

    def start(self) -> None:
        """Start reading."""
        self._thread.start()

    def _run(self) -> None:
        next_due = time.monotonic()
        while not self._stop.is_set():
            image = self._grab()
            timestamp = time.monotonic_ns()
            with self._condition:
                if image is None:
                    self._lost = True
                    self._condition.notify_all()
                    return
                self._latest = (image, timestamp)
                self._delivered = False
                self._condition.notify_all()
            if self._period_s > 0:
                next_due += self._period_s
                self._stop.wait(max(0.0, next_due - time.monotonic()))

    def newest(self) -> Optional[tuple[np.ndarray, int]]:
        """Wait for a frame not yet delivered and return it; None if the source is lost."""
        with self._condition:
            while True:
                if self._latest is not None and not self._delivered:
                    self._delivered = True
                    return self._latest
                if self._lost or self._stop.is_set():
                    return None
                self._condition.wait(timeout=_WAIT_FOR_FRAME_S)

    def stop(self) -> None:
        """Stop the thread and wait for it; safe to call more than once."""
        self._stop.set()
        with self._condition:
            self._condition.notify_all()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=5.0)


class WebcamSource(VideoSource):
    """Frames from a laptop webcam; ``read()`` returns only the newest frame.

    ``width``, ``height`` and ``fps`` are requested from the camera when given; the
    camera may deliver something close instead.
    """

    source_type: SourceType = "webcam"

    def __init__(
        self,
        device: int = 0,
        width: Optional[int] = None,
        height: Optional[int] = None,
        fps: Optional[float] = None,
    ) -> None:
        super().__init__()
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self._capture: Any = None
        self._thread: Optional[_CameraThread] = None

    def open(self) -> None:
        """Open the camera and start the camera thread; raises ``RuntimeError`` on failure."""
        self.close()
        capture = (
            cv2.VideoCapture(self.device, cv2.CAP_DSHOW)
            if sys.platform == "win32"
            else cv2.VideoCapture(self.device)
        )
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Could not open webcam {self.device}")
        if self.width:
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height:
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        if self.fps:
            capture.set(cv2.CAP_PROP_FPS, self.fps)
        self._capture = capture
        self._opened_once = True
        self._frame_id = 0
        self._thread = _CameraThread(self._grab, 0.0)
        self._thread.start()

    def _grab(self) -> Optional[np.ndarray]:
        """Read one image from the camera; None if the camera is lost."""
        ok, image = self._capture.read()
        return image if ok and image is not None else None

    def read(self) -> Optional[FramePacket]:
        """Return the newest frame, or None if the camera is lost."""
        if self._thread is None:
            self._require_opened_once("WebcamSource")
            return None
        frame = self._thread.newest()
        return None if frame is None else self._packet(frame[0], frame[1])

    def close(self) -> None:
        """Stop the camera thread and release the camera; safe to call more than once."""
        if self._thread is not None:
            self._thread.stop()
            self._thread = None
        if self._capture is not None:
            self._capture.release()
            self._capture = None


class VirtualPiCamSource(VideoSource):
    """The Pi camera, simulated on a laptop by looping a video file.

    It behaves like the real camera will: frames of the requested size, BGR, delivered at the
    requested rate, newest frame only, ``source_type`` ``"picam"``, and it never ends. The
    real driver is added later behind the same functions.
    """

    source_type: SourceType = "picam"

    def __init__(
        self, path: str, width: int = 1280, height: int = 720, fps: float = _DEFAULT_FPS
    ) -> None:
        super().__init__()
        self.path = path
        self.width = width
        self.height = height
        self.fps = fps
        self._capture: Any = None
        self._thread: Optional[_CameraThread] = None

    def open(self) -> None:
        """Open the video file and start the camera thread; raises ``RuntimeError`` on failure."""
        self.close()
        self._capture = _open_capture(self.path, f"video file '{self.path}'")
        self._opened_once = True
        self._frame_id = 0
        self._thread = _CameraThread(self._grab, 1.0 / self.fps)
        self._thread.start()

    def _grab(self) -> Optional[np.ndarray]:
        """Read the next frame, restart the file at its end, and resize to the camera size."""
        ok, image = self._capture.read()
        if not ok or image is None:
            self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, image = self._capture.read()
            if not ok or image is None:
                return None
        if image.shape[1] != self.width or image.shape[0] != self.height:
            resized: np.ndarray = cv2.resize(image, (self.width, self.height))
            return resized
        return image  # type: ignore[no-any-return]

    def read(self) -> Optional[FramePacket]:
        """Return the newest frame; None only after ``close()`` or if the file is unreadable."""
        if self._thread is None:
            self._require_opened_once("VirtualPiCamSource")
            return None
        frame = self._thread.newest()
        return None if frame is None else self._packet(frame[0], frame[1])

    def close(self) -> None:
        """Stop the camera thread and release the file; safe to call more than once."""
        if self._thread is not None:
            self._thread.stop()
            self._thread = None
        if self._capture is not None:
            self._capture.release()
            self._capture = None
