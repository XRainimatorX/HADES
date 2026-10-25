"""Contract tests: types match docs/spec.md and configs/default.yaml."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from hades import contracts

ROOT = Path(__file__).resolve().parents[1]


def _spec_blocks() -> dict[str, list[str]]:
    """Field names of every ``Name { ... }`` format block in docs/spec.md."""
    blocks: dict[str, list[str]] = {}
    current = None
    for line in (ROOT / "docs" / "spec.md").read_text(encoding="utf-8").splitlines():
        start = re.match(r"^([A-Z]\w+) \{$", line)
        if start:
            current = start.group(1)
            blocks[current] = []
        elif line.startswith("}"):
            current = None
        elif current:
            field = re.match(r"^  (\w+):", line)
            if field:
                blocks[current].append(field.group(1))
    return blocks


SPEC_BLOCKS = _spec_blocks()


def test_spec_blocks_found() -> None:
    assert len(SPEC_BLOCKS) >= 17


@pytest.mark.parametrize("name", sorted(n for n in SPEC_BLOCKS if n != "EventRecord"))
def test_dataclass_matches_spec(name: str) -> None:
    cls = getattr(contracts, name)
    assert [f.name for f in dataclasses.fields(cls)] == SPEC_BLOCKS[name]


def test_event_record_spec_fields() -> None:
    assert SPEC_BLOCKS["EventRecord"] == ["type", "schema_version"]
    assert {f.name for f in dataclasses.fields(contracts.EventRecord)} == {
        "type",
        "fields",
        "schema_version",
    }


def test_schema_version_default() -> None:
    frame = contracts.FramePacket(0, 1, np.zeros((2, 2, 3), np.uint8), "video")
    assert frame.schema_version == contracts.SCHEMA_VERSION == "0.1"


def test_packet_chain_constructs() -> None:
    det = contracts.Detection((0.0, 0.0, 10.0, 10.0), "drone", 0.9)
    dp = contracts.DetectionPacket(0, [det], 12.5, 1, 2)
    trk = contracts.Track(1, "drone", 0.88, det.bbox, True)
    tp = contracts.TrackingPacket(0, [trk], 1, 3)
    cmd = contracts.ActuatorCommand(1, "blink", "pulse", False, 0, 1, 4)
    st = contracts.ActuatorStatus("blink", "pulse", False, None, True, 5)
    assert dp.detections[0].class_name == "drone"
    assert tp.targets[0].is_confirmed
    assert cmd.t_command - cmd.timestamp == 3
    assert st.last_command_frame_id is None


def test_packets_are_frozen() -> None:
    det = contracts.Detection((0.0, 0.0, 1.0, 1.0), "drone", 0.5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        det.confidence = 0.6  # type: ignore[misc]


def _keys(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return {f.name: _keys(getattr(obj, f.name, None)) for f in dataclasses.fields(obj)}
    return None


def _shape(cls: type) -> dict[str, Any]:
    out: dict[str, Any] = {}
    hints = {f.name: f.type for f in dataclasses.fields(cls)}
    for name, typ in hints.items():
        sub = getattr(contracts, typ, None) if isinstance(typ, str) else None
        out[name] = _shape(sub) if sub is not None and dataclasses.is_dataclass(sub) else None
    return out


def test_default_yaml_matches_config() -> None:
    data = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text(encoding="utf-8"))

    def shape(d: Any) -> Any:
        return {k: shape(v) for k, v in d.items()} if isinstance(d, dict) else None

    assert shape(data) == _shape(contracts.Config)
    assert data["schema_version"] == contracts.SCHEMA_VERSION


def test_classes_yaml() -> None:
    data = yaml.safe_load((ROOT / "data" / "classes.yaml").read_text(encoding="utf-8"))
    assert data == {"schema_version": "0.1", "names": {0: "drone"}}


def test_events_csv_header_in_spec() -> None:
    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    assert ",".join(contracts.EVENTS_CSV_COLUMNS) in spec


# --- skeleton stubs: expected to fail until each work package lands ---------


@pytest.mark.xfail(raises=NotImplementedError, strict=True, reason="stub")
def test_load_config_stub() -> None:
    from hades import config

    config.load_config(str(ROOT / "configs" / "default.yaml"))


@pytest.mark.xfail(raises=NotImplementedError, strict=True, reason="stub")
def test_validate_dataset_stub() -> None:
    from ml import dataset

    dataset.validate_dataset(str(ROOT / "data" / "dataset_v1"))
