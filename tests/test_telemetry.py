"""Tests for the run log and the replay (work package E).

Runs are written into a temporary folder, never into ``runs/``. The packets come from the shared
``sample_packets.jsonl`` fixture and the frames from the fixture video, not from sample data
written here. Every test calls a function and checks what it returns or wrote.
"""

# type() is deliberate (np.int64 is an int subclass); the private converter and helper are tested
# directly because they define what the log contains.
# pylint: disable=unidiomatic-typecheck,protected-access

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
import pytest
from conftest import require_real_video, sample_packets

from hades import telemetry
from hades.contracts import (
    SCHEMA_VERSION,
    ActuatorCommand,
    Detection,
    DetectionPacket,
    EventRecord,
    FramePacket,
    RunMetadata,
    SystemState,
)
from hades.telemetry import ReplaySource, Telemetry, file_sha256, git_info, packet_to_record

MakeFrame = Callable[[int], FramePacket]


def _meta(source_type: str, source_uri: str, run_id: str = "test-run-001") -> RunMetadata:
    return RunMetadata(
        run_id=run_id,
        started_at="2026-11-20T12:00:00Z",
        git_commit="abc1234",
        git_dirty=False,
        model_path="tests/fixtures/test_model.pt",
        model_sha256="a" * 64,
        config_sha256="b" * 64,
        hardware="test-hardware",
        source_type=source_type,  # type: ignore[arg-type]
        source_uri=source_uri,
    )


@pytest.fixture(name="metadata")
def fixture_metadata(drone_daylight_01: Path) -> RunMetadata:
    """Metadata of a run whose source is the fixture video."""
    return _meta("video", str(require_real_video(drone_daylight_01).resolve()))


def _lines(run_dir: Path) -> list[dict[str, Any]]:
    text = (run_dir / "events.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _write_run(
    tmp_path: Path, metadata: RunMetadata, messages: list[object]
) -> tuple[Path, list[dict[str, Any]]]:
    log = Telemetry(runs_dir=str(tmp_path))
    log.start_run(metadata)
    for message in messages:
        log.record(message)
    log.end_run()
    assert log.run_dir is not None
    return log.run_dir, _lines(log.run_dir)


# 1. start_run creates the run folder and meta.json with every field
def test_start_run_creates_the_folder_and_metadata(tmp_path: Path, metadata: RunMetadata) -> None:
    """meta.json holds every RunMetadata field and nothing else."""
    log = Telemetry(runs_dir=str(tmp_path))
    log.start_run(metadata)
    try:
        assert log.run_dir == tmp_path / metadata.run_id
        saved = json.loads((tmp_path / metadata.run_id / "meta.json").read_text(encoding="utf-8"))
        assert saved == dataclasses.asdict(metadata)
        assert set(saved) == {f.name for f in dataclasses.fields(RunMetadata)}
        assert saved["schema_version"] == SCHEMA_VERSION
        assert (tmp_path / metadata.run_id / "events.jsonl").is_file()
    finally:
        log.end_run()


# 2. every packet type in sample_packets.jsonl is written as one line with the right type and fields
def test_each_sample_packet_is_written_as_one_line_with_its_type_and_fields(
    tmp_path: Path,
    metadata: RunMetadata,
    make_frame: MakeFrame,
    detection_packet: DetectionPacket,
    states: list[SystemState],
) -> None:
    """Frame, detection and state packets each give one line, in the order recorded."""
    frame = make_frame(detection_packet.frame_id)
    _, records = _write_run(tmp_path, metadata, [frame, detection_packet, states[0]])
    assert [r["type"] for r in records] == ["frame", "detection", "state"]
    by_type = {r["type"]: r for r in records}
    expected = {r["type"]: r for r in sample_packets()}
    assert by_type["detection"] == expected["detection"]
    assert by_type["state"] == expected["state"]
    assert {k for k in by_type["frame"] if k not in ("height", "width")} == {
        k for k in expected["frame"] if k not in ("height", "width")
    }
    assert by_type["frame"]["frame_id"] == frame.frame_id


@pytest.mark.parametrize(
    ("packet", "event_type"),
    [
        (ActuatorCommand(1, "blink", "pulse", False, 7, 10, 20), "command"),
        (SystemState("ALERTING", "CONFIRMED", 7, 10), "state"),
    ],
)
def test_other_packet_types_get_their_own_type(
    packet: object, event_type: str, tmp_path: Path, metadata: RunMetadata
) -> None:
    """The type string follows the packet class, and every field of the packet is kept."""
    _, records = _write_run(tmp_path, metadata, [packet])
    assert records[0]["type"] == event_type
    for field in dataclasses.fields(packet):  # type: ignore[arg-type]
        assert field.name in records[0]


def test_an_event_record_is_written_with_its_fields_flattened(
    tmp_path: Path, metadata: RunMetadata
) -> None:
    """An EventRecord keeps its type and puts its fields at the top level."""
    record = EventRecord("status", {"healthy": True, "t_status": 5})
    _, records = _write_run(tmp_path, metadata, [record])
    assert records == [
        {"type": "status", "healthy": True, "t_status": 5, "schema_version": SCHEMA_VERSION}
    ]


def test_an_event_record_cannot_override_the_type() -> None:
    """The type and schema version belong to the record, not to its fields."""
    with pytest.raises(ValueError, match="override"):
        packet_to_record(EventRecord("frame", {"type": "state"}))


# 3. a FramePacket record has height and width and no image
def test_a_frame_record_has_height_and_width_and_no_image(
    tmp_path: Path, metadata: RunMetadata, make_frame: MakeFrame
) -> None:
    """The picture itself is never written to the log."""
    frame = make_frame(3)
    _, records = _write_run(tmp_path, metadata, [frame])
    record = records[0]
    assert (record["height"], record["width"]) == frame.image.shape[:2]
    assert "image" not in record
    assert record["source_type"] == "video" and record["source_id"] == "cam0"


def test_recording_a_frame_does_not_copy_its_image(monkeypatch: pytest.MonkeyPatch) -> None:
    """dataclasses.asdict would deep-copy the image every frame; the writer must not use it."""

    def forbidden(*_: Any, **__: Any) -> None:
        raise AssertionError("dataclasses.asdict must not be used on a packet with an image")

    monkeypatch.setattr(dataclasses, "asdict", forbidden)
    frame = FramePacket(1, 2, np.zeros((4, 6, 3), np.uint8), "video")
    assert packet_to_record(frame)["width"] == 6


# 4. NumPy numbers and tuples are written as plain JSON values
def test_numpy_numbers_and_tuples_are_written_as_plain_json(
    tmp_path: Path, metadata: RunMetadata
) -> None:
    """np.float32 / np.int64 become float / int; a tuple becomes a list."""
    packet = DetectionPacket(
        frame_id=np.int64(9),  # type: ignore[arg-type]
        detections=(
            Detection(
                (np.float64(1.0), np.float64(2.0), np.float64(3.0), np.float64(4.0)),
                "drone",
                np.float32(0.5),  # type: ignore[arg-type]
            ),
        ),
        inference_ms=np.float32(12.5),  # type: ignore[arg-type]
        timestamp=np.int64(100),  # type: ignore[arg-type]
        t_detect=np.int64(200),  # type: ignore[arg-type]
    )
    run_dir, records = _write_run(tmp_path, metadata, [packet])
    record = records[0]
    assert record["frame_id"] == 9 and type(record["frame_id"]) is int  # noqa: E721
    assert record["detections"][0]["bbox"] == [1.0, 2.0, 3.0, 4.0]
    assert record["detections"][0]["confidence"] == 0.5
    json.loads((run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])


def test_values_that_json_cannot_hold_become_null(tmp_path: Path, metadata: RunMetadata) -> None:
    """NaN and infinity are not valid JSON; they are written as null, not as invalid text."""
    state = telemetry._to_json_value({"a": float("nan"), "b": float("inf"), "c": 1.5})
    assert state == {"a": None, "b": None, "c": 1.5}


# 5. records queued just before end_run all appear in the file
def test_every_record_queued_before_end_run_is_in_the_file(
    tmp_path: Path, metadata: RunMetadata, states: list[SystemState]
) -> None:
    """500 packets recorded in a burst and then end_run(): all 500 lines are there."""
    burst = [dataclasses.replace(states[0], frame_id=i) for i in range(500)]
    _, records = _write_run(tmp_path, metadata, list(burst))
    assert [r["frame_id"] for r in records] == list(range(500))


def test_records_after_end_run_are_ignored_and_end_run_can_repeat(
    tmp_path: Path, metadata: RunMetadata, states: list[SystemState]
) -> None:
    """Once the run has ended nothing more is accepted, and ending again is harmless."""
    log = Telemetry(runs_dir=str(tmp_path))
    log.start_run(metadata)
    log.record(states[0])
    log.end_run()
    log.record(states[0])
    log.end_run()
    assert log.run_dir is not None and len(_lines(log.run_dir)) == 1


# 6. record() returns without waiting for the disk
def test_record_does_not_wait_for_the_writer(
    tmp_path: Path,
    metadata: RunMetadata,
    states: list[SystemState],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With a writer that needs 50 ms per line, 20 calls to record() still return at once."""
    log = Telemetry(runs_dir=str(tmp_path))
    log.start_run(metadata)
    real_dumps = telemetry.json.dumps

    def slow_dumps(*args: Any, **kwargs: Any) -> str:
        time.sleep(0.05)
        return real_dumps(*args, **kwargs)

    monkeypatch.setattr(telemetry.json, "dumps", slow_dumps)
    started = time.perf_counter()
    for i in range(20):
        log.record(dataclasses.replace(states[0], frame_id=i))
    elapsed = time.perf_counter() - started
    assert elapsed < 0.4  # writing them takes about a second
    log.end_run()
    assert log.run_dir is not None and len(_lines(log.run_dir)) == 20


# 7. git_info returns ("unknown", False) when git cannot be run
@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError(),
        subprocess.CalledProcessError(128, "git"),
        subprocess.TimeoutExpired("git", 5),
    ],
)
def test_git_info_without_git(error: Exception, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing git, a failing git and a hung git all give ("unknown", False)."""

    def broken(*_: Any, **__: Any) -> Any:
        raise error

    monkeypatch.setattr(telemetry.subprocess, "run", broken)
    assert git_info() == ("unknown", False)


def test_git_info_in_the_repository_reports_a_commit_and_the_dirty_flag() -> None:
    """In this repository git works: a short hash and a boolean."""
    commit, dirty = git_info()
    assert commit != "unknown" and len(commit) >= 7 and isinstance(dirty, bool)


@pytest.mark.parametrize(
    ("status", "dirty"),
    [("", False), ("  \n", False), (" M src/hades/x.py\n", True), ("?? new.txt\n", True)],
)
def test_git_info_reports_whether_the_working_tree_has_changes(
    status: str, dirty: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clean tree gives dirty False; modified or untracked files give dirty True."""

    def fake_git(*args: str) -> str:
        return "abc1234\n" if args[0] == "rev-parse" else status

    monkeypatch.setattr(telemetry, "_git", fake_git)
    assert git_info() == ("abc1234", dirty)


def test_git_info_with_an_empty_commit_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """If git prints no commit the run is marked unknown rather than given an empty hash."""
    monkeypatch.setattr(telemetry, "_git", lambda *args: "\n")
    assert git_info() == ("unknown", False)


def test_git_is_called_with_a_fixed_argument_list_and_no_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue 0, rule 27: a list of arguments, never a shell command string."""
    calls: list[tuple[Any, dict[str, Any]]] = []

    def spy(args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, stdout="abc1234\n", stderr="")

    monkeypatch.setattr(telemetry.subprocess, "run", spy)
    git_info()
    assert calls and all(isinstance(args, list) and args[0] == "git" for args, _ in calls)
    assert all(not kwargs.get("shell") for _, kwargs in calls)


# 8. file_sha256 matches the hash of the whole file
def test_file_sha256_matches_the_whole_file(tmp_path: Path) -> None:
    """A file larger than one read chunk gives the same hash as hashing it at once."""
    path = tmp_path / "big.bin"
    path.write_bytes(np.random.default_rng(0).bytes(2_500_000))
    assert file_sha256(str(path)) == hashlib.sha256(path.read_bytes()).hexdigest()


def test_file_sha256_of_a_known_value(tmp_path: Path) -> None:
    """The hash of "abc" is the well-known SHA-256 value."""
    path = tmp_path / "abc.txt"
    path.write_bytes(b"abc")
    assert file_sha256(str(path)) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


# 9. replaying a video run gives the same number of frames in the same order
def test_replay_gives_the_same_frames_in_the_same_order(
    tmp_path: Path, metadata: RunMetadata
) -> None:
    """Every frame of the original video comes back once, numbered from 0, as source "video"."""
    run_dir, _ = _write_run(tmp_path, metadata, [])
    capture = cv2.VideoCapture(metadata.source_uri)
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    replay = ReplaySource(str(run_dir), realtime=False)
    replay.open()
    try:
        frames = []
        while (frame := replay.read()) is not None:
            frames.append(frame)
    finally:
        replay.close()
    assert [f.frame_id for f in frames] == list(range(count)) and count > 0
    assert {f.source_type for f in frames} == {"video"}
    assert all(f.image.ndim == 3 and f.image.shape[2] == 3 for f in frames)
    stamps = [f.timestamp for f in frames]
    assert stamps == sorted(stamps)


def test_replay_is_live_by_default(tmp_path: Path, metadata: RunMetadata) -> None:
    """By default frames come at the video's own rate, like a live source."""
    run_dir, _ = _write_run(tmp_path, metadata, [])
    replay = ReplaySource(str(run_dir))
    replay.open()
    try:
        started = time.monotonic()
        frames = [replay.read() for _ in range(10)]
        elapsed = time.monotonic() - started
    finally:
        replay.close()
    assert all(f is not None for f in frames) and elapsed >= 0.25


def test_read_after_close_returns_none_and_close_can_repeat(
    tmp_path: Path, metadata: RunMetadata
) -> None:
    """A replay that was opened and closed has stopped; it does not silently restart."""
    run_dir, _ = _write_run(tmp_path, metadata, [])
    replay = ReplaySource(str(run_dir), realtime=False)
    assert replay.read() is not None  # the first read opens the video
    replay.close()
    replay.close()
    assert replay.read() is None


# 10. replaying a run whose source was not a video file raises RuntimeError
def test_replaying_a_webcam_run_raises_runtime_error(tmp_path: Path) -> None:
    """Live camera runs are recorded but cannot be replayed (Issue 0, rule 20)."""
    run_dir, _ = _write_run(tmp_path, _meta("webcam", "0", "webcam-test"), [])
    with pytest.raises(RuntimeError, match="requires 'video'"):
        ReplaySource(str(run_dir))


def test_replay_errors_say_what_is_wrong(tmp_path: Path, metadata: RunMetadata) -> None:
    """A missing meta.json, broken JSON or a missing video each give a clear RuntimeError."""
    with pytest.raises(RuntimeError, match="meta.json was not found"):
        ReplaySource(str(tmp_path / "nowhere"))

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "meta.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="invalid JSON"):
        ReplaySource(str(broken))

    not_object = tmp_path / "list"
    not_object.mkdir()
    (not_object / "meta.json").write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(RuntimeError, match="JSON object"):
        ReplaySource(str(not_object))

    gone, _ = _write_run(tmp_path, _meta("video", str(tmp_path / "gone.mp4"), "gone"), [])
    replay = ReplaySource(str(gone))
    with pytest.raises(RuntimeError, match="does not exist"):
        replay.open()

    no_uri = tmp_path / "nouri"
    no_uri.mkdir()
    (no_uri / "meta.json").write_text('{"source_type": "video"}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="source_uri"):
        ReplaySource(str(no_uri))


# the writer
def test_a_packet_that_cannot_be_written_is_skipped_and_the_run_continues(
    tmp_path: Path, metadata: RunMetadata, states: list[SystemState]
) -> None:
    """An unsupported object is dropped (and logged); the packets around it are still written."""
    _, records = _write_run(tmp_path, metadata, [states[0], object(), states[0]])
    assert [r["type"] for r in records] == ["state", "state"]


def test_a_disk_error_in_the_writer_is_reported_by_end_run(
    tmp_path: Path,
    metadata: RunMetadata,
    states: list[SystemState],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If writing fails the run does not end silently: end_run() raises."""
    log = Telemetry(runs_dir=str(tmp_path))
    log.start_run(metadata)

    def full_disk(*_: Any, **__: Any) -> str:
        raise OSError("no space left on device")

    monkeypatch.setattr(telemetry.json, "dumps", full_disk)
    log.record(states[0])
    with pytest.raises(RuntimeError, match="writer failed"):
        log.end_run()


def test_starting_a_second_run_before_the_first_ends_is_an_error(
    tmp_path: Path, metadata: RunMetadata
) -> None:
    """One run at a time; ending the first allows the next."""
    log = Telemetry(runs_dir=str(tmp_path))
    log.start_run(metadata)
    try:
        with pytest.raises(RuntimeError, match="previous run"):
            log.start_run(_meta("video", metadata.source_uri, "second"))
    finally:
        log.end_run()
    log.start_run(_meta("video", metadata.source_uri, "second"))
    log.end_run()


def test_start_run_needs_run_metadata(tmp_path: Path) -> None:
    """Anything else than RunMetadata is refused."""
    with pytest.raises(TypeError, match="RunMetadata"):
        Telemetry(runs_dir=str(tmp_path)).start_run({"run_id": "x"})  # type: ignore[arg-type]


def test_a_run_folder_is_never_reused(tmp_path: Path, metadata: RunMetadata) -> None:
    """Starting a run with an id that already has a folder fails instead of overwriting it."""
    _write_run(tmp_path, metadata, [])
    with pytest.raises(FileExistsError):
        Telemetry(runs_dir=str(tmp_path)).start_run(metadata)


def test_importing_the_module_creates_no_runs_folder(tmp_path: Path) -> None:
    """Importing hades.telemetry and building a Telemetry writes nothing."""
    Telemetry(runs_dir=str(tmp_path / "runs"))
    assert not (tmp_path / "runs").exists()


class _Colour(enum.Enum):
    RED = "red"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (True, True),
        (np.bool_(False), False),
        (np.int32(7), 7),
        (_Colour.RED, "red"),
        (np.array([[1, 2], [3, 4]]), [[1, 2], [3, 4]]),
        ({1: (1, 2)}, {"1": [1, 2]}),
        (frozenset((3, 3)), [3]),
        (b"bytes", "b'bytes'"),
    ],
)
def test_values_are_converted_to_plain_json(value: Any, expected: Any) -> None:
    """Enums, arrays, sets, dictionary keys and unknown objects all become JSON-compatible."""
    converted = telemetry._to_json_value(value)  # pylint: disable=protected-access
    assert converted == expected
    json.dumps(converted)
