# Phase 3: Code Generation — Detailed Reference

## Purpose

Transform Figma design context into production-ready React + Tailwind CSS components. This phase takes the output of Phases 0–2 and produces actual code files.

## Inputs

Phase 3 receives:
- **Design context** — HTML/CSS reference code from `get_design_context` (per-section if Phase 2 ran)
- **Inferred tokens** — `inferred_tokens.json` from Phase 1 (if it ran)
- **Code Connect mappings** — from `get_code_connect_map` (if available)
- **Assembly layout** — section order and layout type from Phase 2 (if it ran)
- **Screenshots** — Figma screenshots for visual reference

## Component Generation Strategy

### Priority 1: Use Code Connect (If Available)

When `get_code_connect_map` returned mappings, the MCP server's `get_design_context` already wraps recognized components in `CodeConnectSnippet` markers:

```html
<!-- CodeConnectSnippet: Button -->
<!-- import: import { Button } from '@/components/ui/button' -->
<!-- code: <Button variant="primary" size="md">Click me</Button> -->
```

When you see these markers:
- Use the exact import path and component usage from the snippet
- Preserve all specified props
- Do NOT recreate the component — use the existing one from the codebase

### Priority 2: Use Inferred Components (If Phase 1 Ran)

When Phase 1 detected component patterns but no Code Connect exists, generate reusable components:

```tsx
// Inferred from Phase 1: Card pattern (6 instances, ~300x200px)
interface CardProps {
  title: string;
  description: string;
  imageUrl: string;
  ctaText?: string;
  onCtaClick?: () => void;
}

export function Card({ title, description, imageUrl, ctaText = 'Learn More', onCtaClick }: CardProps) {
  return (
    <div className="rounded-lg bg-white shadow-md overflow-hidden w-[300px]">
      <img src={imageUrl} alt={title} className="w-full h-[140px] object-cover" />
      <div className="p-4 flex flex-col gap-2">
        <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
        <p className="text-sm text-gray-500">{description}</p>
        {ctaText && (
          <button onClick={onCtaClick} className="mt-2 text-blue-600 font-medium text-sm hover:underline">
            {ctaText}
          </button>
        )}
      </div>
    </div>
  );
}
```

### Priority 3: Generate Inline (No Patterns Detected)

When neither Code Connect nor inferred components are available, generate code directly from the design context. Every element becomes inline JSX with Tailwind classes.

## Tailwind Class Mapping

### Colors

Map Figma hex values to Tailwind classes using the inferred token system (or standard Tailwind palette):

| Figma Property | CSS Property | Tailwind Pattern |
|---|---|---|
| Fill (background) | `background-color` | `bg-{color}` |
| Fill (text) | `color` | `text-{color}` |
| Stroke | `border-color` | `border-{color}` |

**With inferred tokens:**
```
#0066cc (inferred as "primary") → bg-primary (if tailwind.config extended)
                                  OR bg-blue-600 (closest default)
```

**Without tokens, find closest Tailwind default:**

```python
# Conceptual matching
tailwind_colors = {
    "gray-50": "#f9fafb", "gray-100": "#f3f4f6", ...,
    "blue-500": "#3b82f6", "blue-600": "#2563eb", ...
}
# Find color with minimum Euclidean distance in RGB space
```

### Spacing

Map pixel values to Tailwind spacing utilities:

| Pixels | Tailwind | Example |
|:---:|---|---|
| 0 | `0` | `p-0` |
| 1 | `px` | `p-px` |
| 2 | `0.5` | `p-0.5` |
| 4 | `1` | `p-1` |
| 8 | `2` | `p-2`, `gap-2` |
| 12 | `3` | `p-3` |
| 16 | `4` | `p-4`, `gap-4` |
| 20 | `5` | `p-5` |
| 24 | `6` | `p-6` |
| 32 | `8` | `p-8` |
| 40 | `10` | `p-10` |
| 48 | `12` | `p-12` |
| 64 | `16` | `p-16` |

For values not in the scale, use arbitrary values: `p-[18px]`

### Layout

| Figma Layout | Tailwind Classes |
|---|---|
| Auto layout horizontal | `flex flex-row` |
| Auto layout vertical | `flex flex-col` |
| Auto layout wrap | `flex flex-wrap` |
| Gap: 16px | `gap-4` |
| Align items: center | `items-center` |
| Justify: space-between | `justify-between` |
| Fixed width | `w-[{value}px]` |
| Fill container | `flex-1` or `w-full` |
| Hug contents | `w-fit` |

### Typography

| Figma Property | Tailwind |
|---|---|
| Font size 12px | `text-xs` |
| Font size 14px | `text-sm` |
| Font size 16px | `text-base` |
| Font size 18px | `text-lg` |
| Font size 20px | `text-xl` |
| Font size 24px | `text-2xl` |
| Font weight 400 | `font-normal` |
| Font weight 500 | `font-medium` |
| Font weight 600 | `font-semibold` |
| Font weight 700 | `font-bold` |
| Line height 1.2 | `leading-tight` |
| Line height 1.5 | `leading-normal` |
| Line height 2 | `leading-loose` |

## Section Assembly (When Phase 2 Ran)

If the design was decomposed into sections, generate each as a separate component, then assemble:

### Vertical Stack Layout

```tsx
import Header from './Header';
import Hero from './Hero';
import Features from './Features';
import Testimonials from './Testimonials';
import Pricing from './Pricing';
import CTA from './CTA';
import Footer from './Footer';

export default function LandingPage() {
  return (
    <div className="flex flex-col min-h-screen">
      <Header />
      <Hero />
      <Features />
      <Testimonials />
      <Pricing />
      <CTA />
      <Footer />
    </div>
  );
}
```

### Sidebar Layout

```tsx
import Sidebar from './Sidebar';
import MainContent from './MainContent';

export default function DashboardPage() {
  return (
    <div className="flex min-h-screen">
      <Sidebar className="w-[280px] shrink-0" />
      <main className="flex-1 flex flex-col">
        <MainContent />
      </main>
    </div>
  );
}
```

### Repeated Components

When Phase 2 identified repeated patterns, generate the component once and render with data:

```tsx
import { Card } from './Card';

const cardsData = [
  { title: 'Feature 1', description: 'Description...', imageUrl: 'http://localhost:...' },
  { title: 'Feature 2', description: 'Description...', imageUrl: 'http://localhost:...' },
  // ... extracted from Figma content
];

export function FeaturesSection() {
  return (
    <section className="py-16 px-8">
      <h2 className="text-3xl font-bold text-center mb-12">Features</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
        {cardsData.map((card, i) => (
          <Card key={i} {...card} />
        ))}
      </div>
    </section>
  );
}
```

## Asset Handling

**Images from Figma MCP:**
The `get_design_context` response includes localhost URLs for images and SVGs. Use them directly:

```tsx
// CORRECT — use the Figma MCP localhost URL
<img src="http://localhost:3845/figma/images/abc123/1:234" alt="Hero" className="w-full" />

// WRONG — never use placeholders
<img src="/placeholder.png" alt="Hero" />

// WRONG — never import random packages
import { ImageIcon } from 'lucide-react';
```

**SVG icons:**
If the MCP response includes inline SVG, embed it directly or extract to a separate component:

```tsx
function ArrowIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path d="M5 12h14M12 5l7 7-7 7" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
```

## Tailwind Config Generation

If Phase 1 inferred custom colors or spacing that don't map to Tailwind defaults, generate a config extension:

```ts
// tailwind.config.ts
import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#0066cc',
        'primary-light': '#e6f0ff',
        secondary: '#6c757d',
        surface: '#f8f9fa',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '8px',
      },
    },
  },
  plugins: [],
};

export default config;
```

## Critical Rules

1. **No hardcoded pixel values in className** — Use Tailwind utilities. Only use `[Xpx]` arbitrary values when no utility exists.
2. **No placeholder images** — Use Figma MCP localhost URLs for all assets.
3. **No invented component libraries** — Only use Code Connect mappings or inferred components.
4. **Preserve visual hierarchy** — The DOM structure should reflect the visual nesting from Figma.
5. **Use semantic HTML** — `<nav>` for navigation, `<main>` for main content, `<footer>` for footer, `<section>` for sections, `<article>` for cards.
6. **Include responsive hints** — Even if Figma shows one breakpoint, add responsive classes where layout obviously needs to adapt (e.g., `grid-cols-1 md:grid-cols-3` for card grids).
7. **TypeScript** — All components use TypeScript with proper interfaces for props.
8. **Default exports** — Each component file has a default export.

## Output Files

For a typical landing page conversion:

```
output/
├── LandingPage.tsx        (parent assembly component)
├── Header.tsx             (section component)
├── Hero.tsx               (section component)
├── Features.tsx           (section component)
├── Card.tsx               (inferred reusable component)
├── Button.tsx             (inferred reusable component)
├── Testimonials.tsx       (section component)
├── Pricing.tsx            (section component)
├── CTA.tsx                (section component)
├── Footer.tsx             (section component)
├── tailwind.config.ts     (custom tokens extension)
└── inferred_tokens.json   (token reference from Phase 1)
```
