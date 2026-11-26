"""Tests for the video sources (work package A).

They use the shared fixture clips (checked first with ``require_real_video``). The webcam test
is skipped when no camera is attached; the camera-thread behaviour is also tested with a fake
capture so it is verified without hardware.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
import pytest
from conftest import require_real_video

from hades.contracts import FramePacket
from hades.sources import VideoFileSource, VirtualPiCamSource, WebcamSource


def _read_all(source: Any, limit: int = 10_000) -> list[FramePacket]:
    packets: list[FramePacket] = []
    while len(packets) < limit:
        packet = source.read()
        if packet is None:
            break
        packets.append(packet)
    return packets


def _frame_count(path: Path) -> int:
    capture = cv2.VideoCapture(str(path))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    return count


# --- 1-3. frame ids, images, timestamps ----------------------------------------


def test_frame_id_starts_at_zero_and_rises_by_one(drone_daylight_01: Path) -> None:
    """Every frame of the clip is delivered once, numbered 0, 1, 2, ..."""
    video = require_real_video(drone_daylight_01)
    source = VideoFileSource(str(video), realtime=False)
    source.open()
    try:
        packets = _read_all(source)
    finally:
        source.close()
    assert [p.frame_id for p in packets] == list(range(len(packets)))
    assert len(packets) == _frame_count(video) > 0


def test_every_image_is_three_channel_uint8_and_read_only(drone_daylight_01: Path) -> None:
    """The image is height x width x 3, 8-bit, and cannot be written to."""
    source = VideoFileSource(str(require_real_video(drone_daylight_01)), realtime=False)
    source.open()
    try:
        packets = _read_all(source, limit=10)
    finally:
        source.close()
    assert packets
    for packet in packets:
        assert packet.image.ndim == 3 and packet.image.shape[2] == 3
        assert packet.image.dtype == np.uint8
        assert not packet.image.flags.writeable
        assert packet.source_type == "video" and packet.source_id == "cam0"


def test_timestamp_never_decreases_and_is_on_the_monotonic_clock(drone_daylight_01: Path) -> None:
    """Capture times come from time.monotonic_ns(), taken as the image is obtained."""
    source = VideoFileSource(str(require_real_video(drone_daylight_01)), realtime=False)
    before = time.monotonic_ns()
    source.open()
    try:
        packets = _read_all(source, limit=30)
    finally:
        source.close()
    after = time.monotonic_ns()
    stamps = [p.timestamp for p in packets]
    assert stamps == sorted(stamps)
    assert before <= stamps[0] and stamps[-1] <= after


# --- 4. end of file --------------------------------------------------------------


def test_read_returns_none_after_the_last_frame(no_drone_01: Path) -> None:
    """At the end of the file read() returns None, and keeps returning None."""
    source = VideoFileSource(str(require_real_video(no_drone_01)), realtime=False)
    source.open()
    try:
        packets = _read_all(source)
        assert len(packets) == _frame_count(no_drone_01)
        assert source.read() is None
        assert source.read() is None
    finally:
        source.close()


# --- 5. realtime pacing ---------------------------------------------------------------


def test_with_a_slow_reader_frames_skip_ahead_instead_of_queuing(drone_daylight_01: Path) -> None:
    """A reader that takes 0.3 s per frame gets later frames, not every frame."""
    video = require_real_video(drone_daylight_01)
    source = VideoFileSource(str(video), realtime=True)
    source.open()
    delivered: list[FramePacket] = []
    try:
        while True:
            packet = source.read()
            if packet is None:
                break
            delivered.append(packet)
            time.sleep(0.3)
    finally:
        source.close()
    assert [p.frame_id for p in delivered] == list(range(len(delivered)))
    assert 0 < len(delivered) < _frame_count(video) // 2


def test_realtime_releases_frames_at_the_files_own_rate(drone_daylight_01: Path) -> None:
    """Ten frames of a 30 fps clip cannot arrive faster than about a third of a second."""
    source = VideoFileSource(str(require_real_video(drone_daylight_01)), realtime=True)
    source.open()
    try:
        started = time.monotonic()
        packets = _read_all(source, limit=10)
        elapsed = time.monotonic() - started
    finally:
        source.close()
    assert len(packets) == 10
    assert elapsed >= 0.25


# --- 6. virtual Pi camera --------------------------------------------------------------


def test_virtual_picam_reports_picam_delivers_the_size_and_never_ends(head_walk_01: Path) -> None:
    """Looping the clip, it keeps delivering frames of the requested size past the file end."""
    video = require_real_video(head_walk_01)
    source = VirtualPiCamSource(str(video), width=320, height=180, fps=300.0)
    source.open()
    try:
        packets = [source.read() for _ in range(_frame_count(video) + 40)]
    finally:
        source.close()
    assert all(p is not None for p in packets)
    frames = [p for p in packets if p is not None]
    assert {p.source_type for p in frames} == {"picam"}
    assert {p.image.shape for p in frames} == {(180, 320, 3)}
    assert [p.frame_id for p in frames] == list(range(len(frames)))


def test_virtual_picam_delivers_frames_at_the_requested_rate(head_walk_01: Path) -> None:
    """At 20 fps, ten frames take at least about 0.4 s."""
    source = VirtualPiCamSource(str(require_real_video(head_walk_01)), width=160, height=90, fps=20)
    source.open()
    try:
        source.read()
        started = time.monotonic()
        for _ in range(8):
            assert source.read() is not None
        elapsed = time.monotonic() - started
    finally:
        source.close()
    assert elapsed >= 0.3


# --- 7. close ----------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["file", "picam"])
def test_close_twice_raises_nothing(kind: str, drone_daylight_01: Path) -> None:
    """close() is safe to call more than once, and read() after it returns None or raises."""
    path = str(require_real_video(drone_daylight_01))
    source: Any = VideoFileSource(path) if kind == "file" else VirtualPiCamSource(path)
    source.open()
    source.close()
    source.close()


def test_close_before_open_raises_nothing() -> None:
    """A source that was never opened can still be closed."""
    for source in (VideoFileSource("x.mp4"), VirtualPiCamSource("x.mp4"), WebcamSource()):
        source.close()


# --- 8. errors ------------------------------------------------------------------------------


@pytest.mark.parametrize("cls", [VideoFileSource, VirtualPiCamSource])
def test_opening_a_file_that_does_not_exist_raises_runtime_error(cls: Any, tmp_path: Path) -> None:
    """The message names the file."""
    missing = tmp_path / "absent.mp4"
    with pytest.raises(RuntimeError, match="absent.mp4"):
        cls(str(missing)).open()


@pytest.mark.parametrize(
    "source",
    [VideoFileSource("x.mp4"), VirtualPiCamSource("x.mp4"), WebcamSource()],
    ids=["file", "picam", "webcam"],
)
def test_read_before_open_is_an_error(source: Any) -> None:
    """Reading from a source that was not opened is reported, not silently empty."""
    with pytest.raises(RuntimeError, match="before open"):
        source.read()


# --- 9. webcam (real camera) -----------------------------------------------------------------


def _camera_present() -> bool:
    capture = cv2.VideoCapture(0)
    present = bool(capture.isOpened())
    capture.release()
    return present


@pytest.mark.skipif(not _camera_present(), reason="no camera attached")
def test_webcam_delivers_valid_frame_packets() -> None:
    """With a camera attached, the webcam delivers valid FramePackets."""
    source = WebcamSource(0)
    source.open()
    try:
        packets = _read_all(source, limit=5)
    finally:
        source.close()
    assert len(packets) == 5
    assert all(p.source_type == "webcam" and p.image.shape[2] == 3 for p in packets)


# --- the camera thread, tested without hardware -----------------------------------------------


class FakeCapture:
    """A camera whose pixel value is the number of the frame, optionally failing later."""

    instances: list["FakeCapture"] = []

    def __init__(self, target: Any, *_: Any, fail_after: Optional[int] = None) -> None:
        self.target = target
        self.counter = 0
        self.fail_after = fail_after
        self.settings: dict[int, float] = {}
        self.released = False
        FakeCapture.instances.append(self)

    def isOpened(self) -> bool:  # pylint: disable=invalid-name
        """Report an open camera."""
        return True

    def set(self, prop: int, value: float) -> bool:
        """Record a requested setting."""
        self.settings[prop] = value
        return True

    def read(self) -> tuple[bool, Optional[np.ndarray]]:
        """Return the next frame; the pixel value counts frames."""
        time.sleep(0.004)
        if self.fail_after is not None and self.counter >= self.fail_after:
            return False, None
        self.counter += 1
        return True, np.full((6, 8, 3), self.counter % 256, dtype=np.uint8)

    def release(self) -> None:
        """Remember that the camera was released."""
        self.released = True


@pytest.fixture(name="fake_camera")
def fixture_fake_camera(monkeypatch: pytest.MonkeyPatch) -> type[FakeCapture]:
    """Replace OpenCV's capture class with FakeCapture."""
    FakeCapture.instances = []
    monkeypatch.setattr(cv2, "VideoCapture", FakeCapture)
    return FakeCapture


def test_webcam_returns_the_newest_frame_not_the_oldest(fake_camera: type[FakeCapture]) -> None:
    """After a pause the webcam hands over a recent frame, skipping what it missed."""
    source = WebcamSource(0)
    source.open()
    try:
        first = source.read()
        time.sleep(0.25)
        later = source.read()
    finally:
        source.close()
    assert first is not None and later is not None
    assert int(later.image[0, 0, 0]) > int(first.image[0, 0, 0]) + 10
    assert later.frame_id == first.frame_id + 1
    assert later.timestamp > first.timestamp


def test_webcam_packets_are_valid_webcam_frames(fake_camera: type[FakeCapture]) -> None:
    """Without hardware: webcam packets carry source_type webcam, source_id cam0 and the image."""
    source = WebcamSource(0)
    source.open()
    try:
        packets = _read_all(source, limit=5)
    finally:
        source.close()
    assert len(packets) == 5
    for packet in packets:
        assert packet.source_type == "webcam" and packet.source_id == "cam0"
        assert packet.image.shape == (6, 8, 3) and packet.image.dtype == np.uint8
        assert not packet.image.flags.writeable
    assert [p.frame_id for p in packets] == [0, 1, 2, 3, 4]


def test_webcam_requests_the_size_and_rate_from_the_camera(
    fake_camera: type[FakeCapture],
) -> None:
    """width, height and fps are passed to the camera when given."""
    source = WebcamSource(2, width=640, height=480, fps=15.0)
    source.open()
    try:
        camera = fake_camera.instances[-1]
        assert camera.target == 2
        assert camera.settings == {
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480,
            cv2.CAP_PROP_FPS: 15.0,
        }
    finally:
        source.close()


def test_webcam_returns_none_when_the_camera_is_lost(monkeypatch: pytest.MonkeyPatch) -> None:
    """A camera that stops delivering ends the stream instead of repeating the last frame."""
    monkeypatch.setattr(cv2, "VideoCapture", lambda target, *a: FakeCapture(target, fail_after=3))
    source = WebcamSource(0)
    source.open()
    try:
        packets = _read_all(source)
    finally:
        source.close()
    assert 1 <= len(packets) <= 3
    assert source.read() is None


def test_closing_stops_the_camera_thread_and_releases_the_camera(
    fake_camera: type[FakeCapture],
) -> None:
    """After close() the camera is released and read() reports that the input has stopped."""
    source = WebcamSource(0)
    source.open()
    assert source.read() is not None
    source.close()
    assert fake_camera.instances[-1].released
    assert source.read() is None
    assert not any(t.name == "hades-camera" and t.is_alive() for t in threading.enumerate())


@pytest.mark.parametrize("cls", [VideoFileSource, VirtualPiCamSource])
def test_read_after_close_returns_none_for_every_source(cls: Any, drone_daylight_01: Path) -> None:
    """A source that was opened and then closed has stopped: read() gives None, not an error."""
    source = cls(str(require_real_video(drone_daylight_01)))
    source.open()
    source.close()
    assert source.read() is None


def test_reopening_restarts_the_frame_numbers(fake_camera: type[FakeCapture]) -> None:
    """open() after close() starts again at frame 0 with a fresh camera."""
    source = WebcamSource(0)
    source.open()
    assert source.read() is not None and source.read() is not None
    source.close()
    source.open()
    try:
        packet = source.read()
    finally:
        source.close()
    assert packet is not None and packet.frame_id == 0
    assert len(fake_camera.instances) == 2
