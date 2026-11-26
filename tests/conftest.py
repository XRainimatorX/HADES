"""Shared test helpers and fixture paths (work package F).

Every work package uses these helpers:

* fixture paths for each file in ``tests/fixtures/``
* ``require_real_video()`` / ``require_real_file()`` fail clearly if a fixture is missing or a
  Git LFS pointer
* ``sample_packets()`` returns the records in ``sample_packets.jsonl`` as dictionaries
* ``packets``, ``states``, ``detection_packet`` build contract objects from those records
* ``make_frame(frame_id)`` builds a FramePacket from the fixture video
* ``write_config()`` writes a configuration file based on ``configs/default.yaml``

Import the functions with ``from conftest import require_real_video, sample_packets``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Union

import cv2
import pytest
import yaml

from hades.contracts import Detection, DetectionPacket, FramePacket, SystemState

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "configs" / "default.yaml"

LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"


def require_real_file(path: Path | str) -> Path:
    """Return the path if it is a real file; otherwise fail the test.

    Fails with a clear message when the file is missing or is a Git LFS pointer
    (a small text stub left behind when LFS files were not downloaded).
    """
    target = Path(path)
    if not target.is_file():
        pytest.fail(f"fixture missing: {target}. Commit it before running this test.")
    with open(target, "rb") as handle:
        head = handle.read(len(LFS_POINTER_PREFIX))
    if head == LFS_POINTER_PREFIX:
        pytest.fail(
            f"{target.name} is a Git LFS pointer, not the real file. "
            "Download it with: git lfs pull --include=tests/fixtures/"
        )
    return target


def require_real_video(path: Path | str) -> Path:
    """Return the path if it is a real video file; otherwise fail the test (Issue 0, rule 22)."""
    return require_real_file(path)


def sample_packets() -> list[dict[str, Any]]:
    """Return every packet in ``tests/fixtures/sample_packets.jsonl`` as a dictionary."""
    path = FIXTURES_DIR / "sample_packets.jsonl"
    if not path.is_file():
        pytest.fail(f"fixture missing: {path}. Commit it before running this test.")
    packets: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    packets.append(json.loads(line))
                except json.JSONDecodeError as error:
                    pytest.fail(f"{path.name} line {number} is not valid JSON: {error}")
    return packets


@pytest.fixture(name="drone_daylight_01")
def fixture_drone_daylight_01() -> Path:
    """Short clip with one drone in view."""
    return FIXTURES_DIR / "drone_daylight_01.mp4"


@pytest.fixture(name="no_drone_01")
def fixture_no_drone_01() -> Path:
    """Short clip of empty sky."""
    return FIXTURES_DIR / "no_drone_01.mp4"


@pytest.fixture(name="head_walk_01")
def fixture_head_walk_01() -> Path:
    """Short clip filmed from a helmet while walking."""
    return FIXTURES_DIR / "head_walk_01.mp4"


@pytest.fixture(name="sample_packets_path")
def fixture_sample_packets_path() -> Path:
    """One example of each Stage 2 packet, in the run-log format."""
    return FIXTURES_DIR / "sample_packets.jsonl"


@pytest.fixture(name="test_model")
def fixture_test_model() -> Path:
    """Official YOLOv8n pretrained weights, used for format and speed tests."""
    return FIXTURES_DIR / "test_model.pt"


# --- contract objects built from the shared fixtures ------------------------------------------


def _build(record: dict[str, Any]) -> Union[DetectionPacket, SystemState, None]:
    """Build the packet a run-log record describes; frame records have no image, so skip them."""
    fields = {key: value for key, value in record.items() if key != "type"}
    if record["type"] == "detection":
        fields["detections"] = tuple(
            Detection(tuple(d["bbox"]), d["class_name"], d["confidence"])
            for d in fields["detections"]
        )
        return DetectionPacket(**fields)
    if record["type"] == "state":
        return SystemState(**fields)
    return None


@pytest.fixture(name="packets", scope="session")
def fixture_packets() -> list[Union[DetectionPacket, SystemState]]:
    """The detection and state packets in sample_packets.jsonl, as contract objects."""
    built = (_build(record) for record in sample_packets())
    return [packet for packet in built if packet is not None]


@pytest.fixture(name="states", scope="session")
def fixture_states(packets: list[Any]) -> list[SystemState]:
    """Every SystemState in the sample packets."""
    found = [p for p in packets if isinstance(p, SystemState)]
    assert found, "sample_packets.jsonl contains no state record"
    return found


@pytest.fixture(name="detection_packet", scope="session")
def fixture_detection_packet(packets: list[Any]) -> DetectionPacket:
    """The first DetectionPacket in the sample packets that holds a detection."""
    found = [p for p in packets if isinstance(p, DetectionPacket) and p.detections]
    assert found, "sample_packets.jsonl has no detection record with a detection"
    return found[0]


@pytest.fixture(name="make_frame", scope="session")
def fixture_make_frame() -> Callable[[int], FramePacket]:
    """Return ``make_frame(frame_id)``: a FramePacket with that id, read from the fixture video.

    The picture is frame ``frame_id`` of the clip, wrapping round if the id is larger than the
    clip, so any id from the sample packets can be used with a short clip.
    """
    path = require_real_video(FIXTURES_DIR / "drone_daylight_01.mp4")

    def make(frame_id: int) -> FramePacket:
        capture = cv2.VideoCapture(str(path))
        try:
            count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_id % count)
            ok, image = capture.read()
        finally:
            capture.release()
        if not ok:
            pytest.fail(f"could not read a frame from {path.name}")
        fps = 30.0
        return FramePacket(frame_id, int(frame_id * 1e9 / fps), image, "video")

    return make


def write_config(directory: Path, **sections: dict[str, Any]) -> str:
    """Write ``config.yaml`` into ``directory``: the default configuration with sections changed.

    Each keyword is a section of the configuration (``source``, ``detector``, ...); its entries
    replace the default ones. Returns the path of the file.
    """
    data = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    for name, changes in sections.items():
        data[name].update(changes)
    path = directory / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)
