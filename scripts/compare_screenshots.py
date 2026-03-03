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


# ── Main Comparison ──────────────────────────────────────────────────────────

def compare(
    reference_path: str,
    rendered_path: str,
    ssim_threshold: float = 0.85,
    pixel_diff_threshold: float = 15.0,
) -> dict[str, Any]:
    """
    Full comparison between reference and rendered screenshots.
    Returns a complete diff report.
    """
    # Load images
    ref_img = load_and_normalize(reference_path)
    rendered_img = load_and_normalize(rendered_path, target_size=ref_img.size)

    # Compute metrics
    ssim = compute_ssim_simple(ref_img, rendered_img)
    pixel_diff = pixel_diff_percentage(ref_img, rendered_img)
    diff_regions = find_diff_regions(ref_img, rendered_img)

    passed = ssim >= ssim_threshold and pixel_diff <= pixel_diff_threshold

    return {
        "ssim": ssim,
        "pixel_diff_pct": pixel_diff,
        "diff_regions": diff_regions,
        "diff_region_count": len(diff_regions),
        "pass": passed,
        "thresholds": {
            "ssim_min": ssim_threshold,
            "pixel_diff_max": pixel_diff_threshold,
        },
        "image_sizes": {
            "reference": list(ref_img.size),
            "rendered": list(rendered_img.size),
        },
    }


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
        "--output",
        type=str,
        default="-",
        help="Output file path for JSON report (default: stdout)",
    )

    args = parser.parse_args()

    try:
        report = compare(
            args.reference,
            args.rendered,
            ssim_threshold=args.ssim_threshold,
            pixel_diff_threshold=args.pixel_threshold,
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
