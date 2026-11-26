"""Tests for the web monitor (work package D).

They use the shared sample packets and the fixture video (through ``make_frame``), not their own
sample data. Every test calls the monitor and checks what it returns over HTTP.
"""

from __future__ import annotations

import dataclasses
import json
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Iterator

import cv2
import numpy as np
import pytest

from hades.contracts import DetectionPacket, FramePacket, SystemState
from hades.monitor import WebMonitor

MakeFrame = Callable[[int], FramePacket]


@pytest.fixture(name="mon")
def fixture_mon() -> Iterator[WebMonitor]:
    """A monitor serving on a free port; the number of threads it added is remembered."""
    before = threading.active_count()
    monitor = WebMonitor()
    monitor.start(0)  # port 0 = any free port
    monitor.port = monitor._server.server_address[1]  # type: ignore[union-attr,attr-defined]  # pylint: disable=protected-access
    monitor.threads_added = threading.active_count() - before  # type: ignore[attr-defined]
    yield monitor
    monitor.stop()


def get(monitor: Any, path: str) -> bytes:
    """GET a path from the running monitor."""
    with urllib.request.urlopen(f"http://127.0.0.1:{monitor.port}{path}", timeout=3) as response:
        return bytes(response.read())


def green_pixels(jpeg: bytes) -> int:
    """How many clearly green pixels the JPEG has (the box colour)."""
    image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR).astype(int)
    blue, green, red = image[..., 0], image[..., 1], image[..., 2]
    return int(((green > 150) & (red < 100) & (blue < 100)).sum())


# 1. start() runs the server in one background thread
def test_start_uses_one_background_thread(mon: Any) -> None:
    """One daemon thread serves the page, and requests do not add threads."""
    assert mon._thread.is_alive() and mon._thread.daemon  # pylint: disable=protected-access
    assert mon.threads_added == 1


def test_requests_do_not_start_more_threads(mon: Any) -> None:
    """After many requests the thread count is the same as before them."""
    before = threading.active_count()
    for _ in range(10):
        get(mon, "/status.json")
    assert threading.active_count() == before


def test_the_server_listens_on_this_computer_only(mon: Any) -> None:
    """The development page is not exposed to the network by default."""
    assert mon._server.server_address[0] == "127.0.0.1"  # pylint: disable=protected-access


def test_start_twice_does_not_start_a_second_server(mon: Any) -> None:
    """A second start() does nothing."""
    server = mon._server  # pylint: disable=protected-access
    mon.start(0)
    assert mon._server is server  # pylint: disable=protected-access


# 2. publish() only stores the latest of its type and returns immediately
def test_publish_stores_latest_and_returns_fast(
    mon: Any, make_frame: MakeFrame, detection_packet: DetectionPacket, states: list[SystemState]
) -> None:
    """publish() stores the newest packet of each type, ignores unknown ones and never renders."""
    f1, f2 = make_frame(0), make_frame(1)
    started = time.perf_counter()
    mon.publish(f1)
    mon.publish(f2)
    mon.publish(detection_packet)
    mon.publish(states[0])
    mon.publish(object())  # unknown type: no exception
    assert time.perf_counter() - started < 0.05
    assert mon._cache is None  # pylint: disable=protected-access
    assert mon._frame is f2  # pylint: disable=protected-access
    assert mon._detection is detection_packet  # pylint: disable=protected-access
    assert mon._state is states[0]  # pylint: disable=protected-access


# 3. Boxes only for the DetectionPacket matching the frame shown
def test_boxes_only_on_matching_frame(
    mon: Any, make_frame: MakeFrame, detection_packet: DetectionPacket
) -> None:
    """A box is drawn only when the detection has the same frame_id as the frame shown."""
    frame_id = detection_packet.frame_id
    mon.publish(make_frame(frame_id))
    plain = get(mon, "/frame.jpg")  # no detection yet

    mon.publish(detection_packet)  # same frame_id
    boxed = get(mon, "/frame.jpg")
    assert green_pixels(boxed) > green_pixels(plain) + 20

    other = make_frame(frame_id + 1)  # different frame_id
    mon.publish(other)
    mon.publish(detection_packet)
    mismatched = get(mon, "/frame.jpg")
    mon.publish(other)
    assert mismatched == get(mon, "/frame.jpg")
    assert green_pixels(mismatched) <= green_pixels(plain) + 20


# 4. The original FramePacket image is never changed
def test_original_image_unchanged(
    mon: Any, make_frame: MakeFrame, detection_packet: DetectionPacket
) -> None:
    """Boxes are drawn on a copy; the frame's own pixels stay as they were."""
    frame = make_frame(detection_packet.frame_id)
    before = frame.image.copy()
    mon.publish(frame)
    mon.publish(detection_packet)
    get(mon, "/frame.jpg")
    get(mon, "/frame.jpg")
    assert np.array_equal(frame.image, before)
    assert not frame.image.flags.writeable


# 5. /status.json reflects the latest SystemState and DetectionPacket
def test_status_reflects_latest(
    mon: Any, make_frame: MakeFrame, detection_packet: DetectionPacket, states: list[SystemState]
) -> None:
    """The status shows the newest state and the detections of the newest detection packet."""
    mon.publish(make_frame(detection_packet.frame_id))
    mon.publish(detection_packet)
    mon.publish(states[0])
    status = json.loads(get(mon, "/status.json"))
    assert status["frame_id"] == detection_packet.frame_id
    assert len(status["detections"]) == len(detection_packet.detections)
    shown, sent = status["detections"][0], detection_packet.detections[0]
    assert shown["confidence"] == pytest.approx(sent.confidence)
    assert shown["class_name"] == sent.class_name
    assert shown["bbox"] == list(sent.bbox)
    assert status["state"] == states[0].state

    newer = dataclasses.replace(states[-1], state="ALERTING")
    mon.publish(newer)
    status = json.loads(get(mon, "/status.json"))
    assert status["state"] == "ALERTING"
    assert set(status) >= {"state", "fps", "frame_id", "detections"}


def test_status_before_anything_is_published(mon: Any) -> None:
    """With nothing published the status is empty, not an error."""
    status = json.loads(get(mon, "/status.json"))
    assert status == {"state": None, "fps": 0.0, "frame_id": None, "detections": []}


def test_frame_rate_comes_from_the_frames_published(mon: Any, make_frame: MakeFrame) -> None:
    """Two polls one second of capture time apart and 30 frames apart give 30 fps."""
    first = make_frame(0)
    mon.publish(first)
    assert json.loads(get(mon, "/status.json"))["fps"] == 0.0  # first poll: nothing to compare
    later = FramePacket(30, first.timestamp + 1_000_000_000, first.image, "video")
    mon.publish(later)
    assert json.loads(get(mon, "/status.json"))["fps"] == 30.0


# the page and the error answers
def test_the_page_is_served(mon: Any) -> None:
    """The root answers with the monitoring page."""
    page = get(mon, "/").decode()
    assert "HADES Monitor" in page and "/frame.jpg" in page and "/status.json" in page


def test_no_frame_yet_is_a_503_and_an_unknown_path_a_404(mon: Any) -> None:
    """Asking for the picture before one exists, or for an unknown path, is answered clearly."""
    with pytest.raises(urllib.error.HTTPError) as no_frame:
        get(mon, "/frame.jpg")
    assert no_frame.value.code == 503
    with pytest.raises(urllib.error.HTTPError) as unknown:
        get(mon, "/nothing")
    assert unknown.value.code == 404


def test_the_picture_is_a_valid_jpeg_of_the_frame_size(mon: Any, make_frame: MakeFrame) -> None:
    """/frame.jpg decodes to an image with the frame's height and width."""
    frame = make_frame(0)
    mon.publish(frame)
    image = cv2.imdecode(np.frombuffer(get(mon, "/frame.jpg"), np.uint8), cv2.IMREAD_COLOR)
    assert image.shape == frame.image.shape


def test_the_same_frame_is_not_encoded_twice(mon: Any, make_frame: MakeFrame) -> None:
    """Polling the same frame and detection again reuses the picture."""
    mon.publish(make_frame(0))
    first = get(mon, "/frame.jpg")
    cached = mon._cache  # pylint: disable=protected-access
    assert get(mon, "/frame.jpg") == first
    assert mon._cache is cached  # pylint: disable=protected-access
