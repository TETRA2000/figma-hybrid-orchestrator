# Phase 1: Structure Inference — Detailed Reference

## Purpose

When a Figma file scores 0–3 (unstructured), it lacks the tokens, components, and semantic structure that produce good code. Phase 1 compensates by analyzing the raw visual data and inferring a token system and component catalog. This transforms a chaotic file into one with enough structure for clean code generation.

## Overview

Phase 1 extracts three things:
1. **Color tokens** — clustered from all fills and strokes
2. **Spacing scale** — derived from padding, gap, and margin values
3. **Component candidates** — repeated visual patterns identified as reusable elements

## Step 1: Sample Representative Nodes

Don't fetch every node — that causes token overflow. Instead, sample 8–12 nodes strategically:

**Sampling strategy:**
- Pick 2–3 nodes from the top of the frame (likely header/nav)
- Pick 4–5 nodes from the middle (likely content — cards, sections)
- Pick 2–3 nodes from the bottom (likely footer)
- Prefer nodes with 3+ children (more structure to analyze)
- Avoid leaf nodes (text, icons) — they don't reveal layout patterns

For each sampled node:
```
Call: get_design_context(nodeId, fileKey)
```

This returns reference HTML/CSS code. Parse it to extract style values.

## Step 2: Color Clustering

### Extract All Colors

From each `get_design_context` response, collect:
- Background colors (`background-color`, `background`)
- Text colors (`color`)
- Border colors (`border-color`, `border`)
- Fill colors from SVG elements

You'll typically get 20–50 unique hex values from 8–12 sampled nodes.

### Cluster by Similarity

Many of these hex values are near-duplicates (e.g., `#0066cc` and `#0068ce`). Cluster them:

**Algorithm (simple Euclidean in RGB):**

```python
# Use scripts/infer_tokens.py for the actual implementation
# Conceptual approach:

1. Convert each hex to (R, G, B) tuple
2. Sort by luminance (0.299*R + 0.587*G + 0.114*B)
3. Group colors where Euclidean distance < 30 (out of 441 max)
4. For each cluster, pick the most-used color as representative
5. Assign semantic names based on usage context
```

**Naming heuristic:**
- Most-used dark color (luminance < 50) → `text-primary`
- Most-used medium color → `text-secondary`
- Most-used very light color → `background`
- Most-used saturated color → `primary`
- Second most-used saturated color → `secondary`
- Reds → `error` or `destructive`
- Greens → `success`
- Yellows/ambers → `warning`
- Remaining → `gray-100` through `gray-900` by luminance

### Map to Tailwind

For each inferred token, find the closest Tailwind default color:

| Inferred Token | Hex | Closest Tailwind |
|---|---|---|
| primary | #0066cc | `blue-600` |
| text-primary | #1a1a2e | `gray-900` |
| background | #f8f9fa | `gray-50` |
| error | #dc3545 | `red-600` |

If the design uses colors far from Tailwind defaults, generate a `tailwind.config.ts` extension:
```ts
// tailwind.config.ts (extend section)
colors: {
  primary: '#0066cc',
  secondary: '#6c757d',
  // ...
}
```

## Step 3: Spacing Scale Extraction

### Collect Spacing Values

From sampled `get_design_context` responses, extract:
- `padding` (all sides)
- `gap` (flex/grid gap)
- `margin` (all sides)
- `border-radius`

### Identify Base Unit

Count frequency of each value. Common base units:

| Base Unit | Scale Pattern | Common In |
|---|---|---|
| 4px | 0, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64 | Material Design, most modern UI |
| 8px | 0, 8, 16, 24, 32, 48, 64, 96 | Larger-scale layouts |
| 5px | 0, 5, 10, 15, 20, 30, 40 | Custom/legacy systems |

**Detection algorithm:**
1. Collect all spacing values
2. Compute GCD (greatest common divisor) of the most frequent values
3. If GCD is 4 or 8, use that as base
4. Otherwise, use 4 as default

### Build Scale

```json
{
  "base": 4,
  "scale": {
    "0": 0, "px": 1, "0.5": 2, "1": 4, "1.5": 6,
    "2": 8, "3": 12, "4": 16, "5": 20, "6": 24,
    "8": 32, "10": 40, "12": 48, "16": 64
  }
}
```

Map each collected spacing value to the nearest scale step. Values that don't fit the scale are rounded to the nearest step and flagged.

## Step 4: Typography Extraction

### Collect Font Data

From sampled nodes, extract:
- `font-family`
- `font-size` (px)
- `font-weight`
- `line-height`
- `letter-spacing`

### Build Typography Scale

Group by size and weight to identify roles:

| Size Range | Likely Role | Tailwind Class |
|---|---|---|
| 32–48px | Heading 1 | `text-3xl` to `text-5xl` |
| 24–30px | Heading 2 | `text-2xl` to `text-3xl` |
| 18–22px | Heading 3 | `text-lg` to `text-xl` |
| 14–16px | Body | `text-sm` to `text-base` |
| 12–13px | Caption/Small | `text-xs` to `text-sm` |

Output:
```json
{
  "heading-1": { "family": "Inter", "size": 36, "weight": 700, "tailwind": "text-4xl font-bold" },
  "heading-2": { "family": "Inter", "size": 24, "weight": 600, "tailwind": "text-2xl font-semibold" },
  "body": { "family": "Inter", "size": 16, "weight": 400, "tailwind": "text-base font-normal" },
  "caption": { "family": "Inter", "size": 12, "weight": 400, "tailwind": "text-xs font-normal" }
}
```

## Step 5: Component Pattern Detection

### Identify Repeated Structures

From the metadata XML, look for subtrees that appear multiple times with similar structure:

**Similarity criteria:**
- Same number of children (±1)
- Similar bounding box dimensions (within 20%)
- Similar child types (e.g., both have [image, text, text, button])
- Different content but same layout

**Example:** If the metadata contains 6 frames that are each ~300x200px, each with an image, a heading text, a body text, and a button — that's a "Card" component.

### Build Component Catalog

For each detected pattern:

```json
{
  "name": "Card",
  "instances": 6,
  "typical_size": { "width": 300, "height": 200 },
  "children_pattern": ["IMAGE", "TEXT (heading)", "TEXT (body)", "FRAME (button)"],
  "sample_nodes": ["123:456", "123:789"],
  "inferred_props": ["title: string", "description: string", "imageUrl: string"]
}
```

Name components based on their structure:
- Image + text + button → `Card`
- Icon + text (horizontal) → `ListItem` or `MenuItem`
- Input field + label → `FormField`
- Large text + small text (stacked) → `HeroSection`
- Horizontal row of icons/links → `NavBar` or `Footer`

## Complete Output Format

The final `inferred_tokens.json`:

```json
{
  "meta": {
    "source_file_key": "abc123",
    "source_node_id": "0:1",
    "assessment_score": 2,
    "sampled_nodes": 10,
    "generated_at": "2026-03-03T12:00:00Z"
  },
  "colors": {
    "primary": { "hex": "#0066cc", "tailwind": "blue-600", "usage": "buttons, links, accents" },
    "secondary": { "hex": "#6c757d", "tailwind": "gray-500", "usage": "secondary text, borders" },
    "background": { "hex": "#ffffff", "tailwind": "white", "usage": "page background" },
    "surface": { "hex": "#f8f9fa", "tailwind": "gray-50", "usage": "card backgrounds" },
    "text-primary": { "hex": "#212529", "tailwind": "gray-800", "usage": "headings, body text" },
    "text-secondary": { "hex": "#6c757d", "tailwind": "gray-500", "usage": "captions, metadata" },
    "error": { "hex": "#dc3545", "tailwind": "red-600", "usage": "error states" },
    "success": { "hex": "#28a745", "tailwind": "green-600", "usage": "success states" }
  },
  "spacing": {
    "base_unit": 4,
    "scale": [0, 2, 4, 8, 12, 16, 24, 32, 48, 64],
    "common_patterns": {
      "card_padding": 16,
      "section_gap": 32,
      "element_gap": 8,
      "page_margin": 64
    }
  },
  "typography": {
    "font_families": ["Inter", "sans-serif"],
    "scale": {
      "display": { "size": 48, "weight": 700, "line_height": 1.1, "tailwind": "text-5xl font-bold" },
      "h1": { "size": 36, "weight": 700, "line_height": 1.2, "tailwind": "text-4xl font-bold" },
      "h2": { "size": 24, "weight": 600, "line_height": 1.3, "tailwind": "text-2xl font-semibold" },
      "h3": { "size": 18, "weight": 600, "line_height": 1.4, "tailwind": "text-lg font-semibold" },
      "body": { "size": 16, "weight": 400, "line_height": 1.5, "tailwind": "text-base" },
      "small": { "size": 14, "weight": 400, "line_height": 1.5, "tailwind": "text-sm" },
      "caption": { "size": 12, "weight": 400, "line_height": 1.4, "tailwind": "text-xs" }
    }
  },
  "radii": {
    "none": 0, "sm": 4, "md": 8, "lg": 16, "full": 9999
  },
  "components": [
    {
      "name": "Card",
      "instances": 6,
      "typical_size": { "width": 300, "height": 200 },
      "children_pattern": ["IMAGE", "TEXT", "TEXT", "BUTTON"],
      "sample_nodes": ["123:456", "123:789"]
    },
    {
      "name": "Button",
      "instances": 12,
      "typical_size": { "width": 120, "height": 40 },
      "variants": ["primary (filled)", "secondary (outlined)"],
      "sample_nodes": ["124:100", "124:200"]
    }
  ],
  "tailwind_config_extension": {
    "colors": {
      "primary": "#0066cc",
      "secondary": "#6c757d",
      "surface": "#f8f9fa"
    }
  }
}
```

## Presenting to the User

After Phase 1 completes, present a summary:

```
Inferred Design System:
- 8 color tokens (primary: #0066cc, secondary: #6c757d, ...)
- 4px base spacing scale (10 steps)
- Inter font family, 7-level type scale
- 2 component patterns detected: Card (6 instances), Button (12 instances)

Custom Tailwind config will be generated for non-standard colors.
Proceeding to Phase 2 (decomposition) → Phase 3 (code generation).
```

Allow the user to correct any misidentified tokens before continuing.
