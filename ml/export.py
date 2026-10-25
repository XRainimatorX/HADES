"""Conversion to the on-device model format (work package G)."""

from __future__ import annotations


def export(model_dir: str, target_format: str) -> str:
    """Convert a trained model to a hardware-specific format and return the new file path."""
    raise NotImplementedError
