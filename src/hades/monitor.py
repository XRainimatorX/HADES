"""Development web monitor (work package D); the state styles belong to work package L.

``WebMonitor`` serves a plain page with the latest frame (with the detection boxes of the same
frame), the frame rate, the system state and the latest detections. ``publish()`` only stores the
message as the latest of its type and returns, so it never slows the main loop. One server thread
is started by ``start()``; nothing starts when the module is imported.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional

import cv2
import numpy as np

from hades.contracts import DetectionPacket, FramePacket, StateStyle, SystemState

FPS_STALE_S = 2.0  # report 0 fps if no new frame was seen for this long
BOX_COLOUR = (0, 255, 0)  # BGR

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


def state_style(state: str) -> StateStyle:
    """Return the label and colour for a system state (work package L, Stage 4)."""
    raise NotImplementedError


class WebMonitor:
    """Implements ``contracts.WebMonitor``.

    The server listens on ``host`` (this computer only by default), so the page is not exposed to
    the network unless the host is changed on purpose.
    """

    def __init__(self, jpeg_quality: int = 80, host: str = "127.0.0.1") -> None:
        self.jpeg_quality = jpeg_quality
        self.host = host

        self._lock = threading.Lock()
        self._frame: Optional[FramePacket] = None
        self._detection: Optional[DetectionPacket] = None
        self._state: Optional[SystemState] = None

        # Touched only by the single server thread, so no lock is needed.
        self._cache: Optional[tuple[FramePacket, Optional[DetectionPacket], bytes]] = None
        self._fps_prev: Optional[tuple[int, int, float, float]] = None

        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ start
    def start(self, port: int) -> None:
        """Start the development web page on the given port."""
        if self._server:
            return
        monitor = self

        class Handler(BaseHTTPRequestHandler):
            """Serves the page, the latest frame and the latest status."""

            timeout = 5

            def log_message(self, format: str, *args: Any) -> None:  # pylint: disable=W0622
                """Keep the console quiet."""

            def _send(self, code: int, body: bytes, ctype: str) -> None:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # pylint: disable=invalid-name
                """Answer one request."""
                path = self.path.split("?", maxsplit=1)[0]
                if path == "/":
                    self._send(200, PAGE.encode(), "text/html; charset=utf-8")
                elif path == "/frame.jpg":
                    jpeg = monitor._frame_jpeg()  # pylint: disable=protected-access
                    if jpeg is None:
                        self._send(503, b"no frame yet", "text/plain")
                    else:
                        self._send(200, jpeg, "image/jpeg")
                elif path == "/status.json":
                    body = json.dumps(monitor._status()).encode()  # pylint: disable=W0212
                    self._send(200, body, "application/json")
                else:
                    self._send(404, b"not found", "text/plain")

        # Plain HTTPServer (not a threading one) -> exactly one server thread.
        self._server = HTTPServer((self.host, port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the server thread."""
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
    def _frame_jpeg(self) -> Optional[bytes]:
        """The latest frame as a JPEG, with boxes only if the detection belongs to that frame."""
        with self._lock:
            frame, det = self._frame, self._detection
        if frame is None:
            return None
        if det is not None and det.frame_id != frame.frame_id:
            det = None

        cache = self._cache
        if cache and cache[0] is frame and cache[1] is det:
            return cache[2]

        # Copy first: the FramePacket's own array is never modified.
        image = np.array(frame.image, copy=True)
        if det is not None:
            for detection in det.detections:
                x1, y1, x2, y2 = (int(round(v)) for v in detection.bbox)
                cv2.rectangle(image, (x1, y1), (x2, y2), BOX_COLOUR, 2)
                label = f"{detection.class_name} {detection.confidence:.2f}"
                cv2.putText(
                    image, label, (x1 + 2, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    BOX_COLOUR, 1,
                )  # fmt: skip
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        if not ok:
            return None
        jpeg = bytes(encoded.tobytes())
        self._cache = (frame, det, jpeg)
        return jpeg

    def _fps(self, frame: Optional[FramePacket]) -> float:
        """Frame rate from the change of frame_id and timestamp between status polls."""
        if frame is None:
            return 0.0
        now = time.monotonic()
        frame_id, stamp = frame.frame_id, frame.timestamp
        prev = self._fps_prev
        if prev is None:
            self._fps_prev = (frame_id, stamp, now, 0.0)
            return 0.0
        prev_id, prev_stamp, prev_wall, prev_fps = prev
        if frame_id == prev_id and stamp == prev_stamp:  # no new frame since the last poll
            return prev_fps if now - prev_wall <= FPS_STALE_S else 0.0
        elapsed = (stamp - prev_stamp) / 1e9
        fps = (
            round((frame_id - prev_id) / elapsed, 1) if frame_id > prev_id and elapsed > 0 else 0.0
        )
        self._fps_prev = (frame_id, stamp, now, fps)
        return fps

    def _status(self) -> dict[str, Any]:
        """The latest state, frame rate and detections, as JSON-ready values."""
        with self._lock:
            state, det, frame = self._state, self._detection, self._frame
        if det is not None:
            frame_id: Optional[int] = det.frame_id
        else:
            frame_id = frame.frame_id if frame is not None else None
        return {
            "state": state.state if state is not None else None,
            "fps": self._fps(frame),
            "frame_id": frame_id,
            "detections": [
                {
                    "bbox": [float(v) for v in d.bbox],
                    "class_name": d.class_name,
                    "confidence": float(d.confidence),
                }
                for d in (det.detections if det is not None else ())
            ],
        }
