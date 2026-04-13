"""Enumerations for Tirithel domain models."""

import enum


class SessionStatus(str, enum.Enum):
    RECORDING = "recording"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SegmentType(str, enum.Enum):
    ISSUE_DESCRIPTION = "issue_description"
    ACTION_INSTRUCTION = "action_instruction"
    CLARIFICATION = "clarification"
    CONFIRMATION = "confirmation"
    OTHER = "other"


class Speaker(str, enum.Enum):
    SUPPORT_AGENT = "support_agent"
    USER = "user"
    SYSTEM = "system"


class ActionType(str, enum.Enum):
    CLICK = "click"
    TYPE = "type"
    NAVIGATE = "navigate"
    SELECT = "select"
    SCROLL = "scroll"
    MENU_OPEN = "menu_open"
    DIALOG_OPEN = "dialog_open"


class UIElementType(str, enum.Enum):
    BUTTON = "button"
    MENU_ITEM = "menu_item"
    TEXT_FIELD = "text_field"
    DROPDOWN = "dropdown"
    TAB = "tab"
    LINK = "link"
    CHECKBOX = "checkbox"
    LABEL = "label"


class CorrelationType(str, enum.Enum):
    DIRECT = "direct"
    INFERRED = "inferred"
    TEMPORAL = "temporal"
