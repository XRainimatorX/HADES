"""State machine and threshold-to-trigger logic (decision layer).

Stage 2 skeleton only: the interface is real, the decision logic is not. The engine
always reports ``SCANNING`` and never issues a command, so the monitor and the virtual
OLED screen (work package D) have a ``SystemState`` to show. Thresholds, confirmation,
cooldown and state transitions are built in Stage 4 (docs/decisions.md, entry 12).
"""

from __future__ import annotations

from typing import Optional

from hades.contracts import ActuatorCommand, StateName, SystemState, TrackingPacket


class StateMachine:
    """Implements ``contracts.DecisionEngine``."""

    def __init__(self) -> None:
        self._state: StateName = "IDLE"

    def step(self, trk: TrackingPacket) -> tuple[SystemState, Optional[ActuatorCommand]]:
        """Return the system state and a command if the outputs must change.

        Skeleton: the state is always ``SCANNING`` and no command is ever returned.
        """
        previous = self._state
        self._state = "SCANNING"
        state = SystemState(
            state=self._state,
            previous=previous,
            frame_id=trk.frame_id,
            timestamp=trk.timestamp,
        )
        return state, None

    def on_source_lost(self, timestamp: int) -> Optional[ActuatorCommand]:
        """Return an off command if an alert was active.

        Skeleton: no alert is ever active, so there is never a command to return.
        """
        return None
