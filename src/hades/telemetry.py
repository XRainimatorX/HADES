"""Event logging, run metadata, replay, summaries and error records (work packages E, M, N, R)."""

from __future__ import annotations

import argparse
from typing import Optional

from hades.contracts import FramePacket, RunMetadata, SessionSummary


class RunLog:
    """Implements ``contracts.Telemetry``."""

    def start_run(self, meta: RunMetadata) -> None:
        """Create the run folder and write ``meta.json``."""
        raise NotImplementedError

    def record(self, message: object) -> None:
        """Append one packet to ``events.jsonl``."""
        raise NotImplementedError

    def end_run(self) -> None:
        """Finish writing and close the log."""
        raise NotImplementedError


class ReplaySource:
    """Plays a recorded video as if it were live; ``source_type`` is ``video``."""

    def open(self) -> None:
        """Open the recording."""
        raise NotImplementedError

    def read(self) -> Optional[FramePacket]:
        """Return the next frame, or None at the end."""
        raise NotImplementedError

    def close(self) -> None:
        """Release the recording."""
        raise NotImplementedError


def summarise(run_dir: str) -> SessionSummary:
    """Produce the one-page summary of a run."""
    raise NotImplementedError


def export_session(run_dir: str, out_dir: str) -> str:
    """Write the run's events as a spreadsheet file and return its path."""
    raise NotImplementedError


def report_error(package: str, code: str, message: str, frame_id: Optional[int] = None) -> None:
    """Record an error in the standard form."""
    raise NotImplementedError


def replay_main(argv: Optional[list[str]] = None) -> int:
    """Entry point of ``hades-replay``."""
    parser = argparse.ArgumentParser(
        prog="hades-replay", description="Replay a clip through HADES."
    )
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--clip", required=True)
    parser.parse_args(argv)
    raise NotImplementedError
