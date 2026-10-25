"""False positive / false negative analysis (work package H)."""

from __future__ import annotations

from hades.contracts import ErrorCaseReport, ThresholdSuggestion


def analyse(predictions_path: str, dataset_dir: str, conf: float) -> ErrorCaseReport:
    """Compare predictions with labels at a confidence level and list every mistake."""
    raise NotImplementedError


def suggest_thresholds(report: ErrorCaseReport) -> ThresholdSuggestion:
    """Turn the mistake list into recommended settings."""
    raise NotImplementedError
