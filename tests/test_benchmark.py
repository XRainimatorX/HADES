"""Tests for the benchmark runner and the shared test helpers (work package F).

Stand-in sources and detectors with known timings are used, so the benchmark
code can be tested before work packages A and B are finished. Reports are
written to a temporary folder, never to ``bench/reports/``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

import cv2
import numpy as np
import pytest
from conftest import FIXTURES_DIR, LFS_POINTER_PREFIX, require_real_video, sample_packets

from bench import benchmark
from hades import contracts, detect, sources
from hades.contracts import BenchmarkReport, DetectionPacket, FramePacket

MS = 1_000_000


class StandInSource:
    """Delivers a fixed number of tiny frames, then None."""

    def __init__(self, frames: int) -> None:
        self._frames = frames
        self._next = 0
        self.opened = False
        self.closed = False

    def open(self) -> None:
        """Mark the source as open."""
        self.opened = True

    def read(self) -> Optional[FramePacket]:
        """Return the next frame or None at the end."""
        if self._next >= self._frames:
            return None
        frame = FramePacket(
            frame_id=self._next,
            timestamp=1_000 * (self._next + 1),
            image=np.zeros((2, 2, 3), dtype=np.uint8),
            source_type="video",
        )
        self._next += 1
        return frame

    def close(self) -> None:
        """Mark the source as closed."""
        self.closed = True


class StandInDetector:
    """Takes a known time per frame: ``latencies_ms[frame_id]``."""

    def __init__(self, latencies_ms: list[float], min_confidence: float) -> None:
        self.latencies_ms = latencies_ms
        self.min_confidence = min_confidence
        self.loaded_path: Optional[str] = None

    def load(self, model_path: str) -> None:
        """Remember which model was loaded."""
        self.loaded_path = model_path

    def detect(self, frame: FramePacket) -> DetectionPacket:
        """Return an empty packet whose t_detect is timestamp plus the known latency."""
        latency_ns = int(self.latencies_ms[frame.frame_id] * MS)
        return DetectionPacket(
            frame_id=frame.frame_id,
            detections=[],
            inference_ms=1.0,
            timestamp=frame.timestamp,
            t_detect=frame.timestamp + latency_ns,
        )


class Harness:
    """Wires stand-ins into the benchmark and records what was created."""

    def __init__(self, tmp_path: Path, latencies_ms: list[float]) -> None:
        self.model = tmp_path / "model.pt"
        self.model.write_bytes(b"not a real model, only bytes to hash")
        self.config = tmp_path / "config.yaml"
        self.set_config(hardware="unit-test-laptop")
        self.source = StandInSource(len(latencies_ms))
        self.detector: Optional[StandInDetector] = None
        self.latencies_ms = latencies_ms
        self.clip_requested: Optional[str] = None

    def set_config(self, hardware: str) -> None:
        """Write a configuration file naming the hardware."""
        self.config.write_text(
            f"hardware:\n  name: {hardware}\n"
            f"detector:\n  model_path: {self.model.as_posix()}\n  min_confidence: 0.4\n",
            encoding="utf-8",
        )

    def make_source(self, clip: str) -> StandInSource:
        """Stand-in for benchmark._make_source."""
        self.clip_requested = clip
        return self.source

    def make_detector(self, min_confidence: float) -> StandInDetector:
        """Stand-in for benchmark._make_detector."""
        self.detector = StandInDetector(self.latencies_ms, min_confidence)
        return self.detector


@pytest.fixture(name="make_harness")
def fixture_make_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[list[float]], Harness]:
    """Build a harness with the given per-frame latencies and install it."""

    def build(latencies_ms: list[float]) -> Harness:
        harness = Harness(tmp_path, latencies_ms)
        monkeypatch.setattr(benchmark, "_make_source", harness.make_source)
        monkeypatch.setattr(benchmark, "_make_detector", harness.make_detector)
        return harness

    return build


def clock(monkeypatch: pytest.MonkeyPatch, values: list[int]) -> None:
    """Make the benchmark's monotonic clock return the given values in order."""
    ticks: Iterator[int] = iter(values)
    monkeypatch.setattr(benchmark, "_now_ns", lambda: next(ticks))


# --- 1. require_real_video ---------------------------------------------------


def test_require_real_video_fails_on_lfs_pointer(tmp_path: Path) -> None:
    """A Git LFS pointer is rejected with a message that says what to do."""
    pointer = tmp_path / "clip.mp4"
    pointer.write_bytes(LFS_POINTER_PREFIX + b"\noid sha256:abc\nsize 123\n")
    with pytest.raises(pytest.fail.Exception, match="LFS pointer"):
        require_real_video(pointer)


def test_require_real_video_fails_on_missing_file(tmp_path: Path) -> None:
    """A missing fixture is reported by name."""
    with pytest.raises(pytest.fail.Exception, match="fixture missing"):
        require_real_video(tmp_path / "absent.mp4")


def test_require_real_video_passes_on_real_video(tmp_path: Path) -> None:
    """A video written by OpenCV passes and its path is returned."""
    path = tmp_path / "real.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (32, 32))
    for _ in range(5):
        writer.write(np.zeros((32, 32, 3), dtype=np.uint8))
    writer.release()
    assert require_real_video(path) == path


# --- shared fixtures: names and sample packets -------------------------------


@pytest.mark.parametrize(
    ("name", "filename"),
    [
        ("drone_daylight_01", "drone_daylight_01.mp4"),
        ("no_drone_01", "no_drone_01.mp4"),
        ("head_walk_01", "head_walk_01.mp4"),
        ("sample_packets_path", "sample_packets.jsonl"),
        ("test_model", "test_model.pt"),
    ],
)
def test_every_fixture_is_available_by_name(
    name: str, filename: str, request: pytest.FixtureRequest
) -> None:
    """Each file in Issue 0's fixture list resolves to its path inside tests/fixtures/."""
    assert request.getfixturevalue(name) == FIXTURES_DIR / filename


def test_sample_packets_returns_every_packet_in_the_file(sample_packets_path: Path) -> None:
    """sample_packets() returns one dictionary per non-empty line of the file, in order."""
    lines = [line for line in sample_packets_path.read_text(encoding="utf-8").splitlines() if line]
    packets = sample_packets()
    assert len(packets) == len(lines) == 3
    assert packets == [json.loads(line) for line in lines]


def test_sample_packets_cover_frame_detection_and_state() -> None:
    """One example of each Stage 2 packet, with the fields docs/spec.md and contracts.py define."""
    by_type = {packet["type"]: packet for packet in sample_packets()}
    assert set(by_type) == {"frame", "detection", "state"}

    frame_fields = [f.name for f in dataclasses.fields(contracts.FramePacket) if f.name != "image"]
    assert set(by_type["frame"]) == {"type", "height", "width", *frame_fields}
    assert "image" not in by_type["frame"]

    detection_fields = [f.name for f in dataclasses.fields(contracts.DetectionPacket)]
    assert set(by_type["detection"]) == {"type", *detection_fields}
    detection = by_type["detection"]["detections"][0]
    assert set(detection) == {f.name for f in dataclasses.fields(contracts.Detection)}
    assert detection["class_name"] == "drone"

    state_fields = [f.name for f in dataclasses.fields(contracts.SystemState)]
    assert set(by_type["state"]) == {"type", *state_fields}


def test_sample_packets_belong_to_one_frame_and_obey_timing() -> None:
    """All three packets describe the same frame, and detection finishes after capture."""
    packets = {packet["type"]: packet for packet in sample_packets()}
    assert {p["frame_id"] for p in packets.values()} == {1042}
    assert packets["detection"]["t_detect"] >= packets["frame"]["timestamp"]
    assert packets["detection"]["timestamp"] == packets["frame"]["timestamp"]
    assert all(p["schema_version"] == contracts.SCHEMA_VERSION for p in packets.values())


def test_sample_packets_fails_clearly_when_a_line_is_not_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A broken line is reported with its line number."""
    import conftest  # pylint: disable=import-outside-toplevel

    (tmp_path / "sample_packets.jsonl").write_text(
        '{"type": "frame"}\nnot json\n', encoding="utf-8"
    )
    monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)
    with pytest.raises(pytest.fail.Exception, match="line 2"):
        conftest.sample_packets()


# --- 2. latency --------------------------------------------------------------


def test_latency_reports_median_p95_and_max(make_harness: Callable[[list[float]], Harness]) -> None:
    """Latencies 1..20 ms give median 10.5, nearest-rank p95 19 and maximum 20."""
    harness = make_harness([float(n) for n in range(1, 21)])
    report = benchmark.run_benchmark("latency", str(harness.config), "clip.mp4")
    assert report.kind == "latency"
    assert report.result == {"median_ms": 10.5, "p95_ms": 19.0, "max_ms": 20.0}


def test_latency_values_are_ordered(make_harness: Callable[[list[float]], Harness]) -> None:
    """Median never exceeds p95, and p95 never exceeds the maximum, for unsorted input."""
    harness = make_harness([30.0, 5.0, 80.0, 12.0, 7.0, 41.0, 9.0])
    result = benchmark.run_benchmark("latency", str(harness.config), "clip.mp4").result
    assert result["median_ms"] <= result["p95_ms"] <= result["max_ms"]
    assert result["median_ms"] == 12.0
    assert result["max_ms"] == 80.0


# --- 3. samples --------------------------------------------------------------


@pytest.mark.parametrize("kind", ["latency", "fps", "memory"])
def test_samples_equals_frames_measured(
    kind: str, make_harness: Callable[[list[float]], Harness]
) -> None:
    """samples is the number of frames the source delivered."""
    harness = make_harness([2.0] * 7)
    report = benchmark.run_benchmark(kind, str(harness.config), "clip.mp4")
    assert report.samples == 7


def test_source_is_opened_closed_and_given_the_clip(
    make_harness: Callable[[list[float]], Harness],
) -> None:
    """The clip is passed to the source, which is opened and then closed."""
    harness = make_harness([1.0, 1.0])
    benchmark.run_benchmark("latency", str(harness.config), "tests/fixtures/x.mp4")
    assert harness.clip_requested == "tests/fixtures/x.mp4"
    assert harness.source.opened and harness.source.closed


def test_source_is_closed_when_detection_fails(
    make_harness: Callable[[list[float]], Harness],
) -> None:
    """A detector error propagates, but the source is still closed."""
    harness = make_harness([1.0])  # one latency for two frames: the second frame raises IndexError
    harness.source = StandInSource(2)
    with pytest.raises(IndexError):
        benchmark.run_benchmark("latency", str(harness.config), "clip.mp4")
    assert harness.source.closed


def test_no_frames_is_an_error(make_harness: Callable[[list[float]], Harness]) -> None:
    """A clip that yields no frames cannot produce a report."""
    harness = make_harness([])
    with pytest.raises(RuntimeError, match="no frames"):
        benchmark.run_benchmark("latency", str(harness.config), "clip.mp4")


# --- 4. fps and memory -------------------------------------------------------


def test_fps_reports_average_and_minimum(
    make_harness: Callable[[list[float]], Harness], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Frames finishing at 0.1, 0.2, 0.3 and 0.7 s: 4 frames in 0.7 s, slowest gap 0.4 s."""
    harness = make_harness([1.0] * 4)
    clock(monkeypatch, [0, 100 * MS, 200 * MS, 300 * MS, 700 * MS])
    result = benchmark.run_benchmark("fps", str(harness.config), "clip.mp4").result
    assert set(result) == {"fps_avg", "fps_min"}
    assert result["fps_avg"] == pytest.approx(4 / 0.7)
    assert result["fps_min"] == pytest.approx(1 / 0.4)


def test_memory_reports_start_end_and_peak(
    make_harness: Callable[[list[float]], Harness], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Start is the first sample, end the last, peak the largest."""
    harness = make_harness([1.0] * 3)
    readings = iter([100.0, 120.0, 150.0, 130.0])
    monkeypatch.setattr(benchmark, "_rss_mb", lambda: next(readings))
    result = benchmark.run_benchmark("memory", str(harness.config), "clip.mp4").result
    assert result == {"memory_start_mb": 100.0, "memory_end_mb": 130.0, "memory_peak_mb": 150.0}


def test_real_memory_reading_is_positive() -> None:
    """The unpatched memory reading is a positive number of megabytes."""
    assert benchmark._rss_mb() > 0  # pylint: disable=protected-access


# --- 5. hardware and model ---------------------------------------------------


def test_hardware_comes_from_the_configuration(
    make_harness: Callable[[list[float]], Harness],
) -> None:
    """The hardware label is whatever the configuration says."""
    harness = make_harness([1.0, 2.0])
    harness.set_config(hardware="pi5-hailo")
    report = benchmark.run_benchmark("latency", str(harness.config), "clip.mp4")
    assert report.hardware == "pi5-hailo"


def test_model_is_hashed_loaded_and_configured(
    make_harness: Callable[[list[float]], Harness],
) -> None:
    """The report carries the model's SHA-256; the detector gets the configured path and threshold."""
    harness = make_harness([1.0, 2.0])
    report = benchmark.run_benchmark("latency", str(harness.config), "clip.mp4")
    assert report.model_sha256 == hashlib.sha256(harness.model.read_bytes()).hexdigest()
    assert harness.detector is not None
    assert harness.detector.loaded_path == harness.model.as_posix()
    assert harness.detector.min_confidence == 0.4
    assert report.schema_version == "0.1"
    assert len(report.run_id) == 36


def test_run_ids_are_unique(make_harness: Callable[[list[float]], Harness]) -> None:
    """Two runs never share a run_id."""
    harness = make_harness([1.0])
    first = benchmark.run_benchmark("latency", str(harness.config), "clip.mp4")
    harness.source = StandInSource(1)
    second = benchmark.run_benchmark("latency", str(harness.config), "clip.mp4")
    assert first.run_id != second.run_id


# --- configuration and model errors ------------------------------------------


def test_config_that_is_not_a_mapping_is_rejected(
    make_harness: Callable[[list[float]], Harness],
) -> None:
    """A configuration file that does not hold sections is reported with its path."""
    harness = make_harness([1.0])
    harness.config.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected a mapping"):
        benchmark.run_benchmark("latency", str(harness.config), "clip.mp4")


def test_config_without_a_detector_section_is_rejected(
    make_harness: Callable[[list[float]], Harness],
) -> None:
    """A missing section is named in the error."""
    harness = make_harness([1.0])
    harness.config.write_text("hardware:\n  name: x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="'detector' section"):
        benchmark.run_benchmark("latency", str(harness.config), "clip.mp4")


def test_missing_model_file_stops_the_run_before_any_frame_is_read(
    make_harness: Callable[[list[float]], Harness],
) -> None:
    """The model hash needs the file; without it nothing is opened or measured."""
    harness = make_harness([1.0])
    harness.model.unlink()
    with pytest.raises(FileNotFoundError):
        benchmark.run_benchmark("latency", str(harness.config), "clip.mp4")
    assert not harness.source.opened


# --- A and B are called as their issues define -------------------------------


def test_factories_call_a_and_b_with_the_arguments_their_issues_define(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VideoFileSource(path, realtime=True) and UltralyticsDetector(min_confidence=...)."""

    class FakeSource:
        """Records how it was constructed."""

        def __init__(self, path: str, realtime: bool) -> None:
            self.args: tuple[str, bool] = (path, realtime)

    class FakeDetector:
        """Records how it was constructed."""

        def __init__(self, min_confidence: float) -> None:
            self.min_confidence = min_confidence

    monkeypatch.setattr(sources, "VideoFileSource", FakeSource, raising=False)
    monkeypatch.setattr(detect, "UltralyticsDetector", FakeDetector, raising=False)
    made_source: Any = benchmark._make_source("c.mp4")  # pylint: disable=protected-access
    made_detector: Any = benchmark._make_detector(0.3)  # pylint: disable=protected-access
    assert made_source.args == ("c.mp4", True)
    assert made_detector.min_confidence == 0.3


@pytest.mark.parametrize(
    ("factory", "argument", "name", "package"),
    [
        ("_make_source", "c.mp4", "VideoFileSource", "A"),
        ("_make_detector", 0.3, "UltralyticsDetector", "B"),
    ],
)
def test_missing_a_or_b_class_names_the_work_package(
    factory: str, argument: object, name: str, package: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Before A and B are delivered, the error says which class and which package is missing."""
    monkeypatch.delattr(sources, "VideoFileSource", raising=False)
    monkeypatch.delattr(detect, "UltralyticsDetector", raising=False)
    with pytest.raises(RuntimeError, match=rf"{name}.*work package {package}"):
        getattr(benchmark, factory)(argument)


def test_fps_is_zero_when_no_time_passed(
    make_harness: Callable[[list[float]], Harness], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clock that does not advance gives zero rather than a division error."""
    harness = make_harness([1.0] * 2)
    clock(monkeypatch, [5, 5, 5])
    result = benchmark.run_benchmark("fps", str(harness.config), "clip.mp4").result
    assert result == {"fps_avg": 0.0, "fps_min": 0.0}


# --- 6. unsupported kinds ----------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "stage"),
    [("range", "Stage 4"), ("false_alarm", "Stage 4"), ("stability", "Stage 5")],
)
def test_later_kinds_name_their_stage(
    kind: str, stage: str, make_harness: Callable[[list[float]], Harness]
) -> None:
    """Kinds measured later raise an error that names the stage they belong to."""
    harness = make_harness([1.0])
    with pytest.raises(ValueError, match=stage):
        benchmark.run_benchmark(kind, str(harness.config), "clip.mp4")


def test_unknown_kind_lists_supported_kinds(make_harness: Callable[[list[float]], Harness]) -> None:
    """A kind that does not exist is rejected and the supported ones are listed."""
    harness = make_harness([1.0])
    with pytest.raises(ValueError, match="latency, fps, memory"):
        benchmark.run_benchmark("sparkle", str(harness.config), "clip.mp4")


# --- 7. write_report ---------------------------------------------------------


def _report() -> BenchmarkReport:
    return BenchmarkReport(
        run_id="3f2c9a1e-7b4d-4e8a-9f1c-2d5e6a7b8c9d",
        kind="latency",
        hardware="dev-laptop",
        model_sha256="9b1e",
        samples=412,
        result={"median_ms": 31.2, "p95_ms": 48.7, "max_ms": 63.0},
    )


def test_write_report_content_equals_report(tmp_path: Path) -> None:
    """The file written holds exactly the report's fields and values."""
    report = _report()
    target = tmp_path / "reports" / f"{report.run_id}.json"
    benchmark.write_report(report, str(target))
    assert json.loads(target.read_text(encoding="utf-8")) == asdict(report)


def test_write_report_into_a_folder_names_the_file_by_run_id(tmp_path: Path) -> None:
    """Given an existing folder, the file is ``<run_id>.json``."""
    report = _report()
    benchmark.write_report(report, str(tmp_path))
    written = tmp_path / f"{report.run_id}.json"
    assert json.loads(written.read_text(encoding="utf-8"))["run_id"] == report.run_id
