#!/usr/bin/env python3
"""
infer_tokens.py — Infer design tokens from raw color and spacing values.

Takes lists of hex colors and spacing values extracted from Figma MCP responses,
clusters them into a coherent token system, and outputs inferred_tokens.json.

Usage:
    python infer_tokens.py --colors "#0066cc,#0068ce,#fff,#f8f9fa,#212529,#6c757d,#dc3545,#28a745" \
                           --spacing "4,8,8,12,16,16,16,24,32,32,48" \
                           --fonts "Inter:16:400,Inter:24:700,Inter:14:400,Inter:36:700,Inter:12:400" \
                           --radii "4,8,8,16,9999" \
                           --output inferred_tokens.json

    python infer_tokens.py --help
"""

import argparse
import json
import math
import sys
from collections import Counter
from typing import Any


# ── Color Utilities ──────────────────────────────────────────────────────────

def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    if len(h) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB tuple to hex string."""
    return f"#{r:02x}{g:02x}{b:02x}"


def color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Euclidean distance between two RGB colors. Max ~441."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


def luminance(r: int, g: int, b: int) -> float:
    """Perceived luminance (0–255)."""
    return 0.299 * r + 0.587 * g + 0.114 * b


def saturation(r: int, g: int, b: int) -> float:
    """Simple saturation metric (0–1). Higher = more colorful."""
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    if max_c == 0:
        return 0.0
    return (max_c - min_c) / max_c


def dominant_hue(r: int, g: int, b: int) -> str:
    """Classify the dominant hue of an RGB color."""
    if saturation(r, g, b) < 0.15:
        return "gray"
    max_c = max(r, g, b)
    if max_c == r and g < b:
        return "red" if r > 150 else "gray"
    if max_c == r and g >= b:
        if g > 200 and r > 200:
            return "yellow"
        return "orange" if g > 100 else "red"
    if max_c == g:
        return "green"
    if max_c == b:
        return "blue" if b > 100 else "gray"
    return "gray"


# ── Color Clustering ─────────────────────────────────────────────────────────

CLUSTER_THRESHOLD = 30  # Euclidean distance in RGB space


def cluster_colors(hex_colors: list[str]) -> list[dict]:
    """
    Cluster similar colors together.
    Returns list of clusters with representative color and count.
    """
    if not hex_colors:
        return []

    # Count occurrences
    color_counts = Counter(hex_colors)
    unique_colors = list(color_counts.keys())

    # Convert to RGB
    rgb_colors = {}
    for h in unique_colors:
        try:
            rgb_colors[h] = hex_to_rgb(h)
        except ValueError:
            continue

    # Simple greedy clustering
    clusters: list[dict] = []
    assigned = set()

    # Sort by frequency (most common first)
    sorted_colors = sorted(rgb_colors.keys(), key=lambda c: color_counts[c], reverse=True)

    for color in sorted_colors:
        if color in assigned:
            continue

        rgb = rgb_colors[color]
        cluster_members = [color]
        cluster_count = color_counts[color]

        for other in sorted_colors:
            if other in assigned or other == color:
                continue
            other_rgb = rgb_colors[other]
            if color_distance(rgb, other_rgb) < CLUSTER_THRESHOLD:
                cluster_members.append(other)
                cluster_count += color_counts[other]
                assigned.add(other)

        assigned.add(color)

        r, g, b = rgb
        clusters.append({
            "representative": color,
            "rgb": list(rgb),
            "members": cluster_members,
            "count": cluster_count,
            "luminance": round(luminance(r, g, b), 1),
            "saturation": round(saturation(r, g, b), 3),
            "hue": dominant_hue(r, g, b),
        })

    return sorted(clusters, key=lambda c: c["count"], reverse=True)


# ── Tailwind Color Matching ──────────────────────────────────────────────────

TAILWIND_COLORS = {
    "slate-50": "#f8fafc", "slate-100": "#f1f5f9", "slate-200": "#e2e8f0",
    "slate-300": "#cbd5e1", "slate-400": "#94a3b8", "slate-500": "#64748b",
    "slate-600": "#475569", "slate-700": "#334155", "slate-800": "#1e293b",
    "slate-900": "#0f172a", "slate-950": "#020617",
    "gray-50": "#f9fafb", "gray-100": "#f3f4f6", "gray-200": "#e5e7eb",
    "gray-300": "#d1d5db", "gray-400": "#9ca3af", "gray-500": "#6b7280",
    "gray-600": "#4b5563", "gray-700": "#374151", "gray-800": "#1f2937",
    "gray-900": "#111827", "gray-950": "#030712",
    "red-50": "#fef2f2", "red-500": "#ef4444", "red-600": "#dc2626",
    "red-700": "#b91c1c",
    "orange-500": "#f97316", "orange-600": "#ea580c",
    "amber-500": "#f59e0b", "amber-600": "#d97706",
    "yellow-500": "#eab308",
    "green-50": "#f0fdf4", "green-500": "#22c55e", "green-600": "#16a34a",
    "green-700": "#15803d",
    "blue-50": "#eff6ff", "blue-500": "#3b82f6", "blue-600": "#2563eb",
    "blue-700": "#1d4ed8",
    "indigo-500": "#6366f1", "indigo-600": "#4f46e5",
    "purple-500": "#a855f7", "purple-600": "#9333ea",
    "pink-500": "#ec4899", "pink-600": "#db2777",
    "white": "#ffffff", "black": "#000000",
}


def find_closest_tailwind(hex_color: str) -> str:
    """Find the closest Tailwind color name for a given hex."""
    try:
        rgb = hex_to_rgb(hex_color)
    except ValueError:
        return "gray-500"

    best_name = "gray-500"
    best_dist = float('inf')

    for tw_name, tw_hex in TAILWIND_COLORS.items():
        tw_rgb = hex_to_rgb(tw_hex)
        dist = color_distance(rgb, tw_rgb)
        if dist < best_dist:
            best_dist = dist
            best_name = tw_name

    return best_name


# ── Semantic Naming ──────────────────────────────────────────────────────────

def assign_semantic_names(clusters: list[dict]) -> dict[str, dict]:
    """
    Assign semantic names to color clusters based on their properties.
    Returns a dict of semantic_name -> color info.
    """
    tokens = {}
    used_names = set()

    # Separate into categories
    grays = [c for c in clusters if c["hue"] == "gray"]
    chromatic = [c for c in clusters if c["hue"] != "gray"]

    # Assign primary (most-used chromatic color)
    if chromatic:
        primary = chromatic[0]
        tokens["primary"] = {
            "hex": primary["representative"],
            "tailwind": find_closest_tailwind(primary["representative"]),
            "usage": "buttons, links, accents",
        }
        used_names.add(id(primary))

    # Assign secondary (second most-used chromatic)
    if len(chromatic) > 1:
        secondary = chromatic[1]
        tokens["secondary"] = {
            "hex": secondary["representative"],
            "tailwind": find_closest_tailwind(secondary["representative"]),
            "usage": "secondary actions, borders",
        }
        used_names.add(id(secondary))

    # Assign semantic colors by hue
    hue_to_semantic = {"red": "error", "green": "success", "yellow": "warning", "orange": "warning"}
    for cluster in chromatic:
        if id(cluster) in used_names:
            continue
        semantic = hue_to_semantic.get(cluster["hue"])
        if semantic and semantic not in tokens:
            tokens[semantic] = {
                "hex": cluster["representative"],
                "tailwind": find_closest_tailwind(cluster["representative"]),
                "usage": f"{semantic} states",
            }
            used_names.add(id(cluster))

    # Assign gray scale
    grays_sorted = sorted(grays, key=lambda c: c["luminance"])
    gray_names = [
        ("text-primary", "headings, body text", lambda l: l < 80),
        ("text-secondary", "captions, metadata", lambda l: 80 <= l < 160),
        ("border", "borders, dividers", lambda l: 160 <= l < 220),
        ("surface", "card backgrounds, secondary bg", lambda l: 220 <= l < 250),
        ("background", "page background", lambda l: l >= 250),
    ]

    for gray in grays_sorted:
        if id(gray) in used_names:
            continue
        for name, usage, lum_check in gray_names:
            if name not in tokens and lum_check(gray["luminance"]):
                tokens[name] = {
                    "hex": gray["representative"],
                    "tailwind": find_closest_tailwind(gray["representative"]),
                    "usage": usage,
                }
                used_names.add(id(gray))
                break

    return tokens


# ── Spacing Inference ────────────────────────────────────────────────────────

def infer_spacing_scale(values: list[int]) -> dict[str, Any]:
    """
    Infer a spacing scale from raw pixel values.
    Returns base unit and scale mapping.
    """
    if not values:
        return {"base_unit": 4, "scale": [0, 4, 8, 12, 16, 24, 32, 48, 64]}

    # Count frequencies
    freq = Counter(values)
    common_values = sorted(freq.keys())

    # Detect base unit via GCD of most common values
    top_values = [v for v, _ in freq.most_common(10) if v > 0]
    if len(top_values) >= 2:
        base = top_values[0]
        for v in top_values[1:]:
            base = math.gcd(base, v)
        # Prefer 4 or 8 as base
        if base == 0:
            base = 4
        elif base > 8:
            base = 8
        elif base < 4:
            base = 4
    else:
        base = 4

    # Build scale from observed values, rounded to base
    scale_set = {0}
    for v in common_values:
        rounded = round(v / base) * base
        scale_set.add(rounded)

    scale = sorted(scale_set)

    # Identify common patterns
    patterns = {}
    most_common = freq.most_common(5)
    pattern_names = ["element_gap", "card_padding", "section_gap", "page_margin", "large_gap"]
    sorted_common = sorted(most_common, key=lambda x: x[0])
    for i, (val, count) in enumerate(sorted_common):
        if i < len(pattern_names):
            patterns[pattern_names[i]] = val

    return {
        "base_unit": base,
        "scale": scale,
        "common_patterns": patterns,
        "raw_frequencies": dict(freq.most_common(20)),
    }


# ── Typography Inference ─────────────────────────────────────────────────────

def infer_typography(font_specs: list[str]) -> dict[str, Any]:
    """
    Infer typography scale from font specifications.
    Input format: "family:size:weight" per entry.
    """
    if not font_specs:
        return {"font_families": ["sans-serif"], "scale": {}}

    families = Counter()
    sizes = []

    for spec in font_specs:
        parts = spec.split(":")
        if len(parts) >= 3:
            family, size, weight = parts[0], int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            family, size, weight = parts[0], int(parts[1]), 400
        else:
            continue
        families[family] += 1
        sizes.append({"family": family, "size": size, "weight": weight})

    # Map sizes to roles
    size_to_role = [
        (48, "display", "text-5xl"),
        (36, "h1", "text-4xl"),
        (30, "h2", "text-3xl"),
        (24, "h3", "text-2xl"),
        (20, "h4", "text-xl"),
        (18, "h5", "text-lg"),
        (16, "body", "text-base"),
        (14, "small", "text-sm"),
        (12, "caption", "text-xs"),
    ]

    weight_map = {
        300: "font-light", 400: "font-normal", 500: "font-medium",
        600: "font-semibold", 700: "font-bold", 800: "font-extrabold",
    }

    # Deduplicate by size+weight
    seen = set()
    unique_sizes = []
    for s in sizes:
        key = (s["size"], s["weight"])
        if key not in seen:
            seen.add(key)
            unique_sizes.append(s)

    scale = {}
    for entry in sorted(unique_sizes, key=lambda x: -x["size"]):
        # Find closest role
        best_role = "body"
        best_tw = "text-base"
        best_diff = float('inf')
        for ref_size, role, tw_class in size_to_role:
            diff = abs(entry["size"] - ref_size)
            if diff < best_diff:
                best_diff = diff
                best_role = role
                best_tw = tw_class

        if best_role not in scale:
            tw_weight = weight_map.get(entry["weight"], "font-normal")
            scale[best_role] = {
                "size": entry["size"],
                "weight": entry["weight"],
                "family": entry["family"],
                "tailwind": f"{best_tw} {tw_weight}",
            }

    return {
        "font_families": [f for f, _ in families.most_common()],
        "scale": scale,
    }


# ── Radii Inference ──────────────────────────────────────────────────────────

def infer_radii(values: list[int]) -> dict[str, int]:
    """Infer border-radius scale from raw values."""
    if not values:
        return {"none": 0, "sm": 4, "md": 8, "lg": 16, "full": 9999}

    freq = Counter(values)
    unique = sorted(freq.keys())

    radii = {"none": 0}
    names = ["sm", "md", "lg", "xl", "2xl"]

    non_zero = [v for v in unique if v > 0 and v < 999]
    for i, val in enumerate(non_zero[:len(names)]):
        radii[names[i]] = val

    # Check for "full" (pill shape)
    if any(v >= 999 for v in unique):
        radii["full"] = 9999

    return radii


# ── Main ─────────────────────────────────────────────────────────────────────

def build_tokens(
    colors: list[str],
    spacing: list[int],
    fonts: list[str],
    radii: list[int],
) -> dict[str, Any]:
    """Build the complete inferred token system."""

    # Color analysis
    clusters = cluster_colors(colors)
    color_tokens = assign_semantic_names(clusters)

    # Build custom tailwind config for non-standard colors
    tailwind_extension = {}
    for name, info in color_tokens.items():
        tw = info["tailwind"]
        hex_val = info["hex"]
        # If the closest tailwind color is far from exact, add to extension
        try:
            tw_rgb = hex_to_rgb(TAILWIND_COLORS.get(tw, "#000000"))
            actual_rgb = hex_to_rgb(hex_val)
            if color_distance(tw_rgb, actual_rgb) > 15:
                tailwind_extension[name] = hex_val
        except (ValueError, KeyError):
            tailwind_extension[name] = hex_val

    # Spacing analysis
    spacing_result = infer_spacing_scale(spacing)

    # Typography analysis
    typography_result = infer_typography(fonts)

    # Radii analysis
    radii_result = infer_radii(radii)

    return {
        "meta": {
            "generator": "figma-hybrid-orchestrator/infer_tokens.py",
            "color_clusters": len(clusters),
            "unique_colors_input": len(set(colors)),
            "spacing_values_input": len(spacing),
            "font_specs_input": len(fonts),
        },
        "colors": color_tokens,
        "spacing": spacing_result,
        "typography": typography_result,
        "radii": radii_result,
        "tailwind_config_extension": {
            "colors": tailwind_extension,
        } if tailwind_extension else {},
    }


def main():
    parser = argparse.ArgumentParser(
        description="Infer design tokens from raw color and spacing values extracted from Figma."
    )
    parser.add_argument(
        "--colors",
        type=str,
        default="",
        help="Comma-separated hex colors (e.g., '#0066cc,#fff,#212529')",
    )
    parser.add_argument(
        "--spacing",
        type=str,
        default="",
        help="Comma-separated spacing values in px (e.g., '4,8,16,24,32')",
    )
    parser.add_argument(
        "--fonts",
        type=str,
        default="",
        help="Comma-separated font specs as 'family:size:weight' (e.g., 'Inter:16:400,Inter:24:700')",
    )
    parser.add_argument(
        "--radii",
        type=str,
        default="",
        help="Comma-separated border-radius values in px (e.g., '4,8,16')",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="-",
        help="Output file path (default: stdout)",
    )

    args = parser.parse_args()

    colors = [c.strip() for c in args.colors.split(",") if c.strip()] if args.colors else []
    spacing = [int(s.strip()) for s in args.spacing.split(",") if s.strip()] if args.spacing else []
    fonts = [f.strip() for f in args.fonts.split(",") if f.strip()] if args.fonts else []
    radii = [int(r.strip()) for r in args.radii.split(",") if r.strip()] if args.radii else []

    tokens = build_tokens(colors, spacing, fonts, radii)

    output_json = json.dumps(tokens, indent=2)

    if args.output == "-":
        print(output_json)
    else:
        with open(args.output, "w") as f:
            f.write(output_json)
        print(f"Tokens written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
