"""Retry Limit Policy Rule Evaluator for Phase 2.9 Step 2.

Architectural layer: policy evaluator.

Enforces retry limits, minimum cooldown intervals, duplicate request prevention,
and in-progress attempt guardrails using centralized PolicyConfig.
"""

from datetime import datetime, timezone
from typing import Sequence

from app.core.enums import ActionType, RecoveryAttemptStatus, RuleCheckStatus
from app.models.domain import RecoveryAttempt
from app.policy.config import PolicyConfig
from app.policy.models import RuleCheckResult

_NON_RETRYABLE_CATEGORIES = frozenset(
    {
        "fraud_suspected",
        "stolen_card",
        "lost_card",
        "account_closed",
        "pickup_card",
        "restricted_card",
    }
)


class RetryLimitEvaluator:
    """Evaluates retry counts, cooldown periods, and attempt states against PolicyConfig."""

    RULE_NAME = "retry_limit_evaluation"

    def evaluate(
        self,
        *,
        action_type: ActionType,
        attempts: Sequence[RecoveryAttempt],
        config: PolicyConfig,
        current_time: datetime | None = None,
        proposed_idempotency_key: str | None = None,
        failure_category: str | None = None,
    ) -> RuleCheckResult:
        """Evaluate whether a proposed payment retry is permitted.

        Args:
            action_type: Proposed ActionType.
            attempts: Historical recovery attempts for this recovery case.
            config: Authoritative PolicyConfig instance.
            current_time: Reference timestamp for evaluation.
            proposed_idempotency_key: Unique idempotency key for this retry proposal.
            failure_category: Normalized failure category of the original transaction.

        Returns:
            RuleCheckResult with PASSED, FAILED, or NEEDS_REVIEW status.
        """
        # If the proposed action is not a payment retry, retry limits do not apply
        if action_type is not ActionType.RETRY_PAYMENT:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.PASSED,
                reason_code="NOT_A_RETRY_ACTION",
                message=f"Action {action_type.value} does not consume retry quota.",
                details={"action_type": action_type.value},
            )

        now = current_time or datetime.now(timezone.utc)

        # 1. Non-retryable failure category check
        if failure_category is not None:
            norm_cat = failure_category.strip().lower()
            if norm_cat in _NON_RETRYABLE_CATEGORIES:
                return RuleCheckResult(
                    rule_name=self.RULE_NAME,
                    status=RuleCheckStatus.FAILED,
                    reason_code="RETRY_NOT_SUPPORTED",
                    message=f"Failure category '{norm_cat}' is permanent and does not support retries.",
                    details={"failure_category": norm_cat},
                )

        # 2. Duplicate idempotency key check
        if proposed_idempotency_key:
            for att in attempts:
                if att.idempotency_key == proposed_idempotency_key:
                    return RuleCheckResult(
                        rule_name=self.RULE_NAME,
                        status=RuleCheckStatus.FAILED,
                        reason_code="DUPLICATE_RETRY_REQUEST",
                        message=f"Attempt with idempotency key '{proposed_idempotency_key}' has already been processed.",
                        details={"idempotency_key": proposed_idempotency_key},
                    )

        # 3. Check for previous successful attempt
        for att in attempts:
            if att.status is RecoveryAttemptStatus.SUCCEEDED:
                return RuleCheckResult(
                    rule_name=self.RULE_NAME,
                    status=RuleCheckStatus.FAILED,
                    reason_code="PREVIOUS_ATTEMPT_SUCCEEDED",
                    message="A previous recovery attempt already succeeded; cannot retry.",
                    details={"successful_attempt_id": str(att.id)},
                )

        # 4. Check for active retry already in progress
        for att in attempts:
            if att.status is RecoveryAttemptStatus.STARTED:
                return RuleCheckResult(
                    rule_name=self.RULE_NAME,
                    status=RuleCheckStatus.FAILED,
                    reason_code="RETRY_ALREADY_IN_PROGRESS",
                    message="Another recovery attempt is currently in progress.",
                    details={"in_progress_attempt_id": str(att.id)},
                )

        # 5. Check for uncertain previous outcome requiring verification
        for att in attempts:
            if att.status is RecoveryAttemptStatus.UNCERTAIN:
                return RuleCheckResult(
                    rule_name=self.RULE_NAME,
                    status=RuleCheckStatus.NEEDS_REVIEW,
                    reason_code="PREVIOUS_OUTCOME_UNKNOWN",
                    message="A prior attempt resulted in an uncertain outcome; operator verification required.",
                    details={"uncertain_attempt_id": str(att.id)},
                )

        # 6. Count consumed payment retry attempts
        # Only payment retries that were not cancelled consume retry quota
        consumed_attempts = [
            att
            for att in attempts
            if att.action_type is ActionType.RETRY_PAYMENT
            and att.status is not RecoveryAttemptStatus.CANCELLED
        ]
        prior_retry_count = len(consumed_attempts)

        # 7. Check max retry quota
        if not config.can_retry(prior_retry_count):
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.FAILED,
                reason_code="RETRY_LIMIT_EXCEEDED",
                message=f"Case has executed {prior_retry_count} retries; maximum allowed is {config.max_retry_attempts}.",
                details={
                    "prior_retry_count": prior_retry_count,
                    "max_retry_attempts": config.max_retry_attempts,
                    "max_total_attempts": config.max_total_attempts,
                },
            )

        # 8. Check cooldown window if there was a previous attempt
        if consumed_attempts:
            # Find the most recent timestamp among prior consumed attempts
            latest_attempt = max(
                consumed_attempts,
                key=lambda a: a.finished_at or a.started_at or datetime.min.replace(tzinfo=timezone.utc),
            )
            latest_time = latest_attempt.finished_at or latest_attempt.started_at

            if latest_time is not None:
                if not config.is_cooldown_elapsed(latest_time, now):
                    return RuleCheckResult(
                        rule_name=self.RULE_NAME,
                        status=RuleCheckStatus.FAILED,
                        reason_code="RETRY_COOLDOWN_ACTIVE",
                        message=f"Cooldown active; minimum {config.retry_cooldown_hours} hours required between retries.",
                        details={
                            "latest_attempt_at": latest_time.isoformat(),
                            "retry_cooldown_hours": config.retry_cooldown_hours,
                        },
                    )

        # All retry limit guardrails passed
        return RuleCheckResult(
            rule_name=self.RULE_NAME,
            status=RuleCheckStatus.PASSED,
            reason_code="RETRY_LIMIT_OK",
            message=f"Retry permitted. {prior_retry_count} of {config.max_retry_attempts} retries used.",
            details={
                "prior_retry_count": prior_retry_count,
                "max_retry_attempts": config.max_retry_attempts,
            },
        )
