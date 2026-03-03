# Phase 4: Playwright Verification — Detailed Reference

## Purpose

Visually verify that the generated React + Tailwind code matches the original Figma design. This phase renders the output in a real browser, screenshots it at multiple breakpoints, and compares against the Figma screenshots. Mismatches trigger targeted fixes in an iterative loop.

## Prerequisites

- **Playwright MCP server** must be configured (e.g., `@anthropic-ai/playwright-mcp` or `@anthropic-ai/mcp-playwright`)
- **Node.js** available for rendering the component fixture
- **Figma screenshots** from `get_screenshot` calls (collected during Phase 2 or Phase 3)

If Playwright MCP is not available, skip this phase and report:
```
Phase 4 skipped: Playwright MCP not detected.
Tip: Install @anthropic-ai/playwright-mcp to enable visual verification.
```

## Step 1: Create a Rendering Fixture

Generate a minimal HTML file that renders the React component with Tailwind:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Figma Verification Fixture</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    // Inject custom Tailwind config if Phase 1 generated one
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            primary: '#0066cc',
            secondary: '#6c757d',
            surface: '#f8f9fa',
          }
        }
      }
    }
  </script>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
</head>
<body class="m-0 p-0">
  <div id="root"></div>
  <script type="text/babel">
    // Inline the generated component here
    function LandingPage() {
      return (
        // ... generated JSX ...
      );
    }
    ReactDOM.createRoot(document.getElementById('root')).render(<LandingPage />);
  </script>
</body>
</html>
```

Save this file to a temporary location and serve it (or open directly with `file://`).

## Step 2: Screenshot at Multiple Breakpoints

Use Playwright to capture the rendered output at standard breakpoints:

| Breakpoint | Width | Viewport Height | Represents |
|---|:---:|:---:|---|
| Mobile | 320px | 568px | iPhone SE |
| Tablet | 768px | 1024px | iPad |
| Desktop | 1024px | 768px | Small laptop |
| Wide | 1440px | 900px | Standard desktop |

**Playwright commands for each breakpoint:**

```
1. Navigate to the fixture URL
2. Set viewport size to (width, height)
3. Wait for page to fully render (networkidle or fixed delay)
4. Take full-page screenshot
5. Save as verification_{breakpoint}.png
```

## Step 3: Get Figma Reference Screenshots

For comparison, get Figma screenshots at matching sizes:

```
Call: get_screenshot(nodeId, fileKey) for each section
```

The Figma screenshot represents the design intent. The Playwright screenshot represents the implementation.

Note: Figma screenshots are at the design's native size. If the design was created at 1440px width, the 1440px comparison will be most accurate. Other breakpoints test responsive behavior that may not exist in the Figma file.

**Strategy:**
- 1440px (or native width): **strict comparison** — should match closely
- Other breakpoints: **structural comparison** — check that layout adapts reasonably

## Step 4: Compare Screenshots

Use `scripts/compare_screenshots.py` to compute difference metrics:

**Metrics:**
- **SSIM (Structural Similarity Index):** 0.0 (completely different) to 1.0 (identical). Target: > 0.85
- **Pixel diff percentage:** Percentage of pixels that differ by > threshold. Target: < 15%
- **Diff region bounding boxes:** Rectangular areas where differences concentrate

**Comparison command:**
```bash
python scripts/compare_screenshots.py \
  --reference figma_screenshot.png \
  --rendered playwright_screenshot.png \
  --output diff_report.json
```

**Output:**
```json
{
  "ssim": 0.82,
  "pixel_diff_pct": 18.3,
  "diff_regions": [
    { "x": 100, "y": 400, "width": 300, "height": 50, "severity": "high" },
    { "x": 800, "y": 200, "width": 100, "height": 100, "severity": "medium" }
  ],
  "pass": false,
  "threshold": { "ssim_min": 0.85, "pixel_diff_max": 15.0 }
}
```

## Step 5: Iterative Fix Loop

If the comparison fails (SSIM < 0.85 OR pixel diff > 15%), analyze and fix:

### Error Classification

Examine the diff regions and classify the errors:

| Error Type | Visual Signal | Fix Strategy |
|---|---|---|
| **Spacing off** | Content shifted vertically/horizontally | Adjust padding/margin/gap utilities |
| **Color wrong** | Region has different hue/saturation | Fix the color class mapping |
| **Missing element** | Large blank region in rendered vs content in Figma | Re-check the design context for missing nodes |
| **Wrong size** | Element too large or too small | Fix width/height utilities |
| **Font mismatch** | Text renders differently | Usually acceptable — font rendering varies by OS |
| **Image missing** | White/broken image area | Check localhost URL is still valid |

### Fix Strategy

For each classified error:

1. **Spacing:** Compare the Figma node's padding/gap values against the generated Tailwind classes. Adjust classes.
2. **Color:** Look up the correct hex from design context, re-map to Tailwind.
3. **Missing element:** Re-fetch the design context for that specific region and add the missing node.
4. **Wrong size:** Check if the Figma node had fixed dimensions and add explicit width/height.

### Iteration Limit

Maximum 3 iterations. After each fix:
1. Update the fixture
2. Re-screenshot with Playwright
3. Re-compare
4. If pass → done. If fail and iterations < 3 → fix again. If iterations = 3 → report remaining issues.

## Step 6: Generate Verification Report

```
Verification Report
═══════════════════

| Breakpoint | SSIM  | Pixel Diff | Status |
|------------|-------|-----------|--------|
| 320px      | 0.79  | 22.1%     | WARN   |
| 768px      | 0.88  | 11.5%     | PASS   |
| 1024px     | 0.91  | 8.2%      | PASS   |
| 1440px     | 0.93  | 5.1%      | PASS   |

Iterations: 2 of 3
Total fixes applied: 4
  - 2 spacing adjustments (gap-4 → gap-6 in Features section)
  - 1 color correction (bg-gray-100 → bg-gray-50 in Card)
  - 1 missing element added (decorative divider in Footer)

Remaining issues:
  - 320px mobile: Layout doesn't collapse to single column (Figma design is desktop-only)
  - Minor font rendering differences (Inter vs system fallback)

Recommendation: The 320px differences are expected since the Figma design
only shows a desktop layout. Consider adding mobile-specific responsive
classes manually.
```

## Thresholds

| Metric | Pass | Warn | Fail |
|---|:---:|:---:|:---:|
| SSIM (native width) | ≥ 0.85 | 0.75–0.84 | < 0.75 |
| SSIM (other widths) | ≥ 0.75 | 0.65–0.74 | < 0.65 |
| Pixel diff (native) | ≤ 15% | 15–25% | > 25% |
| Pixel diff (other) | ≤ 25% | 25–35% | > 35% |

Note: Non-native breakpoints have looser thresholds because the Figma design may not include responsive variants.

## Graceful Degradation

If any step fails, Phase 4 degrades gracefully:

| Failure | Behavior |
|---|---|
| Playwright MCP not available | Skip Phase 4 entirely |
| Fixture fails to render | Report error, suggest checking generated code for syntax issues |
| Screenshot comparison script errors | Report "verification inconclusive", deliver code without verification |
| All 3 iterations fail to converge | Deliver code + full diff report + list of remaining issues |
| Figma screenshot not available | Skip comparison for that section, note in report |

Phase 4 never blocks code delivery. It enhances confidence but is not a gate.
