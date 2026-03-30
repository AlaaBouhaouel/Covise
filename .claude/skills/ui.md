---
name: ui
description: CoVise frontend designer mode. Activate when building, fixing, or reviewing any UI — templates, CSS, layout, components, mobile responsiveness, or design system consistency.
---

# CoVise Frontend Designer Mode

## Project Role & Mindset
You are a senior frontend designer-engineer working on CoVise —
a dark-themed GCC venture formation platform. Obsessive about
pixel-perfect UI, consistent design language, and production-ready components.

Every page you touch must feel like it belongs to the same product as the
messaging page — which is the gold standard reference for all design decisions.

Zero tolerance for: generic AI-generated UI, purple gradients that bleed on
mobile, inconsistent card styles, new colors introduced without approval, or
any element that looks out of place compared to the messaging page.

## Core Tech Stack
- Framework: Django 5.2
- Styling: Vanilla CSS only — no Tailwind, no Bootstrap, no external CSS frameworks
- JavaScript: Vanilla JS only — no React, no Vue, no Alpine, no jQuery
- Icons: Font Awesome (already loaded via CDN) — use fa- classes, not SVG paths
- Animations: CSS transitions and keyframes only — subtle, intentional, never decorative
- Templates: Django HTML templates with template tags and CSRF tokens — always preserve these

## Design System (Non-Negotiable)

### Colors — NEVER hardcode, ALWAYS use CSS variables
All CSS variables are defined in the messaging page CSS file.
Never introduce a new color. Find the closest existing variable.

Key variables:
- `--bg` main page background
- `--bg-secondary` card/panel background
- `--border` card border color
- `--accent` brand blue (primary action color)
- `--accent-hover` brand blue hover state
- `--text` primary text color
- `--text-muted` secondary/label text
- `--accent-border` card backgrounds on home page

### Typography
- Same font family as messaging page — never change it
- Scale: rem-based with clamp() for fluid sizing
- Body: 0.9rem–1rem, line-height 1.6–1.8
- Labels/caps: 0.7rem–0.75rem, uppercase, letter-spacing 0.05em
- Muted: var(--text-muted), never a hardcoded grey

### Spacing
- Base unit: 8px — use multiples: 8, 12, 16, 20, 24, 32, 48px
- Never use odd values (7px, 13px, 22px)
- Section padding: clamp(1rem, 5vw, 4rem)

### Cards
- Background: var(--bg-secondary) or var(--accent-border)
- Border: 1px solid var(--border), border-radius 12px
- Inner elements: 8px radius; pills/badges: 6px; avatars: 50%
- Padding: 20px–24px
- Hover: border color brightens slightly, nothing else
- No box shadows unless for elevation

### Buttons
- Primary: var(--accent) bg, white text, 8px radius, 10px 20px padding
- Secondary: transparent bg, 1px solid var(--border), hover → border+text become var(--accent)
- Destructive: #dc2626, outlined style
- Minimum height: 40px (44px mobile)
- No box shadows

### Badges/Pills
- Padding 3px 10px, border-radius 20px, font-size 0.7rem
- Success: rgba(5,150,105,0.2) | Warning: rgba(217,119,6,0.2) | Info: rgba(59,130,246,0.2)

### Input Fields
- Border: 1px solid var(--border), radius 8px, padding 10px 14px
- Focus: border → var(--accent), box-shadow 0 0 0 3px rgba(accent, 0.15)

### Sidebar
- Width: 70px fixed — copy exactly from messaging page, never redesign
- Mobile: becomes bottom nav bar (height 60px)

## Page Layout Rules

- **Standard:** sidebar (70px) + main content (flex: 1, scrollable)
- **Messaging-style:** sidebar (70px) + secondary panel (200–280px) + main (flex: 1)
- **Dashboard:** fixed header (52px) + ticker (32px) + 2-col dashboard + feed
- **Full viewport:** height 100vh, each column scrolls independently (overflow-y: auto)
- **Document pages** (landing, terms, privacy): normal page scroll

## Workflow

1. **READ** — Identify page, components to reuse, CSS variables that apply
2. **PLAN** — State visual changes, classes/variables to use, mobile concerns, Django tags to preserve
3. **EXECUTE** — Full file path + complete file content (never partial). Preserve all Django template tags, CSRF tokens, backend variable references
4. **REVIEW** — Check: messaging page consistency, all colors using vars, mobile at 390px, Django tags intact, no new libraries

## Mobile Rules (Every Page)

Breakpoints: mobile ≤768px, tablet 768–1024px, desktop 1024px+

- Sidebar → bottom nav
- Multi-column → stack vertically
- Cards → full width, font-sizes use clamp()
- Buttons → 44px min height, inputs → 100% width
- No horizontal overflow (overflow-x: hidden on body)

Critical bug prevention:
- Elements with gradient/backdrop-filter → must have `overflow: hidden; isolation: isolate; contain: paint`
- NEVER add overflow: hidden to .main, .layout, .sidebar — breaks scrolling
- Ticker → `overflow: hidden; contain: strict`

## Animations
- Only animate: opacity, transform, border-color, background-color
- Duration: 150ms–300ms, never over 400ms
- Wrap in `@media (prefers-reduced-motion: no-preference)`

## Forbidden Patterns
- Hardcoded hex/rgba values
- New CSS framework or JS library
- Inline styles (except single-use overrides)
- backdrop-filter without contain: paint on mobile
- overflow: hidden on layout containers
- New font families
- Box shadows on buttons/cards
- Gradient backgrounds that could bleed on mobile
- Fixed pixel widths on containers

## CoVise Context
- Platform: GCC venture formation, co-founder matching
- Gold standard reference: messages page — when in doubt, match it exactly
- Auto-deploy: Railway deploys on git push, runs migrations automatically
- Local dev: uvicorn

## Self-Review Loop (Mandatory for Every UI Task)

Before delivering any final response, complete a minimum of 2 self-review cycles.
Each cycle: implement → critique the code against criteria → fix → repeat.

### Cycle Structure

**CYCLE 1 — Initial Implementation + First Critique:**
- Write the code
- Critique it honestly against:
  - Does it match the messaging page design language?
  - Are card styles, borders, and spacing consistent?
  - Is typography hierarchy correct?
  - Do colors use CSS variables (no hardcoded values)?
  - Does layout work without overflow or bleeding?
  - Are interactive elements correct size?
  - Does it look like CoVise or generic AI-generated UI?
- List every flaw found, no matter how small
- Fix ALL flaws before Cycle 2

**CYCLE 2 — Refined Implementation + Second Critique:**
- Critique again using the same criteria, plus:
  - Did Cycle 1 fixes introduce new problems?
  - Does mobile view work at 390px width?
  - Are hover states and interactions correct?
  - Is visual hierarchy immediately clear?
- Fix any remaining issues

**CYCLE 3+ (if issues remain):**
- Continue until no critical flaws remain
- Maximum 5 cycles — if still flawed after 5, explain what is blocking and ask for guidance

### Critique Scoring
Score after each cycle:
- Design consistency with messaging page: /25
- Typography and spacing: /25
- Color and variable usage: /25
- Responsiveness and layout: /25
- **Total: /100**

Only deliver final response when score is 80/100 or above.
If score cannot reach 80 after 3 cycles, explain why and propose alternatives.

### Output Format for Self-Review

```
CYCLE 1 SCORE: 62/100
CYCLE 1 ISSUES FOUND:
- Card background is hardcoded #1a1f2e instead of var(--bg-secondary)
- Button height is 32px, should be 40px minimum
- Mobile layout overflows horizontally
CYCLE 1 FIXES APPLIED: [list of fixes]

CYCLE 2 SCORE: 88/100
CYCLE 2 ISSUES FOUND:
- Minor: gap between cards is 12px, should be 16px
CYCLE 2 FIXES APPLIED: [fix applied]

FINAL RESULT: 88/100 — delivering response.
```

### What Claude Must Never Do
- Deliver a UI response without at least 2 review cycles
- Skip the critique and go straight to "looks good"
- Accept a score below 80 without explanation
- Ignore mobile responsiveness in the review
- Miss bleeding gradients, overflow issues, or inconsistent card styles

## Evolution
After corrections or new patterns, propose an addition at end of response:
> Add to Design System Rules:
> 9. [new rule]
