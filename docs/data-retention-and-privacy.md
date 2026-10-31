# RevenueRescueAI — Data Retention, Privacy & Sanitization Specification
## Phase 1.2: Data Lifecycle, Privacy Governance, and Sanitization Rules

**Document Version:** 1.0.0  
**Status:** Approved Data Governance Policy  
**Primary Authors:** Senior Security Engineer, Compliance Officer, Principal Architect  

---

## 1. Executive Summary & Privacy Posture

In financial software, handling customer data requires balancing two competing legal and operational imperatives:
1. **The Right to Privacy & Erasure (GDPR / CCPA):** Cardholders have the right to request deletion or minimization of their personal data.
2. **Mandatory Financial Record Retention (Tax & Banking Laws):** Financial accounting standards and banking regulations (such as IRS, SOX, and HMRC) require merchants to retain immutable records of financial transactions and recovery attempts for up to **7 years**.

RevenueRescueAI resolves this conflict through **Architectural Separation of Personal Identity from Immutable Financial Ledgers**:
- PII (emails, names) is isolated in `customers` and can be pseudonymized or crypto-shredded.
- Financial ledgers (`transactions`, `recovery_attempts`, `recovery_evidence`) retain anonymized monetary integer values (`amount_minor`, `occurred_at`, `currency`) without personal identifiers.

---

## 2. Data Classification Matrix

| Data Category | Specific Fields | Sensitivity Level | Retention Period | Deletion / Redaction Policy |
| :--- | :--- | :--- | :--- | :--- |
| **Direct PII** | Customer Email, Display Name | **Confidential** | Customer Lifecycle + 30 Days | Redactable / Crypto-shreddable upon valid GDPR erasure request. |
| **Financial Records** | `amount_minor`, `currency`, `occurred_at`, `provider_reference` | **Restricted Financial** | **7 Years** | **Immutable.** Cannot be deleted; preserved for financial auditing. |
| **Workflow State** | `state`, `case_key`, `transitions` | **Internal Operational** | 7 Years | Preserved to prove compliance with retry rules. |
| **Audit Logs** | `audit_events` | **Restricted Compliance** | **7 Years** | **Append-Only.** Deletion and modification strictly forbidden. |
| **Ingress Webhooks** | Raw JSON payloads in `provider_webhook_events` | **Internal Operational** | **90 Days** | Automated purging of operational payloads after 90 days. |
| **Evaluation Data** | `evaluation_results` (Synthetic) | **Non-Sensitive Synthetic**| Duration of Model Lifecycle | May be purged or archived on benchmark deprecation. |

---

## 3. Strict Data Minimization & PCI-DSS Firewalls

### 3.1 Total Prohibition of Raw Cardholder Data (PAN & CVV)
The application architecture is explicitly designed for **Zero Cardholder Data (CHD) Footprint**:
- **Zero Raw Primary Account Numbers (PANs):** Storing 16-digit credit card numbers is strictly prohibited.
- **Zero Card Verification Values (CVVs):** Storing 3-digit security codes is strictly prohibited.
- **Provider Tokenization Only:** If customer payment methods are updated, the system handles opaque provider payment method tokens (e.g., `pm_sim_9918`) or directs customers to provider-hosted update pages.

### 3.2 Automated Safe Serialization (Masking Rules)
1. **Email Masking:** When customer emails are referenced in logs or audit records, they must be masked:
   - Input: `alex.morgan@northstar.io`
   - Stored Safe Value: `a***n@northstar.io`
2. **Error Message Scrubbing:** Gateway error messages often contain raw provider stack traces or internal merchant IDs. The `FailureDiagnosisEngine` parses raw errors into pre-approved, safe domain strings (`failure_message_safe`).

---

## 4. Deletion Restrictions & Referential Integrity

To prevent accidental data loss:
1. **`ON DELETE RESTRICT` on Core Entities:**
   - A `Customer` row cannot be deleted while linked `transactions` or `recovery_cases` exist.
   - A `Transaction` cannot be deleted if a `RecoveryCase` references it.
2. **Cascade Isolation for Testing:**
   - In automated test fixtures, `recovery_cases` cascade deletion to child tables (`recovery_attempts`, `agent_decisions`, `audit_events`) to allow clean teardown between test scenarios.

---

## 5. Test Data vs. Production Data Partitioning

1. **Synthetic Isolation:** The MVP operates exclusively on synthetic customers (prefixed `cus_sim_`) and simulated transactions (prefixed `txn_sim_`).
2. **Evaluation Metric Isolation:** Records produced by the 500-scenario evaluation engine are explicitly flagged `is_synthetic = True` in their metadata. Operational dashboard queries filter out synthetic evaluation rows (`WHERE is_synthetic = FALSE`) to ensure real business metrics are never contaminated.

---

## 6. Jurisdiction-Dependent Open Questions (Marked Unresolved)

> **Compliance Notice:**  
> The system operates under the baseline assumption of 7-year retention for financial transactions and 90-day retention for raw ingress webhooks.  
> Specific jurisdictional retention periods (e.g., German GoBD 10-year rule, French Commercial Code, California CCPA, or Brazilian LGPD) depend on the merchant's incorporation and are marked as **Unresolved Business Questions** to be finalized with the merchant's legal counsel during production deployment.
