"""Development web monitor (work packages D and L)."""

from __future__ import annotations

from hades.contracts import StateStyle


class Monitor:
    """Implements ``contracts.WebMonitor``."""

    def start(self, port: int) -> None:
        """Start the web page on the given port."""
        raise NotImplementedError

    def publish(self, message: object) -> None:
        """Push any runtime packet to the page."""
        raise NotImplementedError


def state_style(state: str) -> StateStyle:
    """Return the label and colour for a system state."""
    raise NotImplementedError
