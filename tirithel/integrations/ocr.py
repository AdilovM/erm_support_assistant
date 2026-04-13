"""OCR integration using Tesseract for extracting text from screenshots."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class OCRWord:
    """A single word detected by OCR with position and confidence."""

    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float
    block_num: int = 0
    line_num: int = 0


@dataclass
class OCRResult:
    """Full OCR result for an image."""

    full_text: str
    words: list[OCRWord]
    image_width: int
    image_height: int


class TesseractOCR:
    """Wrapper around pytesseract for OCR operations."""

    def __init__(self, language: str = "eng", confidence_threshold: float = 0.6):
        self.language = language
        self.confidence_threshold = confidence_threshold

    def extract(self, image: Image.Image) -> OCRResult:
        """Extract text and word positions from an image."""
        import pytesseract

        data = pytesseract.image_to_data(
            image,
            lang=self.language,
            output_type=pytesseract.Output.DICT,
        )

        words = []
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            conf = float(data["conf"][i])

            if not text or conf < 0:
                continue

            confidence = conf / 100.0
            if confidence < self.confidence_threshold:
                continue

            words.append(
                OCRWord(
                    text=text,
                    x=data["left"][i],
                    y=data["top"][i],
                    width=data["width"][i],
                    height=data["height"][i],
                    confidence=confidence,
                    block_num=data["block_num"][i],
                    line_num=data["line_num"][i],
                )
            )

        full_text = pytesseract.image_to_string(image, lang=self.language).strip()

        return OCRResult(
            full_text=full_text,
            words=words,
            image_width=image.width,
            image_height=image.height,
        )

    def extract_from_path(self, image_path: str) -> OCRResult:
        """Extract text from an image file path."""
        image = Image.open(image_path)
        return self.extract(image)
