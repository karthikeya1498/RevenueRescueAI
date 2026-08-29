# Failure Handling

The system treats external uncertainty as a first-class state. Malformed AI output is rejected and escalated; timeouts and ambiguous payment responses remain uncertain or pending; database failures stop side effects until state is safely persisted; duplicate requests are absorbed through idempotency; partial failures are recorded for resumability.

Retries must be bounded, classified, observable, and policy-approved. Safe states are preferred over optimistic completion. Future logs will include severity, component, correlation ID, case ID, and outcome without secrets or full sensitive payloads.
