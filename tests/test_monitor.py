import dataclasses
import json
import threading
import time
import urllib.request
from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from hades.monitor import WebMonitor


@pytest.fixture
def mon():
    before = threading.active_count()
    m = WebMonitor()
    m.start(0)                                   # port 0 = any free port
    m._port = m._server.server_address[1]
    m._threads_added = threading.active_count() - before
    yield m
    m.stop()


def get(m, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{m._port}{path}", timeout=3) as r:
        return r.read()


def green_pixels(jpeg: bytes) -> int:
    a = np.asarray(Image.open(BytesIO(jpeg)).convert("RGB")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return int(((g > 150) & (r < 100) & (b < 100)).sum())


# 1. start() runs the server in one background thread
def test_start_uses_one_background_thread(mon):
    assert mon._thread.is_alive() and mon._thread.daemon
    assert mon._threads_added == 1
    for _ in range(5):                           # requests must not add threads
        get(mon, "/status.json")
    assert threading.active_count() - (threading.active_count() - mon._threads_added) \
        == mon._threads_added


# 2. publish() only stores the latest of its type and returns immediately
def test_publish_stores_latest_and_returns_fast(mon, make_frame, detection_packet, states):
    f1, f2 = make_frame(0), make_frame(1)
    t0 = time.perf_counter()
    mon.publish(f1); mon.publish(f2)
    mon.publish(detection_packet); mon.publish(states[0])
    mon.publish(object())                        # unknown type: no exception
    assert time.perf_counter() - t0 < 0.01
    assert mon._cache is None                    # nothing rendered by publish()
    assert mon._frame is f2                      # latest of its type only
    assert mon._detection is detection_packet and mon._state is states[0]


# 3. Boxes only for the DetectionPacket matching the frame shown
def test_boxes_only_on_matching_frame(mon, make_frame, detection_packet):
    fid = detection_packet.frame_id
    frame = make_frame(fid)
    mon.publish(frame)
    plain = get(mon, "/frame.jpg")               # no detection yet

    mon.publish(detection_packet)                # same frame_id
    boxed = get(mon, "/frame.jpg")
    assert green_pixels(boxed) > green_pixels(plain) + 20

    other = make_frame(fid + 1)                  # different frame_id
    mon.publish(other)
    mon.publish(detection_packet)
    mismatched = get(mon, "/frame.jpg")
    mon.publish(other)                           # reference render of that frame
    assert mismatched == get(mon, "/frame.jpg")
    assert green_pixels(mismatched) <= green_pixels(plain) + 20


# 4. The original FramePacket image is never changed
def test_original_image_unchanged(mon, make_frame, detection_packet):
    frame = make_frame(detection_packet.frame_id)
    before = frame.image.copy()
    mon.publish(frame); mon.publish(detection_packet)
    get(mon, "/frame.jpg"); get(mon, "/frame.jpg")
    assert np.array_equal(frame.image, before)


# 5. /status.json reflects the latest SystemState and DetectionPacket
def test_status_reflects_latest(mon, make_frame, detection_packet, states):
    mon.publish(make_frame(detection_packet.frame_id))
    mon.publish(detection_packet)
    mon.publish(states[0])
    s = json.loads(get(mon, "/status.json"))
    assert s["frame_id"] == detection_packet.frame_id
    assert len(s["detections"]) == len(detection_packet.detections)
    d0, p0 = s["detections"][0], detection_packet.detections[0]
    assert d0["confidence"] == pytest.approx(p0.confidence)
    assert d0["class_name"] == str(getattr(p0.class_name, "name", p0.class_name))
    assert s["state"] == str(getattr(states[0].state, "name", states[0].state))

    newer = dataclasses.replace(states[-1])      # publish a later state
    mon.publish(newer)
    s = json.loads(get(mon, "/status.json"))
    assert s["state"] == str(getattr(newer.state, "name", newer.state))
    assert set(s) >= {"state", "fps", "frame_id", "detections"}