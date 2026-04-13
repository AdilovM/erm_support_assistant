"""Tests for the UI element detector."""

from tirithel.integrations.ocr import OCRWord
from tirithel.processing.ui_element_detector import UIElementDetector


class TestUIElementDetector:
    def setup_method(self):
        self.detector = UIElementDetector()

    def test_detect_button(self):
        words = [
            OCRWord(text="Save", x=100, y=500, width=50, height=20, confidence=0.95),
        ]
        elements = self.detector.detect(words, 1920, 1080)

        assert len(elements) >= 1
        save_elem = [e for e in elements if e.label == "Save"]
        assert len(save_elem) == 1
        assert save_elem[0].element_type == "button"

    def test_detect_menu_item(self):
        words = [
            OCRWord(text="File", x=10, y=5, width=30, height=15, confidence=0.9),
            OCRWord(text="Edit", x=60, y=5, width=30, height=15, confidence=0.9),
            OCRWord(text="View", x=110, y=5, width=30, height=15, confidence=0.9),
        ]
        elements = self.detector.detect(words, 1920, 1080)

        menu_items = [e for e in elements if e.element_type == "menu_item"]
        assert len(menu_items) >= 2

    def test_detect_label_with_colon(self):
        words = [
            OCRWord(text="Name:", x=50, y=200, width=60, height=18, confidence=0.85),
        ]
        elements = self.detector.detect(words, 1920, 1080)

        assert len(elements) >= 1
        label = [e for e in elements if e.label == "Name:"]
        assert len(label) == 1
        assert label[0].element_type == "label"

    def test_empty_words(self):
        elements = self.detector.detect([], 1920, 1080)
        assert elements == []

    def test_grouped_words(self):
        # Words close together should be grouped
        words = [
            OCRWord(text="Fee", x=100, y=200, width=30, height=18, confidence=0.9),
            OCRWord(text="Schedule:", x=135, y=200, width=80, height=18, confidence=0.9),
        ]
        elements = self.detector.detect(words, 1920, 1080)

        assert any("Fee Schedule:" in e.label for e in elements)

    def test_confidence_in_output(self):
        words = [
            OCRWord(text="OK", x=400, y=600, width=30, height=20, confidence=0.92),
        ]
        elements = self.detector.detect(words, 1920, 1080)

        assert len(elements) >= 1
        assert elements[0].confidence > 0
