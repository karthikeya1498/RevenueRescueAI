# RevenueRescue AI — Five-Minute Submission Video

**Author:** Karthikeya  
**Target duration:** 5:00  
**Mode:** screen-recorded walkthrough with concise narration  
**Source of truth:** verified Phase 8/9 synthetic evaluation baseline, seed `42`, rule version `phase8.v1`

## Recording notes

Record the local frontend at a readable desktop width. Keep the browser zoom at 100%. Use the dashboard in simulation mode. Do not claim that the displayed synthetic figures represent production revenue or that the UI executes a real payment. The presenter should pause briefly on the trace drawer so the panel can see the reasoning and safety boundaries.

## Storyboard and narration

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:25 | Title card or command center landing state | “RevenueRescue AI is an agentic revenue recovery system. When a payment fails or revenue becomes at risk, the system detects the signal, gathers context, proposes a bounded action, validates it through deterministic policy, handles uncertainty safely, and audits the complete journey.” |
| 0:25–0:55 | Overview command center | “This is the visual command center. The 500-scenario evaluation baseline shows 400 at-risk cases, 182 recovered cases, 980,887 minor units recovered, and a 100 percent safety rate. These are synthetic regression metrics, not a production forecast.” |
| 0:55–1:25 | Recovery queue | “The recovery queue is designed for human-in-the-loop operations. It separates awaiting decisions, verification-pending cases, and escalations. The system does not hide uncertainty behind a successful-looking recovery number.” |
| 1:25–2:25 | Agent Traces page; open the Northstar Labs trace | “The transaction trace is the central observability surface. First, the system detects a failed payment. Then it gathers customer and attempt context. The structured agent proposes a retry with confidence 0.94. The deterministic policy validates that this is attempt one of two. The controlled tool returns a simulated success. Each step has a timestamp and an explicit outcome.” |
| 2:25–3:05 | Open the Asteria Living uncertain trace | “Here is the failure story. A provider outcome is unknown. The system does not blindly retry. It preserves uncertainty, routes the case to verification, and makes operator review visible. This is the behavior we want from an agentic financial system: uncertainty becomes a state, not an exception that disappears.” |
| 3:05–3:40 | Evaluation Lab | “The Evaluation Lab measures recovery revenue, case recovery rate, action accuracy, safety, failure classifications, escalation routes, verification routes, stops, and rejections. Action accuracy is deliberately reported separately from revenue recovery so the system cannot optimize for revenue while hiding poor decisions.” |
| 3:40–4:15 | Architecture or code/documentation view | “Under the interface are explicit layers: deterministic risk detection, structured agent contracts, allow-listed tools, policy enforcement, resilience classification, and reproducible evaluation. Real provider execution and customer communication remain disabled in this demonstration.” |
| 4:15–4:45 | Readiness/health or repository overview | “Phase 10 adds production-style polish: request correlation IDs, structured access events, liveness and readiness endpoints, migration smoke checks, a non-root container, Compose configuration, CI, and comprehensive tests.” |
| 4:45–5:00 | Return to overview; final title card | “RevenueRescue AI is built around a simple rule: recover revenue, but never at the cost of control. The next production steps would be approved provider contracts, authentication, persistent audit retention, real data governance, and a reviewed rollout.” |

## Exact claims allowed on screen

The following claims are supported by the repository’s verified artifacts: 500 deterministic scenarios; 400 at-risk cases; 182 recovered cases; 980,887 recovered minor units; 45.34 percent revenue recovery rate; 45.50 percent case recovery rate; 20 percent action accuracy; 100 percent safety rate; 181 failure classifications; 90 escalations; 91 verification routes; 46 stops; and 46 rejections.

## Recording checklist

Before recording, run the frontend build, start the local backend/frontend services, verify the trace drawer, open one successful trace and one uncertain trace, and keep the 500-scenario report available for reference. After recording, check that the five-minute video does not expose secrets, local filesystem paths, or unverified production claims.
