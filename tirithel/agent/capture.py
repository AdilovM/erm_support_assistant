"""Screen capture module - takes periodic screenshots using mss."""

from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass
from threading import Event, Thread

import mss
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class CapturedFrame:
    """A captured screenshot with metadata."""

    image_bytes: bytes
    timestamp: float
    width: int
    height: int


class ScreenCapture:
    """Captures screenshots at configurable intervals.

    Runs in a background thread and calls a callback with each frame.
    """

    def __init__(self, interval_seconds: float = 3.0, monitor: int = 0):
        """
        Args:
            interval_seconds: Time between captures.
            monitor: Monitor index (0 = all monitors combined).
        """
        self.interval = interval_seconds
        self.monitor = monitor
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._callback = None
        self._last_hash: str | None = None

    def start(self, callback):
        """Start capturing in a background thread.

        Args:
            callback: Function called with each CapturedFrame.
        """
        self._callback = callback
        self._stop_event.clear()
        self._thread = Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Screen capture started (interval: %.1fs)", self.interval)

    def stop(self):
        """Stop the capture loop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Screen capture stopped")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def capture_once(self) -> CapturedFrame | None:
        """Take a single screenshot and return it."""
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[self.monitor]
                raw = sct.grab(monitor)

                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

                buf = io.BytesIO()
                img.save(buf, format="PNG", optimize=True)
                image_bytes = buf.getvalue()

                return CapturedFrame(
                    image_bytes=image_bytes,
                    timestamp=time.time(),
                    width=img.width,
                    height=img.height,
                )
        except Exception as e:
            logger.error("Screenshot capture failed: %s", e)
            return None

    def _capture_loop(self):
        """Background loop that captures frames at intervals."""
        while not self._stop_event.is_set():
            frame = self.capture_once()
            if frame and self._callback:
                try:
                    self._callback(frame)
                except Exception as e:
                    logger.error("Frame callback failed: %s", e)

            self._stop_event.wait(self.interval)
