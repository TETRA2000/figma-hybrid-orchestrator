# Phase 4: Playwright Verification — Detailed Reference

## Purpose

Visually AND structurally verify that the generated React + Tailwind code matches the original Figma design. This phase goes beyond pixel-level comparison — it performs **element-level verification** that catches the real-world mismatches LLMs produce: missing gradients, distorted SVGs, collapsed spacing, unstyled buttons, and wrong alignment.

## Prerequisites

- **Playwright MCP server** must be configured (e.g., `@anthropic-ai/playwright-mcp` or `@anthropic-ai/mcp-playwright`)
- **Node.js** available for rendering the component fixture
- **Figma screenshots** from `get_screenshot` calls (collected during Phase 2 or Phase 3)

If Playwright MCP is not available, skip this phase and report:
```
Phase 4 skipped: Playwright MCP not detected.
Tip: Install @anthropic-ai/playwright-mcp to enable visual verification.
```

## The Two-Layer Approach

Simple pixel diffing (SSIM) catches ~40% of real issues. The other 60% require **structural verification** — measuring actual CSS properties against the Figma spec. Phase 4 uses both layers:

**Layer 1: Visual comparison** — Screenshot SSIM for overall fidelity
**Layer 2: Structural audit** — Element-by-element CSS property checks via Playwright `page.evaluate()`

Layer 2 is where the high-impact bugs are caught.

---

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
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            /* inject inferred or real tokens here */
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
    function Page() { return ( /* ... */ ); }
    ReactDOM.createRoot(document.getElementById('root')).render(<Page />);
  </script>
</body>
</html>
```

## Step 2: Layer 1 — Visual Screenshot Comparison

### Capture at the Design's Native Width

The Figma design has a specific width (e.g., 1699px for this iPhone 17 Pro page). Screenshot at that exact width for the most meaningful comparison.

```
1. Navigate to the fixture URL
2. Set viewport width to Figma frame width (from metadata)
3. Wait for full render (networkidle + 1s extra for images)
4. Take full-page screenshot
```

### Run Pixel Comparison

```bash
python scripts/compare_screenshots.py \
  --reference figma_screenshot.png \
  --rendered playwright_screenshot.png \
  --output layer1_report.json
```

This gives a rough overall score. But the **real value** comes from Layer 2.

---

## Step 3: Layer 2 — Structural Audit (The Critical Step)

Use Playwright's `page.evaluate()` to measure actual CSS properties of rendered elements. Check each item against the Figma metadata and design context.

### Audit Checklist

Run these checks in priority order. Each maps to a common mismatch pattern (see `references/common-mismatches.md`):

#### Check 1: Container Width & Margins (Mismatch M3)

```javascript
// In Playwright page.evaluate():
// Figma says content starts at x=309.5 in a 1699px frame → ~1080px content area
const sections = document.querySelectorAll('section, [class*="max-w"]');
sections.forEach(s => {
  const rect = s.getBoundingClientRect();
  const computed = getComputedStyle(s);
  console.log(`Section: width=${rect.width}, marginLeft=${computed.marginLeft}, maxWidth=${computed.maxWidth}`);
});
```

**Expected:** Content sections should have `max-width` close to the Figma content width (1080px in this case), centered with auto margins.

**Fail condition:** Section width equals viewport width (no max-width constraint).

#### Check 2: Vertical Spacing Between Sections (Mismatch M4)

```javascript
const sections = document.querySelectorAll('section');
for (let i = 0; i < sections.length - 1; i++) {
  const current = sections[i].getBoundingClientRect();
  const next = sections[i + 1].getBoundingClientRect();
  const gap = next.top - current.bottom;
  console.log(`Gap between section ${i} and ${i+1}: ${gap}px`);
}
```

**Expected:** Gaps should be within ±20% of the Figma metadata gaps (calculated from y-offsets).

**Fail condition:** Gap is < 50% of expected OR sections overlap.

#### Check 3: Text Gradient / Special Fills (Mismatch M1)

```javascript
// Check if gradient text is actually rendered with gradient
const gradientTexts = document.querySelectorAll('[class*="bg-gradient"], [class*="bg-clip-text"]');
gradientTexts.forEach(el => {
  const style = getComputedStyle(el);
  console.log(`Gradient text: backgroundImage=${style.backgroundImage}, webkitTextFillColor=${style.webkitTextFillColor}`);
});

// Also check: are there headings that SHOULD have gradients but don't?
const allHeadings = document.querySelectorAll('h1, h2, h3, [class*="text-4xl"], [class*="text-5xl"]');
allHeadings.forEach(h => {
  const style = getComputedStyle(h);
  const color = style.color;
  console.log(`Heading "${h.textContent.substring(0, 20)}": color=${color}, bgImage=${style.backgroundImage}`);
});
```

**Expected:** If the Figma screenshot shows gradient/metallic text, the rendered heading should have `background-image: linear-gradient(...)` and `-webkit-text-fill-color: transparent`.

**Fail condition:** Heading renders as flat color when Figma shows gradient.

#### Check 4: Image / SVG Aspect Ratios (Mismatch M2)

```javascript
const images = document.querySelectorAll('img, svg');
images.forEach(img => {
  if (img.tagName === 'IMG') {
    const natural = { w: img.naturalWidth, h: img.naturalHeight };
    const rendered = { w: img.clientWidth, h: img.clientHeight };
    const naturalRatio = natural.w / natural.h;
    const renderedRatio = rendered.w / rendered.h;
    const distortion = Math.abs(naturalRatio - renderedRatio) / naturalRatio;
    console.log(`IMG: natural=${natural.w}x${natural.h}, rendered=${rendered.w}x${rendered.h}, distortion=${(distortion*100).toFixed(1)}%`);
  } else {
    const vb = img.getAttribute('viewBox');
    const rect = img.getBoundingClientRect();
    console.log(`SVG: viewBox=${vb}, rendered=${rect.width}x${rect.height}`);
  }
});
```

**Expected:** Distortion < 5%.

**Fail condition:** Any image with distortion > 10%.

#### Check 5: Button Styling (Mismatch M5)

```javascript
const buttons = document.querySelectorAll('a, button');
buttons.forEach(btn => {
  const style = getComputedStyle(btn);
  const text = btn.textContent.trim();
  if (['Buy', 'Pre-order', 'Learn more', 'Order', 'Shop'].some(t => text.includes(t))) {
    console.log(`Button "${text}": bg=${style.backgroundColor}, borderRadius=${style.borderRadius}, padding=${style.padding}, display=${style.display}`);
  }
});
```

**Expected:** CTA buttons (Pre-order, Buy) should have non-transparent `background-color`, `border-radius > 0`, and visible padding.

**Fail condition:** Primary CTA has `background-color: transparent` or `rgba(0,0,0,0)`.

#### Check 6: Text Alignment (Mismatch M7)

```javascript
// Check headings and paragraphs for correct alignment
const textElements = document.querySelectorAll('h1, h2, h3, h4, p');
textElements.forEach(el => {
  const style = getComputedStyle(el);
  const rect = el.getBoundingClientRect();
  const parentRect = el.parentElement.getBoundingClientRect();
  const centerOffset = Math.abs((rect.left + rect.width/2) - (parentRect.left + parentRect.width/2));
  console.log(`"${el.textContent.substring(0, 30)}": textAlign=${style.textAlign}, centerOffset=${centerOffset.toFixed(0)}px`);
});
```

**Expected:** Centered text elements have `textAlign: center` or `centerOffset < 20px`.

**Fail condition:** Element should be centered (per Figma) but has `textAlign: left` and `centerOffset > 50px`.

#### Check 7: Heading Sizes (Mismatch M6)

```javascript
const headings = document.querySelectorAll('h1, h2, h3');
headings.forEach(h => {
  const style = getComputedStyle(h);
  console.log(`"${h.textContent.substring(0, 30)}": fontSize=${style.fontSize}, fontWeight=${style.fontWeight}, lineHeight=${style.lineHeight}`);
});
```

**Expected:** Font sizes within ±15% of Figma metadata text node heights.

**Fail condition:** Rendered font-size is > 130% or < 70% of Figma value.

---

## Step 4: Classify and Prioritize Fixes

After both layers complete, compile a prioritized fix list:

```
Structural Audit Results:
═══════════════════════════

P0 — CRITICAL (breaks visual identity):
  [ ] M1: "Pro" heading rendered as flat gray, should have gold gradient
       → Fix: Add bg-gradient-to-b with gold color stops + bg-clip-text
  [ ] M2: Apple logo SVG distorted (18x22 → 200x50, 340% width distortion)
       → Fix: Change to h-[22px] w-auto, remove explicit width

P1 — LAYOUT (visually broken):
  [ ] M3: Content sections full-width instead of 1080px max
       → Fix: Add max-w-[1080px] mx-auto wrapper to each section
  [ ] M4: Section gaps 20px instead of 160px (87% smaller)
       → Fix: Add gap-[160px] or explicit spacers between sections

P2 — COMPONENTS (wrong but functional):
  [ ] M5: "Pre-order" button renders as plain text link
       → Fix: Add bg-blue-600 text-white rounded-full px-7 py-3
  [ ] M5: Nav "Buy" button unstyled
       → Fix: Add bg-blue-600 text-white rounded-full px-4 py-1.5 text-xs

P3 — POLISH (minor differences):
  [ ] M7: "DESIGN" label left-aligned, should be left-aligned within container
       → Acceptable: container alignment is the real issue (M3)
```

## Step 5: Iterative Fix Loop

Maximum 3 iterations. Fix in priority order (P0 → P1 → P2 → P3):

**Iteration 1:** Fix all P0 issues (gradient text, distorted images)
**Iteration 2:** Fix all P1 issues (container widths, spacing)
**Iteration 3:** Fix P2 issues (button styles, interactive elements)

After each fix:
1. Update the component code
2. Re-render in Playwright
3. Re-run the structural audit (Layer 2)
4. Re-run screenshot comparison (Layer 1)
5. If all P0 and P1 pass → declare success. P2/P3 remaining issues go in the report.

## Step 6: Generate Verification Report

```
Verification Report
═══════════════════

Layer 1 — Visual Comparison:
| Breakpoint | SSIM  | Pixel Diff | Status |
|------------|-------|-----------|--------|
| 1699px     | 0.91  | 7.2%      | PASS   |

Layer 2 — Structural Audit:
| Check               | Status | Detail                                    |
|---------------------|--------|-------------------------------------------|
| Container widths    | PASS   | max-w-[1080px] applied to all sections    |
| Section spacing     | PASS   | Gaps within ±20% of Figma spec            |
| Gradient text       | PASS   | "Pro" has gold gradient (fixed iteration 1)|
| Image aspect ratios | PASS   | Logo 18x22 preserved (fixed iteration 1)  |
| Button styles       | PASS   | Pre-order: blue pill (fixed iteration 2)  |
| Text alignment      | PASS   | Centered where Figma centers              |
| Heading sizes       | WARN   | H2 is 64px, Figma shows 76px (±15%)      |

Iterations: 2 of 3
Fixes applied: 6
  P0: 2 (gradient text, SVG aspect ratio)
  P1: 2 (container max-width, section gaps)
  P2: 2 (Pre-order button, Buy button)

Remaining:
  - H2 size ±15% — within tolerance but noticeable
  - Mobile breakpoints untested (design is desktop-only)
```

## Thresholds

### Layer 1 (Visual)

| Metric | Pass | Warn | Fail |
|---|:---:|:---:|:---:|
| SSIM (native width) | ≥ 0.85 | 0.75–0.84 | < 0.75 |
| Pixel diff (native) | ≤ 15% | 15–25% | > 25% |

### Layer 2 (Structural)

| Check | Pass | Warn | Fail |
|---|---|---|---|
| Container width | Within ±5% of Figma | Within ±15% | > 15% off or no max-width |
| Section gaps | Within ±20% of Figma | Within ±40% | > 40% off or collapsed |
| Gradient text | Has gradient CSS | Has flat color close to gradient midpoint | Wrong color entirely |
| Image aspect ratio | Distortion < 5% | 5–15% | > 15% |
| Button styling | Has bg + radius + padding | Has some styling | Plain text link |
| Text alignment | Matches Figma | Off by < 20px | Opposite alignment |
| Font sizes | Within ±10% | ±10–20% | > 20% off |

## Graceful Degradation

| Failure | Behavior |
|---|---|
| Playwright MCP not available | Skip Phase 4 entirely, note in output |
| Fixture fails to render | Report syntax error, suggest fix |
| Layer 1 fails but Layer 2 passes | Trust Layer 2 (pixel diffs may be fonts/antialiasing) |
| Layer 2 JS errors | Fall back to Layer 1 only, report partial audit |
| All 3 iterations fail to converge | Deliver code + full report with remaining P0/P1 issues highlighted |

Phase 4 never blocks code delivery. It enhances confidence but is not a gate.
