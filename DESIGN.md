---
name: DMCU Operations Console
colors:
  surface: '#fff9ee'
  surface-dim: '#dfd9cf'
  surface-bright: '#fff9ee'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f9f3e9'
  surface-container: '#f3ede3'
  surface-container-high: '#ede8dd'
  surface-container-highest: '#e7e2d8'
  on-surface: '#1d1c15'
  on-surface-variant: '#404947'
  inverse-surface: '#32302a'
  inverse-on-surface: '#f6f0e6'
  outline: '#707977'
  outline-variant: '#bfc8c6'
  surface-tint: '#306762'
  primary: '#003834'
  on-primary: '#ffffff'
  primary-container: '#14504b'
  on-primary-container: '#89c1ba'
  inverse-primary: '#99d1ca'
  secondary: '#665685'
  on-secondary: '#ffffff'
  secondary-container: '#dcc9ff'
  on-secondary-container: '#615280'
  tertiary: '#6a0003'
  on-tertiary: '#ffffff'
  tertiary-container: '#8f1511'
  on-tertiary-container: '#ff9c8f'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b4ede6'
  primary-fixed-dim: '#99d1ca'
  on-primary-fixed: '#00201d'
  on-primary-fixed-variant: '#134f4a'
  secondary-fixed: '#ebddff'
  secondary-fixed-dim: '#d1bef3'
  on-secondary-fixed: '#22133d'
  on-secondary-fixed-variant: '#4e3f6c'
  tertiary-fixed: '#ffdad5'
  tertiary-fixed-dim: '#ffb4aa'
  on-tertiary-fixed: '#410001'
  on-tertiary-fixed-variant: '#8d1410'
  background: '#fff9ee'
  on-background: '#1d1c15'
  surface-variant: '#e7e2d8'
  alert-green-fg: '#2E7D4F'
  alert-green-bg: '#E6F1EA'
  alert-yellow-fg: '#A8850C'
  alert-yellow-bg: '#FAF2D8'
  alert-orange-fg: '#C06716'
  alert-orange-bg: '#FBEBDC'
  alert-red-fg: '#B33127'
  alert-red-bg: '#FAE8E6'
  alert-discontinued-fg: '#5B6470'
  alert-discontinued-bg: '#EBEDF0'
  alert-none-fg: '#9A968D'
  alert-none-bg: '#F0EEEA'
  source-sitrep-bg: '#E3EFED'
  source-field-bg: '#EEEAF4'
typography:
  headline-lg:
    fontFamily: Public Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Public Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-md:
    fontFamily: Public Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Public Sans
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  technical-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: -0.01em
  technical-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
  stat-lg:
    fontFamily: Public Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  console-gutter: 12px
  card-padding: 16px
  row-height-dense: 32px
  margin-page: 24px
  section-gap: 32px
---

## Brand & Style
The design system is engineered for high-stakes, time-pressured government emergency management. The personality is **authoritative, institutional, and transparently mechanical**. It rejects "consumer SaaS" aesthetics in favor of a dense, high-utility **Operations Console** style. 

The aesthetic is a hybrid of **Modern Corporate** and **Functional Minimalism**, with a strict adherence to the principle that "colour is signal, not decoration." The UI should feel like a precision instrument—reliable, dry, and professional. It uses high-contrast "accent borders" and "tonal bands" to surface critical information without adding visual noise. The primary goal is to minimize cognitive load for officers under stress by ensuring the most severe data (Red Alerts, Verification Failures) is impossible to miss.

## Colors
The palette is divided into functional layers. The **Primary Color** (#14504B) represents authoritative SITREP data and brand identity. The **Secondary Color** (#6B5B8A) identifies unverified Field/Survey123 data. 

**Neutral Bias:** Neutrals use a slight warm bias (`#9A968D` base) to ensure the chromatic alert levels read as active signals rather than UI ornamentation.

**Alert Levels:** These are fixed functional tokens. Never use grey text on a colored background; always use the specific `fg` tint provided for each alert level to ensure accessibility and professional rigor.

**Rules of Application:**
- **Red** is strictly reserved for the "Red" alert level, destructive actions, and verification failures.
- **Source Distinction:** Use the SITREP and Field background tints to group data by its origin. These sources must never visually merge.

## Typography
Typography is optimized for legibility under pressure. **Public Sans** provides open apertures for body text, while **JetBrains Mono** is used for technical markers, citations, and system-generated slugs to denote "machine-verified" content.

**Numerical Integrity:** Every column of figures, stat card, and citation ID must use `tabular-nums` (tnum) to ensure vertical alignment of digits, facilitating rapid scanning of magnitudes.

**Hierarchy Strategy:** Distinguish hierarchy through weight (400 for regular, 600-700 for emphasis) and color rather than drastic size changes. This keeps the interface compact for the operations console.

## Layout & Spacing
The layout follows an **Operations Console** model: high density, low whitespace. 

- **Grid:** Use a 12-column fluid grid for the main dashboard, but prioritize "Fourteen Corporations" as a fixed-row vertical list where silence (no filing) is as visible as activity.
- **Density:** Rows on screen beat whitespace. Use a tight vertical rhythm for tables.
- **Breakpoints:**
  - **Mobile (<768px):** Reflow 14-corporation tables into summary cards; prioritize the "Needs Review" action band at the top.
  - **Desktop (1024px+):** Full multi-pane view showing SITREPS and Field Data side-by-side to allow for instant comparison.
- **Visual Grouping:** Prefer background tonal shifts over borders to separate regions. Use a `12px` console gutter to keep data tightly coupled.

## Elevation & Depth
This system uses **Tonal Layers** and **Bold Leading Borders** rather than shadows to convey hierarchy. 

- **Surface Tiers:** Use subtle background shifts (e.g., a warm-grey-50 vs. white) to distinguish the "Administration" layer from the "Operations" layer. 
- **Accent Borders:** Use 3–4px solid leading-edge borders on cards and table rows to encode status. This is the primary method for surfacing Alert Levels (Green, Red, etc.) without adding heavy fill colors.
- **Depth:** Avoid shadows and blurs. The console should feel flat and "printed" to minimize rendering noise on low-power field devices and to ensure clarity in printed reports.

## Shapes
The shape language is **Soft (0.25rem)**. This slight rounding provides just enough professional finish without the "bubbly" feel of consumer apps. 

- **Standard Radius:** 0.375rem for cards and buttons.
- **Technical Markers:** Use 0px (sharp) or very small radius for citation markers and JetBrains Mono tags to reinforce their "data" nature.
- **Alert Badges:** Use a slightly higher roundedness (pill-style) only for status badges to make them distinct from structural UI elements like buttons.

## Components
- **Alert Badges:** High-contrast background/foreground pairs. The text label must always be present. Use a 4px leading border of the same hue if the badge is embedded in a row.
- **Source Fact Groups:** Authoritative SITREP data groups are styled with a Primary-tinted background. Unverified Field data uses a Secondary-tinted background. Never interleave these; they must occupy distinct visual regions.
- **Action Bands:** When a "Needs Review" count is > 0, it transforms from a statistic into a full-width high-contrast band at the top of the viewport.
- **Citation Markers:** Small, JetBrains Mono blocks (e.g., `[S-04]`). These should look like technical references, not interactive buttons.
- **Status Cards:** Use "Incomplete" styling for reports that fail verification—low saturation, dashed borders, and clear "Verification Failure" labels. Never polish a report that needs review.
- **Data Tables:** High density, no horizontal borders between rows (use alternating tonal stripes instead). Every column of figures must align via tabular numerals.