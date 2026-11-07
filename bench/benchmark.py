"""Latency, FPS and memory measurement (work package F).

Stage 2 measures three things on a fixed clip played as a live source:

* ``latency``  capture to end of detection (``t_detect - timestamp``)
* ``fps``      frames processed per second
* ``memory``   resident memory at the start, at the end and at its peak

Range, false alarm rate and stability are measured in later stages, but they
already use the same report format.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import statistics
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

import psutil
import yaml

from hades.contracts import BenchmarkKind, BenchmarkReport, Detector, Source

_now_ns: Callable[[], int] = time.monotonic_ns

_NS_PER_MS = 1_000_000
_NS_PER_S = 1_000_000_000
_BYTES_PER_MB = 1024 * 1024

SUPPORTED_KINDS = ("latency", "fps", "memory")
_LATER_STAGES = {
    "range": "Stage 4",
    "false_alarm": "Stage 4",
    "stability": "Stage 5 (work package O)",
}


def _read_config(config_path: str) -> dict[str, object]:
    """Read the configuration file; only ``yaml.safe_load`` is used."""
    with open(config_path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{config_path}: expected a mapping at the top level")
    return data


def _section(cfg: dict[str, object], name: str) -> dict[str, object]:
    """Return one section of the configuration or raise a clear error."""
    value = cfg.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"configuration has no '{name}' section")
    return value


def _sha256_of(path: str) -> str:
    """SHA-256 of a file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_class(module: str, name: str, package: str) -> Any:
    """Look a class up by name, so this module imports before work packages A and B exist.

    Raises a clear error naming the work package if the class is not there yet.
    """
    try:
        return getattr(importlib.import_module(module), name)
    except AttributeError as error:
        raise RuntimeError(
            f"{module}.{name} was not found; it is delivered by work package {package}"
        ) from error


def _make_source(clip: str) -> Source:
    """Create the video-file source (WP A); the clip is played as a live source."""
    source: Source = _load_class("hades.sources", "VideoFileSource", "A")(clip, realtime=True)
    return source


def _make_detector(min_confidence: float) -> Detector:
    """Create the detector (WP B)."""
    detector: Detector = _load_class("hades.detect", "UltralyticsDetector", "B")(
        min_confidence=min_confidence
    )
    return detector


def _rss_mb() -> float:
    """Resident memory of this process in megabytes."""
    return float(psutil.Process().memory_info().rss) / _BYTES_PER_MB


def _percentile(sorted_values: list[float], fraction: float) -> float:
    """Nearest-rank percentile of an already sorted, non-empty list."""
    rank = max(1, math.ceil(fraction * len(sorted_values)))
    return sorted_values[rank - 1]


def _latency_result(latencies_ms: list[float]) -> dict[str, float]:
    """Median, 95th percentile (nearest rank) and maximum latency."""
    ordered = sorted(latencies_ms)
    return {
        "median_ms": float(statistics.median(ordered)),
        "p95_ms": float(_percentile(ordered, 0.95)),
        "max_ms": float(ordered[-1]),
    }


def _fps_result(start_ns: int, finish_ns: list[int]) -> dict[str, float]:
    """Average and lowest instantaneous frame rate from frame finish times."""
    elapsed_s = (finish_ns[-1] - start_ns) / _NS_PER_S
    fps_avg = len(finish_ns) / elapsed_s if elapsed_s > 0 else 0.0
    edges = [start_ns, *finish_ns]
    longest_s = max(b - a for a, b in zip(edges, edges[1:])) / _NS_PER_S
    fps_min = 1.0 / longest_s if longest_s > 0 else 0.0
    return {"fps_avg": fps_avg, "fps_min": fps_min}


def _check_kind(kind: str) -> None:
    """Raise a clear error for kinds that are not measured in this stage."""
    if kind in SUPPORTED_KINDS:
        return
    if kind in _LATER_STAGES:
        raise ValueError(
            f"kind '{kind}' is not measured in Stage 2; it is added in {_LATER_STAGES[kind]}"
        )
    raise ValueError(f"unknown kind '{kind}'; supported in Stage 2: {', '.join(SUPPORTED_KINDS)}")


def _measure(source: Source, detector: Detector) -> tuple[int, list[int], list[float], list[float]]:
    """Play the source through the detector; return start time, finish times, latencies, memory."""
    latencies_ms: list[float] = []
    finish_ns: list[int] = []
    memory_mb: list[float] = [_rss_mb()]
    source.open()
    start_ns = _now_ns()
    try:
        while True:
            frame = source.read()
            if frame is None:
                break
            packet = detector.detect(frame)
            finish_ns.append(_now_ns())
            latencies_ms.append((packet.t_detect - packet.timestamp) / _NS_PER_MS)
            memory_mb.append(_rss_mb())
    finally:
        source.close()
    return start_ns, finish_ns, latencies_ms, memory_mb


def _result_for(
    kind: str,
    start_ns: int,
    finish_ns: list[int],
    latencies_ms: list[float],
    memory_mb: list[float],
) -> dict[str, float]:
    """Pick the measured values that belong to ``kind``."""
    if kind == "latency":
        return _latency_result(latencies_ms)
    if kind == "fps":
        return _fps_result(start_ns, finish_ns)
    return {
        "memory_start_mb": memory_mb[0],
        "memory_end_mb": memory_mb[-1],
        "memory_peak_mb": max(memory_mb),
    }


def run_benchmark(kind: str, config_path: str, clip: str) -> BenchmarkReport:
    """Run one kind of measurement on a fixed clip.

    Hardware name, model path and minimum confidence come from the configuration
    file, so laptop figures are always labelled as laptop figures.
    """
    _check_kind(kind)
    cfg = _read_config(config_path)
    detector_cfg = _section(cfg, "detector")
    model_path = str(detector_cfg["model_path"])
    model_sha256 = _sha256_of(model_path)

    detector = _make_detector(float(str(detector_cfg["min_confidence"])))
    detector.load(model_path)
    start_ns, finish_ns, latencies_ms, memory_mb = _measure(_make_source(clip), detector)
    if not latencies_ms:
        raise RuntimeError(f"no frames were measured from {clip}")

    benchmark_kind: BenchmarkKind = kind  # type: ignore[assignment]
    return BenchmarkReport(
        run_id=str(uuid.uuid4()),
        kind=benchmark_kind,
        hardware=str(_section(cfg, "hardware")["name"]),
        model_sha256=model_sha256,
        samples=len(latencies_ms),
        result=_result_for(kind, start_ns, finish_ns, latencies_ms, memory_mb),
    )


def write_report(report: BenchmarkReport, path: str) -> None:
    """Save the report as JSON.

    ``path`` is the file to write; if it is an existing folder the report is
    written to ``<path>/<run_id>.json``. Missing parent folders are created.
    """
    target = Path(path)
    if target.is_dir():
        target = target / f"{report.run_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(asdict(report), handle, indent=2)
        handle.write("\n")
