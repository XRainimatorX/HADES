"""Assembles the chain, runs the main loop, diagnostics, demo and integration runs (P, M, K)."""

from __future__ import annotations

import argparse
from typing import Optional

from hades.contracts import DiagnosticStatus, IntegrationResult


class PipelineDiagnostics:
    """Implements ``contracts.Diagnostics``."""

    def snapshot(self) -> DiagnosticStatus:
        """Collect the current health of every part."""
        raise NotImplementedError


def run_demo(clip: str, config_path: str) -> None:
    """Play a demo clip through the full system."""
    raise NotImplementedError


def run_integration(clip: str, config_path: str) -> IntegrationResult:
    """Run the full pipeline on a clip and check the log."""
    raise NotImplementedError


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point of ``hades-run``."""
    parser = argparse.ArgumentParser(prog="hades-run", description="Run the HADES pipeline.")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.parse_args(argv)
    raise NotImplementedError
