"""Assembles the chain and runs the main loop (the Stage 2 minimum of work package P).

The chain, one pass per frame::

    configuration -> A source -> B detector -> decision skeleton -> E run log
                                                              \\-> D virtual OLED, web monitor

Two things here are deliberately temporary and are replaced in later stages:

* There is no tracker yet (work package I, Stage 3), so the decision skeleton receives an empty
  ``TrackingPacket``.
* The skeleton never issues a command (decisions, entry 12). To show "target seen, LED on" on a
  laptop, the main loop itself sends the configured alert to the alert mock whenever a frame holds
  a detection, and switches it off on the first frame without one. Stage 4 moves this into the
  decision layer.

``run_demo``, ``run_integration`` and ``PipelineDiagnostics`` belong to work packages M, K and P
and are still skeletons.
"""

from __future__ import annotations

import argparse
import dataclasses
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from hades.alert import MockAlert, VirtualOledDisplay
from hades.config import REPO_ROOT, load_config, resolve_path, validate_config
from hades.contracts import (
    ActuatorCommand,
    Alert,
    Config,
    Detector,
    DiagnosticStatus,
    FramePacket,
    IntegrationResult,
    OledDisplay,
    RunMetadata,
    Source,
    SourceConfig,
    TrackingPacket,
    WebMonitor as WebMonitorProtocol,
)
from hades.decide import StateMachine
from hades.detect import UltralyticsDetector
from hades.monitor import WebMonitor
from hades.sources import VideoFileSource, VirtualPiCamSource, WebcamSource
from hades.telemetry import Telemetry, file_sha256, git_info

_NS_PER_S = 1_000_000_000


@dataclasses.dataclass(frozen=True)
class PipelineResult:
    """What one run of the pipeline did."""

    run_dir: Path
    run_id: str
    frames: int
    detections: int
    commands: int


class PipelineDiagnostics:
    """Implements ``contracts.Diagnostics``."""

    def snapshot(self) -> DiagnosticStatus:
        """Collect the current health of every part."""
        raise NotImplementedError


def run_demo(clip: str, config_path: str) -> None:
    """Play a demo clip through the full system."""
    raise NotImplementedError


def run_integration(clip: str, config_path: str) -> IntegrationResult:
    """Run the full pipeline on a clip and check the log."""
    raise NotImplementedError


def build_source(cfg: SourceConfig) -> Source:
    """Create the source the configuration names.

    ``video`` plays a file; ``picam`` is the virtual Pi camera looping a file (the real camera is
    added behind the same functions later); ``webcam`` is a laptop camera, ``uri`` being its number.
    """
    if cfg.type == "video":
        return VideoFileSource(str(resolve_path(cfg.uri)), realtime=cfg.realtime)
    if cfg.type == "picam":
        return VirtualPiCamSource(
            str(resolve_path(cfg.uri)), width=cfg.width, height=cfg.height, fps=cfg.fps
        )
    return WebcamSource(int(cfg.uri), width=cfg.width, height=cfg.height, fps=cfg.fps)


def build_metadata(cfg: Config, config_path: str) -> RunMetadata:
    """Assemble the run's metadata: code version, model and settings fingerprints, source."""
    commit, dirty = git_info()
    uri = cfg.source.uri
    if cfg.source.type != "webcam":
        uri = str(resolve_path(uri))  # absolute, so a replay can find the original video
    return RunMetadata(
        run_id=str(uuid.uuid4()),
        started_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        git_commit=commit,
        git_dirty=dirty,
        model_path=cfg.detector.model_path,
        model_sha256=file_sha256(str(resolve_path(cfg.detector.model_path))),
        config_sha256=file_sha256(config_path),
        hardware=cfg.hardware.name,
        source_type=cfg.source.type,
        source_uri=uri,
    )


def _alert_command(cfg: Config, frame: FramePacket, on: bool) -> ActuatorCommand:
    """The command that switches the alert outputs on (as configured) or off."""
    chosen = cfg.alert.on_alert
    return ActuatorCommand(
        alert_level=1 if on else 0,
        led_mode=chosen.led_mode if on else "off",
        buzzer_mode=chosen.buzzer_mode if on else "off",
        laser_on=chosen.laser_on if on else False,
        frame_id=frame.frame_id,
        timestamp=frame.timestamp,
        t_command=time.monotonic_ns(),
    )


class _Run:
    """The state of one pass over a source: the parts, the run log and the counters."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        cfg: Config,
        log: Telemetry,
        alert: Alert,
        display: OledDisplay,
        monitor: Optional[WebMonitorProtocol],
    ) -> None:
        self.cfg, self.log, self.alert, self.display, self.monitor = (
            cfg,
            log,
            alert,
            display,
            monitor,
        )
        self.engine = StateMachine()
        self.frames = self.detections = self.commands = 0
        self._alert_on = False
        self._last_stamp: Optional[int] = None
        self._fps = 0.0

    def frame(self, frame: FramePacket, detector: Detector) -> None:
        """Take one frame through detection, decision, the run log and the displays."""
        self.log.record(frame)
        packet = detector.detect(frame)
        self.log.record(packet)

        if self._last_stamp is not None and frame.timestamp > self._last_stamp:
            self._fps = _NS_PER_S / (frame.timestamp - self._last_stamp)
        self._last_stamp = frame.timestamp
        tracking = TrackingPacket(frame.frame_id, (), frame.timestamp, time.monotonic_ns())
        state, command = self.engine.step(tracking)
        self.log.record(state)
        if command is not None:
            self._send(command)

        seen = bool(packet.detections)
        if seen != self._alert_on:  # temporary shortcut, see the module note
            self._send(_alert_command(self.cfg, frame, seen))
            self.log.record(self.alert.status())
            self._alert_on = seen

        if self.monitor is not None:
            self.monitor.publish(frame)
            self.monitor.publish(packet)
            self.monitor.publish(state)
        self.display.update(state, self._fps)
        self.frames += 1
        self.detections += len(packet.detections)

    def source_lost(self) -> None:
        """The source ended: let the decision layer switch the outputs off if it needs to."""
        command = self.engine.on_source_lost(time.monotonic_ns())  # pylint: disable=E1128
        if command is not None:
            self._send(command)

    def _send(self, command: ActuatorCommand) -> None:
        self.alert.send(command)
        self.log.record(command)
        self.commands += 1


def run_pipeline(  # pylint: disable=too-many-arguments
    cfg: Config,
    config_path: str,
    *,
    source: Optional[Source] = None,
    detector: Optional[Detector] = None,
    alert: Optional[Alert] = None,
    display: Optional[OledDisplay] = None,
    monitor: Optional[WebMonitorProtocol] = None,
    max_frames: Optional[int] = None,
) -> PipelineResult:
    """Run the chain over a source until it ends, ``max_frames`` frames, or Ctrl+C.

    The run log is always closed, so every record already queued is written, however the run ends.
    Anything not passed in is built from the configuration.
    """
    problems = validate_config(cfg)
    if problems:
        raise ValueError(f"{config_path} is not valid: " + "; ".join(problems))
    source = source or build_source(cfg.source)
    detector = detector or UltralyticsDetector(min_confidence=cfg.detector.min_confidence)

    log = Telemetry(runs_dir=str(resolve_path(cfg.telemetry.runs_dir)))
    meta = build_metadata(cfg, config_path)
    log.start_run(meta)
    run = _Run(cfg, log, alert or MockAlert(), display or VirtualOledDisplay(), monitor)
    try:
        detector.load(str(resolve_path(cfg.detector.model_path)))
        source.open()
        while max_frames is None or run.frames < max_frames:
            frame = source.read()
            if frame is None:
                run.source_lost()
                break
            run.frame(frame, detector)
    finally:
        source.close()
        log.end_run()
    if log.run_dir is None:
        raise RuntimeError("the run log has no folder")
    return PipelineResult(log.run_dir, meta.run_id, run.frames, run.detections, run.commands)


def _resolve_config(path: str) -> str:
    """The configuration path as given if it exists, otherwise relative to the repository root."""
    return path if Path(path).is_file() else str(REPO_ROOT / path)


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point of ``hades-run``."""
    parser = argparse.ArgumentParser(prog="hades-run", description="Run the HADES pipeline.")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--clip", help="play this video file instead of the configured source")
    parser.add_argument("--max-frames", type=int, help="stop after this many frames")
    parser.add_argument("--monitor-port", type=int, help="serve the web monitor on this port")
    args = parser.parse_args(argv)

    config_path = _resolve_config(args.config)
    cfg = load_config(config_path)
    if args.clip:
        cfg = dataclasses.replace(
            cfg, source=dataclasses.replace(cfg.source, type="video", uri=args.clip)
        )
    monitor: Optional[WebMonitor] = None
    if args.monitor_port is not None:
        monitor = WebMonitor()
        monitor.start(args.monitor_port)
    try:
        result = run_pipeline(cfg, config_path, monitor=monitor, max_frames=args.max_frames)
    except KeyboardInterrupt:
        print("stopped; the run log was closed")
        return 130
    finally:
        if monitor is not None:
            monitor.stop()
    print(
        f"run {result.run_id}: {result.frames} frames, {result.detections} detections, "
        f"{result.commands} alert commands -> {result.run_dir}"
    )
    return 0
