import hashlib
import json
import time

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from unittest.mock import patch

import cv2
import numpy as np
import pytest

from hades.contracts import (
    ActuatorCommand,
    ActuatorStatus,
    DetectionPacket,
    ErrorRecord,
    FramePacket,
    RunMetadata,
    SystemState,
    TrackingPacket,
)
from hades.telemetry import (
    Telemetry,
    ReplaySource,
    file_sha256,
    git_info,
)

FIXTURES = Path(__file__).parent / "fixtures"

PACKETS_FILE = FIXTURES / "sample_packets.jsonl"
VIDEO_FILE = FIXTURES / "drone_daylight_01.mp4"


def assert_real_fixture(path: Path):
    """Check that a fixture exists and is not a Git LFS pointer."""
    assert path.is_file(), f"Missing fixture: {path}"

    with path.open("rb") as file:
        header = file.read(200)

    assert not header.startswith(
        b"version https://git-lfs.github.com/spec/v1"
    ), f"{path} is a Git LFS pointer, not the actual file"


@pytest.fixture
def packet_fixture():
    assert_real_fixture(PACKETS_FILE)
    return PACKETS_FILE


@pytest.fixture
def video_fixture():
    assert_real_fixture(VIDEO_FILE)
    return VIDEO_FILE


@pytest.fixture
def metadata(video_fixture):
    return RunMetadata(
        run_id="test-run-001",
        started_at="2026-11-20T12:00:00Z",
        git_commit="testcommit",
        git_dirty=False,
        model_path="models/test.pt",
        model_sha256="abc123",
        config_sha256="def456",
        hardware="test-hardware",
        source_type="video",
        source_uri=str(video_fixture.resolve()),
        schema_version="0.1",
    )


def test_start_run_creates_metadata(tmp_path, metadata):
    telemetry = Telemetry(runs_dir=str(tmp_path))

    telemetry.start_run(metadata)

    try:
        assert telemetry.run_dir == tmp_path / metadata.run_id

        meta_path = telemetry.run_dir / "meta.json"
        assert meta_path.is_file()

        saved = json.loads(meta_path.read_text())

        expected = {
            "run_id": metadata.run_id,
            "started_at": metadata.started_at,
            "git_commit": metadata.git_commit,
            "git_dirty": metadata.git_dirty,
            "model_path": metadata.model_path,
            "model_sha256": metadata.model_sha256,
            "config_sha256": metadata.config_sha256,
            "hardware": metadata.hardware,
            "source_type": metadata.source_type,
            "source_uri": metadata.source_uri,
            "schema_version": metadata.schema_version,
        }

        assert saved == expected

    finally:
        telemetry.end_run()

def load_packet_records(path):
    records = []

    with path.open(encoding="utf-8") as file:
        for line in file:
            if line.strip():
                records.append(json.loads(line))

    assert records, "The packet fixture contains no records"
    return records


def test_packets_are_written_correctly(
    tmp_path, metadata, packet_fixture
):
    telemetry = Telemetry(runs_dir=str(tmp_path))
    telemetry.start_run(metadata)

    try:
        packets = load_contract_packets(packet_fixture)

        for packet in packets:
            telemetry.record(packet)

    finally:
        telemetry.end_run()

    events_path = telemetry.run_dir / "events.jsonl"
    records = [
        json.loads(line)
        for line in events_path.read_text().splitlines()
        if line.strip()
    ]

    assert len(records) == len(packets)

    for packet, record in zip(packets, records):
        assert record["type"] == expected_event_type(packet)

        for field in packet.__dataclass_fields__:
            if isinstance(packet, FramePacket) and field == "image":
                continue
            assert field in record

def test_frame_record_uses_dimensions(tmp_path, metadata, frame_packet):
    telemetry = Telemetry(str(tmp_path))
    telemetry.start_run(metadata)

    try:
        telemetry.record(frame_packet)
    finally:
        telemetry.end_run()

    record = json.loads(
        (telemetry.run_dir / "events.jsonl").read_text().splitlines()[0]
    )

    assert record["height"] == frame_packet.image.shape[0]
    assert record["width"] == frame_packet.image.shape[1]
    assert "image" not in record

def test_numpy_and_tuple_values_are_json_compatible():
    from hades.telemetry import _to_json_value

    result = _to_json_value({
        "integer": np.int64(42),
        "float": np.float32(0.5),
        "bbox": (1.0, 2.0, 3.0, 4.0),
    })

    encoded = json.dumps(result)
    decoded = json.loads(encoded)

    assert decoded["integer"] == 42
    assert decoded["float"] == pytest.approx(0.5)
    assert decoded["bbox"] == [1.0, 2.0, 3.0, 4.0]

def test_end_run_writes_all_queued_packets(
    tmp_path, metadata, packets
):
    telemetry = Telemetry(str(tmp_path))
    telemetry.start_run(metadata)

    for packet in packets:
        telemetry.record(packet)

    telemetry.end_run()

    records = [
        json.loads(line)
        for line in (telemetry.run_dir / "events.jsonl")
        .read_text().splitlines()
    ]

    assert len(records) == len(packets)

def test_record_does_not_wait_for_disk(
    tmp_path, metadata, packet
):
    telemetry = Telemetry(str(tmp_path))
    telemetry.start_run(metadata)

    try:
        with patch.object(
            telemetry,
            "_writer_loop",
            wraps=telemetry._writer_loop,
        ):
            start = time.perf_counter()
            telemetry.record(packet)
            elapsed = time.perf_counter() - start

        assert elapsed < 0.1

    finally:
        telemetry.end_run()

def test_git_info_when_git_unavailable():
    with patch(
        "hades.telemetry.subprocess.run",
        side_effect=FileNotFoundError,
    ):
        result = git_info()

    assert result == ("unknown", False)

def test_file_sha256_matches_whole_file(packet_fixture):
    expected = hashlib.sha256(
        packet_fixture.read_bytes()
    ).hexdigest()

    actual = file_sha256(str(packet_fixture))

    assert actual == expected

def test_replay_video_frame_count_and_order(
    tmp_path, metadata, video_fixture
):
    telemetry = Telemetry(str(tmp_path))
    telemetry.start_run(metadata)
    telemetry.end_run()

    replay = ReplaySource(str(telemetry.run_dir))

    replayed = []

    try:
        while True:
            frame = replay.read()
            if frame is None:
                break

            assert frame.source_type == "video"
            replayed.append(frame.frame_id)

    finally:
        replay.close()

    cap = cv2.VideoCapture(str(video_fixture))
    original_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    assert len(replayed) == original_count
    assert replayed == list(range(original_count))

def test_replay_webcam_raises_runtime_error(tmp_path, metadata):
    webcam_meta = RunMetadata(
        run_id="webcam-test",
        started_at=metadata.started_at,
        git_commit=metadata.git_commit,
        git_dirty=metadata.git_dirty,
        model_path=metadata.model_path,
        model_sha256=metadata.model_sha256,
        config_sha256=metadata.config_sha256,
        hardware=metadata.hardware,
        source_type="webcam",
        source_uri="webcam-0",
        schema_version="0.1",
    )

    telemetry = Telemetry(str(tmp_path))
    telemetry.start_run(webcam_meta)
    telemetry.end_run()

    with pytest.raises(RuntimeError, match="requires 'video'"):
        ReplaySource(str(telemetry.run_dir))