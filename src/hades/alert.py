"""Alert outputs: the virtual OLED screen (work package D) and the alert mock (work package J).

The virtual OLED screen shows in the terminal exactly the text the real 128 x 64 screen will
show, laid out as it will appear there: eight rows of at most 21 characters. It imports no
hardware library, opens no window and writes no file. When the real screen arrives it is added
behind the same ``update`` function.

``MockAlert`` (LED, buzzer, laser) belongs to work package J in Stage 4 and is still a skeleton.
"""

from __future__ import annotations

from hades.contracts import ActuatorCommand, ActuatorStatus, SystemState

OLED_ROWS = 8
OLED_COLS = 21


class MockAlert:
    """Implements ``contracts.Alert`` by recording commands instead of driving hardware."""

    def send(self, cmd: ActuatorCommand) -> None:
        """Apply a command; sending the same command twice changes nothing."""
        raise NotImplementedError

    def status(self) -> ActuatorStatus:
        """Report what the outputs are doing."""
        raise NotImplementedError


def format_lines(state: SystemState, fps: float) -> list[str]:
    """Build the screen text: at most 8 lines of at most 21 characters."""
    lines = [
        "HADES",
        f"STATE  {state.state}",
        f"FPS    {fps:.1f}",
        f"FRAME  {state.frame_id}",
    ]
    return [line[:OLED_COLS] for line in lines[:OLED_ROWS]]


class VirtualOledDisplay:
    """Implements ``contracts.OledDisplay`` on a virtual 128 x 64 screen."""

    def __init__(self, echo: bool = True) -> None:
        self.echo = echo  # print the lines when they change
        self.lines: list[str] = []  # what is currently "on the screen"

    def update(self, state: SystemState, fps: float) -> None:
        """Show the current system state and frame rate."""
        lines = format_lines(state, fps)
        if lines != self.lines and self.echo:
            print("\n".join(lines), end="\n\n")
        self.lines = lines
