"""Latency, FPS and memory measurement (work package F)."""

from __future__ import annotations

from hades.contracts import BenchmarkReport


def run_benchmark(kind: str, config_path: str, clip: str) -> BenchmarkReport:
    """Run one kind of measurement on a fixed clip."""
    raise NotImplementedError


def write_report(report: BenchmarkReport, path: str) -> None:
    """Save the report as JSON."""
    raise NotImplementedError
