"""Claude API client for AI-powered analysis and guidance generation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import anthropic

logger = logging.getLogger(__name__)


@dataclass
class ClassifiedSegment:
    """A conversation segment classified by the LLM."""

    text: str
    segment_type: str  # issue_description, action_instruction, clarification, confirmation, other
    speaker: str
    confidence: float


@dataclass
class NavigationStep:
    """A single step in a navigation path."""

    step_number: int
    action: str  # click, type, navigate, select
    element_label: str
    element_path: str  # hierarchical: "Menu > Submenu > Item"
    description: str  # human-readable description


@dataclass
class IssueSolutionPair:
    """An issue mapped to its navigation solution."""

    issue_summary: str
    entry_point: str
    destination: str
    steps: list[NavigationStep]
    tags: list[str]
    confidence: float


class ClaudeClient:
    """Wrapper around Anthropic Claude API for Tirithel operations."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514", max_tokens: int = 4096):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def classify_conversation(self, transcript: str) -> list[ClassifiedSegment]:
        """Classify conversation segments by type (issue, instruction, etc.)."""
        prompt = f"""Analyze this support session transcript and classify each segment.

For each segment, identify:
- segment_type: one of "issue_description", "action_instruction", "clarification", "confirmation", "other"
- speaker: "support_agent", "user", or "system"
- confidence: 0.0 to 1.0

Return a JSON array of objects with keys: text, segment_type, speaker, confidence.

Transcript:
{transcript}

Return ONLY valid JSON, no other text."""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        try:
            result = json.loads(message.content[0].text)
            return [
                ClassifiedSegment(
                    text=seg["text"],
                    segment_type=seg["segment_type"],
                    speaker=seg["speaker"],
                    confidence=seg.get("confidence", 0.8),
                )
                for seg in result
            ]
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to parse classification response: %s", e)
            return []

    def correlate_session(self, timeline: str) -> list[IssueSolutionPair]:
        """Analyze a unified session timeline and extract issue-solution pairs."""
        prompt = f"""You are analyzing a support session timeline that interleaves conversation
and UI actions (detected from screenshots). Identify all issue-solution pairs.

For each pair, output:
- issue_summary: what the user needed help with
- entry_point: where in the UI the navigation started
- destination: where the navigation ended
- steps: ordered list of UI navigation steps, each with:
  - step_number (starting from 1)
  - action: click, type, navigate, or select
  - element_label: the exact UI element text (button label, menu name, etc.)
  - element_path: hierarchical location like "Main Menu > Administration > System Setup"
  - description: human-readable description of this step
- tags: relevant keywords for search
- confidence: 0.0 to 1.0

Timeline:
{timeline}

Return ONLY a valid JSON array of issue-solution pairs."""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        try:
            result = json.loads(message.content[0].text)
            pairs = []
            for pair in result:
                steps = [
                    NavigationStep(
                        step_number=s["step_number"],
                        action=s["action"],
                        element_label=s["element_label"],
                        element_path=s.get("element_path", ""),
                        description=s.get("description", ""),
                    )
                    for s in pair.get("steps", [])
                ]
                pairs.append(
                    IssueSolutionPair(
                        issue_summary=pair["issue_summary"],
                        entry_point=pair.get("entry_point", ""),
                        destination=pair.get("destination", ""),
                        steps=steps,
                        tags=pair.get("tags", []),
                        confidence=pair.get("confidence", 0.8),
                    )
                )
            return pairs
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to parse correlation response: %s", e)
            return []

    def generate_guidance(self, query: str, matched_paths: list[dict]) -> str:
        """Generate step-by-step guidance from matched navigation paths."""
        paths_text = ""
        for i, path in enumerate(matched_paths, 1):
            paths_text += f"\nPath {i} (confidence: {path.get('confidence_score', 'N/A')}, "
            paths_text += f"used {path.get('use_count', 0)} times):\n"
            paths_text += f"  Issue: {path['issue_summary']}\n"
            paths_text += f"  Steps: {json.dumps(path.get('steps', []), indent=2)}\n"

        prompt = f"""A user is asking for help navigating a software application.

User's question: "{query}"

I found these relevant navigation paths from previous support sessions:
{paths_text}

Generate clear, friendly, step-by-step instructions for the user.
- Use the exact UI element names from the learned paths
- Start with the navigation entry point
- Number each step
- Be concise but precise
- If the path involves typing or entering values, mention the field name
- End with a confirmation of what the user should see when done

If no paths seem relevant, say so honestly and suggest they contact support.

Return the instructions as plain text, not JSON."""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        return message.content[0].text
