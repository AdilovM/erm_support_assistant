"""Split and classify conversation transcripts into meaningful segments."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class RawSegment:
    """A raw segment extracted from a transcript before AI classification."""

    speaker: str
    text: str
    timestamp: datetime | None = None


class ConversationSegmenter:
    """Splits raw conversation transcripts into speaker-turn segments.

    This handles the initial parsing/splitting. AI classification of segment
    types (issue_description, action_instruction, etc.) is done by the LLM
    client in a separate step.
    """

    # Patterns for detecting speaker turns in transcripts
    SPEAKER_PATTERNS = [
        # "Agent: text" or "User: text"
        re.compile(r"^((?:Agent|Support|Rep|Tech|User|Customer|Client)\s*):?\s*(.+)", re.IGNORECASE),
        # "[10:30:01] Speaker: text"
        re.compile(r"^\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?\s*((?:Agent|Support|Rep|Tech|User|Customer|Client)\s*):?\s*(.+)", re.IGNORECASE),
        # "Speaker Name (10:30): text"
        re.compile(r"^([^(]+)\((\d{1,2}:\d{2}(?::\d{2})?)\):?\s*(.+)", re.IGNORECASE),
    ]

    # Keywords that suggest instruction-type content
    INSTRUCTION_KEYWORDS = [
        "click", "go to", "navigate", "open", "select", "choose",
        "type", "enter", "press", "find", "look for", "scroll",
        "expand", "collapse", "right-click", "double-click", "drag",
    ]

    # Keywords that suggest issue description
    ISSUE_KEYWORDS = [
        "can't", "cannot", "unable", "doesn't work", "error",
        "problem", "issue", "need to", "want to", "how do i",
        "help me", "struggling", "broken", "wrong", "missing",
    ]

    def segment_transcript(self, transcript: str) -> list[RawSegment]:
        """Parse a raw transcript into speaker-turn segments."""
        lines = transcript.strip().split("\n")
        segments: list[RawSegment] = []
        current_speaker = "unknown"
        current_text_parts: list[str] = []
        current_timestamp = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            parsed = self._parse_line(line)
            if parsed:
                # Save previous segment
                if current_text_parts:
                    segments.append(
                        RawSegment(
                            speaker=self._normalize_speaker(current_speaker),
                            text=" ".join(current_text_parts),
                            timestamp=current_timestamp,
                        )
                    )
                current_speaker = parsed["speaker"]
                current_text_parts = [parsed["text"]]
                current_timestamp = parsed.get("timestamp")
            else:
                # Continuation of current speaker's text
                current_text_parts.append(line)

        # Don't forget the last segment
        if current_text_parts:
            segments.append(
                RawSegment(
                    speaker=self._normalize_speaker(current_speaker),
                    text=" ".join(current_text_parts),
                    timestamp=current_timestamp,
                )
            )

        return segments

    def _parse_line(self, line: str) -> dict | None:
        """Try to parse a line as a new speaker turn."""
        for pattern in self.SPEAKER_PATTERNS:
            match = pattern.match(line)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    return {"speaker": groups[0].strip(), "text": groups[1].strip()}
                elif len(groups) == 3:
                    # Has timestamp
                    timestamp_str = groups[0] if ":" in groups[0] else groups[1]
                    speaker = groups[1] if ":" in groups[0] else groups[0]
                    text = groups[2]
                    timestamp = self._parse_timestamp(timestamp_str)
                    return {
                        "speaker": speaker.strip(),
                        "text": text.strip(),
                        "timestamp": timestamp,
                    }
        return None

    def _normalize_speaker(self, speaker: str) -> str:
        """Normalize speaker labels to standard values."""
        lower = speaker.lower().strip()
        if any(kw in lower for kw in ["agent", "support", "rep", "tech"]):
            return "support_agent"
        elif any(kw in lower for kw in ["user", "customer", "client"]):
            return "user"
        return "user"

    def _parse_timestamp(self, ts: str) -> datetime | None:
        """Parse a time string into a datetime (today's date + time)."""
        try:
            parts = ts.split(":")
            hour, minute = int(parts[0]), int(parts[1])
            second = int(parts[2]) if len(parts) > 2 else 0
            return datetime.now().replace(hour=hour, minute=minute, second=second, microsecond=0)
        except (ValueError, IndexError):
            return None

    def guess_segment_type(self, text: str) -> str:
        """Heuristic guess of segment type (fallback when LLM is unavailable)."""
        lower = text.lower()

        if any(kw in lower for kw in self.INSTRUCTION_KEYWORDS):
            return "action_instruction"
        elif any(kw in lower for kw in self.ISSUE_KEYWORDS):
            return "issue_description"
        elif lower.startswith(("yes", "no", "that's", "perfect", "thank", "got it")):
            return "confirmation"
        elif "?" in text:
            return "clarification"
        return "other"
