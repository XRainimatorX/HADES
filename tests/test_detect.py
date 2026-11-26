"""Tests for the detector (work package B).

Two kinds of test, both required by Issue B:

* the official YOLOv8n model (``tests/fixtures/test_model.pt``) on the fixture clips, to prove the
  packet format, the timing and the one-packet-per-frame rule. That model has no drone class, so it
  returns no approved detections;
* a scripted fake YOLO, to prove how boxes are filtered, clamped and converted, because the real
  model cannot be made to produce a drone on demand.
"""

# type() is deliberate: np.float64 is a subclass of float, so isinstance() would accept it.
# pylint: disable=unidiomatic-typecheck,use-implicit-booleaness-not-comparison

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterator, Optional

import cv2
import numpy as np
import pytest
import yaml
from conftest import require_real_file, require_real_video

from hades.contracts import CLASS_NAMES, SCHEMA_VERSION, Detection, DetectionPacket, FramePacket
from hades.detect import UltralyticsDetector

ROOT = Path(__file__).resolve().parents[1]
MIN_CONFIDENCE = 0.25


# --- the real model on the fixture clips ----------------------------------------------------------


def _frames(video: Path, limit: Optional[int] = None) -> Iterator[FramePacket]:
    capture = cv2.VideoCapture(str(video))
    frame_id = 0
    try:
        while limit is None or frame_id < limit:
            ok, image = capture.read()
            if not ok:
                return
            yield FramePacket(frame_id, 1_000 + frame_id * 33_000_000, image, "video")
            frame_id += 1
    finally:
        capture.release()


@pytest.fixture(name="real_detector")
def fixture_real_detector(test_model: Path) -> UltralyticsDetector:
    """The detector loaded with the official YOLOv8n weights."""
    detector = UltralyticsDetector(min_confidence=MIN_CONFIDENCE)
    detector.load(str(require_real_file(test_model)))
    return detector


def test_one_packet_per_frame_for_every_frame_of_the_drone_clip(
    real_detector: UltralyticsDetector, drone_daylight_01: Path
) -> None:
    """Every frame gives exactly one packet carrying that frame's id and capture time."""
    frames = list(_frames(require_real_video(drone_daylight_01)))
    packets = [real_detector.detect(frame) for frame in frames]
    assert len(packets) == len(frames) > 0
    assert [p.frame_id for p in packets] == [f.frame_id for f in frames]
    assert [p.timestamp for p in packets] == [f.timestamp for f in frames]


def test_frames_without_a_drone_give_packets_with_an_empty_tuple(
    real_detector: UltralyticsDetector, no_drone_01: Path
) -> None:
    """A valid frame with nothing approved gives an empty tuple, never a missing field."""
    for frame in _frames(require_real_video(no_drone_01), limit=15):
        packet = real_detector.detect(frame)
        assert isinstance(packet.detections, tuple)
        assert packet.detections == ()


def test_timing_fields_are_consistent(
    real_detector: UltralyticsDetector, drone_daylight_01: Path
) -> None:
    """t_detect is not before capture, and inference time is positive and fits inside the delay."""
    for frame in _frames(require_real_video(drone_daylight_01), limit=10):
        packet = real_detector.detect(frame)
        total_ms = (packet.t_detect - packet.timestamp) / 1_000_000
        assert packet.t_detect >= packet.timestamp
        assert 0 < packet.inference_ms <= total_ms


def test_numbers_in_the_packet_are_plain_python(
    real_detector: UltralyticsDetector, drone_daylight_01: Path
) -> None:
    """No NumPy scalar or tensor ends up in a packet."""
    packet = real_detector.detect(next(_frames(require_real_video(drone_daylight_01))))
    assert type(packet.frame_id) is int and type(packet.timestamp) is int  # noqa: E721
    assert type(packet.t_detect) is int and type(packet.inference_ms) is float  # noqa: E721
    assert packet.schema_version == SCHEMA_VERSION


def test_detecting_the_same_frame_twice_gives_the_same_detections(
    real_detector: UltralyticsDetector, drone_daylight_01: Path
) -> None:
    """Results can be reproduced."""
    frame = next(_frames(require_real_video(drone_daylight_01)))
    assert real_detector.detect(frame).detections == real_detector.detect(frame).detections


def test_the_real_model_has_no_approved_class_so_nothing_is_kept(
    real_detector: UltralyticsDetector,
) -> None:
    """The official COCO weights have no drone class; the approved class list is empty."""
    assert "drone" not in real_detector._class_names.values()  # pylint: disable=protected-access
    assert real_detector._approved_ids == []  # pylint: disable=protected-access


# --- a scripted fake YOLO: how boxes are filtered, clamped and converted ---------------


class FakeTensor:
    """What ``.cpu().tolist()`` needs from a tensor."""

    def __init__(self, data: list[Any]) -> None:
        self._data = data

    def cpu(self) -> "FakeTensor":
        """Pretend to move the tensor to the CPU."""
        return self

    def tolist(self) -> list[Any]:
        """Return the values as a list."""
        return self._data


class FakeBoxes:
    """The three tensors of a YOLO result."""

    def __init__(self, rows: list[tuple[list[float], float, int]]) -> None:
        self.xyxy = FakeTensor([r[0] for r in rows])
        self.conf = FakeTensor([r[1] for r in rows])
        self.cls = FakeTensor([r[2] for r in rows])


class FakeResult:
    """One YOLO result."""

    def __init__(self, rows: Optional[list[tuple[list[float], float, int]]], speed: float) -> None:
        self.boxes = None if rows is None else FakeBoxes(rows)
        self.speed = {"inference": speed}


class FakeYOLO:
    """A YOLO model that returns a scripted result and counts its calls."""

    rows: Optional[list[tuple[list[float], float, int]]] = []
    speed = 12.5
    results_per_call = 1
    names: Any = {0: "drone", 1: "bird"}
    instances: list["FakeYOLO"] = []

    def __init__(self, path: str) -> None:
        self.path = path
        self.calls: list[dict[str, Any]] = []
        FakeYOLO.instances.append(self)

    def predict(self, **kwargs: Any) -> list[FakeResult]:
        """Record the call and return the scripted result(s)."""
        self.calls.append(kwargs)
        return [FakeResult(FakeYOLO.rows, FakeYOLO.speed) for _ in range(FakeYOLO.results_per_call)]


@pytest.fixture(name="fake_yolo")
def fixture_fake_yolo(monkeypatch: pytest.MonkeyPatch) -> type[FakeYOLO]:
    """Replace ultralytics.YOLO with the scripted fake and reset its script."""
    import ultralytics  # pylint: disable=import-outside-toplevel

    FakeYOLO.rows, FakeYOLO.speed = [], 12.5
    FakeYOLO.results_per_call, FakeYOLO.names, FakeYOLO.instances = 1, {0: "drone", 1: "bird"}, []
    monkeypatch.setattr(ultralytics, "YOLO", FakeYOLO)
    return FakeYOLO


@pytest.fixture(name="weights")
def fixture_weights(tmp_path: Path) -> str:
    """A file standing in for model weights (the fake never reads it)."""
    path = tmp_path / "model.pt"
    path.write_bytes(b"weights")
    return str(path)


def _frame(width: int = 100, height: int = 80, frame_id: int = 3) -> FramePacket:
    return FramePacket(frame_id, 5_000, np.zeros((height, width, 3), np.uint8), "video")


def _detect(rows: Any, weights: str, **kwargs: Any) -> DetectionPacket:
    FakeYOLO.rows = rows
    detector = UltralyticsDetector(min_confidence=MIN_CONFIDENCE, **kwargs)
    detector.load(weights)
    return detector.detect(_frame())


def test_an_approved_confident_box_is_kept_as_a_plain_detection(
    fake_yolo: type[FakeYOLO], weights: str
) -> None:
    """Drone at 0.92 is accepted with plain Python numbers and the class name from the model."""
    packet = _detect([([10.0, 20.0, 40.0, 60.0], 0.92, 0)], weights)
    assert packet.detections == (Detection((10.0, 20.0, 40.0, 60.0), "drone", 0.92),)
    detection = packet.detections[0]
    assert all(type(v) is float for v in detection.bbox)  # noqa: E721
    assert type(detection.confidence) is float  # noqa: E721
    assert packet.inference_ms == 12.5 and fake_yolo is FakeYOLO


def test_the_three_object_example_from_the_design_note(weights: str, fake_yolo: Any) -> None:
    """Drone 0.92 kept; bird 0.95 dropped (class not approved); drone 0.18 dropped (too low)."""
    rows = [
        ([10.0, 10.0, 30.0, 30.0], 0.92, 0),
        ([40.0, 40.0, 60.0, 60.0], 0.95, 1),
        ([50.0, 10.0, 70.0, 30.0], 0.18, 0),
    ]
    packet = _detect(rows, weights)
    assert [d.confidence for d in packet.detections] == [0.92]


def test_every_kept_class_is_one_the_contract_allows(weights: str, fake_yolo: Any) -> None:
    """Class names come from contracts.CLASS_NAMES, which data/classes.yaml must match."""
    packet = _detect([([1.0, 1.0, 9.0, 9.0], 0.5, 0)], weights)
    assert {d.class_name for d in packet.detections} <= set(CLASS_NAMES)
    listed = yaml.safe_load((ROOT / "data" / "classes.yaml").read_text(encoding="utf-8"))["names"]
    assert set(CLASS_NAMES) == set(listed.values())


def test_boxes_are_clamped_into_the_image(weights: str, fake_yolo: Any) -> None:
    """A box sticking out of the frame is cut to the frame; the others are untouched."""
    packet = _detect([([-15.0, -5.0, 130.0, 50.0], 0.9, 0)], weights)
    assert packet.detections[0].bbox == (0.0, 0.0, 100.0, 50.0)


@pytest.mark.parametrize(
    "box",
    [
        [20.0, 20.0, 20.0, 40.0],  # no width
        [20.0, 40.0, 30.0, 40.0],  # no height
        [30.0, 20.0, 10.0, 40.0],  # x1 > x2
        [200.0, 10.0, 300.0, 40.0],  # entirely outside, clamps to no area
        [float("nan"), 1.0, 5.0, 5.0],  # not finite
        [1.0, 1.0, float("inf"), 5.0],  # not finite
        [1.0, 2.0, 3.0],  # wrong number of coordinates
    ],
)
def test_unusable_boxes_are_dropped(box: list[float], weights: str, fake_yolo: Any) -> None:
    """A box that is not four finite numbers, or has no area, is discarded."""
    assert _detect([(box, 0.9, 0)], weights).detections == ()


def test_confidence_must_be_between_the_minimum_and_one(weights: str, fake_yolo: Any) -> None:
    """Below the minimum, above one and not-a-number are all dropped; the minimum itself is kept."""
    rows = [
        ([1.0, 1.0, 9.0, 9.0], 0.2499, 0),
        ([1.0, 1.0, 9.0, 9.0], MIN_CONFIDENCE, 0),
        ([2.0, 2.0, 9.0, 9.0], 1.0, 0),
        ([3.0, 3.0, 9.0, 9.0], 1.2, 0),
        ([4.0, 4.0, 9.0, 9.0], float("nan"), 0),
    ]
    kept = _detect(rows, weights).detections
    assert [d.confidence for d in kept] == [MIN_CONFIDENCE, 1.0]
    assert all(MIN_CONFIDENCE <= d.confidence <= 1.0 for d in kept)


def test_no_boxes_at_all_gives_an_empty_tuple(weights: str, fake_yolo: Any) -> None:
    """A result without boxes still yields a packet with an empty tuple."""
    assert _detect(None, weights).detections == ()
    assert _detect([], weights).detections == ()


def test_bounding_boxes_always_satisfy_x1_less_than_x2_and_y1_less_than_y2(
    weights: str, fake_yolo: Any
) -> None:
    """Whatever the model returns, every kept box lies inside the image and has an area."""
    rows = [([float(i), float(i), float(i + 7), float(i + 5)], 0.9, 0) for i in range(-3, 120, 7)]
    for d in _detect(rows, weights).detections:
        x1, y1, x2, y2 = d.bbox
        assert 0 <= x1 < x2 <= 100 and 0 <= y1 < y2 <= 80


def test_frame_id_and_timestamp_are_copied_and_t_detect_is_taken_last(
    weights: str, fake_yolo: Any
) -> None:
    """The packet carries the frame's id and capture time; t_detect is later than both."""
    packet = _detect([], weights)
    assert (packet.frame_id, packet.timestamp) == (3, 5_000)
    assert packet.t_detect > packet.timestamp


def test_the_frame_is_not_modified_by_detection(weights: str, fake_yolo: Any) -> None:
    """Detection works on a copy; the FramePacket image keeps its pixels and stays read-only."""
    frame = _frame()
    before = frame.image.copy()
    detector = UltralyticsDetector(min_confidence=MIN_CONFIDENCE)
    FakeYOLO.rows = [([1.0, 1.0, 9.0, 9.0], 0.9, 0)]
    detector.load(weights)
    detector.detect(frame)
    assert np.array_equal(frame.image, before) and not frame.image.flags.writeable


# --- loading --------------------------------------------------------------------------------------


def test_load_runs_exactly_one_warm_up_and_loads_the_model_once(
    weights: str, fake_yolo: type[FakeYOLO]
) -> None:
    """One blank-image inference in load(); loading the same file again does nothing."""
    detector = UltralyticsDetector(min_confidence=MIN_CONFIDENCE, input_size=320)
    detector.load(weights)
    detector.load(weights)
    assert len(fake_yolo.instances) == 1
    calls = fake_yolo.instances[0].calls
    assert len(calls) == 1
    assert calls[0]["imgsz"] == 320 and calls[0]["conf"] == MIN_CONFIDENCE
    assert calls[0]["source"].shape == (320, 320, 3) and not calls[0]["source"].any()


def test_loading_different_weights_into_the_same_detector_is_refused(
    weights: str, tmp_path: Path, fake_yolo: Any
) -> None:
    """A detector serves one model; another file needs a new detector."""
    other = tmp_path / "other.pt"
    other.write_bytes(b"x")
    detector = UltralyticsDetector()
    detector.load(weights)
    with pytest.raises(RuntimeError, match="already loaded"):
        detector.load(str(other))


def test_loading_a_missing_file_names_it(tmp_path: Path, fake_yolo: Any) -> None:
    """The error says which weights file is missing, and nothing is loaded."""
    with pytest.raises(FileNotFoundError, match="absent.pt"):
        UltralyticsDetector().load(str(tmp_path / "absent.pt"))
    assert fake_yolo.instances == []


def test_class_names_may_be_a_list_or_a_dict(weights: str, fake_yolo: type[FakeYOLO]) -> None:
    """YOLO exposes names as a dict or a list; both are understood."""
    fake_yolo.names = ["drone", "bird"]
    assert len(_detect([([1.0, 1.0, 9.0, 9.0], 0.9, 0)], weights).detections) == 1


def test_a_model_without_class_names_is_rejected(weights: str, fake_yolo: type[FakeYOLO]) -> None:
    """A model that does not say what its classes are cannot be used."""
    fake_yolo.names = None
    with pytest.raises(ValueError, match="class names"):
        UltralyticsDetector().load(weights)


# --- misuse ---------------------------------------------------------------------------------------


def test_detect_before_load_is_an_error() -> None:
    """The model must be loaded first."""
    with pytest.raises(RuntimeError, match="load"):
        UltralyticsDetector().detect(_frame())


@pytest.mark.parametrize(
    "image",
    [
        np.zeros((10, 10), np.uint8),  # no colour channels
        np.zeros((10, 10, 4), np.uint8),  # four channels
        np.zeros((10, 10, 3), np.float32),  # not 8-bit
        np.zeros((0, 10, 3), np.uint8),  # empty
    ],
)
def test_an_invalid_image_is_an_error_not_an_empty_result(
    image: np.ndarray, weights: str, fake_yolo: Any
) -> None:
    """Invalid input raises; only a valid frame with nothing found gives an empty tuple."""
    detector = UltralyticsDetector()
    detector.load(weights)
    with pytest.raises(ValueError, match="HxWx3"):
        detector.detect(FramePacket(0, 1, image, "video"))


def test_a_frame_with_another_schema_version_is_refused(weights: str, fake_yolo: Any) -> None:
    """A reader checks the packet format version before using the packet."""
    detector = UltralyticsDetector()
    detector.load(weights)
    old = FramePacket(0, 1, np.zeros((4, 4, 3), np.uint8), "video", schema_version="0.1")
    with pytest.raises(ValueError, match="schema"):
        detector.detect(old)


def test_not_exactly_one_yolo_result_is_an_error(weights: str, fake_yolo: type[FakeYOLO]) -> None:
    """The detector expects one result per frame."""
    detector = UltralyticsDetector()
    detector.load(weights)
    fake_yolo.results_per_call = 2
    with pytest.raises(RuntimeError, match="exactly one"):
        detector.detect(_frame())


@pytest.mark.parametrize("speed", [0.0, -1.0, float("nan"), float("inf")])
def test_a_model_that_reports_no_usable_inference_time_is_an_error(
    speed: float, weights: str, fake_yolo: type[FakeYOLO]
) -> None:
    """inference_ms must be positive and finite, because it is a reported measurement."""
    detector = UltralyticsDetector()
    detector.load(weights)
    fake_yolo.speed = speed
    with pytest.raises(RuntimeError, match="inference time"):
        detector.detect(_frame())


def test_inconsistent_box_tensors_are_an_error(
    weights: str, fake_yolo: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Boxes, scores and classes must line up."""
    detector = UltralyticsDetector()
    detector.load(weights)

    class Broken(FakeResult):
        """A result whose class tensor is one short."""

        def __init__(self) -> None:
            super().__init__([([1.0, 1.0, 9.0, 9.0], 0.9, 0)], 5.0)
            assert self.boxes is not None
            self.boxes.cls = FakeTensor([])

    monkeypatch.setattr(FakeYOLO, "predict", lambda self, **kw: [Broken()])
    with pytest.raises(RuntimeError, match="inconsistent"):
        detector.detect(_frame())


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf")])
def test_min_confidence_must_be_between_zero_and_one(value: float) -> None:
    """A confidence floor outside 0 to 1 is a configuration mistake."""
    with pytest.raises(ValueError, match="min_confidence"):
        UltralyticsDetector(min_confidence=value)


@pytest.mark.parametrize("value", [0, -640, True, 640.0])
def test_input_size_must_be_a_positive_integer(value: Any) -> None:
    """The input size is a whole number of pixels."""
    with pytest.raises(ValueError, match="input_size"):
        UltralyticsDetector(input_size=value)


def test_inference_ms_is_the_models_own_figure(weights: str, fake_yolo: type[FakeYOLO]) -> None:
    """inference_ms comes from the result's speed, not from timing the whole call."""
    fake_yolo.speed = 7.25
    assert _detect([], weights).inference_ms == 7.25 and math.isfinite(7.25)
