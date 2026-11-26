"""Alert outputs: the virtual OLED screen (work package D) and the alert mock (work package J).

The virtual OLED screen shows in the terminal exactly the text the real 128 x 64 screen will
show, laid out as it will appear there: eight rows of at most 21 characters. It imports no
hardware library, opens no window and writes no file. When the real screen arrives it is added
behind the same ``update`` function.

``MockAlert`` stands in for the LED, buzzer and laser. The real drivers are work package J in
Stage 4; the mock is pulled forward in its smallest form so the Stage 2 pipeline can show
"target seen, LED on" on a laptop. It only records commands and reports what the outputs would do.
"""

from __future__ import annotations

import time
from typing import Optional

from hades.contracts import (
    ActuatorCommand,
    ActuatorStatus,
    BuzzerMode,
    LedMode,
    SystemState,
)

OLED_ROWS = 8
OLED_COLS = 21


class MockAlert:
    """Implements ``contracts.Alert`` by recording commands instead of driving hardware."""

    def __init__(self) -> None:
        self.history: list[ActuatorCommand] = []  # every command that changed the outputs
        self._led: LedMode = "off"
        self._buzzer: BuzzerMode = "off"
        self._laser = False
        self._last_frame_id: Optional[int] = None

    def send(self, cmd: ActuatorCommand) -> None:
        """Apply a command; sending the same command twice changes nothing.

        ``alert_level`` 0 means every output is off, whatever the other fields say.
        """
        led, buzzer, laser = (
            (cmd.led_mode, cmd.buzzer_mode, cmd.laser_on)
            if cmd.alert_level == 1
            else ("off", "off", False)
        )
        if (led, buzzer, laser) == (self._led, self._buzzer, self._laser):
            return
        self._led, self._buzzer, self._laser = led, buzzer, laser
        self._last_frame_id = cmd.frame_id
        self.history.append(cmd)

    def status(self) -> ActuatorStatus:
        """Report what the outputs are doing."""
        return ActuatorStatus(
            led_mode=self._led,
            buzzer_mode=self._buzzer,
            laser_on=self._laser,
            last_command_frame_id=self._last_frame_id,
            healthy=True,
            t_status=time.monotonic_ns(),
        )


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
