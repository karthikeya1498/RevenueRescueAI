"""Domain enumerations shared by persistence and future services.

Author: Karthikeya
Architectural layer: domain vocabulary.
"""

from enum import StrEnum


class CustomerStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    RESTRICTED = "restricted"


class TransactionStatus(StrEnum):
    CREATED = "created"
    AUTHORIZED = "authorized"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PENDING = "pending"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    UNKNOWN = "unknown"


class RecoveryCaseState(StrEnum):
    DETECTED = "detected"
    CONTEXT_READY = "context_ready"
    AWAITING_DECISION = "awaiting_decision"
    ACTION_PENDING = "action_pending"
    VERIFICATION_PENDING = "verification_pending"
    RECOVERED = "recovered"
    RETRY_ELIGIBLE = "retry_eligible"
    ESCALATED = "escalated"
    STOPPED = "stopped"
    CLOSED = "closed"


class RecoveryAttemptStatus(StrEnum):
    PLANNED = "planned"
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    CANCELLED = "cancelled"


class ActionType(StrEnum):
    NONE = "none"
    RETRY_PAYMENT = "retry_payment"
    SEND_REMINDER = "send_reminder"
    REQUEST_OPERATOR_REVIEW = "request_operator_review"
    STOP = "stop"


class DecisionValidationStatus(StrEnum):
    NOT_VALIDATED = "not_validated"
    VALID = "valid"
    INVALID = "invalid"
    REJECTED_BY_POLICY = "rejected_by_policy"


class ActorType(StrEnum):
    SYSTEM = "system"
    OPERATOR = "operator"
    AGENT = "agent"
    PROVIDER = "provider"
    USER = "user"
    TEST = "test"


class UserRole(StrEnum):
    ADMIN = "ROLE_ADMIN"
    OPERATOR = "ROLE_OPERATOR"
    AUDITOR = "ROLE_AUDITOR"
    INGESTOR = "ROLE_INGESTOR"


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"


class CanonicalEventType(StrEnum):
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_SUCCEEDED = "PAYMENT_SUCCEEDED"
    SUBSCRIPTION_PAYMENT_FAILED = "SUBSCRIPTION_PAYMENT_FAILED"
    CHECKOUT_ABANDONED = "CHECKOUT_ABANDONED"
    INVOICE_OVERDUE = "INVOICE_OVERDUE"


class EventProcessingStatus(StrEnum):
    RECEIVED = "received"
    VALIDATED = "validated"
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"
    REJECTED = "rejected"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class FailureCategory(StrEnum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    CARD_EXPIRED = "card_expired"
    AUTHENTICATION_REQUIRED = "authentication_required"
    DO_NOT_HONOR = "do_not_honor"
    GENERIC_DECLINE = "generic_decline"
    PROCESSING_ERROR = "processing_error"
    FRAUD_SUSPECTED = "fraud_suspected"
    ABANDONED = "abandoned"
    OVERDUE = "overdue"
    UNKNOWN = "unknown"


class RiskTier(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConsentType(StrEnum):
    RECURRING_BILLING = "recurring_billing"
    COMMUNICATION_EMAIL = "communication_email"
    COMMUNICATION_SMS = "communication_sms"


class ConsentStatus(StrEnum):
    GRANTED = "granted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class PolicyDecisionStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    REQUIRES_REVIEW = "requires_review"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class RuleCheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    MISSING_INFO = "missing_info"


class WorkflowStatus(StrEnum):
    CREATED = "created"
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REQUIRES_REVIEW = "requires_review"


class WorkflowStepType(StrEnum):
    VALIDATE_AUTHORIZATION = "validate_authorization"
    WAIT_COOLDOWN = "wait_cooldown"
    DISPATCH_PAYMENT_RETRY = "dispatch_payment_retry"
    DISPATCH_COMMUNICATION = "dispatch_communication"
    CREATE_SUPPORT_TASK = "create_support_task"
    AWAIT_VERIFICATION = "await_verification"


class WorkflowStepStatus(StrEnum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class ExecutionStatus(StrEnum):
    SUBMITTED = "submitted"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PENDING = "pending"
    UNKNOWN = "unknown"
    CANCELLED = "cancelled"


class ReconciliationStatus(StrEnum):
    MATCHED = "matched"
    DISCREPANCY_DETECTED = "discrepancy_detected"
    RESOLVED = "resolved"
    ESCALATED = "escalated"



