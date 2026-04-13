"""API client - sends captured data to the Tirithel web API."""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


class TirithelAPIClient:
    """HTTP client for communicating with the Tirithel web API."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_prefix = "/api/v1"
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    @property
    def api_url(self) -> str:
        return f"{self.base_url}{self.api_prefix}"

    def health_check(self) -> bool:
        """Check if the API is reachable."""
        try:
            resp = self._client.get(f"{self.api_url}/health")
            return resp.status_code == 200
        except httpx.RequestError:
            return False

    def create_session(
        self, title: str | None = None, profile_id: str | None = None
    ) -> dict:
        """Start a new recording session."""
        resp = self._client.post(
            f"{self.api_url}/sessions",
            json={"title": title, "profile_id": profile_id},
        )
        resp.raise_for_status()
        return resp.json()

    def upload_screenshot(self, session_id: str, image_bytes: bytes) -> dict:
        """Upload a screenshot to the session."""
        resp = self._client.post(
            f"{self.api_url}/sessions/{session_id}/screenshots",
            files={"file": ("screenshot.png", image_bytes, "image/png")},
        )
        resp.raise_for_status()
        return resp.json()

    def add_conversation_segment(
        self,
        session_id: str,
        text: str,
        speaker: str = "user",
        segment_type: str | None = None,
    ) -> dict:
        """Add a conversation segment to the session."""
        payload = {"text": text, "speaker": speaker}
        if segment_type:
            payload["segment_type"] = segment_type
        resp = self._client.post(
            f"{self.api_url}/sessions/{session_id}/conversation",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    def upload_transcript(
        self, session_id: str, transcript: str, use_llm: bool = True
    ) -> list[dict]:
        """Upload a full transcript."""
        resp = self._client.post(
            f"{self.api_url}/sessions/{session_id}/transcript",
            json={"transcript": transcript, "use_llm": use_llm},
        )
        resp.raise_for_status()
        return resp.json()

    def complete_session(self, session_id: str) -> dict:
        """Finalize and process a session."""
        resp = self._client.post(
            f"{self.api_url}/sessions/{session_id}/complete",
        )
        resp.raise_for_status()
        return resp.json()

    def get_session(self, session_id: str) -> dict:
        """Get session details."""
        resp = self._client.get(f"{self.api_url}/sessions/{session_id}")
        resp.raise_for_status()
        return resp.json()

    def list_profiles(self) -> list[dict]:
        """List software profiles."""
        resp = self._client.get(f"{self.api_url}/profiles")
        resp.raise_for_status()
        return resp.json()

    def query_guidance(self, query: str, profile_id: str | None = None) -> dict:
        """Ask for navigation guidance."""
        payload = {"query": query}
        if profile_id:
            payload["profile_id"] = profile_id
        resp = self._client.post(f"{self.api_url}/guidance/query", json=payload)
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._client.close()
