"""Tests for the screen differ."""

import numpy as np
from PIL import Image

from tirithel.processing.screen_differ import ScreenDiffer


class TestScreenDiffer:
    def setup_method(self):
        self.differ = ScreenDiffer()

    def _make_image(self, color: tuple[int, int, int], size: tuple[int, int] = (200, 200)) -> Image.Image:
        """Create a solid color test image."""
        arr = np.full((*size, 3), color, dtype=np.uint8)
        return Image.fromarray(arr, "RGB")

    def test_identical_images(self):
        img = self._make_image((128, 128, 128))
        diff = self.differ.diff(img, img)

        assert not diff.is_significant
        assert diff.overall_change_ratio < 0.01

    def test_different_images(self):
        img1 = self._make_image((0, 0, 0))
        img2 = self._make_image((255, 255, 255))
        diff = self.differ.diff(img1, img2)

        assert diff.is_significant
        assert diff.overall_change_ratio > 0.9

    def test_partial_change(self):
        # Create two images where only a portion differs
        arr1 = np.zeros((200, 200, 3), dtype=np.uint8)
        arr2 = np.zeros((200, 200, 3), dtype=np.uint8)
        arr2[50:100, 50:100] = 255  # White square in the middle

        img1 = Image.fromarray(arr1, "RGB")
        img2 = Image.fromarray(arr2, "RGB")

        diff = self.differ.diff(img1, img2)

        assert diff.is_significant
        assert 0.01 < diff.overall_change_ratio < 0.5
        assert len(diff.changed_regions) > 0

    def test_perceptual_hash(self):
        img = self._make_image((100, 100, 100))
        hash1 = self.differ.compute_perceptual_hash(img)

        assert isinstance(hash1, str)
        assert len(hash1) > 0

    def test_perceptual_hash_similar_images(self):
        img1 = self._make_image((100, 100, 100))
        img2 = self._make_image((102, 100, 100))  # Very slightly different

        hash1 = self.differ.compute_perceptual_hash(img1)
        hash2 = self.differ.compute_perceptual_hash(img2)

        # Similar images should produce same hash
        assert hash1 == hash2

    def test_new_elements_detected(self):
        # Base image is dark
        arr1 = np.zeros((400, 400, 3), dtype=np.uint8)
        arr2 = np.zeros((400, 400, 3), dtype=np.uint8)
        # Add a large bright rectangle (simulating a dialog popup)
        arr2[100:300, 100:300] = 200

        img1 = Image.fromarray(arr1, "RGB")
        img2 = Image.fromarray(arr2, "RGB")

        diff = self.differ.diff(img1, img2)

        assert diff.is_significant
        assert diff.new_elements_appeared
