# Phase 0: Design Quality Assessment — Detailed Reference

## Purpose

Score the Figma file's structure quality (0–8) to determine which pipeline phases are needed. This phase is lightweight — it uses only metadata and quick checks, never full `get_design_context`.

## Step-by-Step

### 1. Get the Node Tree

```
Call: get_metadata(nodeId, fileKey)
```

This returns XML like:
```xml
<document name="My Design">
  <page id="0:1" name="Page 1">
    <frame id="1:2" name="Hero Section" width="1440" height="800" layoutMode="HORIZONTAL">
      <component id="1:3" name="Button/Primary" width="120" height="40">
        <text id="1:4" name="Label" characters="Click me" />
      </component>
      <rectangle id="1:5" name="Rectangle 42" width="300" height="200" />
    </frame>
  </page>
</document>
```

### 2. Score Each Criterion

#### Has Components (+2 points)

Scan the metadata XML for nodes with type `COMPONENT`, `COMPONENT_SET`, or `INSTANCE`.

**Scoring:**
- 2+ unique component definitions → +2
- 1 component definition → +1
- No components → +0

**How to check in metadata:**
Look for `<component ...>` or `<componentSet ...>` tags. Instance nodes (`<instance ...>`) indicate component usage but not definition — count definitions.

#### Has Variables/Tokens (+2 points)

```
Call: get_variable_defs(nodeId, fileKey)
```

**Scoring:**
- Returns 5+ variables → +2
- Returns 1–4 variables → +1
- Returns empty → +0

Variables include color tokens (`primary/500`), spacing values (`spacing/md`), and typography scales. A well-structured file typically has 20+ variables.

#### Has Semantic Layer Names (+1 point)

Analyze the `name` attributes from metadata. Compare against patterns:

**Semantic names (good):** `Header`, `NavigationBar`, `CardTitle`, `Button_Primary`, `HeroImage`, `FooterLinks`

**Generic names (bad):** `Group 5`, `Frame 127`, `Rectangle 42`, `Vector`, `Ellipse 3`

**Scoring heuristic:**
- Count total named nodes (excluding auto-generated names)
- Count nodes with names matching `^(Group|Frame|Rectangle|Vector|Ellipse|Line|Star|Polygon)\s*\d*$`
- If generic names are > 60% of total → +0
- If generic names are 30–60% → +0.5 (round to +1 if other scores are high)
- If generic names are < 30% → +1

#### Uses Auto Layout (+1 point)

Check metadata for `layoutMode` attribute on frame nodes.

**Scoring:**
- 50%+ of frames use auto layout → +1
- < 50% → +0

Auto layout presence means the design has responsive intent, which produces much better code.

#### Has Code Connect Mappings (+2 points)

```
Call: get_code_connect_map(nodeId, fileKey)
```

**Scoring:**
- Returns 3+ mapped components → +2
- Returns 1–2 mapped components → +1
- Returns empty → +0

Code Connect is the highest-value signal. When present, the agent can generate code that directly references existing codebase components.

### 3. Calculate Total Score and Select Pipeline

| Total Score | Classification | Pipeline |
|:---:|---|---|
| 0–3 | Unstructured | Phase 0 → 1 → 2 → 3 → 4 |
| 4–6 | Partially structured | Phase 0 → 2 → 3 → 4 |
| 7–8 | Well-structured | Phase 0 → 3 → 4 |

### 4. Count Nodes for Decomposition Check

Count all nodes in the metadata XML. If total > 500, Phase 2 is mandatory regardless of quality score.

**Estimation formula for token overflow:**
```
estimated_tokens = node_count × 70  (average tokens per node in get_design_context)
```

If `estimated_tokens > 25000`, decomposition is needed.

## Example Assessment Output

```json
{
  "score": 3,
  "breakdown": {
    "components": { "points": 0, "detail": "No COMPONENT or COMPONENT_SET nodes found" },
    "variables": { "points": 1, "detail": "3 variables found (2 colors, 1 spacing)" },
    "naming": { "points": 1, "detail": "28% generic names (below 30% threshold)" },
    "auto_layout": { "points": 1, "detail": "62% of frames use layoutMode" },
    "code_connect": { "points": 0, "detail": "No Code Connect mappings found" }
  },
  "node_count": 347,
  "estimated_tokens": 24290,
  "decomposition_needed": false,
  "pipeline": ["phase-0", "phase-1", "phase-2", "phase-3", "phase-4"],
  "warnings": [
    "No components detected — Phase 1 will infer component patterns",
    "No Code Connect — generated code will use generic component names"
  ]
}
```

## Common File Archetypes

| Archetype | Typical Score | Notes |
|---|:---:|---|
| Design system library | 7–8 | Components, tokens, often Code Connect |
| Marketing landing page (by designer) | 4–6 | Some auto layout, semantic names, few tokens |
| Quick mockup / wireframe | 2–4 | Partial structure, generic names |
| Screenshot-to-Figma import | 0–1 | Flat images, no structure at all |
| Developer handoff file | 5–7 | Structured for dev, may lack tokens |
| Old legacy file | 1–3 | Pre-auto-layout, groups everywhere |
