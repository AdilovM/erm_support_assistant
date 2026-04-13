"""System tray application for the Tirithel desktop agent.

Provides a tray icon with controls to start/stop recording sessions.
Uses pystray for cross-platform system tray support.
"""

from __future__ import annotations

import logging
import sys
import time
from threading import Thread

logger = logging.getLogger(__name__)


class TrayApp:
    """System tray application for controlling Tirithel agent."""

    def __init__(self, agent):
        self.agent = agent
        self._icon = None

    def run(self):
        """Start the system tray application."""
        try:
            import pystray
            from PIL import Image as PILImage
        except ImportError:
            logger.error(
                "pystray not installed. Install with: pip install pystray\n"
                "Falling back to CLI mode."
            )
            self._run_cli_mode()
            return

        # Create a simple icon (blue circle)
        icon_image = PILImage.new("RGB", (64, 64), color=(30, 58, 95))

        menu = pystray.Menu(
            pystray.MenuItem(
                "Start Recording",
                self._on_start,
                visible=lambda item: not self.agent.is_recording,
            ),
            pystray.MenuItem(
                "Stop Recording",
                self._on_stop,
                visible=lambda item: self.agent.is_recording,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: f"Status: {'Recording' if self.agent.is_recording else 'Idle'}",
                None,
                enabled=False,
            ),
            pystray.MenuItem(
                lambda item: f"Frames: {self.agent.frame_count}",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )

        self._icon = pystray.Icon("Tirithel", icon_image, "Tirithel Agent", menu)
        logger.info("Tirithel tray icon started")
        self._icon.run()

    def _run_cli_mode(self):
        """Fallback CLI mode when pystray is not available."""
        print("\n=== Tirithel Desktop Agent (CLI Mode) ===")
        print("Commands: start, stop, status, quit\n")

        while True:
            try:
                cmd = input("tirithel> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                break

            if cmd == "start":
                title = input("Session title (optional): ").strip() or None
                self.agent.start_recording(title=title)
                print("Recording started.")
            elif cmd == "stop":
                self.agent.stop_recording()
                print("Recording stopped and session submitted for processing.")
            elif cmd == "status":
                status = "Recording" if self.agent.is_recording else "Idle"
                print(f"Status: {status}")
                print(f"Frames captured: {self.agent.frame_count}")
                if self.agent.current_session_id:
                    print(f"Session ID: {self.agent.current_session_id}")
            elif cmd in ("quit", "exit", "q"):
                if self.agent.is_recording:
                    self.agent.stop_recording()
                break
            elif cmd == "help":
                print("Commands: start, stop, status, quit")
            else:
                print(f"Unknown command: {cmd}. Type 'help' for commands.")

        print("Tirithel agent stopped.")

    def _on_start(self, icon, item):
        Thread(target=lambda: self.agent.start_recording(), daemon=True).start()

    def _on_stop(self, icon, item):
        Thread(target=lambda: self.agent.stop_recording(), daemon=True).start()

    def _on_quit(self, icon, item):
        if self.agent.is_recording:
            self.agent.stop_recording()
        icon.stop()
