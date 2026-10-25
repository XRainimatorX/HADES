"""Long-running stability test (work package O)."""

from __future__ import annotations

from hades.contracts import BenchmarkReport


def run_stability(duration_s: float, config_path: str) -> BenchmarkReport:
    """Run the system for the given time and report whether it stays stable."""
    raise NotImplementedError
