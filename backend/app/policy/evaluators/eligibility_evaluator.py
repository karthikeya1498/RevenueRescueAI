"""Eligibility Policy Rule Evaluator for Phase 2.9 Step 2.

Architectural layer: policy evaluator.

Determines whether a recovery case and recommendation are structurally,
contractually, and temporally eligible for automated recovery action.
"""

from typing import Any
from uuid import UUID

from app.core.enums import DecisionValidationStatus, RecoveryCaseState, RuleCheckStatus
from app.models.domain import AgentDecision, RecoveryCase
from app.policy.models import RuleCheckResult

_TERMINAL_STATES = frozenset(
    {
        RecoveryCaseState.RECOVERED,
        RecoveryCaseState.CLOSED,
        RecoveryCaseState.STOPPED,
    }
)

_ACTIONABLE_STATES = frozenset(
    {
        RecoveryCaseState.AWAITING_DECISION,
        RecoveryCaseState.RETRY_ELIGIBLE,
        RecoveryCaseState.DETECTED,
    }
)

_ACTIVE_WORKFLOW_STATES = frozenset(
    {
        RecoveryCaseState.ACTION_PENDING,
        RecoveryCaseState.VERIFICATION_PENDING,
    }
)


class EligibilityEvaluator:
    """Evaluates case existence, state validity, ownership, and recommendation alignment."""

    RULE_NAME = "case_eligibility_evaluation"

    def evaluate(
        self,
        *,
        case: RecoveryCase | None,
        recommendation: AgentDecision | None,
        customer_id: UUID | str | None = None,
        expected_transaction_id: UUID | str | None = None,
    ) -> RuleCheckResult:
        """Execute deterministic eligibility verification on the recovery case.

        Args:
            case: Authoritative RecoveryCase domain entity.
            recommendation: Proposed AgentDecision recommendation.
            customer_id: Optional authenticated customer ID for tenant boundary enforcement.
            expected_transaction_id: Optional trigger transaction ID for cross-validation.

        Returns:
            RuleCheckResult containing PASSED, FAILED, or MISSING_INFO status.
        """
        # 1. Case existence check
        if case is None:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.MISSING_INFO,
                reason_code="CASE_NOT_FOUND",
                message="Recovery case record was not found or could not be loaded.",
            )

        # 2. Recommendation existence check
        if recommendation is None:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.MISSING_INFO,
                reason_code="RECOMMENDATION_MISSING",
                message="No AI recommendation was provided for evaluation.",
                details={"case_id": str(case.id)},
            )

        # 3. Association / tenant ownership boundary check
        if customer_id is not None:
            expected_cid = str(customer_id)
            actual_cid = str(case.customer_id)
            if actual_cid != expected_cid:
                return RuleCheckResult(
                    rule_name=self.RULE_NAME,
                    status=RuleCheckStatus.FAILED,
                    reason_code="CUSTOMER_MISMATCH",
                    message="Case belongs to another customer; ownership boundary violated.",
                    details={"case_customer_id": actual_cid, "expected_customer_id": expected_cid},
                )

        if expected_transaction_id is not None:
            expected_tid = str(expected_transaction_id)
            actual_tid = str(case.trigger_transaction_id)
            if actual_tid != expected_tid:
                return RuleCheckResult(
                    rule_name=self.RULE_NAME,
                    status=RuleCheckStatus.FAILED,
                    reason_code="TRANSACTION_MISMATCH",
                    message="Case is not associated with the specified trigger transaction.",
                    details={"case_tx_id": actual_tid, "expected_tx_id": expected_tid},
                )

        # 4. Recommendation association check
        if recommendation.case_id != case.id:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.FAILED,
                reason_code="RECOMMENDATION_MISMATCH",
                message="The proposed recommendation is associated with a different recovery case.",
                details={
                    "case_id": str(case.id),
                    "recommendation_case_id": str(recommendation.case_id),
                },
            )

        # 5. Recommendation staleness check
        if recommendation.validation_status in {
            DecisionValidationStatus.INVALID,
            DecisionValidationStatus.REJECTED_BY_POLICY,
        }:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.FAILED,
                reason_code="RECOMMENDATION_STALE",
                message="Recommendation has already been invalidated or rejected by policy.",
                details={"validation_status": recommendation.validation_status.value},
            )

        if hasattr(recommendation, "decision_version") and recommendation.decision_version < case.version - 2:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.FAILED,
                reason_code="RECOMMENDATION_STALE",
                message="Recommendation version is outdated relative to recent case updates.",
                details={
                    "recommendation_version": recommendation.decision_version,
                    "case_version": case.version,
                },
            )

        # 6. Terminal state check
        if case.state is RecoveryCaseState.RECOVERED:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.FAILED,
                reason_code="CASE_ALREADY_RECOVERED",
                message="Case has already been successfully recovered; further recovery is blocked.",
                details={"state": case.state.value},
            )

        if case.state is RecoveryCaseState.CLOSED:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.FAILED,
                reason_code="CASE_CLOSED",
                message="Case has been closed; no new recovery action may be scheduled.",
                details={"state": case.state.value},
            )

        if case.state is RecoveryCaseState.STOPPED:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.FAILED,
                reason_code="CASE_CANCELLED",
                message="Case was permanently stopped or cancelled.",
                details={"state": case.state.value},
            )

        # 7. Incompatible active workflow check
        if case.state in _ACTIVE_WORKFLOW_STATES:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.FAILED,
                reason_code="WORKFLOW_ALREADY_ACTIVE",
                message=f"Case currently has an active workflow in state {case.state.value}.",
                details={"state": case.state.value},
            )

        # 8. Actionable state check
        if case.state not in _ACTIONABLE_STATES:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.FAILED,
                reason_code="CASE_NOT_ACTIONABLE",
                message=f"Case state {case.state.value} is not an actionable state.",
                details={"state": case.state.value},
            )

        # All eligibility guardrails cleared
        return RuleCheckResult(
            rule_name=self.RULE_NAME,
            status=RuleCheckStatus.PASSED,
            reason_code="ELIGIBILITY_PASSED",
            message="Recovery case is valid, actionable, and aligned with recommendation.",
            details={"case_id": str(case.id), "case_state": case.state.value},
        )
