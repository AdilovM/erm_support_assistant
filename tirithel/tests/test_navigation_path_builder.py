"""Tests for the navigation path builder."""

from tirithel.processing.navigation_path_builder import BuiltPath, NavigationPathBuilder, PathStep


class TestNavigationPathBuilder:
    def setup_method(self):
        self.builder = NavigationPathBuilder()

    def test_build_from_ui_actions(self):
        actions = [
            {"action_type": "click", "element_label": "Administration", "element_path": "Main Menu"},
            {"action_type": "click", "element_label": "System Setup", "element_path": "Administration"},
            {"action_type": "click", "element_label": "Financial", "element_path": "System Setup"},
            {"action_type": "click", "element_label": "Fee Schedules", "element_path": "Financial"},
        ]

        path = self.builder.build_from_ui_actions(
            actions, "Change fee schedule", tags=["fee", "administration"]
        )

        assert path.issue_summary == "Change fee schedule"
        assert len(path.steps) == 4
        assert path.steps[0].element_label == "Administration"
        assert path.steps[3].element_label == "Fee Schedules"
        assert path.entry_point == "Main Menu"
        assert path.destination == "Financial"
        assert "fee" in path.tags

    def test_build_from_llm_response(self):
        llm_pair = {
            "issue_summary": "Update recording fee",
            "entry_point": "Main Menu",
            "destination": "Fee Schedules",
            "steps": [
                {"step_number": 1, "action": "click", "element_label": "Admin", "element_path": "Menu", "description": "Open admin"},
                {"step_number": 2, "action": "click", "element_label": "Fees", "element_path": "Admin", "description": "Open fees"},
            ],
            "tags": ["fee", "recording"],
            "confidence": 0.9,
        }

        path = self.builder.build_from_llm_response(llm_pair)

        assert path.issue_summary == "Update recording fee"
        assert len(path.steps) == 2
        assert path.confidence == 0.9
        assert "recording" in path.tags

    def test_merge_paths(self):
        existing = BuiltPath(
            issue_summary="Change fee",
            entry_point="Main",
            destination="Fees",
            steps=[PathStep(1, "click", "Admin", "Menu", "Go to admin")],
            tags=["fee"],
            confidence=0.8,
        )
        new = BuiltPath(
            issue_summary="Change fee schedule for recording",
            entry_point="Main Menu",
            destination="Fee Schedules",
            steps=[
                PathStep(1, "click", "Admin", "Menu", "Go to admin"),
                PathStep(2, "click", "Fees", "Admin", "Open fees"),
            ],
            tags=["recording"],
            confidence=0.85,
        )

        merged = self.builder.merge_paths(existing, new)

        # Should use the more detailed (longer) version
        assert len(merged.steps) == 2
        # Tags should be merged
        assert "fee" in merged.tags
        assert "recording" in merged.tags
        # Confidence should increase
        assert abs(merged.confidence - 0.85) < 1e-9  # 0.8 + 0.05
        # Use longer summary
        assert "recording" in merged.issue_summary

    def test_steps_to_json(self):
        path = BuiltPath(
            issue_summary="Test",
            entry_point="A",
            destination="B",
            steps=[PathStep(1, "click", "Button", "Menu", "Click button")],
            tags=["test"],
            confidence=0.8,
        )

        json_str = path.steps_to_json()
        assert '"step_number": 1' in json_str
        assert '"element_label": "Button"' in json_str

    def test_to_human_readable(self):
        path = BuiltPath(
            issue_summary="Change fee",
            entry_point="Main",
            destination="Fees",
            steps=[
                PathStep(1, "click", "Administration", "Main Menu", ""),
                PathStep(2, "navigate", "Fee Schedules", "Admin > Financial", ""),
                PathStep(3, "type", "Amount", "Fee dialog", ""),
            ],
            tags=[],
            confidence=0.9,
        )

        readable = path.to_human_readable()
        assert "Click on 'Administration'" in readable
        assert "Navigate to Fee Schedules" in readable
        assert "Type in the 'Amount' field" in readable
