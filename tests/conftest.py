import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hades.contracts import (Detection, DetectionPacket, FramePacket,
                             SystemState)

FIXTURES = ROOT / "tests" / "fixtures"
LFS_MAGIC = b"version https://git-lfs.github.com/spec/"


def assert_real_file(path: Path) -> None:
    """Issue 0, rule 22: fail loudly if a fixture is missing or an LFS pointer."""
    assert path.is_file(), f"fixture missing: {path}"
    with path.open("rb") as f:
        head = f.read(256)
    assert not head.startswith(LFS_MAGIC), (
        f"{path.name} is a Git LFS pointer, not the real file. "
        "Run `git lfs pull` and try again."
    )
    assert path.stat().st_size > 0, f"{path.name} is empty"
    if path.suffix == ".mp4":
        assert b"ftyp" in head[:16], f"{path.name} does not look like an MP4"


# ASSUMPTION: each JSONL line is {"type": "...", "data": {...}}. Adjust here only.
def _build(obj: dict):
    kind, data = obj["type"], dict(obj["data"])
    if kind == "DetectionPacket":
        data["detections"] = [Detection(**d) for d in data["detections"]]
        return DetectionPacket(**data)
    if kind == "SystemState":
        return SystemState(**data)
    if kind == "FramePacket":
        raise ValueError("frames come from the video, not the JSONL")
    raise ValueError(f"unknown packet type: {kind}")


@pytest.fixture(scope="session")
def packets():
    path = FIXTURES / "sample_packets.jsonl"
    assert_real_file(path)
    out = []
    with path.open() as f:
        for line in f:
            if line.strip():
                obj = json.loads(line)
                if obj["type"] != "FramePacket":
                    out.append(_build(obj))
    return out


@pytest.fixture(scope="session")
def states(packets):
    found = [p for p in packets if isinstance(p, SystemState)]
    assert found, "sample_packets.jsonl contains no SystemState"
    return found


@pytest.fixture(scope="session")
def detection_packet(packets):
    found = [p for p in packets
             if isinstance(p, DetectionPacket) and p.detections]
    assert found, "sample_packets.jsonl has no DetectionPacket with detections"
    return found[0]


SOURCE_TYPE = "video"   # ASSUMPTION: replace with the real SourceType value


@pytest.fixture(scope="session")
def make_frame():
    """Return make_frame(frame_id) -> FramePacket read from the fixture video."""
    import cv2
    path = FIXTURES / "drone_daylight_01.mp4"
    assert_real_file(path)

    def _make(frame_id: int) -> FramePacket:
        cap = cv2.VideoCapture(str(path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)   # ASSUMPTION: id == index
        ok, image = cap.read()
        cap.release()
        assert ok, f"could not read frame {frame_id} from the fixture video"
        return FramePacket(frame_id=frame_id,
                           timestamp=int(frame_id * 1e9 / fps),
                           image=image, source_type=SOURCE_TYPE)
    return _make