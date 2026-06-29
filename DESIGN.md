# QuoteSquad Design System

## 1. Atmosphere & Identity

QuoteSquad feels like a quiet evidence room for messy quotes: precise, calm, and slightly forensic. The signature is annotated confidence: every surface makes source quality, uncertainty, and next action visible without turning the product into a dashboard.

## 2. Color

### Palette

| Role | Token | Light | Dark | Usage |
|------|-------|-------|------|-------|
| Surface/primary | --surface-primary | #F7F8F3 | #10120F | Main background |
| Surface/secondary | --surface-secondary | #FFFFFF | #171A16 | Panels, forms |
| Surface/elevated | --surface-elevated | #F0F2EA | #20241E | Raised evidence blocks |
| Text/primary | --text-primary | #151712 | #F6F7F1 | Headlines, body |
| Text/secondary | --text-secondary | #5E655A | #B7BDAF | Captions, hints |
| Text/tertiary | --text-tertiary | #858D7E | #7C8475 | Disabled, muted |
| Border/default | --border-default | #DDE2D4 | #343A30 | Dividers, outlines |
| Border/subtle | --border-subtle | #E9EDE3 | #272D24 | Soft separations |
| Accent/primary | --accent-primary | #1D6B4F | #5DDEAC | CTAs, links, focus |
| Accent/hover | --accent-hover | #15533D | #80E8BF | Hover state |
| Status/success | --status-success | #167447 | #4ADE80 | Confirmed savings |
| Status/warning | --status-warning | #B56B05 | #FBBF24 | Caveats |
| Status/error | --status-error | #B42318 | #F87171 | Overcharge findings |
| Status/info | --status-info | #245A86 | #7DD3FC | Informational gaps |

### Rules

- Accent is reserved for actions, focus rings, and linked citations.
- Evidence states use semantic status colors only.
- Extend this table before introducing a new color.

## 3. Typography

### Scale

| Level | Size | Weight | Line Height | Tracking | Usage |
|-------|------|--------|-------------|----------|-------|
| Display | 48px | 760 | 1.08 | 0 | Product title |
| H1 | 36px | 720 | 1.15 | 0 | Page titles |
| H2 | 28px | 680 | 1.25 | 0 | Section headers |
| H3 | 20px | 660 | 1.35 | 0 | Finding titles |
| Body/lg | 18px | 450 | 1.55 | 0 | Lead copy |
| Body | 16px | 430 | 1.6 | 0 | Default text |
| Body/sm | 14px | 430 | 1.5 | 0 | Secondary info |
| Caption | 12px | 600 | 1.4 | 0.02em | Labels, metadata |
| Overline | 11px | 700 | 1.3 | 0.08em | Rare section labels |

### Font Stack

- Primary: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
- Mono: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace

### Rules

- No body text below 14px.
- Confidence and money figures use the mono stack only when tabular alignment matters.

## 4. Spacing & Layout

### Base Unit

All spacing derives from a base of 4px.

| Token | Value | Usage |
|-------|-------|-------|
| --space-1 | 4px | Tight inline gaps |
| --space-2 | 8px | Compact controls |
| --space-3 | 12px | Field padding |
| --space-4 | 16px | Standard groups |
| --space-5 | 20px | Panel inner gaps |
| --space-6 | 24px | Card padding |
| --space-8 | 32px | Section groups |
| --space-10 | 40px | Major page rhythm |
| --space-12 | 48px | Hero rhythm |
| --space-16 | 64px | Maximum vertical separation |

### Grid

- Max content width: 1180px
- Column system: 12-column desktop, single-column mobile
- Breakpoints: sm 640px, md 768px, lg 1024px, xl 1280px

### Rules

- Forms and reports use dense but breathable spacing.
- No nested cards; evidence items are individual panels.

## 5. Components

### Evidence Panel

- **Structure**: status stripe, title row, finding copy, source row.
- **Variants**: verified, caveated, unverified, suppressed.
- **Spacing**: --space-5 inner padding, --space-3 internal gaps.
- **States**: hover raises border contrast; focus outlines citations.
- **Accessibility**: semantic headings, visible status text, linked citations.
- **Motion**: opacity and translate only, 180ms standard easing.

### Upload Form

- **Structure**: quote text, optional file, zip, consent, submit.
- **Variants**: empty, loading, error.
- **Spacing**: --space-4 between fields, --space-6 panel padding.
- **States**: focus, disabled, loading.
- **Accessibility**: labels above inputs, errors below fields.
- **Motion**: submit button active translate only.

## 6. Motion & Interaction

### Timing

| Type | Duration | Easing | Usage |
|------|----------|--------|-------|
| Micro | 120ms | ease-out | Button press |
| Standard | 220ms | ease-in-out | Panel transitions |
| Emphasis | 420ms | cubic-bezier(0.16, 1, 0.3, 1) | Initial reveal |

### Rules

- Animate transform and opacity only.
- Respect prefers-reduced-motion.
- Every interactive element has hover, active, and focus states.

## 7. Depth & Surface

### Strategy

Borders-only with tonal shifts. No drop shadows in the default UI.

| Type | Value | Usage |
|------|-------|-------|
| Default | 1px solid var(--border-default) | Panels, controls |
| Subtle | 1px solid var(--border-subtle) | Dividers |
