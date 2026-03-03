# Phase 2: Design Decomposition — Detailed Reference

## Purpose

Large or complex Figma frames can produce `get_design_context` responses that exceed token limits (25,000 tokens default, configurable via `MAX_MCP_OUTPUT_TOKENS`). Phase 2 breaks the design into logical sections, processes each independently, and prepares them for assembly in Phase 3.

## When to Run

- Node count > 500 (from Phase 0 metadata)
- Quality score < 7 (partially structured or unstructured files benefit from section-by-section processing)
- Previous `get_design_context` call was truncated or errored with token overflow

## Step 1: Parse the Node Tree

From the Phase 0 `get_metadata` result, extract each direct child of the target frame with its bounding box:

```
Frame "Landing Page" (0, 0, 1440, 3200)
├── Child "Nav" (0, 0, 1440, 80)
├── Child "Hero" (0, 80, 1440, 600)
├── Child "Features" (0, 680, 1440, 800)
├── Child "Testimonials" (0, 1480, 1440, 600)
├── Child "Pricing" (0, 2080, 1440, 700)
├── Child "CTA" (0, 2780, 1440, 300)
└── Child "Footer" (0, 3080, 1440, 120)
```

## Step 2: Identify Logical Sections

Use spatial analysis to classify each child:

### Zone Detection Rules

**Header zone** — Top of the frame:
- Nodes where `y < frame_height * 0.05` OR `y < 100px`
- Typically full-width (`width >= frame_width * 0.9`)
- Usually contains navigation, logo, menu items

**Footer zone** — Bottom of the frame:
- Nodes where `y + height > frame_height * 0.95`
- Typically full-width
- Contains links, copyright, contact info

**Sidebar** — Left or right edge:
- Nodes where `width < frame_width * 0.3` AND `height > frame_height * 0.5`
- Pinned to left edge (`x < 20`) or right edge (`x + width > frame_width - 20`)

**Content sections** — Everything else:
- Group by vertical proximity (nodes within 20px of each other vertically → same section)
- Order top-to-bottom

### Grouping Algorithm

```
1. Sort all direct children by y-position (top to bottom)
2. Classify header/footer/sidebar using rules above
3. For remaining nodes, create sections:
   a. Start a new section with the first remaining node
   b. For each subsequent node:
      - If gap to previous node < 40px → add to current section
      - If gap >= 40px → start new section
4. Name sections: "section-1-hero", "section-2-features", etc.
   (Use the node's own name if it's semantic, otherwise generate one)
```

## Step 3: Estimate Token Budget Per Section

Each section needs its own `get_design_context` call. Estimate tokens:

```
section_tokens ≈ section_node_count × 70
```

**Budget management:**
- If a section has > 350 nodes (~25,000 tokens), split it further by applying the same algorithm to its children
- Target: 50–200 nodes per section (3,500–14,000 tokens)
- Maximum: 350 nodes per section

**Priority order for processing:**
1. Header (users see this first — errors here are most noticeable)
2. Hero / above-the-fold content
3. Content sections (top to bottom)
4. Footer

## Step 4: Fetch Design Context Per Section

For each section:

```
Call: get_design_context(sectionNodeId, fileKey)
Call: get_screenshot(sectionNodeId, fileKey)
```

Store the results mapped to section names:

```json
{
  "sections": [
    {
      "id": "section-0-header",
      "node_id": "1:100",
      "bounds": { "x": 0, "y": 0, "width": 1440, "height": 80 },
      "design_context": "... (HTML/CSS from MCP) ...",
      "screenshot_ref": "screenshot_1_100.png",
      "node_count": 45,
      "tokens_used": 3150
    },
    ...
  ]
}
```

## Step 5: Prepare Assembly Instructions

Generate a layout map that Phase 3 uses to combine sections:

```json
{
  "layout": "vertical-stack",
  "direction": "column",
  "sections_order": [
    "section-0-header",
    "section-1-hero",
    "section-2-features",
    "section-3-testimonials",
    "section-4-pricing",
    "section-5-cta",
    "section-6-footer"
  ],
  "full_frame_width": 1440,
  "full_frame_height": 3200,
  "has_sidebar": false,
  "sidebar_position": null
}
```

For layouts with sidebars:
```json
{
  "layout": "sidebar-content",
  "sidebar": "section-0-sidebar",
  "sidebar_position": "left",
  "sidebar_width": 280,
  "content_sections": ["section-1-header", "section-2-main", "section-3-footer"],
  "content_direction": "column"
}
```

## Handling Edge Cases

### Overlapping Nodes
Some designs have absolutely-positioned overlapping elements (e.g., a floating CTA button over a hero image). These nodes don't fit neatly into sections.

**Strategy:** Process overlapping nodes as part of their nearest section by y-center, then note them as `position: absolute` in the assembly instructions.

### Very Deep Nesting
Some unstructured files have 10+ levels of nested groups. The decomposition should work at the top 2–3 levels only. Deeper nesting is handled by `get_design_context` within each section.

### Single-Section Designs
If the entire frame is one component (e.g., a single card or dialog), skip decomposition and go directly to Phase 3 with the full frame.

**Threshold:** If the frame has < 100 nodes, decomposition is unnecessary.

### Repeated Sections
If Phase 1 identified component patterns (e.g., 6 identical cards), and the decomposition finds a section containing all 6, note this:

```json
{
  "id": "section-3-cards",
  "contains_repeated_pattern": true,
  "pattern_name": "Card",
  "pattern_count": 6,
  "strategy": "Generate Card component once, render 6 instances with different props"
}
```

This saves Phase 3 from generating redundant code.

## Output Summary

After Phase 2, present:

```
Decomposition Complete:
- 7 sections identified (header, hero, features, testimonials, pricing, CTA, footer)
- Layout: vertical stack (no sidebar)
- Total nodes: 623 → split into sections of 45–120 nodes each
- 1 repeated pattern detected: Card (6 instances in "features" section)
- Estimated total tokens: 43,610 (within budget for per-section processing)

Proceeding to Phase 3 (code generation) for each section.
```
