"""Alert outputs (work package J): mock, LED, buzzer, laser, OLED."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from hades.contracts import ActuatorCommand, ActuatorStatus

# class MockAlert:
#     """Implements ``contracts.Alert`` by recording commands instead of driving hardware."""

#     def send(self, cmd: ActuatorCommand) -> None:
#         """Apply a command; sending the same command twice changes nothing."""
#         raise NotImplementedError

#     def status(self) -> ActuatorStatus:
#         """Report what the outputs are doing."""
#         raise NotImplementedError

# import time
# import tkinter as tk
# from PIL import Image, ImageDraw, ImageFont, ImageTk

# W, H, SCALE = 128, 64, 5


# def load_font(size=10):
#     """Use a monospace TTF if available, else Pillow's tiny built-in font."""
#     try:
#         return ImageFont.truetype("DejaVuSansMono.ttf", size)
#     except OSError:
#         return ImageFont.load_default()


# def text_width(draw, s, font):
#     l, _, r, _ = draw.textbbox((0, 0), s, font=font)
#     return r - l


# def fit(draw, s, font, max_w):
#     """Trim text with '...' so it never runs off the screen."""
#     if text_width(draw, s, font) <= max_w:
#         return s
#     while s and text_width(draw, s + "...", font) > max_w:
#         s = s[:-1]
#     return s + "..."


# def render(title="", lines=(), footer="", align="left", border=True):
#     img = Image.new("1", (W, H), 0)
#     draw = ImageDraw.Draw(img)
#     font = load_font(10)
#     pad, max_w = 2, W - 4

#     def x_for(s):
#         tw = text_width(draw, s, font)
#         if align == "center":
#             return (W - tw) // 2
#         if align == "right":
#             return W - tw - pad
#         return pad

#     y = 0
#     if title:
#         draw.rectangle((0, 0, W - 1, 12), fill=1)
#         t = fit(draw, title, font, max_w)
#         draw.text((x_for(t), 0), t, font=font, fill=0)
#         y = 15

#     for line in lines:
#         if y > H - 12:
#             break
#         s = fit(draw, line, font, max_w)
#         draw.text((x_for(s), y), s, font=font, fill=1)
#         y += 11

#     if footer:
#         draw.line((0, H - 13, W - 1, H - 13), fill=1)
#         f = fit(draw, footer, font, max_w)
#         draw.text((x_for(f), H - 12), f, font=font, fill=1)

#     if border:
#         draw.rectangle((0, 0, W - 1, H - 1), outline=1)

#     return img.convert("RGB").resize((W * SCALE, H * SCALE), Image.NEAREST)


# class VirtualOLED:
#     """One persistent window. Call update() as often as you like."""

#     def __init__(self):
#         self.root = self.label = self.photo = None
#         self.headless = False
#         self.closed = False
#         try:
#             self.root = tk.Tk()
#             self.root.title("Virtual OLED")
#             self.root.protocol("WM_DELETE_WINDOW", self.close)
#             self.label = tk.Label(self.root, bg="black")
#             self.label.pack()
#         except tk.TclError:           # no display (e.g. plain Codespaces)
#             self.root = None
#             self.headless = True
#             print("No display available, falling back to oled.png")

#     def close(self):
#         self.closed = True
#         if self.root:
#             self.root.destroy()
#             self.root = None

#     def update(self, title="", lines=(), footer="", **kwargs):
#         """Redraw the frame. Returns False once the window has been closed."""
#         big = render(title, lines, footer, **kwargs)

#         if self.headless:
#             big.save("oled.png")
#             return True
#         if self.closed:
#             return False

#         try:
#             self.photo = ImageTk.PhotoImage(big)   # keep a reference
#             self.label.configure(image=self.photo)
#             self.root.update()
#         except tk.TclError:
#             self.closed = True
#             return False
#         return True

# class OledDisplay:
#     """Shows the current system state and frame rate on the helmet screen."""

#     def __init__(self) -> None:
#         self._screen = VirtualOLED()      # swap for real SSD1306 output later

#     def update(self, state, fps: float) -> None:
#         name = getattr(state, "name", str(state))
#         self._screen.update(
#             title="HADES",
#             lines=[f"STATE: {name}", f"FPS: {fps:.1f}"],
#             align="left",
#         )

# if __name__ == "__main__":
#     oled = VirtualOLED()
#     frame = 0
#     while oled.update(
#         title="HADES",
#         lines=["STATE: SCANNING", "FPS: 24.8", f"FRAME: {frame}"],
#         align="left",
#     ):
#         frame += 1
#         time.sleep(0.1)

"""Alert outputs (work package J): mock, LED, buzzer, laser, OLED."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from hades.contracts import ActuatorCommand, ActuatorStatus, SystemState


class MockAlert:
    """Implements ``contracts.Alert`` by recording commands instead of driving hardware."""

    def send(self, cmd: ActuatorCommand) -> None:
        """Apply a command; sending the same command twice changes nothing."""
        raise NotImplementedError

    def status(self) -> ActuatorStatus:
        """Report what the outputs are doing."""
        raise NotImplementedError


# --- Virtual OLED (128 x 64 = 8 rows of 8 px, 21 columns of 6 px) -----------

W, H, SCALE = 128, 64, 5
OLED_ROWS, OLED_COLS = 8, 21
ROW_PX = H // OLED_ROWS


def _name(v) -> str:
    """Enum -> its name; str or Literal -> the value unchanged."""
    return str(getattr(v, "name", v))


def format_lines(state: SystemState, fps: float) -> list[str]:
    """Build the screen text: at most 8 lines of at most 21 characters."""
    lines = [
        "HADES",
        f"STATE  {_name(state.state)}",
        f"FPS    {fps:.1f}",
        f"FRAME  {state.frame_id}",
    ]
    return [line[:OLED_COLS] for line in lines[:OLED_ROWS]]


def render(lines: list[str]):
    """Draw the lines on a 1-bit 128x64 image, scaled up. Needs Pillow only."""
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.truetype("DejaVuSansMono.ttf", 8)
    except OSError:
        font = ImageFont.load_default()

    img = Image.new("1", (W, H), 0)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((0, i * ROW_PX), line, font=font, fill=1)
    return img.convert("RGB").resize((W * SCALE, H * SCALE), Image.NEAREST)


class _Window:
    """One persistent Tk window; falls back to oled.png if there is no display."""

    def __init__(self) -> None:
        self.root = self.label = self.photo = None
        self.headless = False
        self.closed = False
        try:
            import tkinter as tk
            self._tk = tk
            self.root = tk.Tk()
            self.root.title("Virtual OLED")
            self.root.protocol("WM_DELETE_WINDOW", self.close)
            self.label = tk.Label(self.root, bg="black")
            self.label.pack()
        except Exception:             # no Tk installed, or no display (Codespaces)
            self.root = None
            self.headless = True
            print("No display available, falling back to oled.png")

    def close(self) -> None:
        self.closed = True
        if self.root:
            self.root.destroy()
            self.root = None

    def show(self, lines: list[str]) -> None:
        big = render(lines)
        if self.headless:
            big.save("oled.png")
            return
        if self.closed:
            return
        try:
            from PIL import ImageTk
            self.photo = ImageTk.PhotoImage(big)      # keep a reference
            self.label.configure(image=self.photo)
            self.root.update()
        except self._tk.TclError:
            self.closed = True


class VirtualOledDisplay:
    """Implements ``contracts.OledDisplay`` on a virtual 128 x 64 screen."""

    def __init__(self, show_window: bool = False, echo: bool = True) -> None:
        self.echo = echo                      # print the lines when they change
        self._window = _Window() if show_window else None
        self.lines: list[str] = []            # what is currently "on the screen"

    def update(self, state: SystemState, fps: float) -> None:
        """Show the current system state and frame rate."""
        lines = format_lines(state, fps)
        if lines != self.lines and self.echo:
            print("\n".join(lines), end="\n\n")
        self.lines = lines
        if self._window:
            self._window.show(lines)