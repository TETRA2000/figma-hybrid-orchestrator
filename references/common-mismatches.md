# Common Design-to-Code Mismatches — Catalog & Fixes

This reference catalogs the most frequent and impactful mismatches that occur when converting Figma designs to code. Each entry includes how to detect it, why it happens, and the specific fix. These patterns were identified from real-world Figma MCP conversions.

## Severity Classification

- **P0 — Breaks visual identity**: Gradient text missing, brand colors wrong, logo distorted
- **P1 — Layout broken**: Sections misaligned, spacing collapsed, wrong container widths
- **P2 — Component wrong**: Button styles, interactive element shapes, icon sizing
- **P3 — Minor polish**: Font weight off by one step, border-radius slightly different

Always fix P0 and P1 before moving to P2 and P3.

---

## M1: Gradient / Special Text Effects Missing

**What it looks like:** Text that should have a gradient, metallic, or special fill renders as flat gray or black.

**Why it happens:** Figma represents gradient text as a fill on a text node. The MCP `get_design_context` may output this as a simple `color` property, losing the gradient. LLMs often ignore gradient CSS or simplify it.

**How to detect:**
- In `get_design_context` output, look for text nodes with fills that contain `gradient`, `linearGradient`, or multiple color stops
- In Figma metadata, text nodes where the rendered color looks metallic/gradient in the screenshot but `get_design_context` returns a flat color
- Compare: if a heading in the Figma screenshot has visible color variation but the rendered version is monotone

**Fix pattern (CSS):**
```css
.gradient-text {
  background: linear-gradient(180deg, #c9a96e 0%, #87704e 50%, #c9a96e 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
```

**Fix pattern (Tailwind):**
```tsx
<span className="bg-gradient-to-b from-[#c9a96e] via-[#87704e] to-[#c9a96e] bg-clip-text text-transparent">
  Pro
</span>
```

**Prevention:** When processing text nodes in Phase 3, always call `get_design_context` on the specific text node (not just the parent) to capture gradient fills. If the screenshot shows any non-flat text color, explicitly check for gradients.

---

## M2: SVG / Image Aspect Ratio Distortion

**What it looks like:** Logos, icons, or images appear stretched, squashed, or wrong proportions.

**Why it happens:** The code sets explicit width AND height that don't match the SVG's native aspect ratio, or uses `width: 100%` without constraining height. The Figma MCP localhost URL may serve the asset at a different aspect ratio than expected.

**How to detect:**
- Compare the aspect ratio (width/height) of image/SVG nodes in metadata against the rendered element
- Look for `<img>` or `<svg>` elements where both width and height are set to values that don't match the original ratio
- In Playwright, measure `naturalWidth/naturalHeight` vs `clientWidth/clientHeight`

**Fix pattern:**
```tsx
/* WRONG — forces aspect ratio */
<img src={logoUrl} className="w-[200px] h-[50px]" />

/* CORRECT — preserves aspect ratio */
<img src={logoUrl} className="h-[22px] w-auto" alt="Logo" />

/* For SVGs, also correct: */
<svg viewBox="0 0 18 22" className="h-[22px] w-auto">
```

**Prevention:** In Phase 3 code generation, for image and SVG elements:
1. Always use the Figma node's aspect ratio: `width / height`
2. Set ONE dimension explicitly, let the other be `auto`
3. Prefer `h-[Xpx] w-auto` for icons/logos (height-constrained)
4. Use `object-contain` or `object-cover` for content images, never `object-fill`

---

## M3: Section Margin / Container Width Mismatch

**What it looks like:** Content sections span edge-to-edge instead of being contained with proper margins. Or content is too narrow / too wide compared to the design.

**Why it happens:** The Figma design uses a specific content width (e.g., 1080px) centered within a larger frame (e.g., 1699px), creating implicit side margins. The code generator misses this and makes sections full-width.

**How to detect:**
- In metadata, check if content children have x-offsets significantly greater than 0 (e.g., `x="309.5"` in a 1699px frame = ~310px left margin = ~1080px content area)
- In the rendered output, check if text/content starts at the viewport edge vs. being indented
- Compute: `content_width = frame_width - (2 × content_x)`. If this gives a round number (960, 1080, 1200, 1280), it's an intentional container width

**Fix pattern:**
```tsx
/* WRONG — full width */
<section className="px-4">
  <h2>Titanium. So strong.</h2>
</section>

/* CORRECT — max-width container with centering */
<section className="w-full">
  <div className="max-w-[1080px] mx-auto px-6">
    <h2>Titanium. So strong.</h2>
  </div>
</section>
```

**Prevention:** In Phase 2 decomposition, always calculate the content area width from the metadata:
```
content_x = first content child's x position
content_width = frame_width - (2 * content_x)  // assuming centered
```
Pass `max_content_width` to Phase 3 as a generation parameter. Apply `max-w-[{width}px] mx-auto` to every section's inner container.

---

## M4: Vertical Spacing Collapse

**What it looks like:** Elements are stacked too tightly. The generous whitespace in the Figma design is lost in the render.

**Why it happens:** Figma auto layout gaps and padding values don't transfer correctly. The code generator uses the gap values from individual elements but misses the larger section-level spacing. Also, Figma uses absolute positioning within frames, and the Y-offset differences encode spacing that `get_design_context` may not express as CSS gap/padding.

**How to detect:**
- Calculate vertical gaps between sibling elements from metadata: `gap = next_child.y - (current_child.y + current_child.height)`
- Compare against the rendered spacing (use Playwright's `getBoundingClientRect()`)
- If Figma gap > 40px but rendered gap < 20px, spacing was lost

**Fix pattern:**
```tsx
/* WRONG — no section spacing */
<div className="flex flex-col">
  <HeroSection />
  <DesignSection />
</div>

/* CORRECT — explicit spacing from Figma y-offsets */
<div className="flex flex-col">
  <HeroSection />
  <div className="h-[160px]" /> {/* gap derived from metadata */}
  <DesignSection />
</div>

/* OR better — use gap/padding: */
<div className="flex flex-col gap-[160px]">
  ...
</div>
```

**Prevention:** In Phase 2, when computing section boundaries, also compute the gap between sections:
```
section_gap = next_section.y - (current_section.y + current_section.height)
```
Pass these gaps to Phase 3. In the assembly component, use `gap-[Xpx]` or explicit spacer divs.

---

## M5: Button / Interactive Element Style Wrong

**What it looks like:** Buttons are flat text links instead of styled pills/rounded rectangles. Or the button color, border-radius, or padding is wrong.

**Why it happens:** Figma represents a button as a frame containing text with fills, border-radius, and padding. If `get_design_context` doesn't clearly express the button's visual container, the LLM generates a plain `<a>` or `<button>` without background styles.

**How to detect:**
- Look for link/button frames in metadata with explicit dimensions (e.g., 128px × 49px) and rounded corners
- In the rendered output, check if buttons have background fills, border-radius, and proper padding
- Compare: Figma button has visible background color + rounded shape vs. render shows plain text

**Fix pattern:**
```tsx
/* WRONG — plain text link */
<a href="#" className="text-blue-600">Pre-order</a>

/* CORRECT — styled pill button */
<a href="#" className="inline-flex items-center justify-center px-7 py-3 bg-blue-600 text-white text-sm font-medium rounded-full hover:bg-blue-700 transition-colors">
  Pre-order
</a>

/* Nav "Buy" button — small pill */
<a href="#" className="inline-flex items-center justify-center px-4 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-full">
  Buy
</a>
```

**Prevention:** In Phase 3, when processing Link or Button frames:
1. Check if the frame has a fill color (background)
2. Check if the frame has border-radius (rounded corners)
3. Check the frame's explicit dimensions for padding inference
4. If the frame has fill + radius + text child → it's a styled button, not a plain link

---

## M6: Text Size / Weight Inaccuracy

**What it looks like:** Headings are too large or too small. Body text weight is wrong.

**Why it happens:** The code generator maps Figma font sizes to the nearest Tailwind class, but the jump between classes can be large (e.g., `text-5xl` = 48px vs. `text-6xl` = 60px). Also, font weight values (400 vs 500 vs 600) can be rounded incorrectly.

**How to detect:**
- Compare exact pixel values from Figma metadata `height` attributes on text nodes vs. the Tailwind class chosen
- Fonts rendering at > 120% or < 80% of the Figma size are noticeable
- Use Playwright to measure `computed font-size` and compare

**Fix pattern:**
```tsx
/* WRONG — nearest Tailwind class but wrong size */
<h2 className="text-6xl font-bold">Titanium. So strong.</h2>

/* CORRECT — exact Figma size using arbitrary value */
<h2 className="text-[64px] leading-[1.18] font-bold tracking-tight">Titanium. So strong.</h2>
```

**Prevention:** In Phase 3, when exact size matters (headings, hero text), prefer arbitrary Tailwind values `text-[Xpx]` over named classes. Use named classes only for body text (14–18px range) where ±2px is acceptable.

---

## M7: Centered vs. Left-Aligned Text

**What it looks like:** Text that should be centered is left-aligned, or vice versa.

**Why it happens:** Figma can center text within a frame using auto layout alignment OR by giving the text node an x-offset. If the frame uses auto layout with `center` alignment, `get_design_context` should capture it. But if centering is done via manual positioning (common in unstructured files), the code generator defaults to left alignment.

**How to detect:**
- In metadata, check if text nodes are positioned at the center of their parent: `text.x ≈ (parent.width - text.width) / 2`
- Check if parent frame has alignment properties in `get_design_context`
- In rendered output, compare text alignment visually

**Fix pattern:**
```tsx
/* WRONG — default left align */
<p className="text-sm uppercase tracking-wider text-gray-500">Design</p>

/* CORRECT — centered as in Figma */
<p className="text-sm uppercase tracking-wider text-gray-500 text-center">Design</p>
```

**Prevention:** In Phase 3, for every text node:
1. Calculate `expected_center_x = (parent.width - text.width) / 2`
2. If `|text.x - expected_center_x| < 10px`, the text is centered → add `text-center`
3. If `text.x ≈ parent.width - text.width`, the text is right-aligned → add `text-right`
4. Otherwise, left-aligned (default)

---

## M8: Navigation Bar Sticky / Fixed Positioning Missing

**What it looks like:** The navigation scrolls away with content instead of staying fixed at the top.

**Why it happens:** Figma doesn't have a native "fixed" or "sticky" attribute in the same way CSS does. The design intent is inferred from the nav being at y=0 and overlapping content.

**How to detect:**
- Navigation frame is at y=0 with relatively small height (40–80px)
- Navigation frame is a sibling of the main content frame (not nested inside it)
- In the Figma screenshot, the nav appears to overlay content

**Fix pattern:**
```tsx
<nav className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-md">
  {/* nav content */}
</nav>
<main className="pt-[48px]"> {/* offset for fixed nav height */}
  {/* page content */}
</main>
```

**Prevention:** In Phase 2, when detecting the header zone, check if the Navigation node is a sibling of the Body/content node at the same level. If so, it's likely fixed/sticky. Set `is_fixed_nav: true` in the assembly instructions.

---

## M9: Dark Background Section Contrast

**What it looks like:** A section that should have a dark/colored background renders with a white background, making light-colored text invisible.

**Why it happens:** The background fill is on the Figma frame, but `get_design_context` outputs the children's styles without the container's background.

**How to detect:**
- In `get_design_context`, check if the root element of a section has a background-color that isn't white/#fff
- In the Figma screenshot, sections with dark backgrounds have white/light text
- If the rendered text is the same color as the background, a background is missing

**Fix pattern:**
```tsx
/* WRONG — missing section background */
<section>
  <p className="text-white">...</p>  {/* invisible on white bg */}
</section>

/* CORRECT — section background preserved */
<section className="bg-[#1d1d1f]">
  <p className="text-white">...</p>
</section>
```

**Prevention:** In Phase 3, always check the root fill of each section frame in `get_design_context`. If it's not white/transparent, apply it as `bg-[color]` to the section wrapper.

---

## M10: Figma MCP Asset URLs Breaking in Production

**What it looks like:** Icons, images, and SVGs show as broken image placeholders because the `https://www.figma.com/api/mcp/asset/...` URLs expired or require authentication.

**Why it happens:** The `get_design_context` tool returns localhost or Figma API URLs for image assets. These URLs are temporary (7-day expiry) and may not be accessible from the end user's browser without Figma authentication.

**How to detect:**
- Look for `<img>` elements with `src` containing `figma.com/api/mcp/asset/` or `localhost:3845/figma/`
- In the browser, check if any images fail to load (404 or 403 errors)
- In Playwright, check `img.naturalWidth === 0` for any image element

**Fix pattern:**
```tsx
/* WRONG — Figma URL that will expire */
<img src="https://www.figma.com/api/mcp/asset/abc123" alt="Chip" className="w-6 h-6" />

/* CORRECT — Inline SVG fallback with graceful degradation */
function IconImg({ src, fallback: Fallback, className }) {
  return (
    <>
      <img
        src={src}
        className={className}
        onError={(e) => {
          e.target.style.display = 'none'
          e.target.nextElementSibling.style.display = 'block'
        }}
      />
      <span style={{ display: 'none' }}>
        <Fallback className={className} />
      </span>
    </>
  )
}

/* BEST — Download assets during generation and serve locally */
// During Phase 3, download all Figma asset URLs to /public/assets/
// Then reference them as /assets/chip-icon.svg
```

**Prevention:** In Phase 3, when generating code:
1. Identify all Figma asset URLs from `get_design_context`
2. Either download and embed them locally, or create inline SVG fallbacks
3. For common icons (arrows, chips, locks, etc.), generate semantic SVG components
4. Use an `onError` fallback pattern for graceful degradation

---

## M11: Dual-Layer Background Gradient Simplification

**What it looks like:** Gradient text uses a simplified single gradient when Figma specified multiple background layers.

**Why it happens:** Figma's `get_design_context` returns multi-layer `backgroundImage` values like `linear-gradient(...), linear-gradient(...)`. LLMs often simplify this to a single gradient, losing the visual compositing effect.

**How to detect:**
- In `get_design_context` output, look for `style={{ backgroundImage: "linear-gradient(...), linear-gradient(...)" }}`
- Count the number of gradient layers in the original vs the generated code
- Compare the exact gradient angles and color stops

**Fix pattern:**
```tsx
/* WRONG — simplified to single gradient */
<span style={{ backgroundImage: 'linear-gradient(145deg, #c4b5a0, #867a6c 50%, #3b3b3d 100%)' }}>

/* CORRECT — use the exact Figma gradient values */
<span style={{
  backgroundImage: 'linear-gradient(90deg, rgb(29, 29, 31) 0%, rgb(29, 29, 31) 100%), linear-gradient(145.36deg, rgb(196, 181, 160) 0%, rgb(134, 122, 108) 50%, rgb(59, 59, 61) 100%)'
}}>
```

**Prevention:** In Phase 3, when copying `backgroundImage` from design context:
1. Preserve ALL gradient layers exactly as provided by the MCP
2. Do not simplify or merge multiple gradients into one
3. Keep exact angle values (e.g., `145.36deg` not `145deg`)
4. Preserve `rgb()` format from design context rather than converting to hex

---

## M12: Absolute Positioning Instead of Flex/Grid

**What it looks like:** Elements render at correct positions on the exact design viewport, but the layout breaks on different screen sizes. Code is filled with `position: absolute; left: Xpx; top: Ypx;`.

**Why it happens:** When Figma frames lack auto layout, MCP outputs absolute positioning for all children. LLMs copy these verbatim instead of inferring the intended flex/grid layout.

**How to detect:**
- Count `position: absolute` in output — if >20% of layout elements are absolute, this mismatch is present
- Resize the browser window — absolute-positioned elements won't reflow
- In Playwright: `document.querySelectorAll('[class*="absolute"]').length`

**Fix pattern — Apply the layout inference algorithm (`references/layout-inference.md`):**
```tsx
/* WRONG — absolute positioning from MCP */
<div className="relative w-[1080px] h-[163px]">
  <div className="absolute left-[230px] top-[40px]">48MP</div>
  <div className="absolute left-[409px] top-[40px]">5x</div>
  <div className="absolute left-[570px] top-[40px]">4K120</div>
  <div className="absolute left-[751px] top-[40px]">48MP</div>
</div>

/* CORRECT — inferred flex layout */
<div className="flex justify-center gap-20 pt-10">
  <Stat value="48" unit="MP" label="Fusion camera" />
  <Stat value="5" unit="x" label="Optical zoom" />
  <Stat value="4K" unit="120" label="Dolby Vision" />
  <Stat value="48" unit="MP" label="Ultra Wide" />
</div>
```

**Inference rules (quick reference):**
1. Same Y (±5px) → `flex-direction: row`
2. Same X (±5px) → `flex-direction: column`
3. 2D grid pattern → `display: grid`
4. Equal left/right margins → centered
5. Uniform gaps → `gap-[Xpx]`
6. Items at edges → `justify-between`

**Prevention:** NEVER copy absolute positioning from `get_design_context`. Always infer flex/grid from child bounding boxes.

---

## M13: CSS Cascade Layer Conflict (Tailwind v4)

**Severity:** P1 — Layout broken

**What it looks like:** Content containers have the correct `max-width` but are flush-left instead of centered. All `mx-auto`, `px-*`, `mt-*`, `mb-*`, `gap-*` utilities silently fail. Layout looks "exploded" — text touches edges, spacing collapses between elements.

**Why it happens:** Tailwind CSS v4 generates all utilities inside `@layer utilities { ... }`. In CSS cascade layers, **unlayered styles always beat layered styles regardless of specificity**. If the global CSS has a universal reset outside any layer:

```css
/* THIS BREAKS ALL TAILWIND MARGINS AND PADDING IN v4 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
```

...then `margin: 0` (unlayered, specificity 0,0,0) beats `.mx-auto { margin-inline: auto }` (inside `@layer utilities`, specificity 0,1,0). This is counterintuitive — higher specificity loses because it's in a layer.

**How to detect:**
- In Playwright, check `getComputedStyle(el).marginLeft` on a `mx-auto` element — if it's `0px` instead of `auto`, this bug is present
- Any element with `mx-auto` + `max-w-*` that has `left: 0` instead of being centered
- Multiple spacing utilities failing simultaneously (not just one)

**Programmatic check:**
```javascript
// In Playwright page.evaluate:
const testEl = document.createElement('div');
testEl.className = 'mx-auto';
testEl.style.maxWidth = '100px';
document.body.appendChild(testEl);
const ml = getComputedStyle(testEl).marginLeft;
document.body.removeChild(testEl);
if (ml === '0px') {
  // CASCADE LAYER CONFLICT — unlayered CSS is overriding Tailwind utilities
}
```

**Fix:**
```css
/* Option A: Move reset into Tailwind's base layer */
@layer base {
  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }
}

/* Option B: Remove the reset entirely (Tailwind v4 preflight handles it) */
/* Just delete the * { ... } block */
```

**Prevention:**
- When generating `index.css` or global styles, NEVER write CSS resets outside `@layer base { ... }` when using Tailwind v4
- Tailwind v4's `@import "tailwindcss"` already includes a preflight reset — additional `*` resets are usually unnecessary
- If custom global styles are needed, always wrap them in `@layer base { ... }`
- This does NOT affect Tailwind v3 (which uses `@tailwind` directives without CSS layers)

---

## Verification Checklist (Phase 4)

When running Phase 4, check each mismatch type in order:

```
[ ] M1:  Any gradient/special text rendered as flat color?
[ ] M2:  Any images/SVGs with wrong aspect ratio?
[ ] M3:  Content sections at correct width with proper margins?
[ ] M4:  Vertical spacing between sections matches Figma?
[ ] M5:  Buttons styled as pills/rectangles (not plain text)?
[ ] M6:  Heading sizes within ±10% of Figma values?
[ ] M7:  Text alignment (center/left/right) matches Figma?
[ ] M8:  Navigation fixed/sticky if applicable?
[ ] M9:  Dark section backgrounds preserved?
[ ] M10: Figma asset URLs accessible? Fallbacks provided?
[ ] M11: Multi-layer gradients preserved (not simplified)?
[ ] M12: Absolute positioning converted to flex/grid? (<20% absolute)
[ ] M13: Tailwind utilities actually applying? (test mx-auto → marginLeft !== '0px')
```

This checklist should be evaluated both visually (screenshot comparison) and structurally (computed styles via Playwright).

**Critical M13 check:** Before running any other structural audits, first verify that Tailwind utilities are actually being applied. If M13 fails, ALL other margin/padding checks will give misleading results. Run the cascade layer test first:
