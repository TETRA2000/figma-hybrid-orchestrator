# Decision Trees — Pipeline Selection Reference

## Main Pipeline Decision

```
START: User provides Figma URL/file key + node ID
  │
  ▼
Phase 0: Run Assessment
  │ Call get_metadata, get_variable_defs, get_code_connect_map
  │ Calculate quality score (0–8)
  │ Count total nodes
  │
  ├─── Score 7–8 (Well-structured)
  │      │
  │      ├─ Nodes ≤ 500 ──→ Phase 3 → Phase 4
  │      │                   (Direct codegen, single fetch)
  │      │
  │      └─ Nodes > 500 ──→ Phase 2 → Phase 3 → Phase 4
  │                          (Decompose first, then codegen)
  │
  ├─── Score 4–6 (Partially structured)
  │      │
  │      ├─ Nodes ≤ 500 ──→ Phase 2 → Phase 3 → Phase 4
  │      │                   (Decompose for better section handling)
  │      │
  │      └─ Nodes > 500 ──→ Phase 2 → Phase 3 → Phase 4
  │                          (Decompose mandatory)
  │
  └─── Score 0–3 (Unstructured)
         │
         └─ Always ────────→ Phase 1 → Phase 2 → Phase 3 → Phase 4
                              (Full pipeline: infer → decompose → codegen → verify)
```

## Phase 1 Decision: Should We Infer Structure?

```
Quality Score ≤ 3?
  │
  ├─ YES → Run Phase 1 (Structure Inference)
  │         │
  │         ├─ Sample 8–12 nodes
  │         ├─ Extract colors, spacing, typography
  │         ├─ Cluster into tokens
  │         ├─ Detect component patterns
  │         └─ Present to user for review
  │
  └─ NO (Score ≥ 4) → Skip Phase 1
           │
           ├─ Score 4–6: File has some structure
           │   Use get_variable_defs tokens directly
           │   May still lack Code Connect
           │
           └─ Score 7–8: File is well-structured
               Use tokens + Code Connect as-is
```

## Phase 2 Decision: Should We Decompose?

```
Node count > 500?
  │
  ├─ YES → Decompose (mandatory)
  │
  └─ NO
      │
      ├─ Score < 7? ──→ Decompose (recommended)
      │                  Section-by-section produces better code
      │                  for partially structured files
      │
      └─ Score ≥ 7? ──→ Skip decomposition
                         Well-structured files work fine
                         with a single get_design_context call
```

**Additional decomposition triggers:**
```
Previous get_design_context failed with token overflow?
  └─ YES → Decompose (mandatory, reduce section size)

Frame has clear visual sections (header + content + footer)?
  └─ YES → Decompose (recommended, produces modular components)

Frame is a single component (card, dialog, button)?
  └─ YES → Skip decomposition (process as single unit)
```

## Phase 4 Decision: Should We Verify?

```
Playwright MCP available?
  │
  ├─ NO → Skip Phase 4
  │        Report: "Verification skipped, Playwright MCP not detected"
  │
  └─ YES
      │
      ├─ User requested verification? ──→ Run Phase 4
      │
      ├─ File is critical / pixel-perfect needed? ──→ Run Phase 4
      │
      └─ Quick conversion / exploration? ──→ Offer Phase 4 as optional
           "Would you like me to verify the output against the Figma design?"
```

## Summary: Score → Phases Lookup Table

| Score | Phases | Estimated MCP Calls | Estimated Time |
|:---:|---|:---:|---|
| 8 | 0, 3, 4 | 4–6 | Fast (1–2 min) |
| 7 | 0, 3, 4 | 4–6 | Fast (1–2 min) |
| 6 | 0, 2, 3, 4 | 8–15 | Medium (3–5 min) |
| 5 | 0, 2, 3, 4 | 8–15 | Medium (3–5 min) |
| 4 | 0, 2, 3, 4 | 8–15 | Medium (3–5 min) |
| 3 | 0, 1, 2, 3, 4 | 15–25 | Slow (5–10 min) |
| 2 | 0, 1, 2, 3, 4 | 15–25 | Slow (5–10 min) |
| 1 | 0, 1, 2, 3, 4 | 15–25 | Slow (5–10 min) |
| 0 | 0, 1, 2, 3, 4 | 15–25 | Slow (5–10 min) |

## Rate Limit Awareness

Figma MCP API limits by plan:

| Plan | Monthly Limit |
|---|---|
| Starter (Dev Mode) | 6 calls/month |
| Full (Dev Mode seat) | 2,000 calls/month |
| Organization | 5,000 calls/month |

For Starter plan users, the full pipeline (score 0–3) may consume 15–25 calls — nearly impossible within the 6-call limit. Recommend:
- Skip Phase 4 (saves 4–12 calls)
- Minimize Phase 1 sampling (use 4–5 nodes instead of 8–12)
- Use `get_metadata` liberally (lightweight, may not count toward limits)

Always announce estimated call count before starting the pipeline so the user can decide.
