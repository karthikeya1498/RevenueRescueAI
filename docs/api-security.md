# RevenueRescueAI — API Security, Authentication, & Access Governance
## Phase 1.3: Authentication Protocols, RBAC Matrix, Threat Mitigation, and Sanitization

**Document Version:** 1.0.0  
**Status:** Approved API Security Specification  
**Primary Authors:** Senior Security Architect, API Designer, DevOps Engineer  

---

## 1. Executive Summary & Zero-Trust Posture

The RevenueRescueAI API operates under a **Zero-Trust Financial Security Architecture**:
1. **Never Trust the Client:** Every incoming payload is validated against strict Pydantic v2 schemas; client-side validation is treated as a user experience convenience, not a security boundary.
2. **Never Trust External Events:** All inbound payment events must pass cryptographic HMAC-SHA256 signature verification and replay defense before processing.
3. **Never Trust AI Recommendations:** Machine learning models have zero authorization to execute financial tools; all actions must pass the Deterministic Policy Gate.
4. **Least-Privilege RBAC:** Operators, auditors, system ingestors, and administrators possess strictly bounded permissions.

---

## 2. Authentication Mechanisms

RevenueRescueAI implements two distinct authentication protocols based on caller identity:

### 2.1 Operator & Client Authentication: Bearer Tokens (JWT)
- **Used by:** Frontend Dashboard, Human Operators, Compliance Auditors, Administrators.
- **Header Format:**
  ```http
  Authorization: Bearer <jwt_token>
  ```
- **Token Properties:** Cryptographically signed using HMAC-SHA256 (or asymmetric RS256 in production). Contains actor ID, role, and expiration timestamp (`exp`).
- **Token Expiration:** Short-lived access tokens (1 hour) with refresh rotation.

### 2.2 Provider Webhook Authentication: HMAC-SHA256 Signatures
- **Used by:** External Payment Gateways & Payment Provider Simulator.
- **Header Format:**
  ```http
  X-Signature-SHA256: t=1730289851,v1=5257a863e5b99a02f98...
  X-Event-ID: evt_sim_99812
  ```
- **Replay Attack Defense:** The signature incorporates a UNIX timestamp (`t=`). Payloads arriving with timestamps older than **300 seconds (5 minutes)** are rejected immediately with HTTP 401 Unauthorized.
- **Timing Attack Defense:** Signature comparison uses constant-time string equality (`hmac.compare_digest`).

---

## 3. Role-Based Access Control (RBAC) Matrix

The system defines **Four User Roles**:

| Endpoint Category | Specific Endpoint Paths | `ROLE_INGESTOR` | `ROLE_OPERATOR` | `ROLE_AUDITOR` | `ROLE_ADMIN` |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **System Health** | `GET /health`, `GET /ready` | **Public** | **Public** | **Public** | **Public** |
| **Dashboard** | `GET /api/v1/dashboard/metrics`<br>`GET /api/v1/dashboard/trend` | Denied | **Allowed** | **Allowed** | **Allowed** |
| **Cases (Read)** | `GET /api/v1/cases`<br>`GET /api/v1/cases/{id}`<br>`GET /api/v1/cases/{id}/timeline` | Denied | **Allowed** | **Allowed** | **Allowed** |
| **Webhook Ingress**| `POST /api/v1/webhooks/provider` | **Allowed** | Denied | Denied | Denied |
| **Simulate Event** | `POST /api/v1/events/simulate-failure` | Denied | **Allowed** | Denied | **Allowed** |
| **AI Preview** | `POST /api/v1/recovery/decision-preview`| Denied | **Allowed** | **Allowed** | **Allowed** |
| **Case Actions** | `POST /api/v1/cases/{id}/actions/retry`<br>`POST /api/v1/cases/{id}/actions/escalate`<br>`POST /api/v1/cases/{id}/actions/stop` | Denied | **Allowed** | Denied | **Allowed** |
| **Audit Ledger** | `GET /api/v1/cases/{id}/audit-trail` | Denied | Denied | **Allowed** | **Allowed** |
| **Verification** | `POST /api/v1/verification/verify-evidence` | **Allowed** | Denied | Denied | **Allowed** |
| **Evaluation Run** | `POST /api/v1/evaluation/run` | Denied | Denied | Denied | **Allowed** |
| **Realtime Stream**| `WSS /api/v1/ws/realtime` | Denied | **Allowed** | **Allowed** | **Allowed** |

---

## 4. Ingress Protection & Rate Limiting

To prevent Denial of Service (DoS) attacks, brute-force enumeration, and webhook flooding:

| Route Scope | Rate Limit Threshold | Window | Breach Response |
| :--- | :--- | :--- | :--- |
| **Webhook Ingress** | 100 requests per minute per IP | Sliding 60s | `429 Too Many Requests` + `Retry-After: 60` |
| **Operator Actions** | 60 requests per minute per User | Sliding 60s | `429 Too Many Requests` |
| **Evaluation Batches**| 5 batch runs per hour per Admin | Sliding 60m | `429 Too Many Requests` |
| **Public Health** | 120 requests per minute per IP | Sliding 60s | `429 Too Many Requests` |

---

## 5. Sensitive Data Redaction & Privacy

1. **Zero Cardholder Data (PCI-DSS):** The API never accepts or transmits raw credit card numbers (PANs) or card security codes (CVVs). Only opaque provider references (`pm_sim_...`) are accepted.
2. **Customer Email Masking:** Customer emails returned in case detail endpoints are masked (`alex.morgan@northstar.io` is serialized as `a***n@northstar.io`).
3. **Redacted Audit Logging:** The `RequestObservabilityMiddleware` automatically masks the `Authorization` header, `X-Signature-SHA256` header, and any payload keys matching `password`, `secret`, or `token`.

---

## 6. Prompt Injection Firewall for AI Endpoints

When customer metadata (notes, transaction descriptions) enters the AI reasoning pipeline:
1. **Delimited Input Structure:** User-supplied text is isolated in XML tags (`<customer_note>...</customer_note>`).
2. **Strict Schema Gate:** The model cannot output free-form actions; outputs must parse into `AgentDecisionContract`.
3. **Deterministic Override:** Even if prompt injection instructs the model to return `RETRY_NOW`, the Deterministic Policy Gate rejects the action if the account has spent its 2-retry budget.
