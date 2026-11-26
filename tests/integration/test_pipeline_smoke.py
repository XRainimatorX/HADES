"""Integration smoke test: A -> B -> decision skeleton -> E -> D, all real, on the fixture clip.

This is the check the Project Owner runs before merging (Issue 0, "Common Done Criteria"): the files
the run produces are opened and their contents compared with what was fed in. A file that merely
exists proves nothing.

It needs ``tests/fixtures/drone_daylight_01.mp4`` and ``tests/fixtures/test_model.pt``. The official
model has no drone class, so it finds nothing; what is proved here is that every part works together
and that the log is complete, not that drones are detected.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import pytest
from conftest import FIXTURES_DIR, require_real_file, require_real_video, write_config

from hades.config import load_config
from hades.contracts import SCHEMA_VERSION
from hades.pipeline import PipelineResult, main, run_pipeline
from hades.telemetry import ReplaySource, file_sha256


@pytest.fixture(name="run", scope="module")
def fixture_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """One full run of the real pipeline over the whole fixture clip, shared by the tests below."""
    video = require_real_video(FIXTURES_DIR / "drone_daylight_01.mp4")
    model = require_real_file(FIXTURES_DIR / "test_model.pt")
    tmp_path = tmp_path_factory.mktemp("smoke")
    path = write_config(
        tmp_path,
        source={"type": "video", "uri": str(video), "realtime": False},
        detector={"model_path": str(model), "min_confidence": 0.25},
        telemetry={"runs_dir": str(tmp_path / "runs")},
    )
    result = run_pipeline(load_config(path), path)
    capture = cv2.VideoCapture(str(video))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    return {"result": result, "video": video, "model": model, "count": count, "path": path}


def _events(result: PipelineResult) -> list[dict[str, Any]]:
    text = (result.run_dir / "events.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_every_frame_of_the_clip_is_processed(run: dict[str, Any]) -> None:
    """The run saw exactly the frames the video holds."""
    assert run["count"] > 0
    assert run["result"].frames == run["count"]


def test_events_jsonl_has_a_frame_a_detection_and_a_state_for_every_frame_id(
    run: dict[str, Any],
) -> None:
    """Every frame_id has its three records, with matching capture times, nothing missing."""
    events = _events(run["result"])
    assert len(events) == 3 * run["count"]
    for frame_id in range(run["count"]):
        group = {e["type"]: e for e in events if e["frame_id"] == frame_id}
        assert set(group) == {"frame", "detection", "state"}, f"frame {frame_id} is incomplete"
        assert group["frame"]["timestamp"] == group["detection"]["timestamp"]
        assert group["detection"]["t_detect"] >= group["detection"]["timestamp"]
        assert group["detection"]["detections"] == []
        assert group["state"]["state"] == "SCANNING"
    stamps = [e["timestamp"] for e in events if e["type"] == "frame"]
    assert stamps == sorted(stamps)


def test_frame_records_hold_the_size_and_never_the_picture(run: dict[str, Any]) -> None:
    """Frame records carry height and width, source type video, source cam0 and no image."""
    capture = cv2.VideoCapture(str(run["video"]))
    width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(
        capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )
    capture.release()
    frames = [e for e in _events(run["result"]) if e["type"] == "frame"]
    assert {(f["height"], f["width"]) for f in frames} == {(height, width)}
    assert {(f["source_type"], f["source_id"]) for f in frames} == {("video", "cam0")}
    assert all("image" not in f for f in frames)
    assert {f["schema_version"] for f in _events(run["result"])} == {SCHEMA_VERSION}


def test_meta_json_names_the_code_the_model_and_the_settings_that_ran(run: dict[str, Any]) -> None:
    """The fingerprints in meta.json are those of the files that were actually used."""
    meta = json.loads((run["result"].run_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["run_id"] == run["result"].run_id
    assert meta["model_sha256"] == file_sha256(str(run["model"]))
    assert meta["config_sha256"] == file_sha256(run["path"])
    assert meta["source_type"] == "video" and meta["source_uri"] == str(run["video"])
    assert meta["git_commit"] != "unknown" and meta["schema_version"] == SCHEMA_VERSION


def test_the_run_can_be_replayed_frame_for_frame(run: dict[str, Any]) -> None:
    """The recorded run replays the original video: same number of frames, numbered from 0."""
    replay = ReplaySource(str(run["result"].run_dir), realtime=False)
    replay.open()
    try:
        replayed = []
        while (frame := replay.read()) is not None:
            replayed.append(frame.frame_id)
    finally:
        replay.close()
    assert replayed == list(range(run["count"]))


def test_hades_run_from_the_command_line_writes_a_complete_log(
    tmp_path: Path,
    drone_daylight_01: Path,
    test_model: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The entry point reads the configuration, runs a clip and prints where the log is."""
    path = write_config(
        tmp_path,
        detector={"model_path": str(require_real_file(test_model))},
        telemetry={"runs_dir": str(tmp_path / "runs")},
        source={"realtime": False},
    )
    code = main(
        [
            "--config",
            path,
            "--clip",
            str(require_real_video(drone_daylight_01)),
            "--max-frames",
            "12",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "12 frames" in out
    run_dir = next((tmp_path / "runs").iterdir())
    lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 36
