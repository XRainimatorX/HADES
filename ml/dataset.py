"""Frame extraction, dataset split and validation (work package C)."""

from __future__ import annotations


def extract_frames(video_path: str, out_dir: str, every_n: int) -> list[str]:
    """Save every n-th frame of a video as an image and return the saved paths."""
    raise NotImplementedError


def build_split(dataset_dir: str, ratios: tuple[float, float, float], seed: int) -> str:
    """Assign images to splits by source video, write the manifest, return its path."""
    raise NotImplementedError


def validate_dataset(dataset_dir: str) -> list[str]:
    """Return a list of problems; empty means the dataset is valid."""
    raise NotImplementedError
