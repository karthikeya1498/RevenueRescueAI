"""Escalation Policy Rule Evaluator for Phase 2.9 Step 2.

Architectural layer: policy evaluator.

Determines whether a proposed recovery case must be escalated for human operator
review based on financial exposure, fraud restrictions, AI confidence, or risk flags.
"""

from decimal import Decimal

from app.core.enums import RuleCheckStatus
from app.policy.config import PolicyConfig
from app.policy.models import RuleCheckResult

_FRAUD_CATEGORIES = frozenset(
    {
        "fraud_suspected",
        "stolen_card",
        "lost_card",
        "pickup_card",
        "restricted_card",
        "security_violation",
    }
)


class EscalationEvaluator:
    """Evaluates human escalation triggers with currency-aware financial thresholds."""

    RULE_NAME = "escalation_policy_evaluation"

    def evaluate(
        self,
        *,
        amount_minor: int,
        currency: str,
        config: PolicyConfig,
        ai_confidence: float | Decimal | None = None,
        failure_category: str | None = None,
        prior_retries_exhausted: bool = False,
        fraud_suspected: bool = False,
        has_conflicting_events: bool = False,
        has_uncertain_outcome: bool = False,
        min_confidence_threshold: float = 0.60,
    ) -> RuleCheckResult:
        """Evaluate whether the case requires human operator intervention.

        Args:
            amount_minor: At-risk transaction exposure in minor units.
            currency: Three-letter ISO currency code.
            config: PolicyConfig holding currency-aware thresholds.
            ai_confidence: Confidence score of the AI strategy recommendation (0.0 - 1.0).
            failure_category: Categorized failure reason.
            prior_retries_exhausted: Whether retry budget has been completely spent.
            fraud_suspected: Whether anti-fraud flags were raised.
            has_conflicting_events: Whether duplicate or divergent provider events were received.
            has_uncertain_outcome: Whether a previous attempt left an indeterminate state.
            min_confidence_threshold: Minimum AI confidence required for automated authorization.

        Returns:
            RuleCheckResult with PASSED, NEEDS_REVIEW, or MISSING_INFO status.
        """
        # 1. Hard anti-fraud and security restrictions take top precedence
        norm_cat = (failure_category or "").strip().lower()
        if fraud_suspected or norm_cat in _FRAUD_CATEGORIES:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.NEEDS_REVIEW,
                reason_code="FRAUD_RESTRICTION",
                message="Case flagged for suspected fraud or security restrictions; mandatory human review.",
                details={"fraud_suspected": fraud_suspected, "failure_category": norm_cat},
            )

        # 2. Currency-aware high-value exposure evaluation
        if config.is_high_value(amount_minor, currency):
            threshold = config.get_high_value_threshold(currency)
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.NEEDS_REVIEW,
                reason_code="HIGH_VALUE_REVIEW_REQUIRED",
                message=f"Exposure of {amount_minor} {currency} exceeds high-value threshold of {threshold} minor units.",
                details={"amount_minor": amount_minor, "currency": currency, "threshold_minor": threshold},
            )

        # 3. Retry exhaustion escalation
        if prior_retries_exhausted:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.NEEDS_REVIEW,
                reason_code="RETRY_EXHAUSTED",
                message="All automated retry attempts have been exhausted; operator review required.",
                details={"prior_retries_exhausted": True},
            )

        # 4. Conflicting payment webhook events
        if has_conflicting_events:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.NEEDS_REVIEW,
                reason_code="PAYMENT_EVENT_CONFLICT",
                message="Divergent or conflicting provider webhook events detected; operator intervention required.",
                details={"has_conflicting_events": True},
            )

        # 5. Uncertain payment outcome
        if has_uncertain_outcome:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.NEEDS_REVIEW,
                reason_code="PAYMENT_OUTCOME_UNCERTAIN",
                message="Previous attempt outcome is indeterminate; operator verification required.",
                details={"has_uncertain_outcome": True},
            )

        # 6. Unknown failure category
        if not norm_cat or norm_cat in {"unknown", "unknown_failure"}:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.NEEDS_REVIEW,
                reason_code="UNKNOWN_FAILURE_CATEGORY",
                message="Decline category could not be determined; operator review required.",
                details={"failure_category": norm_cat or "missing"},
            )

        # 7. AI Recommendation confidence checks
        if ai_confidence is None:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.MISSING_INFO,
                reason_code="AI_CONFIDENCE_MISSING",
                message="AI recommendation confidence score is missing; cannot reliably authorize.",
            )

        conf_float = float(ai_confidence)
        if conf_float < min_confidence_threshold:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.NEEDS_REVIEW,
                reason_code="LOW_AI_CONFIDENCE",
                message=f"AI recommendation confidence ({conf_float:.2f}) is below minimum threshold ({min_confidence_threshold:.2f}).",
                details={"confidence": conf_float, "threshold": min_confidence_threshold},
            )

        # All escalation checks cleared
        return RuleCheckResult(
            rule_name=self.RULE_NAME,
            status=RuleCheckStatus.PASSED,
            reason_code="NO_ESCALATION_REQUIRED",
            message="No escalation triggers detected; action may proceed to authorization.",
            details={"amount_minor": amount_minor, "currency": currency, "confidence": conf_float},
        )
