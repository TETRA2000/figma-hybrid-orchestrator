---
name: figma-hybrid-orchestrator
description: >
  Convert Figma designs to React + Tailwind CSS code, especially unstructured files.
  Use this skill when the user wants to turn a Figma design (mockups, prototypes, design systems)
  into production-ready React components — particularly when the file lacks structure
  (no design tokens, no Code Connect, flat layers, generic naming like "Group 5").
  The skill assesses file quality, infers missing tokens and components, handles large files
  smartly via decomposition, generates React + Tailwind code, and optionally verifies
  pixel accuracy with Playwright. Works on ANY Figma file regardless of structure quality.
  Do NOT use for non-Figma design tools or when the user already has complete, working code.
---

# Figma Hybrid Orchestrator

Convert any Figma design to React + Tailwind CSS — even messy, unstructured files.

## How It Works

This skill runs an adaptive pipeline. It first scores the Figma file's structure quality (0–8), then selects the appropriate phases:

| Quality Score | File State | Phases Run |
|:---:|---|---|
| 7–8 | Well-structured (tokens, components, Code Connect) | 0 → 3 → 4 |
| 4–6 | Partially structured (some tokens or naming) | 0 → 2 → 3 → 4 |
| 0–3 | Unstructured (flat layers, no tokens, generic names) | 0 → 1 → 2 → 3 → 4 |

Phase 4 (Playwright verification) runs only if Playwright MCP is available. All other phases always succeed.

---

## Quick Start

The user provides a Figma URL or file key + node ID. Extract them:
- URL format: `https://figma.com/design/:fileKey/:fileName?node-id=:nodeId`
- The fileKey is the path segment after `/design/`
- The nodeId uses `:` separator (convert `-` from URL to `:`)

Then run Phase 0 to assess and decide the pipeline.

---

## Phase 0: Assessment (Always Run First)

**Purpose:** Score the file's structure quality to decide which phases to run.

**Steps:**

1. Call `get_metadata(nodeId, fileKey)` to get the node tree XML
2. Call `get_variable_defs(nodeId, fileKey)` to check for design tokens
3. Call `get_code_connect_map(nodeId, fileKey)` to check for component mappings

**Scoring rubric:**

| Criterion | Points | How to Check |
|---|:---:|---|
| Has reusable components | +2 | Metadata contains nodes with `type="COMPONENT"` or `type="COMPONENT_SET"` |
| Has variables/tokens | +2 | `get_variable_defs` returns non-empty result |
| Has semantic layer names | +1 | Layer names follow patterns like `Header`, `CardTitle`, `Button_Primary` (not `Group 5`, `Rectangle 42`) |
| Uses auto layout | +1 | Metadata nodes have `layoutMode` attribute |
| Has Code Connect mappings | +2 | `get_code_connect_map` returns entries |

**After scoring**, announce the result and selected pipeline to the user:

```
Design Quality Assessment:
- Score: 3/8 (Unstructured)
- Components: None detected
- Tokens: None found
- Naming: Generic (Group, Frame, Rectangle...)
- Auto Layout: Partial
- Code Connect: Not configured

→ Running full pipeline: Phase 0 → 1 → 2 → 3 → 4
```

Also count total nodes from metadata. If node count > 500, Phase 2 (decomposition) is mandatory regardless of score.

For full scoring details, see `references/phase-0-assessment.md`.

---

## Phase 1: Structure Inference (Score 0–3 Only)

**Purpose:** Infer missing design tokens and component patterns from the raw visual data.

**When to run:** Quality score is 0–3 (unstructured file).

**Steps:**

1. Sample 8–12 representative nodes from the metadata tree (pick diverse sizes and depths)
2. For each sampled node, call `get_design_context(nodeId, fileKey)` to get its code representation
3. From the returned code, extract all:
   - Fill colors (hex values)
   - Stroke colors
   - Font families, sizes, weights
   - Padding and gap values
   - Border radius values
4. Run `scripts/infer_tokens.py` with the collected values to cluster them into a token system
5. Identify repeated visual patterns (nodes with similar structure, size, and styles) as candidate components

**Output:** An `inferred_tokens.json` object with:
```json
{
  "colors": { "primary": "#0066cc", "gray-200": "#e5e7eb", ... },
  "spacing": { "base": 4, "scale": [0, 1, 2, 3, 4, 6, 8, 12, 16, 24, 32] },
  "typography": { "heading": { "family": "Inter", "size": 24, "weight": 700 }, ... },
  "radii": { "sm": 4, "md": 8, "lg": 16 },
  "components": [
    { "name": "Card", "instances": 8, "typical_size": [300, 200], "sample_node": "123:456" },
    ...
  ]
}
```

Present the inferred tokens to the user for review before proceeding to Phase 3.

For the full inference algorithm, see `references/phase-1-inference.md`.

---

## Phase 2: Decomposition (Large Files or Score < 7)

**Purpose:** Break large designs into manageable sections to avoid token overflow.

**When to run:** Node count > 500, OR quality score < 7, OR `get_design_context` would exceed ~25,000 tokens.

**Steps:**

1. Parse the metadata XML to extract each top-level child's bounding box (x, y, width, height)
2. Cluster children into logical sections using spatial analysis:
   - **Header zone:** Nodes in the top ~10% of the frame height, spanning full width
   - **Footer zone:** Nodes in the bottom ~10%
   - **Sidebar:** Nodes pinned to left or right edge, tall and narrow
   - **Content sections:** Remaining nodes, grouped by vertical position
3. For each section, call `get_design_context(nodeId, fileKey)` independently
4. Also call `get_screenshot(nodeId, fileKey)` for each section (needed for Phase 4)
5. Pass each section's context + inferred tokens (from Phase 1) to Phase 3

**Token budget rule:** If a section has > 200 child nodes, split it further. Aim for sections with 50–150 nodes each.

For the full decomposition algorithm, see `references/phase-2-decomposition.md`.

---

## Phase 3: Code Generation

**Purpose:** Generate React + Tailwind CSS components from design context.

**Always runs.** This is the core output phase.

**Steps:**

1. Check if Code Connect mappings exist (from Phase 0). If yes, use them as the primary component source
2. If no Code Connect, check if Phase 1 produced inferred components. Use those as the component library
3. For each section (or the whole frame if no decomposition):
   a. Take the `get_design_context` output (reference HTML/CSS code)
   b. Transform it into a React functional component with TypeScript
   c. Map colors to Tailwind classes (use inferred tokens or standard Tailwind palette)
   d. Map spacing to Tailwind utilities (p-4, gap-6, etc.)
   e. Map layout to flex/grid utilities
   f. Extract images/SVGs — use the localhost URLs from Figma MCP directly, do NOT use placeholders
4. If multiple sections were decomposed in Phase 2, create a parent layout component that assembles them
5. Generate a `tailwind.config.ts` extension if custom colors were inferred in Phase 1

**Component template:**

```tsx
import React from 'react';

interface ComponentNameProps {
  // Props inferred from design variants, if any
}

export default function ComponentName({}: ComponentNameProps) {
  return (
    <div className="flex flex-col gap-6 p-8 bg-white">
      {/* Generated structure */}
    </div>
  );
}
```

**Critical rules:**
- NEVER use hardcoded pixel values in className — always use Tailwind utilities
- NEVER create placeholder images — use Figma MCP localhost URLs for all assets
- NEVER invent component libraries — use Code Connect mappings or inferred components only
- Always preserve the visual hierarchy from the Figma frame
- Use `className` (not `class`), use self-closing tags for void elements

For full patterns and examples, see `references/phase-3-codegen.md`.

---

## Phase 4: Playwright Verification (Optional)

**Purpose:** Visually verify the generated code matches the Figma design.

**When to run:** Playwright MCP is available AND the user wants pixel verification.

**If Playwright MCP is not available,** skip this phase and note in the output:
```
Phase 4 skipped: Playwright MCP not detected.
To enable visual verification, configure @anthropic-ai/playwright-mcp or similar.
```

**Steps:**

1. Create a minimal HTML fixture that renders the generated React component:
   - Include Tailwind CSS via CDN
   - Mount the component with ReactDOM
   - Save as a temp `.html` file
2. Use Playwright to open the fixture
3. For each breakpoint (320px, 768px, 1024px, 1440px):
   a. Resize viewport
   b. Take a Playwright screenshot
   c. Get the corresponding Figma screenshot via `get_screenshot(nodeId, fileKey)`
   d. Run `scripts/compare_screenshots.py` to compute SSIM score and diff regions
4. If SSIM < 0.85 at any breakpoint:
   a. Analyze the diff regions — classify errors (spacing, color, missing element, wrong size)
   b. Apply targeted fixes to the component code
   c. Re-render and re-compare (max 3 iterations)
5. Generate a verification report:

```
Verification Report:
| Breakpoint | SSIM Score | Status |
|------------|-----------|--------|
| 320px      | 0.92      | PASS   |
| 768px      | 0.88      | PASS   |
| 1024px     | 0.91      | PASS   |
| 1440px     | 0.87      | PASS   |

Iterations: 2 of 3
Remaining issues: Minor spacing difference in footer (±2px)
```

For the full verification workflow, see `references/phase-4-playwright.md`.

---

## Output Checklist

At the end of the pipeline, deliver:

- [ ] React component file(s) (`.tsx`) with Tailwind CSS
- [ ] `tailwind.config.ts` extension (if custom tokens were inferred)
- [ ] `inferred_tokens.json` (if Phase 1 ran)
- [ ] Design quality report (from Phase 0)
- [ ] Verification report with screenshots (if Phase 4 ran)
- [ ] List of any unresolved issues or manual steps needed

---

## Troubleshooting

**"get_design_context response exceeds token limit"**
→ Increase `MAX_MCP_OUTPUT_TOKENS` env var, or ensure Phase 2 decomposition is running. Reduce section size.

**"No components detected but file looks structured"**
→ The file may use groups instead of components. Score will be lower than expected. Phase 1 will compensate by inferring patterns.

**"Playwright screenshots don't match due to font differences"**
→ Font rendering varies by OS. Focus on layout/spacing accuracy. Color diffs > 5% and layout diffs > 10px are real issues; font anti-aliasing differences are not.

**"Code Connect map is empty"**
→ Code Connect requires explicit setup by the design team. Fall back to `get_code_connect_suggestions` for AI-suggested mappings, or use Phase 1 inference.

---

## Reference Files

| File | When to Read |
|------|-------------|
| `references/phase-0-assessment.md` | Full scoring rubric, metadata parsing examples |
| `references/phase-1-inference.md` | Color clustering algorithm, spacing extraction, pattern detection |
| `references/phase-2-decomposition.md` | Section detection algorithm, token budget management |
| `references/phase-3-codegen.md` | React + Tailwind patterns, Code Connect handling, assembly |
| `references/phase-4-playwright.md` | Fixture setup, screenshot comparison, iterative fix loop |
| `references/decision-trees.md` | Flowcharts for pipeline selection, decomposition triggers |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/infer_tokens.py` | Cluster colors and spacing values into a design token system |
| `scripts/compare_screenshots.py` | Compute SSIM score and diff regions between two screenshots |
