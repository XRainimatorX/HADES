"""Tests for the virtual OLED screen (work package D).

They use the shared sample packets (``states`` fixture), not their own sample data.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from hades.alert import OLED_COLS, OLED_ROWS, MockAlert, VirtualOledDisplay, format_lines
from hades.contracts import ActuatorCommand, SystemState

SRC = Path(__file__).resolve().parents[1] / "src"
HARDWARE = {
    "RPi", "gpiozero", "board", "busio", "digitalio", "smbus", "smbus2", "spidev", "serial",
    "luma", "adafruit_ssd1306", "pigpio", "Adafruit_GPIO",
}  # fmt: skip
NOT_ALLOWED_AT_ALL = HARDWARE | {"tkinter", "PIL"}


# 1. At most eight lines of at most 21 characters
def test_line_count_and_width(states: list[SystemState]) -> None:
    """Every state fits the 8 x 21 screen."""
    for state in states:
        lines = format_lines(state, 24.8)
        assert 1 <= len(lines) <= OLED_ROWS == 8
        assert all(len(line) <= OLED_COLS == 21 for line in lines)


def test_text_longer_than_the_screen_is_cut_not_wrapped() -> None:
    """A frame number too long for a row is cut at 21 characters, never spills onto another row."""
    state = SystemState("SCANNING", "IDLE", 10**30, 1)
    lines = format_lines(state, 1.0)
    assert len(lines) == 4 and all(len(line) <= 21 for line in lines)
    assert lines[3] == ("FRAME  " + str(10**30))[:21]


def test_layout_matches_the_design(states: list[SystemState]) -> None:
    """HADES, STATE, FPS and FRAME rows in the real screen's layout."""
    state = states[0]
    lines = format_lines(state, 24.8)
    assert lines[0] == "HADES"
    assert lines[1] == f"STATE  {state.state}"
    assert lines[2] == "FPS    24.8"
    assert lines[3] == f"FRAME  {state.frame_id}"


# 2. State shown exactly as given in the SystemState packet
@pytest.mark.parametrize("name", ["IDLE", "SCANNING", "CANDIDATE", "CONFIRMED", "ALERTING"])
def test_state_exactly_as_given(name: str) -> None:
    """The state name on the screen is the one in the packet, whichever it is."""
    state = SystemState(name, "IDLE", 1, 1)  # type: ignore[arg-type]
    assert format_lines(state, 10.0)[1] == f"STATE  {name}"


# 3. Frame rate to one decimal place
@pytest.mark.parametrize(
    ("fps", "shown"), [(24.8, "24.8"), (25, "25.0"), (0, "0.0"), (24.84, "24.8"), (24.86, "24.9")]
)
def test_fps_one_decimal(states: list[SystemState], fps: float, shown: str) -> None:
    """The frame rate is shown with exactly one decimal place."""
    assert format_lines(states[0], fps)[2] == f"FPS    {shown}"


def test_update_stores_and_prints_the_lines(
    states: list[SystemState], capsys: pytest.CaptureFixture[str]
) -> None:
    """update() keeps what is "on the screen" and prints it in the terminal."""
    display = VirtualOledDisplay()
    display.update(states[0], 24.8)
    assert display.lines == format_lines(states[0], 24.8)
    assert display.lines[0] in capsys.readouterr().out


def test_unchanged_lines_are_not_printed_again(
    states: list[SystemState], capsys: pytest.CaptureFixture[str]
) -> None:
    """The terminal only shows the screen when its content changes."""
    display = VirtualOledDisplay()
    display.update(states[0], 24.8)
    capsys.readouterr()
    display.update(states[0], 24.8)
    assert capsys.readouterr().out == ""
    display.update(states[0], 12.0)
    assert "FPS    12.0" in capsys.readouterr().out


def test_echo_off_prints_nothing(
    states: list[SystemState], capsys: pytest.CaptureFixture[str]
) -> None:
    """With echo off the screen is only stored."""
    display = VirtualOledDisplay(echo=False)
    display.update(states[0], 24.8)
    assert capsys.readouterr().out == "" and display.lines


def test_update_writes_no_file_and_opens_no_window(
    states: list[SystemState], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The screen is text in the terminal only: nothing is written to the current folder."""
    monkeypatch.chdir(tmp_path)
    VirtualOledDisplay().update(states[0], 24.8)
    assert list(tmp_path.iterdir()) == []


# 4. Imports no hardware library
def test_no_hardware_imports_in_source() -> None:
    """The source file names no hardware, window or imaging library."""
    tree = ast.parse((SRC / "hades" / "alert.py").read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not names & NOT_ALLOWED_AT_ALL


def test_no_hardware_modules_loaded_at_runtime() -> None:
    """Importing hades.alert loads no hardware, window or imaging module."""
    code = (
        "import sys, hades.alert; "
        f"bad = [m for m in sys.modules if m.split('.')[0] in {sorted(NOT_ALLOWED_AT_ALL)}]; "
        "print(bad)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(SRC)},
        check=True,
    )
    assert out.stdout.strip() == "[]"


# the alert mock (pulled forward from work package J)
def _command(level: int, led: str, buzzer: str, laser: bool, frame_id: int = 1) -> ActuatorCommand:
    return ActuatorCommand(level, led, buzzer, laser, frame_id, 10, 20)  # type: ignore[arg-type]


def test_the_mock_starts_with_every_output_off() -> None:
    """Before any command the LED, buzzer and laser are off and nothing has been commanded."""
    status = MockAlert().status()
    assert (status.led_mode, status.buzzer_mode, status.laser_on) == ("off", "off", False)
    assert status.last_command_frame_id is None and status.healthy


def test_the_mock_applies_a_command_and_reports_it() -> None:
    """An alert command turns the outputs on and records which frame caused it."""
    mock = MockAlert()
    mock.send(_command(1, "blink", "pulse", True, frame_id=42))
    status = mock.status()
    assert (status.led_mode, status.buzzer_mode, status.laser_on) == ("blink", "pulse", True)
    assert status.last_command_frame_id == 42
    assert status.t_status > 0


def test_sending_the_same_command_twice_changes_nothing() -> None:
    """The second identical command neither changes the outputs nor the history."""
    mock = MockAlert()
    mock.send(_command(1, "on", "off", False, frame_id=1))
    mock.send(_command(1, "on", "off", False, frame_id=2))
    assert len(mock.history) == 1 and mock.status().last_command_frame_id == 1


def test_alert_level_zero_switches_every_output_off() -> None:
    """Level 0 means no alert, whatever the other fields say."""
    mock = MockAlert()
    mock.send(_command(1, "blink", "pulse", True, frame_id=1))
    mock.send(_command(0, "blink", "pulse", True, frame_id=2))
    status = mock.status()
    assert (status.led_mode, status.buzzer_mode, status.laser_on) == ("off", "off", False)
    assert status.last_command_frame_id == 2 and len(mock.history) == 2
