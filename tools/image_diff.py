"""Make one pixel-difference PNG from reference art and an actual rendered frame.

No alignment or color correction. Pixel metrics are diagnostics, not art acceptance.

Requires Pillow and NumPy. SSIM uses a 7x7 uniform window, sample covariance,
and standard K1=.01, K2=.03 on RGB values in [0, 1].
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def load_rgb(path):
    with Image.open(path) as source:
        rgba = ImageOps.exif_transpose(source).convert("RGBA")
        background = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        return Image.alpha_composite(background, rgba).convert("RGB")


def prepare(reference, candidate, width=960, fit="strict"):
    if width < 16:
        raise ValueError("analysis width must be at least 16 pixels")
    aspect_error = abs((candidate.width / candidate.height) / (reference.width / reference.height) - 1)
    if aspect_error > 0.005 and fit == "strict":
        raise ValueError("Aspect ratios differ by more than 0.5%; capture the same viewport, or explicitly use --fit contain. No stretching/cropping is automatic.")
    size = (width, max(7, round(width * reference.height / reference.width)))
    ref = reference.resize(size, Image.Resampling.LANCZOS)
    if aspect_error > 0.005:
        candidate = ImageOps.pad(candidate, size, method=Image.Resampling.LANCZOS, color=(0, 0, 0))
    else:
        candidate = candidate.resize(size, Image.Resampling.LANCZOS)
    return ref, candidate, aspect_error


def window_mean(array, size=7):
    integral = np.pad(array, ((1, 0), (1, 0), (0, 0))).cumsum(0).cumsum(1)
    return (integral[size:, size:] - integral[:-size, size:] - integral[size:, :-size] + integral[:-size, :-size]) / (size * size)


def ssim_rgb(first, second):
    """Return mean RGB SSIM and its spatial map (three-pixel border excluded)."""
    if min(first.shape[:2]) < 7:
        raise ValueError("SSIM needs a region of at least 7x7 pixels")
    first, second = first.astype(np.float64), second.astype(np.float64)
    mu_a, mu_b = window_mean(first), window_mean(second)
    correction = 49 / 48
    var_a = np.maximum(0, correction * (window_mean(first * first) - mu_a * mu_a))
    var_b = np.maximum(0, correction * (window_mean(second * second) - mu_b * mu_b))
    cov = correction * (window_mean(first * second) - mu_a * mu_b)
    score = ((2 * mu_a * mu_b + 0.01 ** 2) * (2 * cov + 0.03 ** 2)) / ((mu_a * mu_a + mu_b * mu_b + 0.01 ** 2) * (var_a + var_b + 0.03 ** 2))
    spatial = score.mean(axis=2)
    return float(spatial.mean()), spatial


def metrics(first, second, pixel_threshold=10):
    a = np.asarray(first, dtype=np.float64) / 255
    b = np.asarray(second, dtype=np.float64) / 255
    error = np.abs(a - b).mean(axis=2)
    ssim, _ = ssim_rgb(a, b)
    return {
        "rgb_mae_percent": float(error.mean() * 100),
        "ssim_rgb": ssim,
        "changed_pixels_percent": float((error > pixel_threshold / 255).mean() * 100),
    }, error


DIFF_GAMMA = .5
LEGACY_FILES = ("reference.png", "candidate.png", "heatmap.png", "highlighted.png", "comparison.png", "index.html")


def difference_image(first, second):
    """One grayscale error image: equal=black, greater channel error=brighter.

    Use the largest absolute RGB channel difference so color errors cannot cancel.
    A fixed square-root curve exposes small differences without clipping large
    ones or normalizing each run differently. Only maximal error reaches white.
    """
    delta = np.abs(np.asarray(first, dtype=np.int16) - np.asarray(second, dtype=np.int16))
    error = delta.max(axis=2) / 255.0
    return Image.fromarray(np.rint(255 * error ** DIFF_GAMMA).astype(np.uint8))


def compare(reference_path, candidate_path, output, *, width=960, fit="strict", pixel_threshold=10, regions=None, max_mae=None):
    output = Path(output)
    generated_names = (*LEGACY_FILES, "diff.png", "metrics.json")
    if any(Path(source).resolve() == (output / name).resolve() for source in (reference_path, candidate_path) for name in generated_names):
        raise ValueError("Output would overwrite an input image; choose a different output directory")
    if not 0 <= pixel_threshold <= 255:
        raise ValueError("pixel threshold must be between 0 and 255")
    if max_mae is not None and not 0 <= max_mae <= 100:
        raise ValueError("MAE limit must be between 0 and 100 percent")
    original_ref, original_candidate = load_rgb(reference_path), load_rgb(candidate_path)
    ref, candidate, aspect_error = prepare(original_ref, original_candidate, width, fit)
    scores, _ = metrics(ref, candidate, pixel_threshold)
    # Coarse diagnostic only: exposes palette/layout progress without treating it as fidelity.
    sigma = width / 120
    coarse, _ = metrics(ref.filter(ImageFilter.GaussianBlur(sigma)), candidate.filter(ImageFilter.GaussianBlur(sigma)), pixel_threshold)
    scores["blurred_rgb_mae_percent"] = coarse["rgb_mae_percent"]
    regions = regions or {}
    regional = {}
    for name, box in regions.items():
        if len(box) != 4 or not all(0 <= v <= 1 for v in box) or box[2] <= 0 or box[3] <= 0 or box[0] + box[2] > 1.000001 or box[1] + box[3] > 1.000001:
            raise ValueError(f"Invalid normalized x,y,width,height region: {name}")
        x, y, w, h = box
        bounds = (round(x * ref.width), round(y * ref.height), round((x + w) * ref.width), round((y + h) * ref.height))
        regional[name], _ = metrics(ref.crop(bounds), candidate.crop(bounds), pixel_threshold)

    report = {
        "metric_version": 1,
        "reference": {"path": str(Path(reference_path).resolve()), "sha256": hashlib.sha256(Path(reference_path).read_bytes()).hexdigest(), "size": list(original_ref.size)},
        "candidate": {"path": str(Path(candidate_path).resolve()), "sha256": hashlib.sha256(Path(candidate_path).read_bytes()).hexdigest(), "size": list(original_candidate.size)},
        "settings": {"analysis_size": list(ref.size), "fit": fit, "aspect_ratio_error_percent": aspect_error * 100, "pixel_threshold_rgb_levels": pixel_threshold, "blur_sigma_pixels": sigma, "ssim": "RGB mean, 7x7 uniform window, sample covariance, K1=.01 K2=.03, border excluded", "alpha": "composite on black", "color": "encoded RGB; no exposure, alignment, warp, or color matching"},
        "visualization": {"version": 3, "image": "diff.png", "difference": "maximum absolute RGB channel difference", "display_curve": "255 * sqrt(max(abs(reference RGB - capture RGB)) / 255)", "scale": "fixed across runs; equal=black, larger error=brighter, maximum error=white; no clipping or per-image normalization"},
        "metrics": scores, "regions": regional,
        "mae_gate": None if max_mae is None else {"limit_percent": max_mae, "passed": scores["rgb_mae_percent"] <= max_mae},
        "warnings": ["Aspect ratios differ: candidate was letterboxed, not cropped or stretched."] if aspect_error > 0.005 else [],
    }
    output.mkdir(parents=True, exist_ok=True)
    difference_image(ref, candidate).save(output / "diff.png")
    (output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    # This tool reserves these legacy output names. Remove obsolete reports so
    # the directory presents one current review image, not stale visualizations.
    for name in LEGACY_FILES:
        (output / name).unlink(missing_ok=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/image-diff")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--fit", choices=("strict", "contain"), default="strict")
    parser.add_argument("--pixel-threshold", type=float, default=10)
    parser.add_argument("--regions", type=Path, help="JSON mapping names to normalized [x,y,width,height]")
    parser.add_argument("--max-mae-percent", type=float, help="Optional MAE-only gate; exits 1 if exceeded")
    args = parser.parse_args()
    try:
        report = compare(args.reference, args.candidate, args.output, width=args.width, fit=args.fit, pixel_threshold=args.pixel_threshold, regions=json.loads(args.regions.read_text()) if args.regions else None, max_mae=args.max_mae_percent)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Cannot compare images: {exc}\n")
    print(json.dumps({"metrics": report["metrics"], "warnings": report["warnings"], "mae_gate": report["mae_gate"], "diff": str((args.output / 'diff.png').resolve())}, indent=2))
    return 1 if report["mae_gate"] and not report["mae_gate"]["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
