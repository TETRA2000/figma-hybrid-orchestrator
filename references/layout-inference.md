# Layout Inference — Converting Absolute Positions to Flex/Grid

## The Problem

When Figma frames **lack auto layout**, the MCP `get_design_context` tool outputs absolute positioning (`position: absolute`, `left: Xpx`, `top: Ypx`) for all children. This produces unmaintainable code that breaks on different screen sizes.

**Example — Camera stats row WITHOUT auto layout:**
```tsx
/* MCP OUTPUT (absolute — bad for production) */
<div className="relative size-full">
  <div className="absolute left-[229.94px] top-[40px] w-[99.52px]">48MP / Fusion camera</div>
  <div className="absolute left-[409.46px] top-[40px] w-[80.24px]">5x / Optical zoom</div>
  <div className="absolute left-[569.7px]  top-[40px] w-[100.84px]">4K120 / Dolby Vision</div>
  <div className="absolute left-[750.54px] top-[40px] w-[99.52px]">48MP / Ultra Wide</div>
</div>

/* SHOULD BE (flex row — maintainable) */
<div className="flex justify-center gap-20 pt-10">
  <Stat value="48" unit="MP" label="Fusion camera" />
  <Stat value="5" unit="x" label="Optical zoom" />
  <Stat value="4K" unit="120" label="Dolby Vision" />
  <Stat value="48" unit="MP" label="Ultra Wide" />
</div>
```

## When to Apply Layout Inference

Apply this algorithm in Phase 3 (Code Generation) whenever `get_design_context` returns children with `absolute` positioning inside a container. It also informs Phase 2 (Decomposition) when grouping nodes into logical sections.

**Trigger conditions:**
- Container has ≥2 children with `position: absolute`
- Children use `left-[Xpx]` and `top-[Ypx]` positioning
- Container itself is `relative`

## The Algorithm

### Step 1: Extract Child Bounding Boxes

From the `get_design_context` output OR `get_metadata` XML, extract each child's position:

```
child = { id, x, y, width, height, name }
```

**From design context Tailwind classes:**
- `left-[229.94px]` → x = 229.94
- `top-[40px]` → y = 40
- `w-[99.52px]` → width = 99.52
- `h-[81.5px]` → height = 81.5

**From metadata XML attributes:**
- `x="229.9375"` → x = 229.94
- `y="41"` → y = 41
- `width="99.5234375"` → width = 99.52

### Step 2: Detect Layout Direction

**Rule: Same-Y = Horizontal Row**
```
If all children have Y positions within TOLERANCE (5px):
  → layout = "row" (flex-direction: row)
```

**Rule: Same-X = Vertical Column**
```
If all children have X positions within TOLERANCE (5px):
  → layout = "column" (flex-direction: column)
```

**Rule: Grid = Both Rows and Columns**
```
Sort children by Y, then by X within each Y-group.
If there are ≥2 distinct Y-groups AND ≥2 distinct X-groups:
  count_columns = distinct X positions
  count_rows = distinct Y positions
  If count_columns × count_rows ≈ total_children (±1):
    → layout = "grid"
    → grid-template-columns: repeat(count_columns, 1fr)
    → grid-template-rows: repeat(count_rows, 1fr)
```

**Rule: Mixed = Vertical with nested rows**
```
If some children share Y (form rows) but there are multiple Y-groups:
  → Group children by Y-proximity
  → Each Y-group with multiple children = flex row
  → Stack Y-groups vertically = flex column containing flex rows
```

**Tolerance:** Use 5px for Y-grouping (accounts for minor Figma alignment imprecision).

### Step 3: Detect Alignment

#### Horizontal Centering
```
left_margin = first_child.x
right_margin = parent_width - (last_child.x + last_child.width)

If |left_margin - right_margin| < 15px:
  → The row is centered → justify-content: center
```

**Example:**
```
Parent width: 1080px
First child: x=229.94
Last child: x=750.54, width=99.52 → right_edge = 850.06
Left margin: 229.94px
Right margin: 1080 - 850.06 = 229.94px
|229.94 - 229.94| = 0 → CENTERED ✓
```

#### Left Alignment
```
If first_child.x < 20px (near parent left edge):
  → Left aligned → items-start or justify-start
```

#### Right Alignment
```
If parent_width - (last_child.x + last_child.width) < 20px:
  → Right aligned → items-end or justify-end
```

#### Vertical Centering
```
top_margin = first_child.y
bottom_margin = parent_height - (last_child_bottom_edge)

If |top_margin - bottom_margin| < 15px:
  → Vertically centered → items-center (for rows) or justify-center (for columns)
```

### Step 4: Detect Gaps

#### Uniform Gaps (→ Tailwind `gap-[Xpx]`)
```
For horizontal row, sorted by X:
  gaps = []
  for i in 1..n-1:
    gap = child[i].x - (child[i-1].x + child[i-1].width)
    gaps.append(gap)

  If max(gaps) - min(gaps) < 5px:
    → uniform_gap = round(mean(gaps))
    → gap-[uniform_gap_px]
```

**Example:**
```
Children: x=229.94 w=99.52, x=409.46 w=80.24, x=569.7 w=100.84, x=750.54
Gaps: 409.46-329.46=80, 569.7-489.7=80, 750.54-670.54=80
All gaps = 80px → gap-20 (80px / 4 = Tailwind's gap-20)
```

#### Non-Uniform Gaps (→ individual margins)
```
If gaps vary by >5px:
  → Use individual ml-[Xpx] or mt-[Xpx] on each child
```

### Step 5: Detect justify-content Pattern

After determining the row is centered with uniform gaps:

```
total_children_width = sum(child.width for child in children)
total_gaps = uniform_gap × (n - 1)
content_width = total_children_width + total_gaps
remaining_space = parent_width - content_width

If remaining_space > 100px AND uniform_gap is roughly equal to remaining_space/2:
  → justify-content: space-evenly
Else if remaining_space is small (<50px) AND gaps are large:
  → justify-content: space-between
Else:
  → justify-content: center + explicit gap
```

### Step 6: Generate the CSS/Tailwind

**Horizontal row, centered, uniform gap:**
```tsx
<div className="flex justify-center gap-[80px] pt-[40px]">
  {children}
</div>
```

**Vertical column, left-aligned, varying gaps:**
```tsx
<div className="flex flex-col pl-[40px]">
  <div className="mt-[48px]">{icon}</div>
  <div className="mt-[24px]">{heading}</div>
  <div className="mt-[10px]">{paragraph}</div>
</div>
```

**2×2 Grid, uniform gaps:**
```tsx
<div className="grid grid-cols-2 gap-5">
  {cards}
</div>
```

---

## Complete Examples from Real Figma Output

### Example 1: Stats Row (Camera Section)

**Input metadata:**
```xml
<frame id="4:159" width="1080" height="163">
  <frame id="4:160" x="229.94" y="41" width="99.52" height="81.5" />
  <frame id="4:167" x="409.46" y="41" width="80.24" height="81.5" />
  <frame id="4:174" x="569.70" y="41" width="100.84" height="81.5" />
  <frame id="4:181" x="750.54" y="41" width="99.52" height="81.5" />
</frame>
```

**Analysis:**
1. All Y ≈ 41 → **horizontal row**
2. Left margin = 229.94, right margin = 1080 - 850.06 = 229.94 → **centered**
3. Gaps: all 80px → **uniform gap-20**
4. Top position 41px → **pt-10**

**Output:**
```tsx
<div className="border-t border-[rgba(134,134,139,0.2)] pt-10 flex justify-center gap-20">
  <Stat value="48" unit="MP" label="Fusion camera" />
  <Stat value="5" unit="x" label="Optical zoom" />
  <Stat value="4K" unit="120" label="Dolby Vision" />
  <Stat value="48" unit="MP" label="Ultra Wide" />
</div>
```

### Example 2: Feature Card Internals

**Input metadata:**
```xml
<frame id="4:203" width="530" height="265">
  <frame id="4:204" x="40" y="48" width="48" height="48" />   <!-- icon -->
  <frame id="4:209" x="40" y="120" width="450" height="39" />  <!-- heading -->
  <frame id="4:212" x="40" y="169" width="450" height="48" />  <!-- paragraph -->
</frame>
```

**Analysis:**
1. All X = 40 → **vertical column**
2. Left aligned (x=40 → pl-10)
3. Gaps: 120-(48+48)=24, 169-(120+39)=10 → **non-uniform**
4. Top position 48px → **pt-12**

**Output:**
```tsx
<div className="pt-12 pb-10 px-10 flex flex-col">
  <div className="w-12 h-12 rounded-[14px] flex items-center justify-center mb-6">
    <img src={icon} className="w-6 h-6" />
  </div>
  <h3 className="text-[26px] font-bold mb-[10px]">2nm Technology</h3>
  <p className="text-[15px] leading-6">Description...</p>
</div>
```

### Example 3: Navigation Bar

**Input metadata:**
```xml
<frame id="4:362" width="1200" height="47">
  <frame id="4:363" x="24" y="12.5" width="18" height="22" />    <!-- logo -->
  <frame id="4:366" x="426.92" y="11.5" width="312.56" height="24" /> <!-- nav links -->
  <frame id="4:387" x="1124.41" y="8.5" width="51.59" height="30" /> <!-- buy button -->
</frame>
```

**Analysis:**
1. All Y ≈ 8.5–12.5 (within 5px) → **horizontal row**
2. Logo at far left (x=24), button at far right (x=1124 + 52 ≈ 1176 in 1200 container)
3. → **justify-between** (items spread to edges)
4. Vertical alignment: Y values center around 11–12 in 47px height → **items-center**

**Output:**
```tsx
<div className="flex items-center justify-between h-12 max-w-[1200px] mx-auto px-6">
  <a href="#">{logo}</a>
  <nav className="flex gap-8">{links}</nav>
  <a href="#" className="bg-blue-500 rounded-full px-4 py-1.5">Buy</a>
</div>
```

### Example 4: Pricing Cards Row

**Input metadata:**
```xml
<frame id="4:288" width="960" height="388">
  <frame id="4:289" x="0" y="0" width="307" height="388" />
  <frame id="4:313" x="326.66" y="0" width="307" height="388" />
  <frame id="4:337" x="653.33" y="0" width="307" height="388" />
</frame>
```

**Analysis:**
1. All Y = 0 → **horizontal row**
2. 3 children, parent width 960, child width 307 × 3 = 921, gaps ≈ 19.66 × 2 = 39.32
3. 960 - 921 = 39 → small remaining space → children nearly fill parent
4. Gaps: 326.66 - 307 = 19.66, 653.33 - 633.66 = 19.67 → **uniform gap ≈ 20px**
5. Children are same width = equal columns

**Output:**
```tsx
<div className="grid grid-cols-3 gap-5 max-w-[960px] mx-auto">
  <PricingCard ... />
  <PricingCard ... />
  <PricingCard ... />
</div>
```

---

## Decision Flowchart

```
Start with children of a container
│
├─ All children Y within 5px? ──── YES ──→ HORIZONTAL ROW
│   │                                       │
│   │                                       ├─ Logo-left + button-right? → justify-between
│   │                                       ├─ All centered? → justify-center + gap
│   │                                       ├─ Equal widths fill parent? → grid cols
│   │                                       └─ Space-evenly pattern? → justify-evenly
│   │
│   NO
│   │
│   ├─ All children X within 5px? ──── YES ──→ VERTICAL COLUMN
│   │                                          │
│   │                                          ├─ Centered in parent? → items-center
│   │                                          ├─ Left-aligned? → items-start + pl-X
│   │                                          └─ Right-aligned? → items-end + pr-X
│   │
│   NO
│   │
│   ├─ Children form a 2D grid? ──── YES ──→ CSS GRID
│   │   (≥2 row groups × ≥2 col groups       grid-cols-N gap-X
│   │    and count ≈ rows × cols)
│   │
│   NO
│   │
│   └─ Mixed layout ──→ Group by Y-proximity
│       │                Wrap each Y-group in flex-row
│       │                Stack groups in flex-col
│       │
│       └─ Any remaining absolute children? → Keep position: absolute
│           (overlapping decorative elements, badges, etc.)
```

---

## Edge Cases

### Overlapping Elements
If children overlap (child[i].x < child[i-1].x + child[i-1].width), they're likely:
- Decorative overlays → keep `absolute`
- Stacking context elements (z-index) → keep `absolute`
- Background/foreground pairs → extract background to parent style

### Single Child
If a container has only 1 child:
- Convert `left-[X] top-[Y]` to padding: `pl-[X] pt-[Y]`
- Or if centered: `flex items-center justify-center`

### Text Centering Inside Containers
The MCP often outputs text with `-translate-x-1/2 left-[50%]` for centering. Replace with:
```tsx
/* BEFORE (from MCP) */
<p className="-translate-x-1/2 absolute left-[50px] text-center">Text</p>

/* AFTER (semantic) */
<p className="text-center w-full">Text</p>
```

### Nested Absolute Positioning
When card internals (icon, heading, paragraph) all use absolute positioning:
1. Check if they share X → vertical column
2. Calculate gaps between consecutive elements
3. Convert to `flex flex-col` with appropriate spacing

---

## Integration with Phases

### Phase 2 (Decomposition)
When analyzing metadata to identify sections:
- Use Y-grouping to find distinct horizontal "rows" of content
- Nodes sharing similar Y = same section row
- Large Y gaps between groups = section boundaries

### Phase 3 (Code Generation)
When converting `get_design_context` output to production code:
1. Parse the Tailwind classes for `absolute`, `left-[X]`, `top-[Y]`, `w-[X]`, `h-[Y]`
2. Apply the layout inference algorithm above
3. Replace absolute positioning with semantic flex/grid
4. Preserve exact spacing using calculated gaps/padding

### Phase 4 (Verification)
Add structural audit checks:
- Count `position: absolute` in output — flag if >20% of elements are absolute
- Verify containers use flex/grid where layout inference detected patterns
- Check that inferred spacing matches Figma pixel values within 5px

---

## References

- [Figma MCP Server Guide](https://github.com/figma/mcp-server-guide/)
- [Smart Position Info Fork (tianmuji)](https://github.com/tianmuji/Figma-Context-MCP) — adds position data to non-AutoLayout nodes
- [Layout Inference for GUIs (academic)](https://www.sciencedirect.com/science/article/abs/pii/S0950584915001718) — Allen's interval relations + pattern matching
- [Phoenix Codie "Alchemist Engine"](https://www.go-yubi.com/blog/building-phoenix-codie/) — heuristic pattern detection for Figma layouts
- [Anima Flexbox Generation](https://www.animaapp.com/blog/product-updates/producing-flexbox-responsive-code-based-on-figma-adobe-xd-and-sketch-constraints/) — constraint-to-flexbox translation
