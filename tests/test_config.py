"""Tests for the minimal configuration loader."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import yaml

from hades import config
from hades.contracts import Config

DEFAULT = config.REPO_ROOT / "configs" / "default.yaml"


def _data() -> dict:
    return yaml.safe_load(DEFAULT.read_text(encoding="utf-8"))


def _write(tmp_path: Path, data: object) -> str:
    path = tmp_path / "cfg.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


def test_default_config_loads_with_the_values_in_the_file() -> None:
    """Every value in configs/default.yaml reaches the matching Config field."""
    cfg = config.load_config(str(DEFAULT))
    raw = _data()
    assert isinstance(cfg, Config)
    assert cfg.hardware.name == raw["hardware"]["name"]
    assert (cfg.source.type, cfg.source.uri, cfg.source.realtime) == ("webcam", "0", True)
    assert (cfg.source.width, cfg.source.height, cfg.source.fps) == (1280, 720, 30.0)
    assert cfg.detector.min_confidence == raw["detector"]["min_confidence"]
    assert cfg.tracker.confirm_frames == raw["tracker"]["confirm_frames"]
    assert cfg.decision.cooldown_s == raw["decision"]["cooldown_s"]
    assert cfg.alert.on_alert.led_mode == "blink"
    assert cfg.telemetry.runs_dir == "runs"


def test_default_config_is_valid() -> None:
    """The shipped configuration has no problems."""
    assert config.validate_config(config.load_config(str(DEFAULT))) == []


def test_an_integer_is_accepted_where_a_float_is_expected(tmp_path: Path) -> None:
    """``fps: 30`` is read as 30.0."""
    data = _data()
    data["source"]["fps"] = 30
    cfg = config.load_config(_write(tmp_path, data))
    assert cfg.source.fps == 30.0 and isinstance(cfg.source.fps, float)


@pytest.mark.parametrize(
    ("section", "key"),
    [("source", "width"), ("detector", "model_path"), ("decision", "cooldown_s")],
)
def test_a_missing_value_is_named(tmp_path: Path, section: str, key: str) -> None:
    """The error says which value is missing."""
    data = _data()
    del data[section][key]
    with pytest.raises(ValueError, match=key):
        config.load_config(_write(tmp_path, data))


def test_a_missing_section_is_named(tmp_path: Path) -> None:
    """The error says which section is missing."""
    data = _data()
    del data["tracker"]
    with pytest.raises(ValueError, match="tracker"):
        config.load_config(_write(tmp_path, data))


def test_a_value_of_the_wrong_type_is_rejected(tmp_path: Path) -> None:
    """A string where an integer is required names the entry and the value."""
    data = _data()
    data["source"]["width"] = "wide"
    with pytest.raises(ValueError, match=r"'width' must be int, got 'wide'"):
        config.load_config(_write(tmp_path, data))


def test_a_boolean_is_not_accepted_as_an_integer(tmp_path: Path) -> None:
    """``true`` is not a frame count."""
    data = _data()
    data["tracker"]["confirm_frames"] = True
    with pytest.raises(ValueError, match="confirm_frames"):
        config.load_config(_write(tmp_path, data))


def test_a_file_that_is_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    """A list at the top level is not a configuration."""
    with pytest.raises(ValueError, match="top level"):
        config.load_config(_write(tmp_path, ["a", "b"]))


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda c: c["source"].update(type="satellite"), "source.type"),
        (lambda c: c["source"].update(width=0), "source.width"),
        (lambda c: c["source"].update(height=-1), "source.height"),
        (lambda c: c["source"].update(fps=0.0), "source.fps"),
        (lambda c: c["detector"].update(min_confidence=1.5), "min_confidence"),
        (lambda c: c["tracker"].update(confirm_frames=0), "confirm_frames"),
        (lambda c: c["tracker"].update(lost_frames=0), "lost_frames"),
        (lambda c: c["decision"].update(conf_threshold=-0.1), "conf_threshold"),
        (lambda c: c["decision"].update(cooldown_s=-1.0), "cooldown_s"),
        (lambda c: c["alert"]["on_alert"].update(led_mode="strobe"), "led_mode"),
        (lambda c: c["alert"]["on_alert"].update(buzzer_mode="scream"), "buzzer_mode"),
        (lambda c: c.update(schema_version="0.1"), "schema_version"),
        (lambda c: c["hardware"].update(name="  "), "hardware.name"),
    ],
)
def test_each_out_of_range_value_is_reported(tmp_path: Path, change, expected: str) -> None:
    """validate_config names every bad setting and only that setting."""
    data = _data()
    change(data)
    problems = config.validate_config(config.load_config(_write(tmp_path, data)))
    assert len(problems) == 1 and expected in problems[0]


def test_several_problems_are_all_reported(tmp_path: Path) -> None:
    """The list holds every problem, not only the first."""
    data = _data()
    data["source"].update(width=0, fps=-5.0)
    data["decision"].update(conf_threshold=2.0)
    assert len(config.validate_config(config.load_config(_write(tmp_path, data)))) == 3


def test_resolve_path_is_relative_to_the_repository_root(tmp_path: Path) -> None:
    """A relative path does not depend on where the program is started."""
    assert config.resolve_path("models/x.pt") == config.REPO_ROOT / "models" / "x.pt"
    absolute = tmp_path / "x.pt"
    assert config.resolve_path(str(absolute)) == absolute
    assert (config.REPO_ROOT / "configs" / "default.yaml").is_file()


def test_config_covers_every_section_of_the_contract() -> None:
    """The loader fills every Config field, so nothing in the contract is silently skipped."""
    cfg = config.load_config(str(DEFAULT))
    for field in dataclasses.fields(Config):
        assert getattr(cfg, field.name) is not None
