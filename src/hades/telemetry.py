"""Event logging, run metadata, replay, summaries and error records (work packages E, M, N, R)."""

from __future__ import annotations

# import argparse
# from typing import Optional

# from hades.contracts import FramePacket, RunMetadata, SessionSummary


# class RunLog:
#     """Implements ``contracts.Telemetry``."""

#     def start_run(self, meta: RunMetadata) -> None:
#         """Create the run folder and write ``meta.json``."""
#         raise NotImplementedError

#     def record(self, message: object) -> None:
#         """Append one packet to ``events.jsonl``."""
#         raise NotImplementedError

#     def end_run(self) -> None:
#         """Finish writing and close the log."""
#         raise NotImplementedError


# class ReplaySource:
#     """Plays a recorded video as if it were live; ``source_type`` is ``video``."""

#     def open(self) -> None:
#         """Open the recording."""
#         raise NotImplementedError

#     def read(self) -> Optional[FramePacket]:
#         """Return the next frame, or None at the end."""
#         raise NotImplementedError

#     def close(self) -> None:
#         """Release the recording."""
#         raise NotImplementedError


# def summarise(run_dir: str) -> SessionSummary:
#     """Produce the one-page summary of a run."""
#     raise NotImplementedError


# def export_session(run_dir: str, out_dir: str) -> str:
#     """Write the run's events as a spreadsheet file and return its path."""
#     raise NotImplementedError


# def report_error(package: str, code: str, message: str, frame_id: Optional[int] = None) -> None:
#     """Record an error in the standard form."""
#     raise NotImplementedError


# def replay_main(argv: Optional[list[str]] = None) -> int:
#     """Entry point of ``hades-replay``."""
#     parser = argparse.ArgumentParser(
#         prog="hades-replay", description="Replay a clip through HADES."
#     )
#     parser.add_argument("--config", default="configs/default.yaml")
#     parser.add_argument("--clip", required=True)
#     parser.parse_args(argv)
#     raise NotImplementedError


# """Event logging, run metadata and video replay for HADES (work package E)."""

# from __future__ import annotations

import argparse
import dataclasses
import enum
import hashlib
import json
import logging
import math
import queue
import subprocess
import threading
import time

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
    
from typing import Any, Optional

import numpy as np

from hades.contracts import (
    ActuatorCommand,
    ActuatorStatus,
    DetectionPacket,
    ErrorRecord,
    EventRecord,
    FramePacket,
    RunMetadata,
    SessionSummary,
    SystemState,
    TrackingPacket,
)

logger = logging.getLogger(__name__)
SCHEMA_VERSION = "0.1"
_SENTINEL = object()

# These are the concrete packet names defined by contracts.py. Keep this
# mapping aligned with that file; contracts.py itself is not modified here.
_PACKET_TYPES = {
    FramePacket: "frame",
    DetectionPacket: "detection",
    TrackingPacket: "tracking",
    SystemState: "state",
    ActuatorCommand: "command",
    ActuatorStatus: "status",
    ErrorRecord: "error",
}


def file_sha256(path: str) -> str:
    """Return a file's SHA-256 hex digest, reading it in bounded chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def git_info() -> tuple[str, bool]:
    """Return (short commit, dirty); degrade safely when Git is unavailable."""
    repo_dir = Path(__file__).resolve().parents[2]
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return "unknown", False
    if not commit:
        return "unknown", False
    return commit, bool(status.strip())

def _to_json_value(value: Any) -> Any:
    """Convert contract values and NumPy values into plain JSON-compatible data."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, enum.Enum):
        return _to_json_value(value.value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, int):
        return value
    if isinstance(value, np.ndarray):
        return _to_json_value(value.tolist())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _to_json_value(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, dict):
        return {str(key): _to_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_json_value(item) for item in value]
    # Contract fields should normally be covered above. This fallback keeps
    # unexpected metadata printable rather than killing the writer thread.
    return str(value)

def packet_to_record(message: object) -> dict[str, Any]:
    """Convert one contracts.py packet into the flat events.jsonl format."""
    if isinstance(message, EventRecord):
        record = {"type": message.type}
        # EventRecord already carries the packet fields in its `fields` map.
        for key, value in message.fields.items():
            if key in {"type", "schema_version"}:
                raise ValueError(f"EventRecord.fields must not override {key!r}")
            record[key] = _to_json_value(value)
        record["schema_version"] = message.schema_version
        return record

    event_type = next(
        (name for packet_class, name in _PACKET_TYPES.items()
         if isinstance(message, packet_class)),
        None,
    )
    if event_type is None:
        raise TypeError(
            f"unsupported telemetry packet type: {type(message).__name__}"
        )
    if not dataclasses.is_dataclass(message):
        raise TypeError(f"packet {type(message).__name__} is not a dataclass")

    record: dict[str, Any] = {"type": event_type}
    # Avoid dataclasses.asdict() here: it deep-copies the potentially large
    # frame image before we can replace it with its dimensions.
    for field in dataclasses.fields(message):
        value = getattr(message, field.name)
        if isinstance(message, FramePacket) and field.name == "image":
            shape = getattr(value, "shape", None)
            if shape is None or len(shape) < 2:
                raise ValueError("FramePacket.image must have height and width")
            record["height"] = int(shape[0])
            record["width"] = int(shape[1])
        else:
            record[field.name] = _to_json_value(value)

    record.setdefault("schema_version", SCHEMA_VERSION)
    return record

class Telemetry:
    """Asynchronous implementation of the Telemetry protocol in contracts.py.

    `record()` performs only a short lock acquisition and an unbounded queue
    insertion. JSON conversion and disk I/O happen on the writer thread.
    """

    def __init__(self, runs_dir: str = "runs") -> None:
        self._runs_dir = Path(runs_dir)
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._file = None
        self._accepting = False
        self._state_lock = threading.Lock()
        self._writer_error: Optional[BaseException] = None
        self.run_dir: Optional[Path] = None

    def start_run(self, meta: RunMetadata) -> None:
        """Create `runs/<run_id>/`, write meta.json and start the writer."""
        if not isinstance(meta, RunMetadata):
            raise TypeError("meta must be a contracts.RunMetadata instance")

        with self._state_lock:
            if self._thread is not None:
                raise RuntimeError("start_run() called before the previous run ended")

            run_dir = self._runs_dir / meta.run_id
            run_dir.mkdir(parents=True, exist_ok=False)

            try:
                meta_payload = _to_json_value(meta)
                meta_path = run_dir / "meta.json"
                meta_path.write_text(
                    json.dumps(meta_payload, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8",
                )
                event_file = open(run_dir / "events.jsonl", "w", encoding="utf-8")
            except Exception:
                # Do not leave a half-started Telemetry instance behind.
                raise

            self._queue = queue.Queue()
            self._file = event_file
            self._writer_error = None
            self.run_dir = run_dir
            self._accepting = True
            self._thread = threading.Thread(
                target=self._writer_loop,
                name=f"hades-telemetry-{meta.run_id}",
                daemon=False,
            )
            self._thread.start()

    def record(self, message: object) -> None:
        """Queue a packet for asynchronous writing; return without disk I/O."""
        with self._state_lock:
            if not self._accepting:
                return
            self._queue.put_nowait(message)

    def end_run(self) -> None:
        """Drain all accepted records, flush and close the run log.

        The sentinel is queued while holding the same lock used by record(),
        so no accepted packet can be placed behind it.
        """
        with self._state_lock:
            thread = self._thread
            if thread is None:
                return
            self._accepting = False
            self._queue.put_nowait(_SENTINEL)

        thread.join()

        close_error = None
        try:
            if self._file is not None:
                self._file.close()
        except OSError as exc:
            close_error = exc
        finally:
            with self._state_lock:
                self._thread = None
                self._file = None
                self._accepting = False

        if self._writer_error is not None:
            raise RuntimeError("telemetry writer failed while writing events.jsonl") from self._writer_error
        if close_error is not None:
            raise RuntimeError("could not close events.jsonl cleanly") from close_error

    def _writer_loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is _SENTINEL:
                break
            try:
                line = json.dumps(
                    packet_to_record(item),
                    allow_nan=False,
                    separators=(",", ":"),
                )
                self._file.write(line + "\n")
            except (TypeError, ValueError, OSError) as exc:
                # Invalid packet data is logged and skipped; a disk write
                # failure is retained and reported by end_run().
                logger.exception("telemetry: failed to write event record")
                if isinstance(exc, OSError) and self._writer_error is None:
                    self._writer_error = exc
            except Exception as exc:  # keep unexpected packet errors contained
                logger.exception("telemetry: unexpected event serialization error")
                if self._writer_error is None:
                    self._writer_error = exc
            try:
                if self._queue.empty():
                    self._file.flush()
            except OSError as exc:
                if self._writer_error is None:
                    self._writer_error = exc
        try:
            self._file.flush()
        except OSError as exc:
            if self._writer_error is None:
                self._writer_error = exc


# Compatibility with earlier code that used the old name.
RunLog = Telemetry

class ReplaySource:
    """Replay a run's original video as a Source producing FramePackets."""

    def __init__(self, run_dir: str, realtime: bool = False) -> None:
        self._run_dir = Path(run_dir)
        self._realtime = realtime

        try:
            meta = json.loads(
                (self._run_dir / "meta.json").read_text(encoding="utf-8")
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"Cannot replay {run_dir!r}: meta.json was not found."
            ) from None
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Cannot replay {run_dir!r}: meta.json is invalid JSON ({exc})."
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"Cannot replay {run_dir!r}: could not read meta.json ({exc})."
            ) from exc

        if not isinstance(meta, dict):
            raise RuntimeError(
                f"Cannot replay {run_dir!r}: meta.json must contain a JSON object."
            )
        if meta.get("source_type") != "video":
            raise RuntimeError(
                f"Cannot replay run {meta.get('run_id', '?')}: source_type is "
                f"{meta.get('source_type')!r}; ReplaySource requires 'video'."
            )

        source_uri = meta.get("source_uri")
        if not isinstance(source_uri, str) or not source_uri.strip():
            raise RuntimeError(
                f"Cannot replay {run_dir!r}: meta.json has no valid source_uri."
            )
        self._source_uri = source_uri
        self._cap = None
        self._frame_id = 0
        self._fps = 0.0
        self._start_ns: Optional[int] = None

    def open(self) -> None:
        """Open the original video file."""
        import cv2

        video_path = Path(self._source_uri)
        if not video_path.is_file():
            raise RuntimeError(
                f"Cannot replay: original video file {self._source_uri!r} "
                "does not exist."
            )
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(
                f"Cannot replay: OpenCV could not open {self._source_uri!r}."
            )

        self.close()
        self._cap = capture
        self._fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        self._frame_id = 0
        self._start_ns = None

    def read(self) -> Optional[FramePacket]:
        """Return the next video frame as a live-style FramePacket, or None."""
        if self._cap is None:
            self.open()

        if self._realtime and self._fps > 0:
            if self._start_ns is None:
                self._start_ns = time.monotonic_ns()
            due_ns = self._start_ns + int(self._frame_id * 1_000_000_000 / self._fps)
            delay_s = (due_ns - time.monotonic_ns()) / 1_000_000_000
            if delay_s > 0:
                time.sleep(delay_s)

        ok, image = self._cap.read()
        if not ok:
            return None

        packet = FramePacket(
            frame_id=self._frame_id,
            timestamp=time.monotonic_ns(),
            image=image,
            source_type="video",
            schema_version=SCHEMA_VERSION,
        )
        self._frame_id += 1
        return packet

    def close(self) -> None:
        """Release the video capture; safe to call repeatedly."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None


# The following work packages are intentionally left as existing stubs.
def summarise(run_dir: str) -> SessionSummary:
    """Produce the one-page summary of a run."""
    raise NotImplementedError


def export_session(run_dir: str, out_dir: str) -> str:
    """Write the run's events as a spreadsheet file and return its path."""
    raise NotImplementedError


def report_error(
    package: str,
    code: str,
    message: str,
    frame_id: Optional[int] = None,
) -> None:
    """Record an error in the standard form."""
    raise NotImplementedError


def replay_main(argv: Optional[list[str]] = None) -> int:
    """Entry point of `hades-replay`."""
    parser = argparse.ArgumentParser(
        prog="hades-replay",
        description="Replay a clip through HADES.",
    )
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--clip", required=True)
    parser.parse_args(argv)
    raise NotImplementedError