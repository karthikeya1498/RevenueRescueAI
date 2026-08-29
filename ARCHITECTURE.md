# Architecture

RevenueRescue AI separates event detection, context, reasoning, policy, tools, verification, persistence, and presentation. The future LLM is an untrusted decision proposer; deterministic policy remains the authority for permitted action.

```mermaid
flowchart TD
  E[Revenue-risk event] --> D[Deterministic detector]
  D --> C[Context service]
  C --> A[Agent reasoning]
  A --> P[Policy gate]
  P --> T[Controlled tool]
  T --> V[Outcome verification]
  V --> R[Recover, retry, escalate, or stop]
  R --> AU[Audit event]
```

```mermaid
flowchart LR
  UI[React frontend] --> API[FastAPI API]
  API --> S[Services/workflows]
  S --> DB[(Persistence boundary)]
  S --> AG[Agent boundary]
  AG --> POL[Policy boundary]
  POL --> TOOLS[Tool boundary]
```

Phase 1 implements only the API composition, health contract, configuration, logging, and minimal frontend. The rest is documented future architecture.
