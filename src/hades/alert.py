"""Alert outputs (work package J): mock, LED, buzzer, laser, OLED."""

from __future__ import annotations

from hades.contracts import ActuatorCommand, ActuatorStatus


class MockAlert:
    """Implements ``contracts.Alert`` by recording commands instead of driving hardware."""

    def send(self, cmd: ActuatorCommand) -> None:
        """Apply a command; sending the same command twice changes nothing."""
        raise NotImplementedError

    def status(self) -> ActuatorStatus:
        """Report what the outputs are doing."""
        raise NotImplementedError
