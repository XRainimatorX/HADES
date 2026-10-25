"""Training, evaluation and model selection (work package G)."""

from __future__ import annotations


def train(config_path: str) -> str:
    """Train a model and return the new model folder."""
    raise NotImplementedError


def evaluate(model_dir: str, split: str) -> str:
    """Run the model on a split, write predictions and metrics, return the predictions path."""
    raise NotImplementedError
