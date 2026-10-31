"""Domain models, DTOs, and results for Policy Engine Step 1.

Architectural layer: policy domain models.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.core.enums import (
    ActionType,
    ConsentStatus,
    ConsentType,
    DecisionValidationStatus,
    PolicyDecisionStatus,
    RuleCheckStatus,
)
from app.models.domain import CustomerConsent


POLICY_TO_DECISION_VALIDATION_MAP: dict[PolicyDecisionStatus, DecisionValidationStatus] = {
    PolicyDecisionStatus.APPROVED: DecisionValidationStatus.VALID,
    PolicyDecisionStatus.REJECTED: DecisionValidationStatus.REJECTED_BY_POLICY,
    PolicyDecisionStatus.REQUIRES_REVIEW: DecisionValidationStatus.NOT_VALIDATED,
    PolicyDecisionStatus.INSUFFICIENT_INFORMATION: DecisionValidationStatus.INVALID,
}


def map_policy_to_validation_status(
    status: PolicyDecisionStatus,
) -> DecisionValidationStatus:
    """Map a PolicyDecisionStatus to the corresponding DecisionValidationStatus enum value.
    
    Mapping semantics:
    - APPROVED -> VALID (policy authorization succeeded)
    - REJECTED -> REJECTED_BY_POLICY (policy guardrail blocked action)
    - REQUIRES_REVIEW -> NOT_VALIDATED (pending operator human review)
    - INSUFFICIENT_INFORMATION -> INVALID (missing mandatory parameters or consent)
    """
    return POLICY_TO_DECISION_VALIDATION_MAP[status]


@dataclass(frozen=True)
class RuleCheckResult:
    """Individual rule verification outcome within a policy evaluation run.
    
    Attributes:
        rule_name: Canonical identifier of the policy rule.
        status: RuleCheckStatus (PASSED, FAILED, NEEDS_REVIEW, MISSING_INFO).
        reason_code: Machine-readable reason code (e.g., 'CONSENT_EXPIRED').
        message: Human-readable diagnostic explanation.
        details: Additional contextual metadata for auditing and tracing.
    """

    rule_name: str
    status: RuleCheckStatus
    reason_code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_passed(self) -> bool:
        """Return True if this rule passed cleanly."""
        return self.status == RuleCheckStatus.PASSED

    @property
    def is_failed(self) -> bool:
        """Return True if this rule explicitly failed/rejected."""
        return self.status == RuleCheckStatus.FAILED

    @property
    def needs_review(self) -> bool:
        """Return True if this rule escalated to human operator review."""
        return self.status == RuleCheckStatus.NEEDS_REVIEW

    @property
    def is_missing_info(self) -> bool:
        """Return True if insufficient information prevented deterministic evaluation."""
        return self.status == RuleCheckStatus.MISSING_INFO


@dataclass
class CustomerConsentRecord:
    """Decoupled customer consent record independent of transactions.
    
    Represents legal authorization granted by a customer for recurring billing,
    email communications, or SMS messaging.
    
    Financial Safety Rule: Missing, revoked, or expired consent must NEVER authorize
    an automated recovery action (fail-closed).
    """

    customer_id: UUID | str
    consent_type: ConsentType
    status: ConsentStatus = ConsentStatus.GRANTED
    merchant_id: str | None = None
    granted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
    source: str = "checkout_agreement"
    evidence_reference: str | None = None
    version: int = 1
    id: UUID | str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def is_valid(self, at_time: datetime | None = None) -> bool:
        """Fail-closed evaluation of whether this consent is currently active and valid.
        
        Args:
            at_time: Reference timestamp for evaluation (defaults to utcnow).
            
        Returns:
            True if status is GRANTED, not revoked, and not expired.
        """
        now = at_time or datetime.now(timezone.utc)

        # 1. Explicit status check
        if self.status != ConsentStatus.GRANTED:
            return False

        # 2. Revocation check
        if self.revoked_at is not None:
            rev_time = self.revoked_at
            if rev_time.tzinfo is None and now.tzinfo is not None:
                rev_time = rev_time.replace(tzinfo=timezone.utc)
            elif rev_time.tzinfo is not None and now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            if now >= rev_time:
                return False

        # 3. Expiry check
        if self.expires_at is not None:
            exp_time = self.expires_at
            if exp_time.tzinfo is None and now.tzinfo is not None:
                exp_time = exp_time.replace(tzinfo=timezone.utc)
            elif exp_time.tzinfo is not None and now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            if now >= exp_time:
                return False

        return True

    def get_validity_reason(self, at_time: datetime | None = None) -> str:
        """Provide detailed reason code for validity or failure.
        
        Returns:
            'CONSENT_VALID', 'CONSENT_REVOKED', 'CONSENT_EXPIRED', or 'CONSENT_NOT_GRANTED'.
        """
        now = at_time or datetime.now(timezone.utc)

        if self.revoked_at is not None:
            rev_time = self.revoked_at
            if rev_time.tzinfo is None and now.tzinfo is not None:
                rev_time = rev_time.replace(tzinfo=timezone.utc)
            elif rev_time.tzinfo is not None and now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            if now >= rev_time:
                return "CONSENT_REVOKED"

        if self.expires_at is not None:
            exp_time = self.expires_at
            if exp_time.tzinfo is None and now.tzinfo is not None:
                exp_time = exp_time.replace(tzinfo=timezone.utc)
            elif exp_time.tzinfo is not None and now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            if now >= exp_time:
                return "CONSENT_EXPIRED"

        if self.status != ConsentStatus.GRANTED:
            return f"CONSENT_STATUS_{self.status.value.upper()}"

        return "CONSENT_VALID"

    @classmethod
    def from_domain(cls, entity: CustomerConsent) -> "CustomerConsentRecord":
        """Convert an ORM CustomerConsent model to a CustomerConsentRecord DTO."""
        return cls(
            id=entity.id,
            customer_id=entity.customer_id,
            consent_type=entity.consent_type,
            status=entity.status,
            merchant_id=entity.merchant_id,
            granted_at=entity.granted_at,
            revoked_at=entity.revoked_at,
            expires_at=entity.expires_at,
            source=entity.source,
            evidence_reference=entity.evidence_reference,
            version=entity.version,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def to_domain(self) -> CustomerConsent:
        """Convert this record to an ORM CustomerConsent persistence entity."""
        cust_id = UUID(str(self.customer_id)) if isinstance(self.customer_id, str) else self.customer_id
        pk_id = UUID(str(self.id)) if self.id and isinstance(self.id, str) else (self.id or uuid4())
        
        return CustomerConsent(
            id=pk_id,
            customer_id=cust_id,
            consent_type=self.consent_type,
            status=self.status,
            merchant_id=self.merchant_id,
            granted_at=self.granted_at,
            revoked_at=self.revoked_at,
            expires_at=self.expires_at,
            source=self.source,
            evidence_reference=self.evidence_reference,
            version=self.version,
        )


@dataclass(frozen=True)
class PolicyEvaluationResult:
    """Immutable audit record of a complete policy decision evaluation.
    
    Preserves:
    - Recommendation ID
    - Case ID
    - Proposed action
    - Policy version
    - Evaluation timestamp
    - Detailed rule check results
    - Overall decision status
    - Aggregated reason codes
    """

    decision_status: PolicyDecisionStatus
    case_id: UUID | str
    proposed_action: ActionType
    policy_version: str
    rule_results: list[RuleCheckResult]
    reasons: list[str] = field(default_factory=list)
    recommendation_id: UUID | str | None = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata_json: dict[str, Any] = field(default_factory=dict)

    @property
    def is_approved(self) -> bool:
        """Return True if policy evaluation resulted in full approval."""
        return self.decision_status == PolicyDecisionStatus.APPROVED

    @property
    def validation_status(self) -> DecisionValidationStatus:
        """Return the mapped DecisionValidationStatus for FSM synchronization."""
        return map_policy_to_validation_status(self.decision_status)
