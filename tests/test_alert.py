import ast
import subprocess
import sys
from pathlib import Path

import pytest

from hades.alert import VirtualOledDisplay, format_lines

SRC = Path(__file__).resolve().parents[1] / "src"
HARDWARE = {"RPi", "gpiozero", "board", "busio", "digitalio", "smbus", "smbus2",
            "spidev", "serial", "luma", "adafruit_ssd1306", "pigpio", "Adafruit_GPIO"}


def state_text(s):
    return str(getattr(s.state, "name", s.state))


# 1. At most eight lines of at most 21 characters
def test_line_count_and_width(states):
    for s in states:
        lines = format_lines(s, 24.8)
        assert 1 <= len(lines) <= 8
        assert all(len(l) <= 21 for l in lines)


def test_layout_matches_spec(states):
    s = states[0]
    lines = format_lines(s, 24.8)
    assert lines[0] == "HADES"
    assert lines[1].startswith("STATE  ")
    assert lines[2] == "FPS    24.8"
    assert lines[3] == f"FRAME  {s.frame_id}"


# 2. State shown exactly as given in the SystemState packet
def test_state_exactly_as_given(states):
    for s in states:
        assert format_lines(s, 24.8)[1] == f"STATE  {state_text(s)}"[:21]


# 3. Frame rate to one decimal place
@pytest.mark.parametrize("fps, shown", [(24.8, "24.8"), (25, "25.0"),
                                        (0, "0.0"), (24.84, "24.8")])
def test_fps_one_decimal(states, fps, shown):
    assert format_lines(states[0], fps)[2] == f"FPS    {shown}"


def test_update_stores_lines(states, capsys):
    d = VirtualOledDisplay()
    d.update(states[0], 24.8)
    assert d.lines == format_lines(states[0], 24.8)
    assert d.lines[0] in capsys.readouterr().out


# 4. Imports no hardware library
def test_no_hardware_imports_in_source():
    tree = ast.parse((SRC / "hades" / "alert.py").read_text())
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            names.add(n.module.split(".")[0])
    assert not names & HARDWARE


def test_no_hardware_modules_loaded_at_runtime():
    code = ("import sys, hades.alert; "
            f"bad = [m for m in sys.modules if m.split('.')[0] in {sorted(HARDWARE)}]; "
            "print(bad)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, env={"PYTHONPATH": str(SRC)}, check=True)
    assert out.stdout.strip() == "[]"

from conftest import assert_real_file

def test_lfs_pointer_is_detected(tmp_path):
    fake = tmp_path / "x.mp4"
    fake.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 1\n")
    with pytest.raises(AssertionError, match="Git LFS pointer"):
        assert_real_file(fake)