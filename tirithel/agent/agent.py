"""Main desktop agent - orchestrates screen capture, input tracking, and API communication.

This is the core of the desktop agent that:
1. Captures screenshots at regular intervals
2. Tracks mouse clicks and keyboard input
3. Sends captured data to the Tirithel web API
4. Can be controlled via system tray or CLI
"""

from __future__ import annotations

import logging
import queue
import time
from threading import Thread

from tirithel.agent.api_client import TirithelAPIClient
from tirithel.agent.capture import CapturedFrame, ScreenCapture
from tirithel.agent.input_tracker import InputEvent, InputTracker

logger = logging.getLogger(__name__)


class TirithelAgent:
    """Desktop agent that captures support sessions and sends data to the API."""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        capture_interval: float = 3.0,
        profile_id: str | None = None,
    ):
        self.api_client = TirithelAPIClient(base_url=api_url)
        self.screen_capture = ScreenCapture(interval_seconds=capture_interval)
        self.input_tracker = InputTracker()
        self.profile_id = profile_id

        self.current_session_id: str | None = None
        self.is_recording = False
        self.frame_count = 0
        self._event_log: list[dict] = []

        # Queue for async upload
        self._upload_queue: queue.Queue = queue.Queue(maxsize=100)
        self._upload_thread: Thread | None = None

    def start_recording(self, title: str | None = None):
        """Start a new recording session."""
        if self.is_recording:
            logger.warning("Already recording")
            return

        # Check API health
        if not self.api_client.health_check():
            logger.error("Tirithel API is not reachable. Start the server first.")
            return

        # Create session via API
        session = self.api_client.create_session(
            title=title or f"Session {time.strftime('%Y-%m-%d %H:%M')}",
            profile_id=self.profile_id,
        )
        self.current_session_id = session["id"]
        self.frame_count = 0
        self._event_log.clear()
        self.is_recording = True

        # Start upload worker
        self._upload_thread = Thread(target=self._upload_worker, daemon=True)
        self._upload_thread.start()

        # Start screen capture
        self.screen_capture.start(callback=self._on_frame_captured)

        # Start input tracking
        self.input_tracker.start(callback=self._on_input_event)

        logger.info("Recording started - session %s", self.current_session_id)

    def stop_recording(self):
        """Stop recording and process the session."""
        if not self.is_recording:
            return

        self.is_recording = False

        # Stop capture and tracking
        self.screen_capture.stop()
        self.input_tracker.stop()

        # Wait for upload queue to drain
        self._upload_queue.put(None)  # Sentinel to stop worker
        if self._upload_thread:
            self._upload_thread.join(timeout=30)

        # Build and upload event log as transcript
        if self._event_log and self.current_session_id:
            transcript = self._build_event_transcript()
            if transcript:
                try:
                    self.api_client.upload_transcript(
                        self.current_session_id, transcript, use_llm=False
                    )
                except Exception as e:
                    logger.error("Failed to upload event transcript: %s", e)

        # Complete the session
        if self.current_session_id:
            try:
                self.api_client.complete_session(self.current_session_id)
                logger.info(
                    "Session %s completed (%d frames captured)",
                    self.current_session_id,
                    self.frame_count,
                )
            except Exception as e:
                logger.error("Failed to complete session: %s", e)

        self.current_session_id = None

    def _on_frame_captured(self, frame: CapturedFrame):
        """Callback when a screenshot is captured."""
        if not self.is_recording or not self.current_session_id:
            return

        self.frame_count += 1
        self._upload_queue.put(("screenshot", frame))

    def _on_input_event(self, event: InputEvent):
        """Callback when a mouse/keyboard event is detected."""
        if not self.is_recording:
            return

        self._event_log.append({
            "type": event.event_type,
            "timestamp": event.timestamp,
            "x": event.x,
            "y": event.y,
            "button": event.button,
            "text": event.text_buffer,
        })

    def _upload_worker(self):
        """Background thread that uploads captured data to the API."""
        while True:
            try:
                item = self._upload_queue.get(timeout=5)
            except queue.Empty:
                if not self.is_recording:
                    break
                continue

            if item is None:
                break

            item_type, data = item
            if item_type == "screenshot" and self.current_session_id:
                try:
                    self.api_client.upload_screenshot(
                        self.current_session_id, data.image_bytes
                    )
                except Exception as e:
                    logger.warning("Failed to upload screenshot: %s", e)

    def _build_event_transcript(self) -> str:
        """Build a pseudo-transcript from captured input events."""
        lines = []
        for event in self._event_log:
            ts = time.strftime("%H:%M:%S", time.localtime(event["timestamp"]))
            if event["type"] == "click":
                lines.append(
                    f"[{ts}] System: User clicked at ({event['x']}, {event['y']}) "
                    f"with {event['button']} button"
                )
            elif event["type"] == "type" and event["text"]:
                lines.append(f"[{ts}] System: User typed \"{event['text']}\"")
            elif event["type"] == "scroll":
                lines.append(f"[{ts}] System: User scrolled at ({event['x']}, {event['y']})")
        return "\n".join(lines)
