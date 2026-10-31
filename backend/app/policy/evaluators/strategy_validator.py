"""Strategy Policy Rule Validator for Phase 2.9 Step 2.

Architectural layer: policy evaluator.

Verifies that an AI-recommended recovery strategy is canonically recognized,
applicable to the failure category, compatible with the case state, and satisfies
all required prerequisites.
"""

from app.core.enums import ActionType, RecoveryCaseState, RuleCheckStatus
from app.policy.models import RuleCheckResult
from app.services.intelligence.strategy_catalog import RecoveryStrategy, StrategyCatalog

_TERMINAL_STATES = frozenset(
    {
        RecoveryCaseState.RECOVERED,
        RecoveryCaseState.CLOSED,
        RecoveryCaseState.STOPPED,
    }
)


class StrategyValidator:
    """Validates recovery strategy feasibility, applicability, and safety constraints."""

    RULE_NAME = "strategy_policy_validation"

    def evaluate(
        self,
        *,
        strategy: RecoveryStrategy | str,
        failure_category: str | None,
        case_state: RecoveryCaseState,
        has_contact_info: bool = True,
        is_retryable: bool = True,
    ) -> RuleCheckResult:
        """Validate proposed recovery strategy against catalog and context constraints.

        Args:
            strategy: RecoveryStrategy enum member or recognized string.
            failure_category: Normalized failure category of the transaction.
            case_state: Current RecoveryCaseState of the case.
            has_contact_info: Whether customer email/phone is available.
            is_retryable: Whether failure analysis flagged this failure as retryable.

        Returns:
            RuleCheckResult with PASSED or FAILED status and appropriate reason code.
        """
        # 1. Resolve and recognize strategy
        resolved_strategy: RecoveryStrategy | None = None
        if isinstance(strategy, RecoveryStrategy):
            resolved_strategy = strategy
        elif isinstance(strategy, str):
            try:
                resolved_strategy = RecoveryStrategy(strategy.strip().upper())
            except ValueError:
                # Check if it was passed as ActionType string
                try:
                    act = ActionType(strategy.strip().lower())
                    resolved_strategy = StrategyCatalog.map_to_strategy(act)
                except ValueError:
                    resolved_strategy = None

        if resolved_strategy is None:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.FAILED,
                reason_code="STRATEGY_UNSUPPORTED",
                message=f"Strategy '{strategy}' is not an approved recovery strategy in the catalog.",
                details={"provided_strategy": str(strategy)},
            )

        # 2. Terminal case state compatibility check
        if case_state in _TERMINAL_STATES:
            # Only NO_ACTION is valid on a terminal case
            if resolved_strategy is not RecoveryStrategy.NO_ACTION:
                return RuleCheckResult(
                    rule_name=self.RULE_NAME,
                    status=RuleCheckStatus.FAILED,
                    reason_code="STRATEGY_CASE_STATE_MISMATCH",
                    message=f"Actionable strategy {resolved_strategy.value} cannot be applied to terminal case ({case_state.value}).",
                    details={"case_state": case_state.value, "strategy": resolved_strategy.value},
                )

        # 3. Handle NO_ACTION and MANUAL_REVIEW (universally permitted fallbacks)
        if resolved_strategy is RecoveryStrategy.NO_ACTION:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.PASSED,
                reason_code="STRATEGY_VALID",
                message="NO_ACTION strategy is safe and permitted.",
                details={"strategy": resolved_strategy.value},
            )

        if resolved_strategy is RecoveryStrategy.MANUAL_REVIEW:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.PASSED,
                reason_code="STRATEGY_VALID",
                message="MANUAL_REVIEW strategy is permitted.",
                details={"strategy": resolved_strategy.value},
            )

        # 4. Prerequisites check: Customer communication strategies require contact info
        if resolved_strategy in {
            RecoveryStrategy.UPDATE_PAYMENT_METHOD,
            RecoveryStrategy.CUSTOMER_REMINDER,
        }:
            if not has_contact_info:
                return RuleCheckResult(
                    rule_name=self.RULE_NAME,
                    status=RuleCheckStatus.FAILED,
                    reason_code="STRATEGY_PREREQUISITE_MISSING",
                    message=f"Strategy {resolved_strategy.value} requires customer contact info, which is unavailable.",
                    details={"strategy": resolved_strategy.value, "missing_prerequisite": "customer_contact_info"},
                )

        # 5. Failure category compatibility check
        norm_cat = (failure_category or "").strip().lower()

        if resolved_strategy is RecoveryStrategy.RETRY_LATER:
            # If explicit failure category is known, check against catalog applicable categories
            spec = StrategyCatalog.get(RecoveryStrategy.RETRY_LATER)
            if norm_cat and norm_cat not in spec.applicable_failure_categories and not is_retryable:
                return RuleCheckResult(
                    rule_name=self.RULE_NAME,
                    status=RuleCheckStatus.FAILED,
                    reason_code="STRATEGY_FAILURE_MISMATCH",
                    message=f"Retry strategy is incompatible with non-retryable failure category '{norm_cat}'.",
                    details={"strategy": resolved_strategy.value, "failure_category": norm_cat},
                )

        if resolved_strategy is RecoveryStrategy.UPDATE_PAYMENT_METHOD:
            # Expired or invalid card strategies shouldn't be used for transient network errors
            if norm_cat in {"provider_timeout", "network_error"}:
                return RuleCheckResult(
                    rule_name=self.RULE_NAME,
                    status=RuleCheckStatus.FAILED,
                    reason_code="STRATEGY_FAILURE_MISMATCH",
                    message=f"Update payment method strategy is inappropriate for transient error '{norm_cat}'.",
                    details={"strategy": resolved_strategy.value, "failure_category": norm_cat},
                )

        # All strategy validation checks passed
        return RuleCheckResult(
            rule_name=self.RULE_NAME,
            status=RuleCheckStatus.PASSED,
            reason_code="STRATEGY_VALID",
            message=f"Strategy {resolved_strategy.value} is approved and compatible with case context.",
            details={
                "strategy": resolved_strategy.value,
                "action_type": StrategyCatalog.map_to_action(resolved_strategy).value,
            },
        )
