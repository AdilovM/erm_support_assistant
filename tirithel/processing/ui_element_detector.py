"""Detect UI elements (buttons, menus, text fields) from OCR data."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from tirithel.integrations.ocr import OCRWord

logger = logging.getLogger(__name__)


@dataclass
class UIElement:
    """A detected UI element with its properties."""

    element_type: str  # button, menu_item, text_field, dropdown, tab, link, label
    label: str
    x: int
    y: int
    width: int
    height: int
    confidence: float
    children: list[UIElement] = field(default_factory=list)
    parent_label: str | None = None

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2

    def to_dict(self) -> dict:
        return {
            "element_type": self.element_type,
            "label": self.label,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "confidence": self.confidence,
            "parent_label": self.parent_label,
        }


class UIElementDetector:
    """Detects UI elements from OCR word data using heuristic analysis."""

    # Typical menu bar is in the top portion of screen
    MENU_BAR_Y_THRESHOLD_RATIO = 0.08
    # Words close together horizontally are likely the same element
    HORIZONTAL_MERGE_GAP = 15
    # Words close together vertically are likely in the same group
    VERTICAL_MERGE_GAP = 5
    # Common button keywords
    BUTTON_KEYWORDS = {
        "ok", "cancel", "save", "close", "apply", "submit", "delete",
        "add", "edit", "remove", "next", "back", "finish", "search",
        "browse", "open", "new", "print", "export", "import", "refresh",
        "yes", "no", "help", "update", "create", "select",
    }
    # Common menu keywords
    MENU_KEYWORDS = {
        "file", "edit", "view", "tools", "help", "window", "options",
        "settings", "administration", "reports", "setup", "system",
    }
    # Common tab indicators
    TAB_KEYWORDS = {
        "general", "details", "advanced", "settings", "options",
        "properties", "configuration", "summary", "history",
    }

    def detect(self, words: list[OCRWord], image_width: int, image_height: int) -> list[UIElement]:
        """Detect UI elements from OCR word data."""
        if not words:
            return []

        elements = []

        # Group words into text blocks (nearby words = same element)
        text_blocks = self._group_words_into_blocks(words)

        for block in text_blocks:
            element = self._classify_block(block, image_width, image_height)
            if element:
                elements.append(element)

        # Try to build hierarchy (menu items under menu bar, etc.)
        elements = self._build_hierarchy(elements, image_height)

        return elements

    def _group_words_into_blocks(self, words: list[OCRWord]) -> list[list[OCRWord]]:
        """Group nearby words into text blocks."""
        if not words:
            return []

        sorted_words = sorted(words, key=lambda w: (w.y, w.x))
        blocks: list[list[OCRWord]] = []
        current_block: list[OCRWord] = [sorted_words[0]]

        for word in sorted_words[1:]:
            prev = current_block[-1]

            # Check if this word is close enough to merge
            horizontal_gap = word.x - (prev.x + prev.width)
            vertical_gap = abs(word.y - prev.y)

            if vertical_gap <= self.VERTICAL_MERGE_GAP and horizontal_gap <= self.HORIZONTAL_MERGE_GAP:
                current_block.append(word)
            else:
                blocks.append(current_block)
                current_block = [word]

        blocks.append(current_block)
        return blocks

    def _classify_block(
        self, block: list[OCRWord], image_width: int, image_height: int
    ) -> UIElement | None:
        """Classify a text block as a UI element type."""
        label = " ".join(w.text for w in block)
        if not label.strip():
            return None

        # Bounding box of the block
        x = min(w.x for w in block)
        y = min(w.y for w in block)
        max_x = max(w.x + w.width for w in block)
        max_y = max(w.y + w.height for w in block)
        width = max_x - x
        height = max_y - y
        avg_confidence = sum(w.confidence for w in block) / len(block)

        label_lower = label.lower().strip()

        # Classify based on position and content
        menu_bar_threshold = image_height * self.MENU_BAR_Y_THRESHOLD_RATIO

        if y < menu_bar_threshold and label_lower in self.MENU_KEYWORDS:
            element_type = "menu_item"
        elif label_lower in self.BUTTON_KEYWORDS:
            element_type = "button"
        elif label_lower in self.TAB_KEYWORDS:
            element_type = "tab"
        elif label.endswith(":") or label.endswith("*"):
            element_type = "label"
        elif width > image_width * 0.3 and height < 30:
            # Wide, short block likely a text field area
            element_type = "text_field"
        else:
            element_type = "label"

        return UIElement(
            element_type=element_type,
            label=label.strip(),
            x=x,
            y=y,
            width=width,
            height=height,
            confidence=avg_confidence,
        )

    def _build_hierarchy(self, elements: list[UIElement], image_height: int) -> list[UIElement]:
        """Build parent-child relationships between elements."""
        menu_bar_threshold = image_height * self.MENU_BAR_Y_THRESHOLD_RATIO
        menu_items = [e for e in elements if e.element_type == "menu_item" and e.y < menu_bar_threshold]

        # For elements below the menu bar, try to assign a parent menu
        for element in elements:
            if element.element_type == "menu_item" and element.y < menu_bar_threshold:
                continue
            # Find the closest menu item above this element horizontally
            for menu in menu_items:
                if abs(element.x - menu.x) < 100 and element.y > menu.y:
                    element.parent_label = menu.label
                    break

        return elements
