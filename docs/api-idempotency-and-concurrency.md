# RevenueRescueAI — API Idempotency & Concurrency Defenses
## Phase 1.3: Duplicate Prevention, Idempotency Contracts, and Race Condition Mitigation

**Document Version:** 1.0.0  
**Status:** Approved Idempotency Architecture  
**Primary Authors:** Senior Financial Systems Engineer, API Designer, Database Architect  

---

## 1. What is Idempotency? (Beginner-Friendly Explanation)

In simple English:
> **An operation is idempotent if doing it once has the exact same effect as doing it ten times.**

### The Double-Click Financial Nightmare:
Imagine an operator in the dashboard clicks the button **"Retry Payment ($8,420.00)"**.
- Their browser lags for half a second.
- Thinking nothing happened, they click the button a second time.
- If the API is **not idempotent**, the backend charges the customer's credit card **twice**, taking $16,840.00! The customer is furious, their card is overdrawn, and the merchant incurs bank dispute fees.
- If the API **is idempotent**, the second click is recognized as a duplicate of the first. The card is charged **once**, and the second request simply returns the receipt from the first charge.

---

## 2. The Seven Causes of Duplicate Financial Execution

RevenueRescueAI protects against duplicate financial side effects across seven distinct operational scenarios:

| Cause of Duplication | Attack / Failure Vector | Architectural Mitigation Strategy |
| :--- | :--- | :--- |
| **1. UI Double-Click** | Operator clicks action button twice within 500ms. | Frontend disables button immediately; backend enforces `Idempotency-Key`. |
| **2. Browser Refresh** | Operator refreshes the browser page while a POST is pending. | Browser resends identical headers; backend returns cached result. |
| **3. Gateway Network Timeout** | Client sends request; backend charges card; response packet drops. | Client retries with identical key; backend returns cached charge receipt. |
| **4. Duplicate Webhook** | Payment provider sends the same failure event 3 times in 5 minutes. | `uq_provider_event` constraint drops duplicates with HTTP 200. |
| **5. Automated Retry Loop** | Background scheduler attempts to retry a case concurrently. | Pessimistic locking (`SELECT FOR UPDATE`) serializes the workers. |
| **6. Multi-Worker Contention**| Two background daemon threads pick up the same case queue item. | Unique composite constraint `uq_attempt_case_sequence` blocks second worker. |
| **7. Cross-Payload Replay** | Attacker replays an existing key with a different amount or currency. | SHA-256 payload fingerprinting raises HTTP 409 `IDEMPOTENCY_CONFLICT`. |

---

## 3. The `Idempotency-Key` Protocol Specification

Every mutating financial endpoint (such as `POST /api/v1/cases/{case_id}/actions/retry`) mandates an idempotency key passed via HTTP request headers:

```http
POST /api/v1/cases/f7a28190-8812-4c22-b912-334455667788/actions/retry HTTP/1.1
Host: api.revenuerescue.io
Authorization: Bearer <token>
Idempotency-Key: idemp_f7a28190_seq1_99812
Content-Type: application/json

{
  "justification": "Operator manual retry approval."
}
```

### 3.1 Idempotency Key Rules:
1. **Format:** Non-empty string between 16 and 250 characters (typically a UUIDv4 or deterministic composite token).
2. **Payload Fingerprinting:** When a request is received, the backend computes a SHA-256 hash of `(case_id, request_path, request_body)`.
3. **Storage:** The key and payload fingerprint are stored in `recovery_attempts.idempotency_key`.
4. **Retention Window:** Idempotency records are retained for **7 days** to satisfy all payment gateway retry loops.

---

## 4. Concurrency Scenarios & Response Matrix

```
                        +---------------------------------------+
                        |      INCOMING MUTATING API REQUEST    |
                        |      (with Idempotency-Key Header)    |
                        +---------------------------------------+
                                            |
                                            v
                        +---------------------------------------+
                        |   DOES IDEMPOTENCY KEY EXIST IN DB?   |
                        +---------------------------------------+
                                   /                 \
                          [ NO ]                     [ YES ]
                            /                           \
                           v                             v
            +---------------------------+   +---------------------------+
            | 1. Record Attempt as      |   | Compare Payload Hashes:   |
            |    'STARTED'              |   | Does current payload      |
            | 2. Execute side effect    |   | match the stored one?     |
            | 3. Store result & commit  |   +---------------------------+
            +---------------------------+          /             \
                           |               [ MATCH ]             [ MISMATCH ]
                           v                   /                     \
                 Return 200 OK / 201          v                       v
                                    +-------------------+   +-------------------+
                                    | Return Cached     |   | Return HTTP 409   |
                                    | Stored Response   |   | Conflict Error    |
                                    | (Idempotent-      |   | (IDEMPOTENCY_     |
                                    |  Replay: true)    |   |  CONFLICT)        |
                                    +-------------------+   +-------------------+
```

### 4.1 Scenario A: Identical Key with Identical Payload (Replay)
- **Status Code:** `200 OK`
- **Response Header:** `Idempotent-Replay: true`
- **Response Body:** The exact saved JSON response from the original execution.
- **Side Effect:** **Zero.** No charge is dispatched to the payment provider.

### 4.2 Scenario B: Identical Key with Conflicting Payload (Tampering)
- If a client sends the same key but alters the amount or justification:
- **Status Code:** `409 Conflict`
- **Error Response:**
  ```json
  {
    "success": false,
    "error": {
      "code": "IDEMPOTENCY_CONFLICT",
      "message": "The idempotency key was previously used with a different request payload.",
      "request_id": "req_conflict_01"
    }
  }
  ```

### 4.3 Scenario C: Concurrent In-Flight Execution
- If Request 2 arrives while Request 1 is actively executing:
- **Behavior:** Request 2 blocks on the database row lock (`SELECT FOR UPDATE`). When Request 1 completes and commits, Request 2 unblocks, detects the committed key, and returns the cached result without duplicate execution.

---

## 5. Uncertain Outcomes (HTTP 504) & The Verification Handshake

When an external provider call times out (e.g., HTTP 504 Gateway Timeout or TCP connection drop), **the payment may or may not have succeeded on the cardholder's bank account**.

### Invariant INV-008: Strict Prohibition of Blind Retries
Under no circumstances may a client or background worker retry an uncertain payment immediately.

```
+-----------------------------------------------------------------------------------+
|                        SAFE RESOLUTION OF UNCERTAIN OUTCOMES                      |
|                                                                                   |
|  [ Client / Operator ]                 [ Backend API ]        [ Payment Provider ]|
|            |                                  |                        |          |
|            |--- 1. POST /actions/retry ------>|                        |          |
|            |                                  |--- 2. POST /charges -->|          |
|            |                                  |x-- 504 Timeout --------|          |
|            |                                  |                        |          |
|            |<-- 3. HTTP 504 OUTCOME_UNCERTAIN |                        |          |
|            |    (state: verification_pending) |                        |          |
|            |                                  |                        |          |
|            |    [ NO BLIND RETRY PERMITTED ]  |                        |          |
|            |                                  |                        |          |
|            |--- 4. Query Case Status -------->|                        |          |
|            |    GET /cases/{case_id}          |--- 5. GET /charges?key-|          |
|            |                                  |<-- 6. Returns Succeeded|          |
|            |                                  |                        |          |
|            |<-- 7. Case Updated to RECOVERED -| (Proof Verified <72h)  |          |
+-----------------------------------------------------------------------------------+
```
