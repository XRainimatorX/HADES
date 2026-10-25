"""State machine and threshold-to-trigger logic (decision layer)."""

from __future__ import annotations

from typing import Optional

from hades.contracts import ActuatorCommand, SystemState, TrackingPacket


class StateMachine:
    """Implements ``contracts.DecisionEngine``."""

    def step(self, trk: TrackingPacket) -> tuple[SystemState, Optional[ActuatorCommand]]:
        """Return the system state and a command if the outputs must change."""
        raise NotImplementedError

    def on_source_lost(self, timestamp: int) -> Optional[ActuatorCommand]:
        """Return an off command if an alert was active."""
        raise NotImplementedError
