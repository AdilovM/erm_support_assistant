"""Input tracker - monitors mouse clicks and keyboard events."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import Thread

logger = logging.getLogger(__name__)


@dataclass
class InputEvent:
    """A captured mouse or keyboard event."""

    event_type: str  # "click", "type", "scroll"
    timestamp: float
    x: int = 0
    y: int = 0
    button: str = ""  # "left", "right", "middle"
    key: str = ""  # key character or name
    text_buffer: str = ""  # accumulated typed text


class InputTracker:
    """Tracks mouse clicks and keyboard input.

    Uses pynput to monitor input events. Aggregates keystrokes into
    text buffers and reports click positions.
    """

    def __init__(self):
        self._mouse_listener = None
        self._keyboard_listener = None
        self._callback = None
        self._typing_buffer: list[str] = []
        self._last_key_time: float = 0
        self._typing_timeout = 2.0  # seconds of silence before flushing buffer
        self._running = False

    def start(self, callback):
        """Start tracking input events.

        Args:
            callback: Function called with each InputEvent.
        """
        try:
            from pynput import keyboard, mouse
        except ImportError:
            logger.warning(
                "pynput not installed - input tracking disabled. "
                "Install with: pip install pynput"
            )
            return

        self._callback = callback
        self._running = True

        # Mouse listener
        self._mouse_listener = mouse.Listener(
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self._mouse_listener.start()

        # Keyboard listener
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
        )
        self._keyboard_listener.start()

        # Buffer flush thread
        self._flush_thread = Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

        logger.info("Input tracking started")

    def stop(self):
        """Stop tracking input events."""
        self._running = False
        self._flush_typing_buffer()

        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()

        logger.info("Input tracking stopped")

    def _on_click(self, x, y, button, pressed):
        """Handle mouse click events."""
        if not pressed or not self._callback:
            return

        # Flush any pending typing before recording click
        self._flush_typing_buffer()

        event = InputEvent(
            event_type="click",
            timestamp=time.time(),
            x=int(x),
            y=int(y),
            button=button.name if hasattr(button, "name") else str(button),
        )
        self._callback(event)

    def _on_scroll(self, x, y, dx, dy):
        """Handle scroll events."""
        if not self._callback:
            return

        event = InputEvent(
            event_type="scroll",
            timestamp=time.time(),
            x=int(x),
            y=int(y),
        )
        self._callback(event)

    def _on_key_press(self, key):
        """Handle key press events - accumulate into typing buffer."""
        self._last_key_time = time.time()

        try:
            # Regular character key
            char = key.char
            if char:
                self._typing_buffer.append(char)
        except AttributeError:
            # Special key (Enter, Tab, etc.)
            key_name = key.name if hasattr(key, "name") else str(key)
            if key_name in ("enter", "return", "tab"):
                self._flush_typing_buffer()
            elif key_name == "space":
                self._typing_buffer.append(" ")
            elif key_name == "backspace" and self._typing_buffer:
                self._typing_buffer.pop()

    def _flush_typing_buffer(self):
        """Flush accumulated keystrokes as a single type event."""
        if not self._typing_buffer or not self._callback:
            return

        text = "".join(self._typing_buffer).strip()
        self._typing_buffer.clear()

        if text:
            event = InputEvent(
                event_type="type",
                timestamp=time.time(),
                text_buffer=text,
            )
            self._callback(event)

    def _flush_loop(self):
        """Periodically flush typing buffer after silence."""
        while self._running:
            time.sleep(0.5)
            if (
                self._typing_buffer
                and time.time() - self._last_key_time > self._typing_timeout
            ):
                self._flush_typing_buffer()
