"""Compare reference art with an actual rendered frame; no alignment or color correction.

Requires Pillow and NumPy. SSIM uses a 7x7 uniform window, sample covariance,
and standard K1=.01, K2=.03 on RGB values in [0, 1].
"""

import argparse
import hashlib
import html
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

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


def heatmap(error):
    # Fixed scale between comparisons: never renormalize each image to its maximum.
    stops = np.array([0, 0.05, 0.10, 0.25, 0.50, 1.0])
    colors = np.array([[5, 12, 30], [15, 65, 130], [0, 190, 210], [255, 218, 50], [255, 65, 35], [255, 245, 245]])
    mapped = np.stack([np.interp(error, stops, colors[:, c]) for c in range(3)], axis=2)
    return Image.fromarray(np.uint8(mapped))


def compare(reference_path, candidate_path, output, *, width=960, fit="strict", pixel_threshold=10, regions=None, max_mae=None):
    output = Path(output)
    generated_names = ("reference.png", "candidate.png", "heatmap.png", "highlighted.png", "comparison.png", "metrics.json", "index.html")
    if any(Path(source).resolve() == (output / name).resolve() for source in (reference_path, candidate_path) for name in generated_names):
        raise ValueError("Output would overwrite an input image; choose a different output directory")
    if not 0 <= pixel_threshold <= 255:
        raise ValueError("pixel threshold must be between 0 and 255")
    if max_mae is not None and not 0 <= max_mae <= 100:
        raise ValueError("MAE limit must be between 0 and 100 percent")
    original_ref, original_candidate = load_rgb(reference_path), load_rgb(candidate_path)
    ref, candidate, aspect_error = prepare(original_ref, original_candidate, width, fit)
    scores, error = metrics(ref, candidate, pixel_threshold)
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
        "metrics": scores, "regions": regional,
        "mae_gate": None if max_mae is None else {"limit_percent": max_mae, "passed": scores["rgb_mae_percent"] <= max_mae},
        "warnings": ["Aspect ratios differ: candidate was letterboxed, not cropped or stretched."] if aspect_error > 0.005 else [],
    }
    output.mkdir(parents=True, exist_ok=True)
    ref.save(output / "reference.png")
    candidate.save(output / "candidate.png")
    heat = heatmap(error)
    heat.save(output / "heatmap.png")
    highlighted = np.asarray(candidate).copy()
    changed = error > pixel_threshold / 255
    highlighted[changed] = (highlighted[changed] * 0.35 + np.array([255, 30, 90]) * 0.65).astype(np.uint8)
    overlay = Image.fromarray(highlighted)
    overlay.save(output / "highlighted.png")

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    from PIL import ImageFont
    try:
        font = ImageFont.truetype(font_path, 17)
    except OSError:
        font = ImageFont.load_default()
    sheet = Image.new("RGB", (ref.width * 2, (ref.height + 40) * 2 + 52), "#101827")
    draw = ImageDraw.Draw(sheet)
    for index, (label, picture) in enumerate((("REFERENCE", ref), ("RENDERED FRAME", candidate), ("ABSOLUTE RGB ERROR — fixed scale", heat), (f"HIGHLIGHT: pixel error > {pixel_threshold}/255", overlay))):
        x, y = (index % 2) * ref.width, (index // 2) * (ref.height + 40)
        draw.text((x + 14, y + 10), label, font=font, fill="white")
        sheet.paste(picture, (x, y + 40))
    draw.text((14, sheet.height - 36), f"RGB MAE {scores['rgb_mae_percent']:.2f}%    SSIM {scores['ssim_rgb']:.4f}    Changed pixels {scores['changed_pixels_percent']:.2f}% | MAE is not a percentage of visual fidelity", font=font, fill="white")
    sheet.save(output / "comparison.png")
    (output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")

    rows = "".join(f"<tr><td>{html.escape(name)}</td><td>{m['rgb_mae_percent']:.2f}%</td><td>{m['ssim_rgb']:.4f}</td><td>{m['changed_pixels_percent']:.2f}%</td></tr>" for name, m in {"whole image": scores, **regional}.items())
    page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Reference / rendered frame comparison</title>
<style>body{font:16px system-ui;background:#0e1727;color:#eaf2fc;max-width:1160px;margin:32px auto;padding:0 24px}h1{font-size:28px}p{line-height:1.5;color:#c0d0e4}table{border-collapse:collapse;width:100%;margin:24px 0}th,td{text-align:left;padding:12px;border-bottom:1px solid #334357} .viewer{position:relative;line-height:0;overflow:hidden}.viewer img{width:100%}.viewer img.top{position:absolute;inset:0;height:100%;clip-path:inset(0 50% 0 0)}input{width:100%;margin:18px 0}label,figcaption{display:block;margin:12px 0} .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.grid img{width:100%}figure{margin:0}.warning{color:#ffd081}</style>
<h1>Reference / rendered frame</h1><p>Drag to reveal the reference on the left and the rendered frame on the right. Scores describe aligned image appearance, not correctness of the 3D world.</p>
WARNINGS
<div class="viewer"><img src="candidate.png" alt="Rendered frame"><img class="top" id="reference" src="reference.png" alt="Reference image"></div>
<label for="split">Wipe position <output id="value">50%</output></label><input id="split" type="range" min="0" max="100" value="50">
<script>document.querySelector('#split').addEventListener('input',e=>{document.querySelector('#reference').style.clipPath=`inset(0 ${100-e.target.value}% 0 0)`;document.querySelector('#value').textContent=e.target.value+'%'})</script>
<table><thead><tr><th>Region</th><th>RGB MAE ↓</th><th>SSIM ↑</th><th>Changed pixels ↓</th></tr></thead><tbody>ROWS</tbody></table>
<p>MAE: average absolute RGB channel difference / 255 × 100. SSIM: structural similarity, best = 1; it can be negative. Changed pixels: mean RGB error above THRESHOLD/255. Coarse blurred MAE: COARSE%. These measures are complementary; no combined “fidelity percentage” is claimed.</p>
<div class="grid"><figure><img src="heatmap.png" alt="Fixed-scale error heatmap"><figcaption>Absolute RGB error: dark blue 0%, blue 5%, cyan 10%, yellow 25%, red 50%, white 100%. Scale stays fixed.</figcaption></figure><figure><img src="highlighted.png" alt="Differences highlighted in pink"><figcaption>Pixels exceeding the error threshold highlighted in pink.</figcaption></figure></div>
<p>VIEWPORT. No automatic camera alignment, cropping, exposure correction, or color matching. Transparent pixels composite on black. Full parameters, source hashes, and optional MAE gate are in <a href="metrics.json">metrics.json</a>. A low color error alone does not establish a faithful reconstruction.</p></html>"""
    page = page.replace("WARNINGS", "".join(f'<p class="warning">{html.escape(warning)}</p>' for warning in report["warnings"]))
    page = page.replace("ROWS", rows).replace("THRESHOLD", str(pixel_threshold)).replace("COARSE", f"{scores['blurred_rgb_mae_percent']:.2f}").replace("VIEWPORT", f"Analysis viewport: {ref.width} × {ref.height}")
    (output / "index.html").write_text(page)
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
    print(json.dumps({"metrics": report["metrics"], "warnings": report["warnings"], "mae_gate": report["mae_gate"], "report": str((args.output / 'index.html').resolve())}, indent=2))
    return 1 if report["mae_gate"] and not report["mae_gate"]["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
