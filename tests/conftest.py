"""Shared test helpers and fixture paths (work package F).

Every work package uses these helpers:

* fixture paths for each file in ``tests/fixtures/``
* ``require_real_video()`` fails clearly if a fixture is a Git LFS pointer
* ``sample_packets()`` returns the packets in ``sample_packets.jsonl``

Import the functions with ``from conftest import require_real_video, sample_packets``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"


def require_real_video(path: Path | str) -> Path:
    """Return the path if it is a real video file; otherwise fail the test.

    Fails with a clear message when the file is missing or is a Git LFS pointer
    (a small text stub left behind when LFS files were not downloaded).
    """
    video = Path(path)
    if not video.is_file():
        pytest.fail(f"fixture missing: {video}. Commit it before running this test.")
    with open(video, "rb") as handle:
        head = handle.read(len(LFS_POINTER_PREFIX))
    if head == LFS_POINTER_PREFIX:
        pytest.fail(
            f"{video.name} is a Git LFS pointer, not a real video. "
            "Download it with: git lfs pull --include=tests/fixtures/"
        )
    return video


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
