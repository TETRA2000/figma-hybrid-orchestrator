#!/usr/bin/env python3
"""
compare_screenshots.py — Compare a Figma reference screenshot against a rendered screenshot.

Computes structural similarity (SSIM) and pixel-level differences between two images.
Outputs a JSON report with diff metrics and bounding boxes of mismatch regions.

Usage:
    python compare_screenshots.py --reference figma.png --rendered playwright.png --output report.json
    python compare_screenshots.py --reference figma.png --rendered playwright.png  # stdout

Requirements:
    pip install Pillow --break-system-packages
"""

import argparse
import json
import math
import sys
from typing import Any

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow --break-system-packages",
          file=sys.stderr)
    sys.exit(1)


# ── Image Utilities ──────────────────────────────────────────────────────────

def load_and_normalize(path: str, target_size: tuple[int, int] | None = None) -> Image.Image:
    """Load an image and optionally resize to target dimensions."""
    img = Image.open(path).convert("RGB")
    if target_size and img.size != target_size:
        img = img.resize(target_size, Image.Resampling.LANCZOS)
    return img


def pixel_diff_percentage(img1: Image.Image, img2: Image.Image, threshold: int = 30) -> float:
    """
    Calculate percentage of pixels that differ by more than threshold.
    threshold is per-channel Euclidean distance in RGB space.
    """
    if img1.size != img2.size:
        raise ValueError(f"Image sizes don't match: {img1.size} vs {img2.size}")

    pixels1 = img1.load()
    pixels2 = img2.load()
    width, height = img1.size
    total = width * height
    diff_count = 0

    for y in range(height):
        for x in range(width):
            r1, g1, b1 = pixels1[x, y]
            r2, g2, b2 = pixels2[x, y]
            dist = math.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)
            if dist > threshold:
                diff_count += 1

    return round(diff_count / total * 100, 2)


def compute_ssim_simple(img1: Image.Image, img2: Image.Image, window_size: int = 8) -> float:
    """
    Simplified SSIM (Structural Similarity Index) computation.
    Returns value between 0.0 (completely different) and 1.0 (identical).

    This is a simplified implementation that doesn't require scipy/numpy.
    For production use, consider using skimage.metrics.structural_similarity.
    """
    if img1.size != img2.size:
        raise ValueError(f"Image sizes don't match: {img1.size} vs {img2.size}")

    # Convert to grayscale for SSIM
    gray1 = img1.convert("L")
    gray2 = img2.convert("L")

    pixels1 = gray1.load()
    pixels2 = gray2.load()
    width, height = gray1.size

    # SSIM constants
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2

    ssim_sum = 0.0
    window_count = 0

    for y in range(0, height - window_size, window_size // 2):
        for x in range(0, width - window_size, window_size // 2):
            # Extract window
            vals1 = []
            vals2 = []
            for wy in range(window_size):
                for wx in range(window_size):
                    if x + wx < width and y + wy < height:
                        vals1.append(pixels1[x + wx, y + wy])
                        vals2.append(pixels2[x + wx, y + wy])

            if len(vals1) < 4:
                continue

            n = len(vals1)

            # Compute means
            mu1 = sum(vals1) / n
            mu2 = sum(vals2) / n

            # Compute variances and covariance
            var1 = sum((v - mu1) ** 2 for v in vals1) / n
            var2 = sum((v - mu2) ** 2 for v in vals2) / n
            cov = sum((v1 - mu1) * (v2 - mu2) for v1, v2 in zip(vals1, vals2)) / n

            # SSIM for this window
            numerator = (2 * mu1 * mu2 + C1) * (2 * cov + C2)
            denominator = (mu1 ** 2 + mu2 ** 2 + C1) * (var1 + var2 + C2)

            if denominator > 0:
                ssim_sum += numerator / denominator
                window_count += 1

    if window_count == 0:
        return 0.0

    return round(ssim_sum / window_count, 4)


def find_diff_regions(
    img1: Image.Image,
    img2: Image.Image,
    block_size: int = 32,
    threshold: float = 0.3,
) -> list[dict]:
    """
    Find rectangular regions where images differ significantly.
    Divides the image into blocks and checks each for differences.
    Returns bounding boxes of different regions.
    """
    if img1.size != img2.size:
        raise ValueError(f"Image sizes don't match: {img1.size} vs {img2.size}")

    pixels1 = img1.load()
    pixels2 = img2.load()
    width, height = img1.size

    diff_blocks = []

    for by in range(0, height, block_size):
        for bx in range(0, width, block_size):
            total_pixels = 0
            diff_pixels = 0

            for y in range(by, min(by + block_size, height)):
                for x in range(bx, min(bx + block_size, width)):
                    r1, g1, b1 = pixels1[x, y]
                    r2, g2, b2 = pixels2[x, y]
                    dist = math.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)
                    total_pixels += 1
                    if dist > 30:
                        diff_pixels += 1

            if total_pixels > 0 and diff_pixels / total_pixels > threshold:
                diff_blocks.append({
                    "x": bx,
                    "y": by,
                    "width": min(block_size, width - bx),
                    "height": min(block_size, height - by),
                    "diff_ratio": round(diff_pixels / total_pixels, 3),
                })

    # Merge adjacent blocks into larger regions
    return merge_adjacent_regions(diff_blocks, block_size)


def merge_adjacent_regions(blocks: list[dict], block_size: int) -> list[dict]:
    """Merge adjacent diff blocks into larger bounding boxes."""
    if not blocks:
        return []

    # Simple merge: group blocks that are adjacent
    merged = []
    used = set()

    for i, block in enumerate(blocks):
        if i in used:
            continue

        region = {
            "x": block["x"],
            "y": block["y"],
            "width": block["width"],
            "height": block["height"],
            "max_diff_ratio": block["diff_ratio"],
        }

        # Expand region with adjacent blocks
        for j, other in enumerate(blocks):
            if j in used or j == i:
                continue

            # Check if adjacent (within one block size)
            if (abs(other["x"] - (region["x"] + region["width"])) <= block_size and
                    abs(other["y"] - region["y"]) <= block_size):
                # Expand right
                new_right = other["x"] + other["width"]
                region["width"] = new_right - region["x"]
                region["height"] = max(region["height"], other["y"] + other["height"] - region["y"])
                region["max_diff_ratio"] = max(region["max_diff_ratio"], other["diff_ratio"])
                used.add(j)

            elif (abs(other["y"] - (region["y"] + region["height"])) <= block_size and
                  abs(other["x"] - region["x"]) <= block_size):
                # Expand down
                new_bottom = other["y"] + other["height"]
                region["height"] = new_bottom - region["y"]
                region["width"] = max(region["width"], other["x"] + other["width"] - region["x"])
                region["max_diff_ratio"] = max(region["max_diff_ratio"], other["diff_ratio"])
                used.add(j)

        used.add(i)

        # Classify severity
        if region["max_diff_ratio"] > 0.7:
            region["severity"] = "high"
        elif region["max_diff_ratio"] > 0.4:
            region["severity"] = "medium"
        else:
            region["severity"] = "low"

        merged.append(region)

    return merged


# ── Region-Based Comparison ──────────────────────────────────────────────────

def compare_region(
    ref_img: Image.Image,
    rendered_img: Image.Image,
    region: dict,
) -> dict[str, Any]:
    """
    Compare a specific region (bounding box) between reference and rendered.
    Useful for element-level comparison when you know where each element is.
    """
    x, y, w, h = region["x"], region["y"], region["width"], region["height"]

    # Clamp to image bounds
    ref_w, ref_h = ref_img.size
    x2, y2 = min(x + w, ref_w), min(y + h, ref_h)
    x, y = max(0, x), max(0, y)

    if x2 <= x or y2 <= y:
        return {"name": region.get("name", "unknown"), "error": "region out of bounds"}

    ref_crop = ref_img.crop((x, y, x2, y2))
    ren_crop = rendered_img.crop((x, y, x2, y2))

    ssim = compute_ssim_simple(ref_crop, ren_crop)
    pixel_diff = pixel_diff_percentage(ref_crop, ren_crop)

    return {
        "name": region.get("name", f"region_{x}_{y}"),
        "bounds": {"x": x, "y": y, "width": x2 - x, "height": y2 - y},
        "ssim": ssim,
        "pixel_diff_pct": pixel_diff,
    }


def classify_diff_regions(diff_regions: list[dict], ref_img: Image.Image, rendered_img: Image.Image) -> list[dict]:
    """
    Classify each diff region by likely mismatch type based on color analysis.
    """
    classified = []
    for region in diff_regions:
        x, y = region["x"], region["y"]
        w, h = region["width"], region["height"]
        ref_w, ref_h = ref_img.size

        x2 = min(x + w, ref_w)
        y2 = min(y + h, ref_h)
        if x2 <= x or y2 <= y:
            continue

        ref_crop = ref_img.crop((x, y, x2, y2))
        ren_crop = rendered_img.crop((x, y, x2, y2))

        # Analyze the nature of the difference
        ref_pixels = list(ref_crop.getdata())
        ren_pixels = list(ren_crop.getdata())

        # Check if rendered region is mostly white/empty (missing element)
        ren_brightness = sum(sum(p) / 3 for p in ren_pixels) / len(ren_pixels)
        ref_brightness = sum(sum(p) / 3 for p in ref_pixels) / len(ref_pixels)

        # Check color distribution difference
        ref_has_color = any(max(p) - min(p) > 50 for p in ref_pixels[:100])
        ren_has_color = any(max(p) - min(p) > 50 for p in ren_pixels[:100])

        mismatch_type = "unknown"
        if ren_brightness > 240 and ref_brightness < 200:
            mismatch_type = "missing_element"
        elif ref_has_color and not ren_has_color:
            mismatch_type = "gradient_or_color_missing"
        elif abs(ren_brightness - ref_brightness) > 80:
            mismatch_type = "background_color_wrong"
        elif w > ref_w * 0.5 and h < ref_h * 0.1:
            mismatch_type = "spacing_or_alignment"
        else:
            mismatch_type = "style_difference"

        classified.append({
            **region,
            "mismatch_type": mismatch_type,
            "ref_brightness": round(ref_brightness, 1),
            "rendered_brightness": round(ren_brightness, 1),
        })

    return classified


# ── Main Comparison ──────────────────────────────────────────────────────────

def compare(
    reference_path: str,
    rendered_path: str,
    ssim_threshold: float = 0.85,
    pixel_diff_threshold: float = 15.0,
    element_regions: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Full comparison between reference and rendered screenshots.
    Returns a complete diff report.

    If element_regions is provided (list of {"name", "x", "y", "width", "height"}),
    also performs element-level comparison for each region.
    """
    # Load images
    ref_img = load_and_normalize(reference_path)
    rendered_img = load_and_normalize(rendered_path, target_size=ref_img.size)

    # Layer 1: Full-image metrics
    ssim = compute_ssim_simple(ref_img, rendered_img)
    pixel_diff = pixel_diff_percentage(ref_img, rendered_img)
    diff_regions = find_diff_regions(ref_img, rendered_img)

    # Classify diff regions by mismatch type
    classified_regions = classify_diff_regions(diff_regions, ref_img, rendered_img)

    passed = ssim >= ssim_threshold and pixel_diff <= pixel_diff_threshold

    result: dict[str, Any] = {
        "layer1_visual": {
            "ssim": ssim,
            "pixel_diff_pct": pixel_diff,
            "pass": passed,
            "thresholds": {
                "ssim_min": ssim_threshold,
                "pixel_diff_max": pixel_diff_threshold,
            },
        },
        "diff_regions": classified_regions,
        "diff_region_count": len(classified_regions),
        "mismatch_summary": {},
        "image_sizes": {
            "reference": list(ref_img.size),
            "rendered": list(rendered_img.size),
        },
    }

    # Summarize mismatch types
    type_counts: dict[str, int] = {}
    for r in classified_regions:
        t = r.get("mismatch_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    result["mismatch_summary"] = type_counts

    # Layer 2: Element-level comparison (if regions provided)
    if element_regions:
        element_results = []
        for region in element_regions:
            elem_result = compare_region(ref_img, rendered_img, region)
            element_results.append(elem_result)
        result["layer2_elements"] = element_results

        # Element-level pass: all elements SSIM > 0.80
        elem_pass = all(
            e.get("ssim", 0) > 0.80
            for e in element_results
            if "error" not in e
        )
        result["layer2_pass"] = elem_pass

    # Overall pass combines both layers
    result["pass"] = passed and result.get("layer2_pass", True)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Compare a Figma reference screenshot against a rendered screenshot."
    )
    parser.add_argument(
        "--reference",
        type=str,
        required=True,
        help="Path to the Figma reference screenshot (PNG)",
    )
    parser.add_argument(
        "--rendered",
        type=str,
        required=True,
        help="Path to the Playwright rendered screenshot (PNG)",
    )
    parser.add_argument(
        "--ssim-threshold",
        type=float,
        default=0.85,
        help="Minimum SSIM score to pass (default: 0.85)",
    )
    parser.add_argument(
        "--pixel-threshold",
        type=float,
        default=15.0,
        help="Maximum pixel diff percentage to pass (default: 15.0)",
    )
    parser.add_argument(
        "--regions",
        type=str,
        default=None,
        help="JSON file with element regions for Layer 2 comparison. "
             'Format: [{"name": "header", "x": 0, "y": 0, "width": 1699, "height": 80}, ...]',
    )
    parser.add_argument(
        "--output",
        type=str,
        default="-",
        help="Output file path for JSON report (default: stdout)",
    )

    args = parser.parse_args()

    # Load element regions if provided
    element_regions = None
    if args.regions:
        try:
            with open(args.regions) as f:
                element_regions = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load regions file: {e}", file=sys.stderr)

    try:
        report = compare(
            args.reference,
            args.rendered,
            ssim_threshold=args.ssim_threshold,
            pixel_diff_threshold=args.pixel_threshold,
            element_regions=element_regions,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during comparison: {e}", file=sys.stderr)
        sys.exit(1)

    output_json = json.dumps(report, indent=2)

    if args.output == "-":
        print(output_json)
    else:
        with open(args.output, "w") as f:
            f.write(output_json)
        print(f"Report written to {args.output}", file=sys.stderr)

    # Exit with non-zero if comparison failed
    sys.exit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
