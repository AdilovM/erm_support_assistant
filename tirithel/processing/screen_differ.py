"""Detect differences between consecutive screenshots to infer UI actions."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class ScreenRegion:
    """A rectangular region of the screen that changed."""

    x: int
    y: int
    width: int
    height: int
    change_intensity: float  # 0.0 to 1.0 - how much the region changed


@dataclass
class ScreenDiff:
    """Result of comparing two screenshots."""

    is_significant: bool  # True if screens differ meaningfully
    overall_change_ratio: float  # 0.0 to 1.0
    changed_regions: list[ScreenRegion]
    new_elements_appeared: bool  # e.g., a dropdown or dialog
    perceptual_hash_before: str
    perceptual_hash_after: str


class ScreenDiffer:
    """Compares consecutive screenshots to detect UI state changes."""

    # Threshold below which we consider frames identical
    CHANGE_THRESHOLD = 0.02
    # Minimum region size to consider
    MIN_REGION_SIZE = 20
    # Grid size for region analysis
    GRID_SIZE = 50

    def compute_perceptual_hash(self, image: Image.Image, hash_size: int = 16) -> str:
        """Compute a perceptual hash (pHash) for an image.

        Resize to small square, convert to grayscale, compute DCT-like hash.
        """
        small = image.resize((hash_size, hash_size), Image.Resampling.LANCZOS).convert("L")
        pixels = np.array(small, dtype=np.float64)
        avg = pixels.mean()
        bits = (pixels > avg).flatten()
        hash_hex = "".join("1" if b else "0" for b in bits)
        # Convert binary string to hex
        return hex(int(hash_hex, 2))[2:].zfill(hash_size * hash_size // 4)

    def diff(self, before: Image.Image, after: Image.Image) -> ScreenDiff:
        """Compare two screenshots and return the differences."""
        hash_before = self.compute_perceptual_hash(before)
        hash_after = self.compute_perceptual_hash(after)

        # Resize to same dimensions for comparison
        target_size = (
            min(before.width, after.width),
            min(before.height, after.height),
        )
        img_before = before.resize(target_size).convert("RGB")
        img_after = after.resize(target_size).convert("RGB")

        arr_before = np.array(img_before, dtype=np.float64)
        arr_after = np.array(img_after, dtype=np.float64)

        # Compute pixel-level difference
        pixel_diff = np.abs(arr_before - arr_after)
        # Normalize per pixel (max diff is 255*3 across RGB)
        pixel_change = pixel_diff.sum(axis=2) / (255.0 * 3)

        overall_change = float(pixel_change.mean())
        is_significant = overall_change > self.CHANGE_THRESHOLD

        # Find changed regions using grid analysis
        changed_regions = self._find_changed_regions(pixel_change, target_size)

        # Detect if new UI elements appeared (large concentrated change)
        new_elements = any(
            r.change_intensity > 0.5 and r.width > 100 and r.height > 50
            for r in changed_regions
        )

        return ScreenDiff(
            is_significant=is_significant,
            overall_change_ratio=overall_change,
            changed_regions=changed_regions,
            new_elements_appeared=new_elements,
            perceptual_hash_before=hash_before,
            perceptual_hash_after=hash_after,
        )

    def _find_changed_regions(
        self, pixel_change: np.ndarray, image_size: tuple[int, int]
    ) -> list[ScreenRegion]:
        """Identify rectangular regions that changed significantly."""
        regions = []
        height, width = pixel_change.shape

        for y in range(0, height, self.GRID_SIZE):
            for x in range(0, width, self.GRID_SIZE):
                region = pixel_change[
                    y : min(y + self.GRID_SIZE, height),
                    x : min(x + self.GRID_SIZE, width),
                ]
                intensity = float(region.mean())

                if intensity > self.CHANGE_THRESHOLD:
                    rw = min(self.GRID_SIZE, width - x)
                    rh = min(self.GRID_SIZE, height - y)
                    if rw >= self.MIN_REGION_SIZE and rh >= self.MIN_REGION_SIZE:
                        regions.append(
                            ScreenRegion(
                                x=x, y=y, width=rw, height=rh, change_intensity=intensity
                            )
                        )

        # Merge adjacent regions
        return self._merge_adjacent_regions(regions)

    def _merge_adjacent_regions(self, regions: list[ScreenRegion]) -> list[ScreenRegion]:
        """Merge overlapping or adjacent changed regions."""
        if len(regions) <= 1:
            return regions

        merged = []
        used = set()

        for i, r1 in enumerate(regions):
            if i in used:
                continue

            x_min, y_min = r1.x, r1.y
            x_max = r1.x + r1.width
            y_max = r1.y + r1.height
            total_intensity = r1.change_intensity
            count = 1

            for j, r2 in enumerate(regions[i + 1 :], i + 1):
                if j in used:
                    continue
                # Check if adjacent (within one grid cell)
                if (
                    abs(r1.x - r2.x) <= self.GRID_SIZE
                    and abs(r1.y - r2.y) <= self.GRID_SIZE
                ):
                    x_min = min(x_min, r2.x)
                    y_min = min(y_min, r2.y)
                    x_max = max(x_max, r2.x + r2.width)
                    y_max = max(y_max, r2.y + r2.height)
                    total_intensity += r2.change_intensity
                    count += 1
                    used.add(j)

            used.add(i)
            merged.append(
                ScreenRegion(
                    x=x_min,
                    y=y_min,
                    width=x_max - x_min,
                    height=y_max - y_min,
                    change_intensity=total_intensity / count,
                )
            )

        return merged
