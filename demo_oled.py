import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from hades.alert import VirtualOledDisplay
from hades.contracts import SystemState

state = SystemState(state="SCANNING", previous="IDLE", frame_id=1042, timestamp=0)
oled = VirtualOledDisplay()
oled.update(state, 24.8)
print(oled.lines)