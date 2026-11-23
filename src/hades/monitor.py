"""Development web monitor (work packages D and L)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from hades.contracts import StateStyle


# class Monitor:
#     """Implements ``contracts.WebMonitor``."""

#     def start(self, port: int) -> None:
#         """Start the web page on the given port."""
#         raise NotImplementedError

#     def publish(self, message: object) -> None:
#         """Push any runtime packet to the page."""
#         raise NotImplementedError


# def state_style(state: str) -> StateStyle:
#     """Return the label and colour for a system state."""
#     raise NotImplementedError

"""Web monitor: serves the latest frame, state and detections over HTTP."""

import dataclasses
import io
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
from PIL import Image, ImageDraw

from hades.contracts import DetectionPacket, FramePacket, SystemState  # adjust module path if different

FPS_STALE_S = 2.0        # report 0 fps if no new frame was seen for this long


# ---- Adapters: the only place that knows BBox / ClassName / StateName -------
def _name(v) -> str:
    """Enum -> its name, anything else (str, Literal) -> str(v)."""
    return str(getattr(v, "name", v))

def _bbox(d) -> list[float]:
    b = d.bbox
    if dataclasses.is_dataclass(b):
        b = dataclasses.astuple(b)
    return [float(v) for v in b]            # expected order: x1, y1, x2, y2
# -----------------------------------------------------------------------------

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>HADES Monitor</title>
<style>
  body{background:#111;color:#ddd;font-family:monospace;margin:1rem}
  img{max-width:100%;border:1px solid #444}
  pre{background:#1b1b1b;padding:.7rem;overflow:auto}
</style></head><body>
<h2>HADES Monitor</h2>
<img id="f" src="/frame.jpg">
<pre id="s">waiting...</pre>
<script>
async function tick(){
  const t = Date.now();
  document.getElementById('f').src = '/frame.jpg?t=' + t;
  try{
    const r = await fetch('/status.json?t=' + t);
    document.getElementById('s').textContent =
      JSON.stringify(await r.json(), null, 2);
  }catch(e){}
}
setInterval(tick, 200);
</script></body></html>"""


class WebMonitor:
    def __init__(self, jpeg_quality: int = 80) -> None:
        self.jpeg_quality = jpeg_quality

        self._lock = threading.Lock()
        self._frame: FramePacket | None = None
        self._detection: DetectionPacket | None = None
        self._state: SystemState | None = None

        # Touched only by the single server thread, so no lock needed.
        self._cache = None        # (frame, detection_used, jpeg_bytes)
        self._fps_prev = None     # (frame_id, timestamp_ns, wall_time, fps)

        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------ start
    def start(self, port: int) -> None:
        """Start the development web page on the given port."""
        if self._server:
            return
        monitor = self

        class Handler(BaseHTTPRequestHandler):
            timeout = 5

            def log_message(self, *args):
                pass

            def _send(self, code, body, ctype):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = self.path.split("?")[0]
                if path == "/":
                    self._send(200, PAGE.encode(), "text/html; charset=utf-8")
                elif path == "/frame.jpg":
                    jpeg = monitor._frame_jpeg()
                    if jpeg is None:
                        self._send(503, b"no frame yet", "text/plain")
                    else:
                        self._send(200, jpeg, "image/jpeg")
                elif path == "/status.json":
                    body = json.dumps(monitor._status()).encode()
                    self._send(200, body, "application/json")
                else:
                    self._send(404, b"not found", "text/plain")

        # Plain HTTPServer (not Threading...) -> exactly one server thread.
        self._server = HTTPServer(("0.0.0.0", port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    # --------------------------------------------------------------- publish
    def publish(self, message: object) -> None:
        """Store the message as the latest of its type, then return."""
        with self._lock:
            if isinstance(message, FramePacket):
                self._frame = message
            elif isinstance(message, DetectionPacket):
                self._detection = message
            elif isinstance(message, SystemState):
                self._state = message
            # any other packet type is ignored; publish() never raises

    # -------------------------------------------------------------- internals
    def _frame_jpeg(self) -> bytes | None:
        with self._lock:
            frame, det = self._frame, self._detection
        if frame is None:
            return None

        # Boxes only if the detection belongs to the frame being shown.
        if det is not None and det.frame_id != frame.frame_id:
            det = None

        cache = self._cache
        if cache and cache[0] is frame and cache[1] is det:
            return cache[2]

        # Copy first: the FramePacket's own array is never modified.
        rgb = np.ascontiguousarray(np.array(frame.image, copy=True)[..., ::-1])
        img = Image.fromarray(rgb)             # BGR -> RGB
        if det is not None:
            draw = ImageDraw.Draw(img)
            for d in det.detections:
                x1, y1, x2, y2 = _bbox(d)
                draw.rectangle((x1, y1, x2, y2), outline=(0, 255, 0), width=2)
                draw.text((x1 + 2, max(0, y1 - 12)),
                          f"{_name(d.class_name)} {d.confidence:.2f}",
                          fill=(0, 255, 0))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=self.jpeg_quality)
        jpeg = buf.getvalue()
        self._cache = (frame, det, jpeg)
        return jpeg

    def _fps(self, frame: FramePacket | None) -> float:
        """Frame rate from frame_id / timestamp change between status polls."""
        if frame is None:
            return 0.0
        now = time.monotonic()
        fid, ts = frame.frame_id, frame.timestamp
        prev = self._fps_prev
        if prev is None:
            self._fps_prev = (fid, ts, now, 0.0)
            return 0.0
        pfid, pts, pwall, pfps = prev
        if fid == pfid and ts == pts:                 # no new frame since last poll
            return pfps if now - pwall <= FPS_STALE_S else 0.0
        dt = (ts - pts) / 1e9
        fps = round((fid - pfid) / dt, 1) if fid > pfid and dt > 0 else 0.0
        self._fps_prev = (fid, ts, now, fps)
        return fps

    def _status(self) -> dict:
        with self._lock:
            state, det, frame = self._state, self._detection, self._frame
        if det is not None:
            fid = det.frame_id
        else:
            fid = frame.frame_id if frame is not None else None
        return {
            "state": _name(state.state) if state is not None else None,
            "fps": self._fps(frame),
            "frame_id": fid,
            "detections": [
                {"bbox": _bbox(d),
                 "class_name": _name(d.class_name),
                 "confidence": float(d.confidence)}
                for d in (det.detections if det is not None else [])
            ],
        }