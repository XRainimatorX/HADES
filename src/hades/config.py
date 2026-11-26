"""Configuration loading and validation (work package Q, minimal version).

``load_config`` reads ``configs/default.yaml`` (or any file with the same layout) with
``yaml.safe_load`` and builds a ``contracts.Config``. ``validate_config`` checks the values.
Work package Q extends this in Stage 6; nothing here may change the file layout in
``docs/spec.md`` (section Q).

Relative paths in a configuration (model path, runs folder) are relative to the repository
root, not to the folder the program is started from; ``resolve_path`` applies that rule.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, get_args

import yaml

from hades.contracts import (
    SCHEMA_VERSION,
    AlertConfig,
    BuzzerMode,
    Config,
    DecisionConfig,
    DetectorConfig,
    HardwareConfig,
    LedMode,
    OnAlertConfig,
    SourceConfig,
    SourceType,
    TelemetryConfig,
    TrackerConfig,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def resolve_path(path: str) -> Path:
    """Return an absolute path; a relative one is taken relative to the repository root."""
    candidate = Path(path).expanduser()
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def _section(data: dict[str, Any], name: str, where: str) -> dict[str, Any]:
    """Return one mapping from the configuration or raise a clear error."""
    value = data.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"{where}: missing section '{name}'")
    return value


def _get(section: dict[str, Any], key: str, kind: type, where: str) -> Any:
    """Return ``section[key]`` as ``kind`` (an int is accepted where a float is expected)."""
    if key not in section:
        raise ValueError(f"{where}: missing value '{key}'")
    value = section[key]
    if kind is float and isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise ValueError(f"{where}: '{key}' must be {kind.__name__}, got {value!r}")
    return value


def load_config(path: str) -> Config:
    """Read the configuration file and build a ``Config``.

    Raises ``ValueError`` naming the missing or mistyped entry; ranges are checked
    separately by ``validate_config``.
    """
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected sections at the top level")
    where = path
    hardware = _section(data, "hardware", where)
    source = _section(data, "source", where)
    detector = _section(data, "detector", where)
    tracker = _section(data, "tracker", where)
    decision = _section(data, "decision", where)
    alert = _section(data, "alert", where)
    on_alert = _section(alert, "on_alert", f"{where} alert")
    telemetry = _section(data, "telemetry", where)
    return Config(
        schema_version=str(_get(data, "schema_version", str, where)),
        hardware=HardwareConfig(name=_get(hardware, "name", str, where)),
        source=SourceConfig(
            type=_get(source, "type", str, where),
            uri=str(_get(source, "uri", str, where)),
            realtime=_get(source, "realtime", bool, where),
            width=_get(source, "width", int, where),
            height=_get(source, "height", int, where),
            fps=_get(source, "fps", float, where),
        ),
        detector=DetectorConfig(
            model_path=_get(detector, "model_path", str, where),
            min_confidence=_get(detector, "min_confidence", float, where),
        ),
        tracker=TrackerConfig(
            confirm_frames=_get(tracker, "confirm_frames", int, where),
            lost_frames=_get(tracker, "lost_frames", int, where),
        ),
        decision=DecisionConfig(
            conf_threshold=_get(decision, "conf_threshold", float, where),
            alert_duration_s=_get(decision, "alert_duration_s", float, where),
            cooldown_s=_get(decision, "cooldown_s", float, where),
        ),
        alert=AlertConfig(
            on_alert=OnAlertConfig(
                led_mode=_get(on_alert, "led_mode", str, where),
                buzzer_mode=_get(on_alert, "buzzer_mode", str, where),
                laser_on=_get(on_alert, "laser_on", bool, where),
            )
        ),
        telemetry=TelemetryConfig(runs_dir=_get(telemetry, "runs_dir", str, where)),
    )


def validate_config(cfg: Config) -> list[str]:
    """Return a list of problems; empty means valid."""
    problems: list[str] = []

    def check(ok: bool, message: str) -> None:
        if not ok:
            problems.append(message)

    check(
        cfg.schema_version == SCHEMA_VERSION,
        f"schema_version is {cfg.schema_version!r}, expected {SCHEMA_VERSION!r}",
    )
    check(bool(cfg.hardware.name.strip()), "hardware.name must not be empty")
    check(
        cfg.source.type in get_args(SourceType),
        f"source.type must be one of {get_args(SourceType)}, got {cfg.source.type!r}",
    )
    check(cfg.source.width > 0, "source.width must be positive")
    check(cfg.source.height > 0, "source.height must be positive")
    check(cfg.source.fps > 0, "source.fps must be positive")
    check(0.0 <= cfg.detector.min_confidence <= 1.0, "detector.min_confidence must be 0.0-1.0")
    check(bool(cfg.detector.model_path.strip()), "detector.model_path must not be empty")
    check(cfg.tracker.confirm_frames >= 1, "tracker.confirm_frames must be at least 1")
    check(cfg.tracker.lost_frames >= 1, "tracker.lost_frames must be at least 1")
    check(0.0 <= cfg.decision.conf_threshold <= 1.0, "decision.conf_threshold must be 0.0-1.0")
    check(cfg.decision.alert_duration_s >= 0, "decision.alert_duration_s must not be negative")
    check(cfg.decision.cooldown_s >= 0, "decision.cooldown_s must not be negative")
    check(
        cfg.alert.on_alert.led_mode in get_args(LedMode),
        f"alert.on_alert.led_mode must be one of {get_args(LedMode)}",
    )
    check(
        cfg.alert.on_alert.buzzer_mode in get_args(BuzzerMode),
        f"alert.on_alert.buzzer_mode must be one of {get_args(BuzzerMode)}",
    )
    check(bool(cfg.telemetry.runs_dir.strip()), "telemetry.runs_dir must not be empty")
    return problems
