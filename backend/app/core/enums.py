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
    TEST = "test"
