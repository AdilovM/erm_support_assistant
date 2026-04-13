"""Screen capture service - processes uploaded screenshots with OCR and UI detection."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tirithel.config.settings import get_settings
from tirithel.domain.models import Screenshot, SupportSession, UIAction
from tirithel.integrations.ocr import TesseractOCR
from tirithel.processing.screen_differ import ScreenDiffer
from tirithel.processing.ui_element_detector import UIElementDetector

logger = logging.getLogger(__name__)


class ScreenCaptureService:
    """Processes screenshots: OCR, UI element detection, screen diffing, action inference."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.ocr = TesseractOCR(
            language=self.settings.ocr.language,
            confidence_threshold=self.settings.ocr.confidence_threshold,
        )
        self.ui_detector = UIElementDetector()
        self.screen_differ = ScreenDiffer()

    async def process_screenshot(
        self,
        session_id: str,
        image_data: bytes,
        timestamp: datetime | None = None,
    ) -> Screenshot:
        """Process an uploaded screenshot: save, OCR, detect UI elements."""
        # Determine sequence number
        result = await self.db.execute(
            select(Screenshot)
            .where(Screenshot.session_id == session_id)
            .order_by(Screenshot.sequence_number.desc())
            .limit(1)
        )
        last_screenshot = result.scalar_one_or_none()
        seq_number = (last_screenshot.sequence_number + 1) if last_screenshot else 1

        # Save image to disk
        screenshot_dir = os.path.join(self.settings.storage.screenshot_dir, session_id)
        os.makedirs(screenshot_dir, exist_ok=True)

        filename = f"{seq_number:04d}_{uuid.uuid4().hex[:8]}.png"
        image_path = os.path.join(screenshot_dir, filename)

        with open(image_path, "wb") as f:
            f.write(image_data)

        # Open image for processing
        image = Image.open(image_path)

        # Run OCR
        try:
            ocr_result = self.ocr.extract(image)
            ocr_text = ocr_result.full_text
            ocr_data = [
                {
                    "text": w.text,
                    "x": w.x,
                    "y": w.y,
                    "w": w.width,
                    "h": w.height,
                    "confidence": w.confidence,
                }
                for w in ocr_result.words
            ]
        except Exception as e:
            logger.warning("OCR failed for screenshot %s: %s", filename, e)
            ocr_text = ""
            ocr_data = []
            ocr_result = None

        # Detect UI elements
        ui_elements = []
        if ocr_result and ocr_result.words:
            detected = self.ui_detector.detect(
                ocr_result.words, ocr_result.image_width, ocr_result.image_height
            )
            ui_elements = [e.to_dict() for e in detected]

        # Compute perceptual hash
        screen_hash = self.screen_differ.compute_perceptual_hash(image)

        # Create screenshot record
        screenshot = Screenshot(
            session_id=session_id,
            sequence_number=seq_number,
            timestamp=timestamp or datetime.utcnow(),
            image_path=image_path,
            ocr_text=ocr_text,
            ocr_data_json=json.dumps(ocr_data),
            ui_elements_json=json.dumps(ui_elements),
            screen_hash=screen_hash,
        )
        self.db.add(screenshot)
        await self.db.flush()

        # Detect actions by diffing with previous screenshot
        if last_screenshot and last_screenshot.image_path:
            await self._detect_actions(session_id, last_screenshot, screenshot, image)

        return screenshot

    async def _detect_actions(
        self,
        session_id: str,
        prev_screenshot: Screenshot,
        curr_screenshot: Screenshot,
        curr_image: Image.Image,
    ) -> list[UIAction]:
        """Detect UI actions by comparing consecutive screenshots."""
        actions = []

        try:
            prev_image = Image.open(prev_screenshot.image_path)
            diff = self.screen_differ.diff(prev_image, curr_image)
        except Exception as e:
            logger.warning("Screen diff failed: %s", e)
            return actions

        if not diff.is_significant:
            return actions

        # Get current sequence for actions
        result = await self.db.execute(
            select(UIAction)
            .where(UIAction.session_id == session_id)
            .order_by(UIAction.sequence_number.desc())
            .limit(1)
        )
        last_action = result.scalar_one_or_none()
        action_seq = (last_action.sequence_number + 1) if last_action else 1

        # Parse current UI elements
        curr_elements = json.loads(curr_screenshot.ui_elements_json or "[]")
        prev_elements = json.loads(prev_screenshot.ui_elements_json or "[]")

        # Infer action type from diff
        if diff.new_elements_appeared:
            # A new dialog or dropdown appeared
            action_type = "dialog_open"
            # Find new elements that weren't in previous
            prev_labels = {e.get("label", "") for e in prev_elements}
            new_elements = [e for e in curr_elements if e.get("label", "") not in prev_labels]
            label = new_elements[0]["label"] if new_elements else "Unknown dialog"
        else:
            # Likely a click or navigation
            action_type = "click"
            # Use the changed region to find which element was clicked
            label = self._find_clicked_element(diff.changed_regions, curr_elements)

        action = UIAction(
            session_id=session_id,
            screenshot_id=curr_screenshot.id,
            sequence_number=action_seq,
            action_type=action_type,
            element_label=label,
            timestamp=curr_screenshot.timestamp,
            confidence=0.7,
        )
        self.db.add(action)
        actions.append(action)

        return actions

    def _find_clicked_element(
        self, changed_regions: list, ui_elements: list[dict]
    ) -> str:
        """Find which UI element was likely clicked based on changed regions."""
        if not changed_regions or not ui_elements:
            return "Unknown"

        # Find the element closest to the center of the most changed region
        region = max(changed_regions, key=lambda r: r.change_intensity)
        region_cx = region.x + region.width // 2
        region_cy = region.y + region.height // 2

        best_element = None
        best_distance = float("inf")

        for elem in ui_elements:
            ecx = elem["x"] + elem["width"] // 2
            ecy = elem["y"] + elem["height"] // 2
            dist = ((ecx - region_cx) ** 2 + (ecy - region_cy) ** 2) ** 0.5

            if dist < best_distance:
                best_distance = dist
                best_element = elem

        return best_element["label"] if best_element else "Unknown"
