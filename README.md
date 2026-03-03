# figma-hybrid-orchestrator

A Claude Code skill that converts **any** Figma design to React + Tailwind CSS — even messy, unstructured files with flat layers, no tokens, and names like "Group 5".

## The Problem

The Figma MCP server produces great code from well-structured files. But real-world Figma files often lack components, design tokens, Code Connect mappings, and semantic naming. This leads to token overflow, hardcoded values, and no way to verify the output.

Even with structured files, AI code generation produces predictable categories of visual bugs: missing gradients, distorted SVGs, collapsed spacing, unstyled buttons, and wrong container widths. This skill addresses both the structural and the quality problems.

## How It Works

The skill runs an **adaptive pipeline** that scores the Figma file's structure quality (0–8) and selects only the phases needed:

```
Phase 0: Assessment     → Score the file (always runs)
Phase 1: Inference      → Infer missing tokens & components (score 0–3)
Phase 2: Decomposition  → Break large files into sections (score < 7 or 500+ nodes)
Phase 3: Code Generation → Generate React + Tailwind with mismatch prevention (always runs)
Phase 4: Verification   → Two-layer Playwright audit: visual + structural (optional)
```

| Quality Score | File State | Phases Run |
|:---:|---|---|
| 7–8 | Well-structured (tokens, components, Code Connect) | 0 → 3 → 4 |
| 4–6 | Partially structured (some tokens or naming) | 0 → 2 → 3 → 4 |
| 0–3 | Unstructured (flat layers, no tokens, generic names) | 0 → 1 → 2 → 3 → 4 |

## Common Mismatch Catalog

Tested against real-world Figma files (including an Apple-style product page), the skill includes a catalog of 11 common mismatch patterns and their fixes:

| ID | Mismatch | Severity | What Happens |
|---|---|:---:|---|
| M1 | Gradient text missing | P0 | Gold/metallic text renders as flat gray |
| M2 | SVG aspect ratio distortion | P0 | Logos appear stretched or squashed |
| M3 | Container width wrong | P1 | Content spans full viewport instead of centered max-width |
| M4 | Vertical spacing collapsed | P1 | Sections stack too tightly, losing whitespace |
| M5 | Button style missing | P2 | CTA buttons render as plain text links |
| M6 | Heading size inaccurate | P2 | Font sizes >20% off from Figma values |
| M7 | Text alignment wrong | P2 | Centered text renders left-aligned |
| M8 | Nav positioning missing | P3 | Fixed/sticky nav scrolls with content |
| M9 | Dark background missing | P3 | Light text on accidentally-white background |
| M10 | Figma asset URLs broken | P0 | Icons/images fail to load after URL expiry (7 days) |
| M11 | Multi-layer gradient simplified | P1 | Complex background compositing lost when gradients merged |

Phase 3 includes prevention rules for each pattern. Phase 4's structural audit catches them in the rendered output.

## Installation

Copy the `figma-hybrid-orchestrator/` directory into your Claude Code skills folder:

```bash
cp -r figma-hybrid-orchestrator/ /path/to/your/project/.claude/skills/
```

Or into the global skills directory:

```bash
cp -r figma-hybrid-orchestrator/ ~/.claude/skills/
```

### Prerequisites

- **Figma MCP server** — [Figma Dev Mode MCP](https://developers.figma.com/docs/figma-mcp-server/) configured in your Claude Code environment
- **Python 3.10+** — For the bundled scripts
- **Pillow** — For screenshot comparison (`pip install Pillow`)
- **Playwright MCP** *(optional)* — For Phase 4 visual verification ([`@anthropic-ai/playwright-mcp`](https://github.com/anthropic-ai/mcp-playwright))

## File Structure

```
figma-hybrid-orchestrator/
├── SKILL.md                              # Main skill (orchestration logic)
├── references/
│   ├── common-mismatches.md              # 9 mismatch patterns with detection & fixes
│   ├── phase-0-assessment.md             # Scoring rubric & metadata parsing
│   ├── phase-1-inference.md              # Color clustering, spacing, components
│   ├── phase-2-decomposition.md          # Section detection for large files
│   ├── phase-3-codegen.md                # React + Tailwind patterns + mismatch prevention
│   ├── phase-4-playwright.md             # Two-layer verification: visual + structural audit
│   └── decision-trees.md                 # Pipeline selection flowcharts
├── scripts/
│   ├── infer_tokens.py                   # Design token inference from raw values
│   └── compare_screenshots.py            # SSIM + region-aware + mismatch classification
└── assets/
    ├── sample_inferred_tokens.json       # Example Phase 1 output
    └── sample_quality_report.json        # Example Phase 0 output
```

## Usage

Once installed, the skill triggers automatically when you ask Claude Code to convert a Figma design:

```
Convert this Figma design to React components:
https://figma.com/design/abc123/MyDesign?node-id=1-2
```

The skill will assess the file, choose the right pipeline depth, and walk you through each phase.

### Scripts

The bundled scripts can also be used standalone:

**Infer design tokens:**

```bash
python scripts/infer_tokens.py \
  --colors "#0066cc,#fff,#212529,#dc3545,#28a745" \
  --spacing "4,8,16,24,32" \
  --fonts "Inter:16:400,Inter:24:700" \
  --radii "4,8,16" \
  --output tokens.json
```

**Compare screenshots (with element-level regions):**

```bash
# Basic comparison
python scripts/compare_screenshots.py \
  --reference figma_screenshot.png \
  --rendered playwright_screenshot.png \
  --output diff_report.json

# With element regions for Layer 2 comparison
python scripts/compare_screenshots.py \
  --reference figma.png \
  --rendered playwright.png \
  --regions element_regions.json \
  --output diff_report.json
```

The `--regions` file maps Figma node bounding boxes for element-by-element comparison:
```json
[
  {"name": "navigation", "x": 0, "y": 0, "width": 1699, "height": 48},
  {"name": "hero-section", "x": 0, "y": 0, "width": 1699, "height": 1433},
  {"name": "design-section", "x": 0, "y": 1433, "width": 1699, "height": 1288}
]
```

## Phase 4: Two-Layer Verification

Simple pixel diffing catches ~40% of real issues. Phase 4 adds a **structural audit layer** that uses Playwright `page.evaluate()` to measure actual CSS properties:

| Audit Check | What It Catches |
|---|---|
| Container widths | Sections at full viewport width instead of max-width |
| Section spacing | Collapsed vertical gaps between sections |
| Gradient text fills | Gradient/metallic text rendered as flat color |
| Image aspect ratios | Distorted logos and SVGs |
| Button styling | CTA buttons rendered as plain text links |
| Text alignment | Centered text rendered as left-aligned |
| Heading sizes | Font sizes >20% off from Figma values |

The iterative fix loop prioritizes: P0 (identity-breaking) → P1 (layout) → P2 (components) → P3 (polish).

## Figma MCP Tools Used

| Tool | Phase | Purpose |
|------|:---:|---------|
| `get_metadata` | 0, 2 | Node tree structure, bounding boxes |
| `get_variable_defs` | 0, 1 | Design token discovery |
| `get_code_connect_map` | 0, 3 | Component → codebase mappings |
| `get_design_context` | 1, 2, 3 | Structured code for nodes |
| `get_screenshot` | 2, 4 | Visual reference images |
| `get_code_connect_suggestions` | 1 | AI-suggested component mappings |

## Key References

- [Figma MCP Server Guide](https://github.com/figma/mcp-server-guide)
- [Structuring Figma Files for MCP](https://developers.figma.com/docs/figma-mcp-server/structure-figma-file/)
- [Custom Rules & Instructions](https://developers.figma.com/docs/figma-mcp-server/add-custom-rules/)
- [Code Connect Integration](https://developers.figma.com/docs/figma-mcp-server/code-connect-integration/)

## License

MIT
