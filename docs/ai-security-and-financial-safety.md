# AI Security & Financial Safety Invariants

## 1. Safety Invariants (Strict Enforcement)

1. **Recommendations Are Advisory Only**:
   - Every generated recommendation is tagged with `validation_status = NOT_VALIDATED`.
   - The AI engine **never** makes external HTTP requests to Stripe, Razorpay, or banks.
   - It **never** dispatches transactional emails, SMS, or WhatsApp notifications.

2. **Zero Mutation of Authoritative Ledger**:
   - Ingestion and recommendation generation **cannot** change `Transaction.status` to `SUCCESSFUL`.
   - They **cannot** increment `recovered_revenue` metrics.
   - Authoritative revenue recovery is recognized **only** upon cryptographically signed webhook receipts verified in Phase 2.6.

3. **Role-Based Access Control (RBAC)**:
   - `POST /api/v1/cases/{case_id}/recommendations`: Restricted to `OPERATOR` and `ADMIN`.
   - `GET /api/v1/cases/{case_id}/recommendations/*`: Accessible to `OPERATOR`, `ADMIN`, and `AUDITOR`.
   - Webhook Ingestors (`INGESTOR`) and unauthenticated actors are rejected with `403 Forbidden` and `401 Unauthorized`.

4. **Monotonic Audit Trail**:
   - Every decision records an immutable [`AuditEvent`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/models/domain.py) with event type `RECOMMENDATION_GENERATED` and sequential numbering.
   - The raw decision payload is cryptographically hashed with SHA-256 (`raw_response_hash`).
