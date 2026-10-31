# RevenueRescueAI — Design Tokens Specification: Modern Vanilla CSS Variables

> **Document ID:** DOC-TOK-006  
> **Phase:** 0.3 (Metrics Finalization, Safety Invariants & MVP Approval)  
> **Status:** Approved Baseline  
> **Audience:** Frontend Architecture, UI/UX Engineers, Beginner Developers  

---

## 1. Executive Summary

Design tokens are the atomic building blocks of a design system. They store visual attributes such as colors, typography, spacing, elevations, and glows as standardized, reusable variables. In accordance with the technology stack guidelines, RevenueRescueAI uses **Vanilla CSS Custom Properties (CSS Variables)** to ensure maximum flexibility, zero external CSS framework bloat, and complete theme determinism.

This document establishes the definitive design tokens specification for the Dark Neon Fintech Command Center. Frontend engineers can directly import or copy these tokens into `index.css` to build the entire user interface.

---

## 2. Complete CSS Custom Properties Architecture

```css
:root {
  /* ==========================================================================
     1. COLOR TOKENS — SURFACES & CANVAS
     ========================================================================== */
  --color-canvas-base:         #06090E; /* Deep Void Black: Root background */
  --color-surface-primary:     #0B0F19; /* Midnight Navy: Major panel backdrop */
  --color-surface-elevated:    #111827; /* Rich Dark Charcoal: Elevated cards */
  --color-surface-hover:       #172033; /* Interactive hover card surface */
  --color-surface-active:      #1E293B; /* Active selected element surface */
  --color-surface-table-alt:   #0E1420; /* Zebra striping table row background */
  --color-surface-overlay:     rgba(6, 9, 14, 0.75); /* Modal backdrop filter */
  --color-surface-frosted:     rgba(17, 24, 39, 0.85); /* Glassmorphic panel */

  /* ==========================================================================
     2. COLOR TOKENS — BORDERS & SEPARATORS
     ========================================================================== */
  --color-border-subtle:       #1E293B; /* Default ultra-thin card border */
  --color-border-muted:        #334155; /* Secondary separator border */
  --color-border-cyan:         rgba(6, 182, 212, 0.35); /* Luminous cyan panel border */
  --color-border-cyan-hover:   rgba(6, 182, 212, 0.65); /* Highlighted border */
  --color-border-purple:       rgba(168, 85, 247, 0.35); /* AI intelligence border */
  --color-border-amber:        rgba(245, 158, 11, 0.35); /* At-risk warning border */
  --color-border-focus:        #06B6D4; /* 2px keyboard focus ring */

  /* ==========================================================================
     3. COLOR TOKENS — TYPOGRAPHY & TEXT
     ========================================================================== */
  --color-text-primary:        #FFFFFF; /* Pure high-contrast white */
  --color-text-secondary:      #E2E8F0; /* Slate 200: Body and table text */
  --color-text-muted:          #94A3B8; /* Slate 400: Card titles and captions */
  --color-text-subtle:         #64748B; /* Slate 500: Correlation IDs, timestamps */
  --color-text-disabled:       #475569; /* Slate 600: Inactive controls */

  /* ==========================================================================
     4. COLOR TOKENS — ACCENTS & BRAND
     ========================================================================== */
  --color-accent-cyan:         #06B6D4; /* Electric Cyan: System live nodes */
  --color-accent-cyan-glow:    #22D3EE; /* Cyan highlight shimmer */
  --color-accent-blue:         #3B82F6; /* Royal Blue: Primary controls */
  --color-accent-blue-hover:   #60A5FA; /* Hover state for primary buttons */
  --color-accent-purple:       #A855F7; /* Vivid Purple: AI diagnosis */
  --color-accent-magenta:      #EC4899; /* Neon Magenta: High escalation alert */

  /* ==========================================================================
     5. COLOR TOKENS — SEMANTIC STATUS
     ========================================================================== */
  --color-status-success:      #10B981; /* Emerald: Confirmed recovered revenue */
  --color-status-success-bg:   rgba(16, 185, 129, 0.12);
  --color-status-warning:      #F59E0B; /* Amber: Revenue at risk */
  --color-status-warning-bg:   rgba(245, 158, 11, 0.12);
  --color-status-danger:       #F43F5E; /* Crimson Rose: Terminal hard decline */
  --color-status-danger-bg:    rgba(244, 63, 94, 0.12);
  --color-status-info:         #06B6D4; /* Cyan: Eligible / Active */
  --color-status-info-bg:      rgba(6, 182, 212, 0.12);
  --color-status-pending:      #6366F1; /* Indigo: Verification pending */
  --color-status-pending-bg:   rgba(99, 102, 241, 0.12);

  /* ==========================================================================
     6. TYPOGRAPHY TOKENS — FONTS & HIERARCHY
     ========================================================================== */
  --font-family-sans:          'Inter', 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-family-mono:          'JetBrains Mono', 'Roboto Mono', monospace;

  --font-size-2xs:             0.6875rem; /* 11px: Micro metadata */
  --font-size-xs:              0.75rem;   /* 12px: Secondary timestamps */
  --font-size-sm:              0.875rem;  /* 14px: Standard body & table */
  --font-size-base:            1.0rem;    /* 16px: Standard form labels */
  --font-size-lg:              1.125rem;  /* 18px: Large subheadings */
  --font-size-xl:              1.25rem;   /* 20px: Panel titles */
  --font-size-2xl:             1.75rem;   /* 28px: Monospace KPI numbers */
  --font-size-3xl:             2.0rem;    /* 32px: Viewport headers */

  --font-weight-regular:       400;
  --font-weight-medium:        500;
  --font-weight-semibold:      600;
  --font-weight-bold:          700;

  --line-height-tight:         1.2;
  --line-height-normal:        1.5;
  --line-height-relaxed:       1.625;

  --letter-spacing-tight:      -0.02em;
  --letter-spacing-normal:     0em;
  --letter-spacing-wider:      0.05em;

  /* ==========================================================================
     7. SPACING SCALE (4px Base Grid)
     ========================================================================== */
  --space-1:                   4px;
  --space-2:                   8px;
  --space-3:                   12px;
  --space-4:                   16px;
  --space-5:                   20px;   /* Standard KPI card internal padding */
  --space-6:                   24px;   /* Non-negotiable master grid gap */
  --space-8:                   32px;   /* Master workspace canvas padding */
  --space-10:                  40px;
  --space-12:                  48px;
  --space-16:                  64px;

  /* ==========================================================================
     8. BORDER RADIUS TOKENS
     ========================================================================== */
  --radius-xs:                 4px;    /* Nested status badges */
  --radius-sm:                 6px;    /* Form inputs, buttons */
  --radius-md:                 8px;    /* Tooltips, context menus */
  --radius-lg:                 12px;   /* Standard elevated cards, table container */
  --radius-xl:                 16px;   /* Main chart and drawer containers */
  --radius-full:               9999px; /* Circular avatar chips, pills */

  /* ==========================================================================
     9. ELEVATION & DEPTH SHADOWS
     ========================================================================== */
  --shadow-elevation-0:        none;
  --shadow-elevation-1:        0 4px 6px -1px rgba(0, 0, 0, 0.4), 
                               0 2px 4px -2px rgba(0, 0, 0, 0.4);
  --shadow-elevation-2:        0 10px 25px -5px rgba(0, 0, 0, 0.6), 
                               0 8px 10px -6px rgba(0, 0, 0, 0.5); /* Resting card */
  --shadow-elevation-3:        0 14px 28px -4px rgba(0, 0, 0, 0.75), 
                               0 10px 15px -3px rgba(0, 0, 0, 0.6); /* Hover card */
  --shadow-drawer:             -15px 0 35px -5px rgba(0, 0, 0, 0.85);

  /* ==========================================================================
     10. SELECTIVE MULTICOLOUR AMBIENT GLOW TOKENS (6 Prominent Containers Only)
     ========================================================================== */
  /* 1. Confirmed Recovered Revenue KPI Card Glow */
  --glow-recovered-resting:    0 10px 25px -5px rgba(0, 0, 0, 0.6),
                               0 0 25px -2px rgba(6, 182, 212, 0.18);
  --glow-recovered-hover:      0 14px 28px -4px rgba(0, 0, 0, 0.75),
                               0 0 35px 0 rgba(6, 182, 212, 0.30);

  /* 2. Revenue at Risk KPI Card Glow */
  --glow-at-risk-resting:      0 10px 25px -5px rgba(0, 0, 0, 0.6),
                               0 0 25px -2px rgba(245, 158, 11, 0.16);
  --glow-at-risk-hover:        0 14px 28px -4px rgba(0, 0, 0, 0.75),
                               0 0 35px 0 rgba(245, 158, 11, 0.26);

  /* 3. Main Revenue Trends Chart Container Glow */
  --glow-chart-container:      0 12px 30px -5px rgba(0, 0, 0, 0.65),
                               0 0 30px -5px rgba(168, 85, 247, 0.12),
                               0 0 40px -10px rgba(6, 182, 212, 0.10);

  /* 4. Primary Workflow Status Container Glow */
  --glow-workflow-container:   0 12px 30px -5px rgba(0, 0, 0, 0.65),
                               0 0 30px -5px rgba(99, 102, 241, 0.14);

  /* 5. Diagnostic Trace Drawer Edge Glow */
  --glow-drawer-active:        -10px 0 30px rgba(6, 182, 212, 0.20),
                               -2px 0 10px rgba(6, 182, 212, 0.35);

  /* 6. High-Priority Escalation Modal Glow */
  --glow-escalation-alert:     0 0 35px rgba(236, 72, 153, 0.25),
                               0 20px 40px rgba(0, 0, 0, 0.85);

  /* Clean Containers (Glow strictly disabled) */
  --glow-none:                 none;

  /* ==========================================================================
     11. COMPONENT DIMENSION TOKENS
     ========================================================================== */
  --dim-sidebar-width-desktop: 260px;
  --dim-sidebar-width-compact: 72px;
  --dim-topbar-height:         64px;
  --dim-kpi-card-height:       152px; /* Mandatory symmetrical KPI height */
  --dim-analytics-panel-height:380px; /* Aligned chart & workflow panel height */
  --dim-table-row-height:      48px;  /* Uniform high-density table rows */
  --dim-table-header-height:   40px;
  --dim-drawer-width:          540px; /* Diagnostic slide-over inspector */
  --dim-control-height-sm:     32px;  /* Small action buttons, filters */
  --dim-control-height-md:     40px;  /* Standard inputs, search bar */
  --dim-control-height-lg:     48px;  /* Primary modal CTA buttons */

  /* ==========================================================================
     12. TRANSITION & ANIMATION TIMING
     ========================================================================== */
  --transition-fast:           150ms cubic-bezier(0.16, 1, 0.3, 1);
  --transition-normal:         250ms cubic-bezier(0.16, 1, 0.3, 1);
  --transition-drawer:         350ms cubic-bezier(0.16, 1, 0.3, 1);
}

/* Reduced Motion Override for Accessibility */
@media (prefers-reduced-motion: reduce) {
  :root {
    --transition-fast:         0ms !important;
    --transition-normal:       0ms !important;
    --transition-drawer:       0ms !important;
  }
}
```

---

## 3. Component Styling Guidelines with Tokens

### Symmetrical KPI Card Base Rule
```css
.fintech-kpi-card {
  height: var(--dim-kpi-card-height);
  padding: var(--space-5);
  background-color: var(--color-surface-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-elevation-2);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: transform var(--transition-normal), box-shadow var(--transition-normal), border-color var(--transition-normal);
}

.fintech-kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-elevation-3);
  border-color: var(--color-border-muted);
}
```

### Clean Table Row Rule (No Distracting Glow)
```css
.fintech-table-row {
  height: var(--dim-table-row-height);
  border-bottom: 1px solid var(--color-border-subtle);
  background-color: transparent;
  box-shadow: var(--glow-none); /* Absolutely no glow */
  transition: background-color var(--transition-fast);
}

.fintech-table-row:hover {
  background-color: var(--color-surface-hover);
}

.fintech-table-amount {
  font-family: var(--font-family-mono);
  font-variant-numeric: tabular-nums;
  text-align: right;
  color: var(--color-text-primary);
}
```
