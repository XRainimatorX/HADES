"""Configuration loading and validation (work package Q)."""

from __future__ import annotations

from hades.contracts import Config


def load_config(path: str) -> Config:
    """Read the configuration file."""
    raise NotImplementedError


def validate_config(cfg: Config) -> list[str]:
    """Return a list of problems; empty means valid."""
    raise NotImplementedError
