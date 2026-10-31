# ADR-002: Frontend Technology — React 19, TypeScript, Vite & Vanilla CSS Tokens

**Status:** Approved  
**Date:** 2026-10-30  
**Deciders:** Senior Full-Stack Engineer, UI/UX Design Lead  

---

## 1. Context
The user interface must deliver a premium dark neon fintech command center featuring 152px symmetrical KPI cards, responsive recovery queues, real-time agent trace inspections, and 500-scenario evaluation reports.

## 2. Problem
Which frontend framework, build tool, and styling paradigm will provide rapid rendering, zero dependency bloat, and strict adherence to the fintech design tokens?

## 3. Options Considered
1. **Next.js (App Router):** Server-side rendered full-stack framework with React Server Components.
2. **React 19 + TypeScript + Vite + Vanilla CSS Custom Tokens:** Client-side SPA built on native ES modules, strict static typing, and pure CSS variables.
3. **React + Tailwind CSS:** Utility-first CSS framework with JIT compiler.
4. **Vue 3 + Nuxt:** Progressive JavaScript framework with single-file components.

## 4. Decision
We choose **React 19 with TypeScript, Vite, and Vanilla CSS Custom Properties (Design Tokens)**.

## 5. Reasons
- **Sub-Second HMR:** Vite provides near-instant Hot Module Replacement (<50ms), accelerating UI development.
- **Pure Client SPA:** An authenticated internal fintech dashboard requires zero public SEO. Server-side rendering (SSR) in Next.js introduces unnecessary runtime complexity, server memory overhead, and hydration pitfalls.
- **Design Token Purity:** Vanilla CSS Custom Properties (`var(--bg-app)`, `var(--accent-cyan)`) in `index.css` provide 100% exact control over symmetrical dimensions (152px cards) and neon glow filters without downloading megabytes of utility CSS or PostCSS plugins.
- **Type Safety:** TypeScript guarantees that case states, monetary integer minors, and trace steps conform to backend schemas.

## 6. Trade-offs & Consequences
- **Positive:** Blazing fast build times, clean CSS architecture, zero runtime CSS-in-JS overhead, standard browser compatibility.
- **Negative:** Complex routing requires client-side state/view management rather than file-based server routes.

## 7. Reconsideration Conditions
Re-evaluate Next.js only if public customer-facing payment portal pages require search engine optimization (SEO) or edge-rendered personalization.
