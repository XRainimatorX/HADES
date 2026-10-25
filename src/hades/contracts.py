"""Packet types and layer interfaces for HADES (format version 0.1).

This file is the code form of ``docs/spec.md``. Any change needs the Project
Owner's approval and must update both files together.

Timestamps are integer nanoseconds from the monotonic clock unless noted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Protocol

import numpy as np
from numpy.typing import NDArray

SCHEMA_VERSION = "0.1"

# --- shared value sets ------------------------------------------------------

SourceType = Literal["picam", "webcam", "video"]
ClassName = Literal["drone"]
StateName = Literal["IDLE", "SCANNING", "CANDIDATE", "CONFIRMED", "ALERTING", "COOLDOWN"]
LedMode = Literal["off", "on", "blink"]
BuzzerMode = Literal["off", "on", "pulse"]
EventType = Literal["frame", "detection", "tracking", "state", "command", "status", "error"]
BenchmarkKind = Literal["latency", "fps", "memory", "range", "false_alarm", "stability"]
ModelFormat = Literal["pt", "onnx", "hef", "engine"]
Split = Literal["train", "val", "test"]
CaseType = Literal["false_positive", "false_negative"]
BBox = tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels, origin top-left

# --- A: video input ---------------------------------------------------------


@dataclass(frozen=True)
class FramePacket:
    """One frame from the camera or video file."""

    frame_id: int
    timestamp: int  # ns
    image: NDArray[np.uint8]  # height x width x 3, BGR
    source_type: SourceType
    schema_version: str = SCHEMA_VERSION


# --- B: detection -----------------------------------------------------------


@dataclass(frozen=True)
class Detection:
    """One object found in a frame."""

    bbox: BBox
    class_name: ClassName
    confidence: float  # 0.0-1.0


@dataclass(frozen=True)
class DetectionPacket:
    """Everything the model found in one frame; ``detections`` may be empty."""

    frame_id: int
    detections: list[Detection]
    inference_ms: float
    timestamp: int  # ns, copied from the frame
    t_detect: int  # ns
    schema_version: str = SCHEMA_VERSION


# --- I: tracking ------------------------------------------------------------


@dataclass(frozen=True)
class Track:
    """One object currently being followed."""

    target_id: int
    class_name: ClassName
    confidence_smoothed: float  # 0.0-1.0
    bbox: BBox
    is_confirmed: bool


@dataclass(frozen=True)
class TrackingPacket:
    """Every object currently tracked in one frame; ``targets`` may be empty."""

    frame_id: int
    targets: list[Track]
    timestamp: int  # ns, copied from the frame
    t_track: int  # ns
    schema_version: str = SCHEMA_VERSION


# --- decision layer ---------------------------------------------------------


@dataclass(frozen=True)
class SystemState:
    """What the system is currently doing."""

    state: StateName
    previous: StateName
    frame_id: int
    timestamp: int  # ns
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class ActuatorCommand:
    """What the alert outputs must do; produced only when they need to change."""

    alert_level: Literal[0, 1]
    led_mode: LedMode
    buzzer_mode: BuzzerMode
    laser_on: bool
    frame_id: int
    timestamp: int  # ns
    t_command: int  # ns
    schema_version: str = SCHEMA_VERSION


# --- J: actuator ------------------------------------------------------------


@dataclass(frozen=True)
class ActuatorStatus:
    """What the alert outputs are actually doing."""

    led_mode: LedMode
    buzzer_mode: BuzzerMode
    laser_on: bool
    last_command_frame_id: Optional[int]
    healthy: bool
    t_status: int  # ns
    schema_version: str = SCHEMA_VERSION


# --- E: logging / replay ----------------------------------------------------


@dataclass(frozen=True)
class RunMetadata:
    """Contents of ``runs/<run_id>/meta.json``."""

    run_id: str  # UUID
    started_at: str  # ISO 8601, UTC
    git_commit: str
    git_dirty: bool
    model_path: str
    model_sha256: str
    config_sha256: str
    hardware: str
    source_type: SourceType
    source_uri: str
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class EventRecord:
    """One line of ``events.jsonl``: a packet's fields (image replaced by height/width)."""

    type: EventType
    fields: dict[str, object] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION


# --- R: error logging -------------------------------------------------------


@dataclass(frozen=True)
class ErrorRecord:
    """One error written into the run log."""

    t_error: int  # ns
    package: str  # work package letter, e.g. "A"
    code: str  # upper case, e.g. "SOURCE_LOST"
    message: str
    frame_id: Optional[int]
    schema_version: str = SCHEMA_VERSION


# --- F / O: benchmark -------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkReport:
    """One measurement; stability runs use ``kind="stability"`` (section O)."""

    run_id: str
    kind: BenchmarkKind
    hardware: str
    model_sha256: str
    samples: int
    result: dict[str, float]
    schema_version: str = SCHEMA_VERSION


# --- G: model artifact and predictions --------------------------------------


@dataclass(frozen=True)
class ModelMetrics:
    """Accuracy on the test split."""

    precision: float
    recall: float
    map50: float


@dataclass(frozen=True)
class ModelCard:
    """Contents of ``models/<model_name>/model.yaml``."""

    name: str
    version: str
    format: ModelFormat
    input_size: tuple[int, int]  # [width, height]
    classes: dict[int, str]
    dataset: str
    sha256: str
    metrics: ModelMetrics
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class Prediction:
    """One line of ``predictions.jsonl``."""

    image: str  # path within dataset_v1/
    model: str  # name and version
    detections: list[Detection]
    schema_version: str = SCHEMA_VERSION


# --- C: dataset -------------------------------------------------------------


@dataclass(frozen=True)
class ClassesFile:
    """Contents of ``data/classes.yaml``."""

    names: dict[int, str]
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class ManifestRow:
    """One row of ``split_manifest.csv``."""

    image: str  # path relative to dataset_v1/
    split: Split
    source_clip: str
    frame_index: int
    num_objects: int


# --- H: error analysis ------------------------------------------------------


@dataclass(frozen=True)
class ErrorCase:
    """One false positive or false negative."""

    image: str
    case_type: CaseType
    cause: str  # short lower-case tag, e.g. "bird"
    confidence: Optional[float]
    note: str


@dataclass(frozen=True)
class ErrorCaseReport:
    """Contents of ``error_case_report.json``."""

    model: str
    conf: float
    cases: list[ErrorCase]
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class Suggestion:
    """One recommended setting."""

    setting: str  # configuration key, e.g. "decision.conf_threshold"
    value: float
    evidence: str


@dataclass(frozen=True)
class ThresholdSuggestion:
    """Contents of ``threshold_suggestion.yaml``."""

    model: str
    suggestions: list[Suggestion]
    schema_version: str = SCHEMA_VERSION


# --- K: integration ---------------------------------------------------------


@dataclass(frozen=True)
class IntegrationResult:
    """Outcome of one integration or regression test."""

    test_name: str
    result: Literal["pass", "fail"]
    run_id: str
    source: Literal["live", "replay"]
    note: str
    schema_version: str = SCHEMA_VERSION


# --- L: UI ------------------------------------------------------------------


@dataclass(frozen=True)
class StateStyle:
    """Label and colour used to show a system state."""

    state: StateName
    label: str
    colour: str  # hex, e.g. "#FF3B30"
    schema_version: str = SCHEMA_VERSION


# --- M: demo ----------------------------------------------------------------


@dataclass(frozen=True)
class DemoClip:
    """One entry of ``data/demo/demo_manifest.yaml``."""

    name: str
    file: str
    duration_s: float
    description: str


@dataclass(frozen=True)
class DemoManifest:
    """Contents of ``data/demo/demo_manifest.yaml``."""

    clips: list[DemoClip]
    schema_version: str = SCHEMA_VERSION


# --- N: session summary -----------------------------------------------------


@dataclass(frozen=True)
class SessionSummary:
    """Contents of ``runs/<run_id>/summary.json``."""

    run_id: str
    duration_s: float
    frames: int
    detections: int
    alerts: int
    median_latency_ms: Optional[float]
    errors: int
    schema_version: str = SCHEMA_VERSION


EVENTS_CSV_COLUMNS = (
    "type",
    "frame_id",
    "timestamp",
    "state",
    "alert_level",
    "num_detections",
    "num_targets",
    "code",
)

# --- P: diagnostics ---------------------------------------------------------


@dataclass(frozen=True)
class DiagnosticStatus:
    """Health of the whole system at one moment."""

    camera_alive: bool
    model_loaded: bool
    fps: float
    state: StateName
    actuator_status: ActuatorStatus
    t_status: int  # ns
    schema_version: str = SCHEMA_VERSION


# --- Q: configuration -------------------------------------------------------


@dataclass(frozen=True)
class HardwareConfig:
    """``hardware`` section."""

    name: str


@dataclass(frozen=True)
class SourceConfig:
    """``source`` section."""

    type: SourceType
    uri: str
    realtime: bool


@dataclass(frozen=True)
class DetectorConfig:
    """``detector`` section."""

    model_path: str
    min_confidence: float


@dataclass(frozen=True)
class TrackerConfig:
    """``tracker`` section."""

    confirm_frames: int
    lost_frames: int


@dataclass(frozen=True)
class DecisionConfig:
    """``decision`` section."""

    conf_threshold: float
    alert_duration_s: float
    cooldown_s: float


@dataclass(frozen=True)
class OnAlertConfig:
    """``alert.on_alert`` section."""

    led_mode: LedMode
    buzzer_mode: BuzzerMode
    laser_on: bool


@dataclass(frozen=True)
class AlertConfig:
    """``alert`` section."""

    on_alert: OnAlertConfig


@dataclass(frozen=True)
class TelemetryConfig:
    """``telemetry`` section."""

    runs_dir: str


@dataclass(frozen=True)
class Config:
    """Contents of ``configs/default.yaml``."""

    hardware: HardwareConfig
    source: SourceConfig
    detector: DetectorConfig
    tracker: TrackerConfig
    decision: DecisionConfig
    alert: AlertConfig
    telemetry: TelemetryConfig
    schema_version: str = SCHEMA_VERSION


# --- layer interfaces -------------------------------------------------------
# Function-style contracts live in their own modules (see docs/spec.md):
#   config.load_config / validate_config       (Q)
#   telemetry.report_error                     (R)
#   ml.dataset.extract_frames / build_split / validate_dataset      (C)
#   ml.train.train / evaluate, ml.export.export                     (G)
#   ml.analysis.analyse / suggest_thresholds                        (H)
#   bench.benchmark.run_benchmark / write_report                    (F)
#   bench.stability.run_stability                                   (O)
#   telemetry.summarise / export_session                            (N)
#   monitor.state_style                                             (L)
#   pipeline.run_demo / run_integration                             (M, K)


class Source(Protocol):
    """Video input (A)."""

    def open(self) -> None:
        """Connect to the camera or open the video file."""

    def read(self) -> Optional[FramePacket]:
        """Return the newest frame, or None when the video ends or the camera is lost."""

    def close(self) -> None:
        """Release the camera or file; safe to call more than once."""


class Detector(Protocol):
    """Detection (B)."""

    def load(self, model_path: str) -> None:
        """Load the model file once before detection starts."""

    def detect(self, frame: FramePacket) -> DetectionPacket:
        """Run the model on one frame; the same frame gives the same result."""


class Tracker(Protocol):
    """Tracking / filtering (I)."""

    def update(self, det: DetectionPacket) -> TrackingPacket:
        """Match new detections with existing tracks and return the target list."""

    def reset(self) -> None:
        """Clear all tracks."""


class DecisionEngine(Protocol):
    """Decision layer."""

    def step(self, trk: TrackingPacket) -> tuple[SystemState, Optional[ActuatorCommand]]:
        """Return the system state and a command if the outputs must change."""

    def on_source_lost(self, timestamp: int) -> Optional[ActuatorCommand]:
        """Return an off command if an alert was active when the video stopped."""


class Alert(Protocol):
    """Actuator mock / driver (J)."""

    def send(self, cmd: ActuatorCommand) -> None:
        """Apply a command to the outputs; idempotent."""

    def status(self) -> ActuatorStatus:
        """Report what the outputs are actually doing."""


class Telemetry(Protocol):
    """Run logging (E)."""

    def start_run(self, meta: RunMetadata) -> None:
        """Create the run folder and write ``meta.json``."""

    def record(self, message: object) -> None:
        """Append one packet to ``events.jsonl`` without slowing the system."""

    def end_run(self) -> None:
        """Finish writing and close the log."""


class OledDisplay(Protocol):
    """OLED output (D)."""

    def update(self, state: SystemState, fps: float) -> None:
        """Show the current state and frame rate."""


class WebMonitor(Protocol):
    """Development web page (D)."""

    def start(self, port: int) -> None:
        """Start the web page on the given port."""

    def publish(self, message: object) -> None:
        """Push any runtime packet to the page."""


class Diagnostics(Protocol):
    """Diagnostic mode (P)."""

    def snapshot(self) -> DiagnosticStatus:
        """Collect the current health of every part."""
