"""Known-value checks for the measurement tool and its saved report."""

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from tools.image_diff import compare, metrics, prepare, ssim_rgb


class ImageDiffTests(unittest.TestCase):
    def test_identical_texture_has_zero_error_and_unit_ssim(self):
        pixels = np.random.default_rng(42).integers(0, 256, (32, 40, 3), dtype=np.uint8)
        image = Image.fromarray(pixels)
        scores, _ = metrics(image, image)
        self.assertEqual(scores["rgb_mae_percent"], 0)
        self.assertAlmostEqual(scores["ssim_rgb"], 1, places=10)
        self.assertEqual(scores["changed_pixels_percent"], 0)

    def test_black_white_has_max_color_error_and_known_ssim(self):
        scores, _ = metrics(Image.new("RGB", (20, 20), "black"), Image.new("RGB", (20, 20), "white"))
        self.assertEqual(scores["rgb_mae_percent"], 100)
        self.assertEqual(scores["changed_pixels_percent"], 100)
        # Constant images have zero variance; only the luminance term remains.
        self.assertAlmostEqual(scores["ssim_rgb"], 0.0001 / 1.0001, places=10)

    def test_one_white_pixel_counts_once(self):
        a = Image.new("RGB", (20, 20), "black")
        b = a.copy()
        b.putpixel((10, 10), (255, 255, 255))
        scores, _ = metrics(a, b)
        self.assertAlmostEqual(scores["rgb_mae_percent"], 100 / 400)
        self.assertAlmostEqual(scores["changed_pixels_percent"], 100 / 400)

    def test_inverted_checkerboard_has_negative_structural_similarity(self):
        checker = (np.indices((32, 32)).sum(axis=0) % 2).astype(float)
        a = np.repeat(checker[:, :, None], 3, axis=2)
        score, _ = ssim_rgb(a, 1 - a)
        self.assertLess(score, -0.9)

    def test_aspect_mismatch_requires_explicit_letterboxing(self):
        a, b = Image.new("RGB", (160, 90), "white"), Image.new("RGB", (100, 100), "white")
        with self.assertRaisesRegex(ValueError, "Aspect ratios"):
            prepare(a, b, width=160)
        _, boxed, _ = prepare(a, b, width=160, fit="contain")
        self.assertEqual(boxed.size, (160, 90))
        self.assertEqual(boxed.getpixel((0, 45)), (0, 0, 0))
        self.assertEqual(boxed.getpixel((80, 45)), (255, 255, 255))

    def test_regional_score_exposes_small_missing_subject_and_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = Image.new("RGB", (100, 100), "black")
            b = a.copy()
            b.paste("white", (40, 40, 60, 60))
            a.save(root / "a.png")
            b.save(root / "b.png")
            report = compare(root / "a.png", root / "b.png", root / "out", width=100, regions={"subject": [0.4, 0.4, 0.2, 0.2]}, max_mae=10)
            self.assertAlmostEqual(report["metrics"]["rgb_mae_percent"], 4)
            self.assertAlmostEqual(report["regions"]["subject"]["rgb_mae_percent"], 100)
            self.assertTrue(report["mae_gate"]["passed"])
            self.assertEqual(json.loads((root / "out/metrics.json").read_text())["metric_version"], 1)
            for name in ("index.html", "comparison.png", "heatmap.png", "highlighted.png"):
                self.assertTrue((root / "out" / name).is_file())

    def test_report_cannot_overwrite_source_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "reference.png"
            Image.new("RGB", (20, 20), "white").save(source)
            original = source.read_bytes()
            with self.assertRaisesRegex(ValueError, "overwrite"):
                compare(source, source, root)
            self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
