"""Tests for the main program (the Stage 2 minimum of work package P).

The pipeline is run with stand-in sources and detectors whose behaviour is scripted, so the order
of events, the alert shortcut and the way a run ends are checked exactly. The real parts working
together are in ``tests/integration/``.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pytest
from conftest import write_config

from hades import pipeline
from hades.alert import MockAlert
from hades.config import REPO_ROOT, load_config
from hades.contracts import (
    ActuatorCommand,
    Detection,
    DetectionPacket,
    FramePacket,
    SystemState,
)
from hades.pipeline import build_metadata, build_source, run_pipeline
from hades.sources import VideoFileSource, VirtualPiCamSource, WebcamSource

STEP_NS = 33_333_333  # 30 fps


class StandInSource:
    """Delivers ``count`` small frames 1/30 s apart, then None; can fail on a chosen frame."""

    def __init__(self, count: int, fail_at: Optional[BaseException] = None, fail_on: int = -1):
        self.count, self.fail_at, self.fail_on = count, fail_at, fail_on
        self.next = 0
        self.opened = self.closed = False

    def open(self) -> None:
        """Mark as open."""
        self.opened = True

    def read(self) -> Optional[FramePacket]:
        """Return the next frame, or None at the end; raise the scripted error on one frame."""
        if self.next == self.fail_on and self.fail_at is not None:
            raise self.fail_at
        if self.next >= self.count:
            return None
        frame = FramePacket(
            self.next, 1_000 + self.next * STEP_NS, np.zeros((4, 6, 3), np.uint8), "video"
        )
        self.next += 1
        return frame

    def close(self) -> None:
        """Mark as closed."""
        self.closed = True


class ScriptedDetector:
    """Finds a drone on the frames in ``hits``; can fail on a chosen frame."""

    def __init__(self, hits: set[int], fail_on: int = -1) -> None:
        self.hits, self.fail_on = hits, fail_on
        self.loaded: Optional[str] = None

    def load(self, model_path: str) -> None:
        """Remember the model path."""
        self.loaded = model_path

    def detect(self, frame: FramePacket) -> DetectionPacket:
        """Return a detection on the scripted frames and none on the others."""
        if frame.frame_id == self.fail_on:
            raise RuntimeError("model failed")
        found = (
            (Detection((1.0, 1.0, 4.0, 4.0), "drone", 0.9),) if frame.frame_id in self.hits else ()
        )
        return DetectionPacket(frame.frame_id, found, 5.0, frame.timestamp, frame.timestamp + 10)


class Recorder:
    """Stands in for the web monitor and the OLED screen: remembers what it was given."""

    def __init__(self) -> None:
        self.published: list[Any] = []
        self.updates: list[tuple[SystemState, float]] = []

    def publish(self, message: object) -> None:
        """Remember a published packet."""
        self.published.append(message)

    def update(self, state: SystemState, fps: float) -> None:
        """Remember a screen update."""
        self.updates.append((state, fps))


@pytest.fixture(name="setup")
def fixture_setup(tmp_path: Path) -> dict[str, Any]:
    """A configuration whose model file exists and whose runs folder is temporary."""
    model = tmp_path / "model.pt"
    model.write_bytes(b"not a real model")
    path = write_config(
        tmp_path,
        detector={"model_path": str(model)},
        telemetry={"runs_dir": str(tmp_path / "runs")},
        source={"type": "video", "uri": str(tmp_path / "x.mp4"), "realtime": False},
    )
    return {"path": path, "cfg": load_config(path), "model": model, "tmp": tmp_path}


def _events(result: pipeline.PipelineResult) -> list[dict[str, Any]]:
    text = (result.run_dir / "events.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _run(setup: dict[str, Any], frames: int = 6, hits: Optional[set[int]] = None, **kw: Any) -> Any:
    return run_pipeline(
        setup["cfg"],
        setup["path"],
        source=kw.pop("source", StandInSource(frames)),
        detector=kw.pop("detector", ScriptedDetector(hits or set())),
        display=kw.pop("display", Recorder()),
        **kw,
    )


# --- the run ----------------------------------------------------------------------------------


def test_a_run_writes_metadata_and_every_frame_with_its_detection_and_state(
    setup: dict[str, Any],
) -> None:
    """For every frame the log holds a frame, a detection and a state record, in that order."""
    result = _run(setup, frames=6)
    assert (result.frames, result.detections, result.commands) == (6, 0, 0)
    assert (result.run_dir / "meta.json").is_file() and result.run_dir.name == result.run_id
    events = _events(result)
    assert [e["type"] for e in events] == ["frame", "detection", "state"] * 6
    for frame_id in range(6):
        group = [e for e in events if e["frame_id"] == frame_id]
        assert [e["type"] for e in group] == ["frame", "detection", "state"]
        assert group[0]["timestamp"] == group[1]["timestamp"] == group[2]["timestamp"]


def test_the_decision_skeleton_reports_scanning_and_issues_no_command(
    setup: dict[str, Any],
) -> None:
    """Every state record says SCANNING; the first one comes after IDLE."""
    events = _events(_run(setup, frames=4))
    states = [e for e in events if e["type"] == "state"]
    assert [s["state"] for s in states] == ["SCANNING"] * 4
    assert [s["previous"] for s in states] == ["IDLE", "SCANNING", "SCANNING", "SCANNING"]
    assert not [e for e in events if e["type"] == "command"]


def test_the_led_turns_on_at_the_first_detection_and_off_at_the_first_empty_frame(
    setup: dict[str, Any],
) -> None:
    """Temporary Stage 2 shortcut: a detection sends the configured alert to the alert mock."""
    alert = MockAlert()
    result = _run(setup, frames=8, hits={2, 3, 4}, alert=alert)
    assert (result.detections, result.commands) == (3, 2)
    commands = [e for e in _events(result) if e["type"] == "command"]
    assert [(c["frame_id"], c["alert_level"]) for c in commands] == [(2, 1), (5, 0)]
    chosen = setup["cfg"].alert.on_alert
    assert (commands[0]["led_mode"], commands[0]["buzzer_mode"], commands[0]["laser_on"]) == (
        chosen.led_mode,
        chosen.buzzer_mode,
        chosen.laser_on,
    )
    assert (commands[1]["led_mode"], commands[1]["buzzer_mode"], commands[1]["laser_on"]) == (
        "off",
        "off",
        False,
    )
    assert [c.alert_level for c in alert.history] == [1, 0]
    status = alert.status()
    assert (status.led_mode, status.laser_on) == ("off", False)
    statuses = [e for e in _events(result) if e["type"] == "status"]
    assert [s["led_mode"] for s in statuses] == [chosen.led_mode, "off"]


def test_a_command_is_sent_once_while_the_target_stays_in_view(setup: dict[str, Any]) -> None:
    """Five frames with a target give one "on" command, not five."""
    assert _run(setup, frames=5, hits={0, 1, 2, 3, 4}).commands == 1


def test_the_command_carries_the_frame_time_and_a_later_issue_time(setup: dict[str, Any]) -> None:
    """t_command minus timestamp is the end-to-end latency, so it is never negative."""
    commands = [e for e in _events(_run(setup, frames=3, hits={1})) if e["type"] == "command"]
    assert commands and all(c["t_command"] >= c["timestamp"] for c in commands)


def test_the_display_is_updated_each_frame_with_the_state_and_the_frame_rate(
    setup: dict[str, Any],
) -> None:
    """The OLED gets every state; the frame rate is 30 fps from the second frame on."""
    screen = Recorder()
    _run(setup, frames=5, display=screen)
    assert len(screen.updates) == 5
    assert [s.frame_id for s, _ in screen.updates] == [0, 1, 2, 3, 4]
    assert screen.updates[0][1] == 0.0
    assert all(fps == pytest.approx(30.0, rel=0.01) for _, fps in screen.updates[1:])


def test_the_monitor_gets_the_frame_the_detection_and_the_state(setup: dict[str, Any]) -> None:
    """Each frame publishes its three packets to the web monitor."""
    monitor = Recorder()
    _run(setup, frames=3, monitor=monitor)
    kinds = [type(m).__name__ for m in monitor.published]
    assert kinds == ["FramePacket", "DetectionPacket", "SystemState"] * 3


def test_the_model_is_loaded_from_the_configured_path_before_the_first_frame(
    setup: dict[str, Any],
) -> None:
    """detector.load() receives the path from the configuration."""
    detector = ScriptedDetector(set())
    _run(setup, frames=1, detector=detector)
    assert detector.loaded == str(setup["model"])


def test_max_frames_stops_the_run_early_and_closes_the_source(setup: dict[str, Any]) -> None:
    """The source is closed and exactly that many frames were processed."""
    source = StandInSource(100)
    result = _run(setup, source=source, max_frames=7)
    assert result.frames == 7 and source.opened and source.closed


# --- how a run ends ---------------------------------------------------------------------------


def test_when_the_source_ends_the_decision_layer_is_told(
    setup: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """on_source_lost() is called, and a command it returns reaches the alert and the log."""
    off = ActuatorCommand(0, "off", "off", False, 3, 1, 2)

    class Engine(pipeline.StateMachine):
        """A decision engine that issues an off command when the source is lost."""

        def on_source_lost(self, timestamp: int) -> Optional[ActuatorCommand]:
            return off

    monkeypatch.setattr(pipeline, "StateMachine", Engine)
    alert = MockAlert()
    result = _run(setup, frames=3, alert=alert)
    assert [e for e in _events(result) if e["type"] == "command"][-1]["alert_level"] == 0
    assert result.commands == 1


def test_an_error_in_the_detector_still_closes_the_source_and_the_log(
    setup: dict[str, Any],
) -> None:
    """The records of the frames before the error are written, and the error is raised."""
    source = StandInSource(10)
    with pytest.raises(RuntimeError, match="model failed"):
        _run(setup, source=source, detector=ScriptedDetector(set(), fail_on=3))
    assert source.closed
    run_dir = next((setup["tmp"] / "runs").iterdir())
    lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 3 * 3  # frames 0-2 complete; frame 3's frame record too


def test_ctrl_c_closes_the_log_and_main_returns_130(
    setup: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Stopping with Ctrl+C loses no record: three frames were read, three are in the log."""
    source = StandInSource(10, fail_at=KeyboardInterrupt(), fail_on=3)
    monkeypatch.setattr(pipeline, "build_source", lambda cfg: source)
    monkeypatch.setattr(pipeline, "UltralyticsDetector", lambda **kw: ScriptedDetector(set()))
    assert pipeline.main(["--config", setup["path"]]) == 130
    assert "run log was closed" in capsys.readouterr().out
    run_dir = next((setup["tmp"] / "runs").iterdir())
    events = [json.loads(x) for x in (run_dir / "events.jsonl").read_text().splitlines()]
    assert [e["type"] for e in events].count("frame") == 3 and source.closed


# --- refusing to start ------------------------------------------------------------------------


def test_an_invalid_configuration_stops_the_run_before_anything_is_created(
    setup: dict[str, Any],
) -> None:
    """Out-of-range settings are named, and no run folder appears."""
    bad = write_config(
        setup["tmp"],
        detector={"model_path": str(setup["model"]), "min_confidence": 9.0},
        telemetry={"runs_dir": str(setup["tmp"] / "runs")},
    )
    source = StandInSource(3)
    with pytest.raises(ValueError, match="min_confidence"):
        run_pipeline(load_config(bad), bad, source=source, detector=ScriptedDetector(set()))
    assert not (setup["tmp"] / "runs").exists() and not source.opened


def test_a_missing_model_file_stops_the_run_before_anything_is_created(
    setup: dict[str, Any],
) -> None:
    """The model fingerprint needs the file; without it there is no run."""
    setup["model"].unlink()
    with pytest.raises(FileNotFoundError):
        _run(setup)
    assert not (setup["tmp"] / "runs").exists()


# --- building the parts -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source_type", "uri", "expected"),
    [
        ("video", "clips/a.mp4", VideoFileSource),
        ("picam", "clips/a.mp4", VirtualPiCamSource),
        ("webcam", "2", WebcamSource),
    ],
)
def test_the_configured_source_type_decides_which_source_is_built(
    source_type: str, uri: str, expected: type, setup: dict[str, Any]
) -> None:
    """video plays a file, picam is the virtual Pi camera, webcam is a laptop camera."""
    cfg = load_config(
        write_config(
            setup["tmp"],
            source={"type": source_type, "uri": uri, "width": 320, "height": 180, "fps": 15.0},
        )
    )
    source: Any = build_source(cfg.source)
    assert isinstance(source, expected)
    if source_type == "webcam":
        assert (source.device, source.width, source.height, source.fps) == (2, 320, 180, 15.0)
    else:
        assert Path(source.path) == REPO_ROOT / "clips" / "a.mp4"
    if source_type == "picam":
        assert (source.width, source.height, source.fps) == (320, 180, 15.0)
    if source_type == "video":
        assert source.realtime is cfg.source.realtime


def test_the_metadata_names_the_code_the_model_and_the_settings(setup: dict[str, Any]) -> None:
    """Fingerprints are those of the real files; the source is an absolute path for a video."""
    meta = build_metadata(setup["cfg"], setup["path"])
    assert re.fullmatch(r"[0-9a-f-]{36}", meta.run_id)
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", meta.started_at)
    assert meta.model_sha256 == hashlib.sha256(setup["model"].read_bytes()).hexdigest()
    assert meta.config_sha256 == hashlib.sha256(Path(setup["path"]).read_bytes()).hexdigest()
    assert meta.hardware == setup["cfg"].hardware.name and meta.source_type == "video"
    assert Path(meta.source_uri).is_absolute() and isinstance(meta.git_dirty, bool)
    assert meta.git_commit != "unknown"


def test_the_metadata_of_a_webcam_run_keeps_the_device_number(setup: dict[str, Any]) -> None:
    """A webcam has no file path; its source is recorded as the camera number."""
    path = write_config(
        setup["tmp"],
        source={"type": "webcam", "uri": "0"},
        detector={"model_path": str(setup["model"])},
    )
    assert build_metadata(load_config(path), path).source_uri == "0"


def test_two_runs_never_share_an_id(setup: dict[str, Any]) -> None:
    """Every run gets a new run_id."""
    ids = {build_metadata(setup["cfg"], setup["path"]).run_id for _ in range(5)}
    assert len(ids) == 5


def test_main_with_a_clip_plays_that_file_instead_of_the_configured_source(
    setup: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """--clip overrides the source; --max-frames limits the run; a summary line is printed."""
    seen: list[Any] = []

    def fake_build(cfg: Any) -> StandInSource:
        seen.append(cfg)
        return StandInSource(50)

    monkeypatch.setattr(pipeline, "build_source", fake_build)
    monkeypatch.setattr(pipeline, "UltralyticsDetector", lambda **kw: ScriptedDetector(set()))
    code = pipeline.main(["--config", setup["path"], "--clip", "my.mp4", "--max-frames", "4"])
    assert code == 0
    assert (seen[0].type, seen[0].uri) == ("video", "my.mp4")
    assert re.search(
        r"run [0-9a-f-]{36}: 4 frames, 0 detections, 0 alert commands", capsys.readouterr().out
    )


def test_the_configuration_path_may_be_relative_to_the_repository_root() -> None:
    """hades-run --config configs/default.yaml works from any folder."""
    assert Path(pipeline._resolve_config("configs/default.yaml")).is_file()  # pylint: disable=W0212
