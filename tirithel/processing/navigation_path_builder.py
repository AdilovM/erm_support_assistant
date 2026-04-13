"""Build structured navigation paths from UI actions and conversation data."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PathStep:
    """A single step in a navigation path."""

    step_number: int
    action: str
    element_label: str
    element_path: str
    description: str
    screenshot_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "action": self.action,
            "element_label": self.element_label,
            "element_path": self.element_path,
            "description": self.description,
            "screenshot_id": self.screenshot_id,
        }


@dataclass
class BuiltPath:
    """A fully built navigation path ready for storage."""

    issue_summary: str
    entry_point: str
    destination: str
    steps: list[PathStep]
    tags: list[str]
    confidence: float

    def steps_to_json(self) -> str:
        return json.dumps([s.to_dict() for s in self.steps])

    def tags_to_json(self) -> str:
        return json.dumps(self.tags)

    def to_human_readable(self) -> str:
        """Generate a human-readable description of this path."""
        lines = [f"Issue: {self.issue_summary}", ""]
        for step in self.steps:
            if step.action == "click":
                lines.append(f"{step.step_number}. Click on '{step.element_label}'")
            elif step.action == "type":
                lines.append(f"{step.step_number}. Type in the '{step.element_label}' field")
            elif step.action == "navigate":
                lines.append(f"{step.step_number}. Navigate to {step.element_label}")
            elif step.action == "select":
                lines.append(f"{step.step_number}. Select '{step.element_label}'")
            else:
                lines.append(f"{step.step_number}. {step.description or step.action}")

            if step.element_path:
                lines.append(f"   (Location: {step.element_path})")

        return "\n".join(lines)


class NavigationPathBuilder:
    """Builds structured navigation paths from raw UI action data."""

    def build_from_ui_actions(
        self,
        ui_actions: list[dict],
        issue_summary: str,
        tags: list[str] | None = None,
    ) -> BuiltPath:
        """Build a navigation path from a list of UI action records.

        Args:
            ui_actions: List of UI action dicts with keys like
                        action_type, element_label, element_path, etc.
            issue_summary: Summary of the issue this path resolves.
            tags: Optional search tags.
        """
        steps = []
        for i, action in enumerate(ui_actions, 1):
            steps.append(
                PathStep(
                    step_number=i,
                    action=action.get("action_type", "click"),
                    element_label=action.get("element_label", ""),
                    element_path=action.get("element_path", ""),
                    description=action.get("description", ""),
                    screenshot_id=action.get("screenshot_id"),
                )
            )

        entry_point = steps[0].element_path if steps else ""
        destination = steps[-1].element_path if steps else ""

        return BuiltPath(
            issue_summary=issue_summary,
            entry_point=entry_point,
            destination=destination,
            steps=steps,
            tags=tags or [],
            confidence=0.8,
        )

    def build_from_llm_response(self, llm_pair: dict) -> BuiltPath:
        """Build a navigation path from an LLM-generated issue-solution pair.

        Args:
            llm_pair: Dict from ClaudeClient.correlate_session() with keys:
                      issue_summary, entry_point, destination, steps, tags, confidence
        """
        steps = []
        for s in llm_pair.get("steps", []):
            steps.append(
                PathStep(
                    step_number=s.get("step_number", 0),
                    action=s.get("action", "click"),
                    element_label=s.get("element_label", ""),
                    element_path=s.get("element_path", ""),
                    description=s.get("description", ""),
                )
            )

        return BuiltPath(
            issue_summary=llm_pair.get("issue_summary", ""),
            entry_point=llm_pair.get("entry_point", ""),
            destination=llm_pair.get("destination", ""),
            steps=steps,
            tags=llm_pair.get("tags", []),
            confidence=llm_pair.get("confidence", 0.8),
        )

    def merge_paths(self, existing: BuiltPath, new: BuiltPath) -> BuiltPath:
        """Merge a new path into an existing similar one.

        Keeps the more detailed version of steps and increases confidence.
        """
        # Use whichever has more detailed steps
        if len(new.steps) > len(existing.steps):
            merged_steps = new.steps
        else:
            merged_steps = existing.steps

        # Merge tags
        merged_tags = list(set(existing.tags + new.tags))

        # Increase confidence (capped at 1.0)
        merged_confidence = min(1.0, existing.confidence + 0.05)

        # Use the longer/more detailed issue summary
        summary = new.issue_summary if len(new.issue_summary) > len(existing.issue_summary) else existing.issue_summary

        return BuiltPath(
            issue_summary=summary,
            entry_point=existing.entry_point or new.entry_point,
            destination=existing.destination or new.destination,
            steps=merged_steps,
            tags=merged_tags,
            confidence=merged_confidence,
        )
