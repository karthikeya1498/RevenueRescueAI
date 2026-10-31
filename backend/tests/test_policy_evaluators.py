"""Unit test suite for Step 2: Modular Policy Rule Evaluators.

Verifies the independent operation, reason codes, fail-closed guardrails,
and Single Responsibility Principle for all five policy evaluators:
1. EligibilityEvaluator
2. ConsentValidator
3. RetryLimitEvaluator
4. StrategyValidator
5. EscalationEvaluator
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.enums import (
    ActionType,
    ConsentStatus,
    ConsentType,
    DecisionValidationStatus,
    RecoveryAttemptStatus,
    RecoveryCaseState,
    RuleCheckStatus,
)
from app.models.domain import AgentDecision, RecoveryAttempt, RecoveryCase
from app.policy.config import PolicyConfig
from app.policy.evaluators import (
    ConsentValidator,
    EligibilityEvaluator,
    EscalationEvaluator,
    RetryLimitEvaluator,
    StrategyValidator,
)
from app.policy.models import CustomerConsentRecord
from app.services.intelligence.strategy_catalog import RecoveryStrategy


# -------------------------------------------------------------------------
# 1. EligibilityEvaluator Tests
# -------------------------------------------------------------------------
class TestEligibilityEvaluator:
    """Test suite for EligibilityEvaluator."""

    def setup_method(self):
        self.evaluator = EligibilityEvaluator()
        self.case_id = uuid4()
        self.customer_id = uuid4()
        self.tx_id = uuid4()
        self.now = datetime.now(timezone.utc)

        self.case = RecoveryCase(
            id=self.case_id,
            customer_id=self.customer_id,
            trigger_transaction_id=self.tx_id,
            case_key="case_test_001",
            state=RecoveryCaseState.AWAITING_DECISION,
            priority=100,
            opened_at=self.now,
            last_state_changed_at=self.now,
            version=1,
        )

        self.recommendation = AgentDecision(
            id=uuid4(),
            case_id=self.case_id,
            action_type=ActionType.RETRY_PAYMENT,
            reason_code="AI_RECOMMENDED_RETRY",
            validation_status=DecisionValidationStatus.NOT_VALIDATED,
            decision_version=1,
        )

    def test_valid_actionable_case(self):
        result = self.evaluator.evaluate(
            case=self.case,
            recommendation=self.recommendation,
            customer_id=self.customer_id,
            expected_transaction_id=self.tx_id,
        )
        assert result.is_passed is True
        assert result.reason_code == "ELIGIBILITY_PASSED"

    def test_case_not_found(self):
        result = self.evaluator.evaluate(
            case=None,
            recommendation=self.recommendation,
        )
        assert result.is_missing_info is True
        assert result.reason_code == "CASE_NOT_FOUND"

    def test_recommendation_missing(self):
        result = self.evaluator.evaluate(
            case=self.case,
            recommendation=None,
        )
        assert result.is_missing_info is True
        assert result.reason_code == "RECOMMENDATION_MISSING"

    def test_recommendation_mismatch(self):
        other_rec = AgentDecision(
            id=uuid4(),
            case_id=uuid4(),  # Different case ID
            action_type=ActionType.RETRY_PAYMENT,
            reason_code="OTHER_CASE_REC",
            validation_status=DecisionValidationStatus.NOT_VALIDATED,
        )
        result = self.evaluator.evaluate(
            case=self.case,
            recommendation=other_rec,
        )
        assert result.is_failed is True
        assert result.reason_code == "RECOMMENDATION_MISMATCH"

    def test_customer_tenant_mismatch(self):
        different_customer = uuid4()
        result = self.evaluator.evaluate(
            case=self.case,
            recommendation=self.recommendation,
            customer_id=different_customer,
        )
        assert result.is_failed is True
        assert result.reason_code == "CUSTOMER_MISMATCH"

    def test_case_already_recovered(self):
        self.case.state = RecoveryCaseState.RECOVERED
        result = self.evaluator.evaluate(
            case=self.case,
            recommendation=self.recommendation,
        )
        assert result.is_failed is True
        assert result.reason_code == "CASE_ALREADY_RECOVERED"

    def test_case_closed(self):
        self.case.state = RecoveryCaseState.CLOSED
        result = self.evaluator.evaluate(
            case=self.case,
            recommendation=self.recommendation,
        )
        assert result.is_failed is True
        assert result.reason_code == "CASE_CLOSED"

    def test_case_cancelled(self):
        self.case.state = RecoveryCaseState.STOPPED
        result = self.evaluator.evaluate(
            case=self.case,
            recommendation=self.recommendation,
        )
        assert result.is_failed is True
        assert result.reason_code == "CASE_CANCELLED"

    def test_workflow_already_active(self):
        self.case.state = RecoveryCaseState.ACTION_PENDING
        result = self.evaluator.evaluate(
            case=self.case,
            recommendation=self.recommendation,
        )
        assert result.is_failed is True
        assert result.reason_code == "WORKFLOW_ALREADY_ACTIVE"

    def test_stale_recommendation_rejected_status(self):
        self.recommendation.validation_status = DecisionValidationStatus.REJECTED_BY_POLICY
        result = self.evaluator.evaluate(
            case=self.case,
            recommendation=self.recommendation,
        )
        assert result.is_failed is True
        assert result.reason_code == "RECOMMENDATION_STALE"


# -------------------------------------------------------------------------
# 2. ConsentValidator Tests
# -------------------------------------------------------------------------
class TestConsentValidator:
    """Test suite for ConsentValidator."""

    def setup_method(self):
        self.validator = ConsentValidator()
        self.customer_id = uuid4()
        self.merchant_id = "merch_acme_01"
        self.now = datetime.now(timezone.utc)

    def test_valid_recurring_billing_consent(self):
        consent = CustomerConsentRecord(
            customer_id=self.customer_id,
            consent_type=ConsentType.RECURRING_BILLING,
            status=ConsentStatus.GRANTED,
            merchant_id=self.merchant_id,
            granted_at=self.now - timedelta(days=10),
        )
        result = self.validator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            customer_id=self.customer_id,
            consents=[consent],
            merchant_id=self.merchant_id,
            evaluation_time=self.now,
        )
        assert result.is_passed is True
        assert result.reason_code == "CONSENT_VALID"

    def test_missing_recurring_billing_consent(self):
        result = self.validator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            customer_id=self.customer_id,
            consents=[],
            merchant_id=self.merchant_id,
            evaluation_time=self.now,
        )
        assert result.is_failed is True
        assert result.reason_code == "CONSENT_MISSING"

    def test_revoked_recurring_billing_consent(self):
        consent = CustomerConsentRecord(
            customer_id=self.customer_id,
            consent_type=ConsentType.RECURRING_BILLING,
            status=ConsentStatus.GRANTED,
            granted_at=self.now - timedelta(days=20),
            revoked_at=self.now - timedelta(days=2),
        )
        result = self.validator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            customer_id=self.customer_id,
            consents=[consent],
            evaluation_time=self.now,
        )
        assert result.is_failed is True
        assert result.reason_code == "CONSENT_REVOKED"

    def test_expired_recurring_billing_consent(self):
        consent = CustomerConsentRecord(
            customer_id=self.customer_id,
            consent_type=ConsentType.RECURRING_BILLING,
            status=ConsentStatus.GRANTED,
            granted_at=self.now - timedelta(days=100),
            expires_at=self.now - timedelta(hours=1),
        )
        result = self.validator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            customer_id=self.customer_id,
            consents=[consent],
            evaluation_time=self.now,
        )
        assert result.is_failed is True
        assert result.reason_code == "CONSENT_EXPIRED"

    def test_valid_email_consent(self):
        consent = CustomerConsentRecord(
            customer_id=self.customer_id,
            consent_type=ConsentType.COMMUNICATION_EMAIL,
            status=ConsentStatus.GRANTED,
            granted_at=self.now,
        )
        result = self.validator.evaluate(
            action_type=ActionType.SEND_REMINDER,
            customer_id=self.customer_id,
            consents=[consent],
            communication_channel="email",
            evaluation_time=self.now,
        )
        assert result.is_passed is True
        assert result.reason_code == "CONSENT_VALID"

    def test_independent_channels_email_not_satisfying_sms(self):
        """Email consent must NEVER satisfy an SMS communication action."""
        email_consent = CustomerConsentRecord(
            customer_id=self.customer_id,
            consent_type=ConsentType.COMMUNICATION_EMAIL,
            status=ConsentStatus.GRANTED,
            granted_at=self.now,
        )
        result = self.validator.evaluate(
            action_type=ActionType.SEND_REMINDER,
            customer_id=self.customer_id,
            consents=[email_consent],
            communication_channel="sms",
            evaluation_time=self.now,
        )
        assert result.is_failed is True
        assert result.reason_code == "CONSENT_MISSING"

    def test_consent_customer_mismatch(self):
        other_customer = uuid4()
        consent = CustomerConsentRecord(
            customer_id=other_customer,
            consent_type=ConsentType.RECURRING_BILLING,
            status=ConsentStatus.GRANTED,
            granted_at=self.now,
        )
        result = self.validator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            customer_id=self.customer_id,
            consents=[consent],
            evaluation_time=self.now,
        )
        assert result.is_failed is True
        assert result.reason_code == "CONSENT_CUSTOMER_MISMATCH"

    def test_consent_merchant_mismatch(self):
        consent = CustomerConsentRecord(
            customer_id=self.customer_id,
            consent_type=ConsentType.RECURRING_BILLING,
            status=ConsentStatus.GRANTED,
            merchant_id="merchant_other",
            granted_at=self.now,
        )
        result = self.validator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            customer_id=self.customer_id,
            consents=[consent],
            merchant_id="merchant_target",
            evaluation_time=self.now,
        )
        assert result.is_failed is True
        assert result.reason_code == "CONSENT_MERCHANT_MISMATCH"

    def test_missing_granted_at_is_invalid(self):
        consent = CustomerConsentRecord(
            customer_id=self.customer_id,
            consent_type=ConsentType.RECURRING_BILLING,
            status=ConsentStatus.GRANTED,
            granted_at=None,
        )
        result = self.validator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            customer_id=self.customer_id,
            consents=[consent],
            evaluation_time=self.now,
        )
        assert result.is_failed is True
        assert result.reason_code == "CONSENT_INVALID"

    def test_internal_operator_review_requires_no_consent(self):
        result = self.validator.evaluate(
            action_type=ActionType.REQUEST_OPERATOR_REVIEW,
            customer_id=self.customer_id,
            consents=[],
            evaluation_time=self.now,
        )
        assert result.is_passed is True
        assert result.reason_code == "NO_CONSENT_REQUIRED"


# -------------------------------------------------------------------------
# 3. RetryLimitEvaluator Tests
# -------------------------------------------------------------------------
class TestRetryLimitEvaluator:
    """Test suite for RetryLimitEvaluator."""

    def setup_method(self):
        self.evaluator = RetryLimitEvaluator()
        self.config = PolicyConfig(max_retry_attempts=3, retry_cooldown_hours=4)
        self.case_id = uuid4()
        self.now = datetime.now(timezone.utc)

    def test_non_retry_action_bypasses_limits(self):
        result = self.evaluator.evaluate(
            action_type=ActionType.SEND_REMINDER,
            attempts=[],
            config=self.config,
        )
        assert result.is_passed is True
        assert result.reason_code == "NOT_A_RETRY_ACTION"

    def test_first_retry_no_prior_attempts(self):
        result = self.evaluator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            attempts=[],
            config=self.config,
            current_time=self.now,
        )
        assert result.is_passed is True
        assert result.reason_code == "RETRY_LIMIT_OK"

    def test_retry_within_limit_with_elapsed_cooldown(self):
        # 1 previous failed attempt executed 5 hours ago
        past_att = RecoveryAttempt(
            id=uuid4(),
            case_id=self.case_id,
            sequence_number=1,
            status=RecoveryAttemptStatus.FAILED,
            action_type=ActionType.RETRY_PAYMENT,
            started_at=self.now - timedelta(hours=6),
            finished_at=self.now - timedelta(hours=5),
            idempotency_key="key_attempt_1",
        )
        result = self.evaluator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            attempts=[past_att],
            config=self.config,
            current_time=self.now,
        )
        assert result.is_passed is True
        assert result.reason_code == "RETRY_LIMIT_OK"
        assert result.details["prior_retry_count"] == 1

    def test_cooldown_active(self):
        # Previous attempt finished 2 hours ago (< 4h cooldown)
        past_att = RecoveryAttempt(
            id=uuid4(),
            case_id=self.case_id,
            sequence_number=1,
            status=RecoveryAttemptStatus.FAILED,
            action_type=ActionType.RETRY_PAYMENT,
            started_at=self.now - timedelta(hours=3),
            finished_at=self.now - timedelta(hours=2),
            idempotency_key="key_attempt_1",
        )
        result = self.evaluator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            attempts=[past_att],
            config=self.config,
            current_time=self.now,
        )
        assert result.is_failed is True
        assert result.reason_code == "RETRY_COOLDOWN_ACTIVE"

    def test_retry_limit_exceeded(self):
        # 3 previous attempts executed
        attempts = [
            RecoveryAttempt(
                id=uuid4(),
                case_id=self.case_id,
                sequence_number=i,
                status=RecoveryAttemptStatus.FAILED,
                action_type=ActionType.RETRY_PAYMENT,
                started_at=self.now - timedelta(days=i),
                finished_at=self.now - timedelta(days=i) + timedelta(minutes=1),
                idempotency_key=f"key_{i}",
            )
            for i in range(1, 4)
        ]
        result = self.evaluator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            attempts=attempts,
            config=self.config,
            current_time=self.now,
        )
        assert result.is_failed is True
        assert result.reason_code == "RETRY_LIMIT_EXCEEDED"

    def test_retry_already_in_progress(self):
        att_running = RecoveryAttempt(
            id=uuid4(),
            case_id=self.case_id,
            sequence_number=1,
            status=RecoveryAttemptStatus.STARTED,
            action_type=ActionType.RETRY_PAYMENT,
            started_at=self.now - timedelta(minutes=10),
            idempotency_key="key_running",
        )
        result = self.evaluator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            attempts=[att_running],
            config=self.config,
            current_time=self.now,
        )
        assert result.is_failed is True
        assert result.reason_code == "RETRY_ALREADY_IN_PROGRESS"

    def test_previous_attempt_succeeded(self):
        att_succ = RecoveryAttempt(
            id=uuid4(),
            case_id=self.case_id,
            sequence_number=1,
            status=RecoveryAttemptStatus.SUCCEEDED,
            action_type=ActionType.RETRY_PAYMENT,
            started_at=self.now - timedelta(days=1),
            finished_at=self.now - timedelta(days=1),
            idempotency_key="key_succ",
        )
        result = self.evaluator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            attempts=[att_succ],
            config=self.config,
            current_time=self.now,
        )
        assert result.is_failed is True
        assert result.reason_code == "PREVIOUS_ATTEMPT_SUCCEEDED"

    def test_previous_attempt_outcome_uncertain(self):
        att_unc = RecoveryAttempt(
            id=uuid4(),
            case_id=self.case_id,
            sequence_number=1,
            status=RecoveryAttemptStatus.UNCERTAIN,
            action_type=ActionType.RETRY_PAYMENT,
            started_at=self.now - timedelta(hours=10),
            idempotency_key="key_unc",
        )
        result = self.evaluator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            attempts=[att_unc],
            config=self.config,
            current_time=self.now,
        )
        assert result.needs_review is True
        assert result.reason_code == "PREVIOUS_OUTCOME_UNKNOWN"

    def test_duplicate_idempotency_key(self):
        att = RecoveryAttempt(
            id=uuid4(),
            case_id=self.case_id,
            sequence_number=1,
            status=RecoveryAttemptStatus.FAILED,
            action_type=ActionType.RETRY_PAYMENT,
            idempotency_key="dup_key_123",
        )
        result = self.evaluator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            attempts=[att],
            config=self.config,
            proposed_idempotency_key="dup_key_123",
        )
        assert result.is_failed is True
        assert result.reason_code == "DUPLICATE_RETRY_REQUEST"

    def test_unsupported_fraud_failure_category(self):
        result = self.evaluator.evaluate(
            action_type=ActionType.RETRY_PAYMENT,
            attempts=[],
            config=self.config,
            failure_category="fraud_suspected",
        )
        assert result.is_failed is True
        assert result.reason_code == "RETRY_NOT_SUPPORTED"


# -------------------------------------------------------------------------
# 4. StrategyValidator Tests
# -------------------------------------------------------------------------
class TestStrategyValidator:
    """Test suite for StrategyValidator."""

    def setup_method(self):
        self.validator = StrategyValidator()

    def test_valid_retry_strategy(self):
        result = self.validator.evaluate(
            strategy=RecoveryStrategy.RETRY_LATER,
            failure_category="insufficient_funds",
            case_state=RecoveryCaseState.AWAITING_DECISION,
            is_retryable=True,
        )
        assert result.is_passed is True
        assert result.reason_code == "STRATEGY_VALID"

    def test_unsupported_arbitrary_strategy(self):
        result = self.validator.evaluate(
            strategy="UNAUTHORIZED_AI_STRATEGY",
            failure_category="insufficient_funds",
            case_state=RecoveryCaseState.AWAITING_DECISION,
        )
        assert result.is_failed is True
        assert result.reason_code == "STRATEGY_UNSUPPORTED"

    def test_retry_strategy_incompatible_with_permanent_failure(self):
        result = self.validator.evaluate(
            strategy=RecoveryStrategy.RETRY_LATER,
            failure_category="card_expired",
            case_state=RecoveryCaseState.AWAITING_DECISION,
            is_retryable=False,
        )
        assert result.is_failed is True
        assert result.reason_code == "STRATEGY_FAILURE_MISMATCH"

    def test_update_payment_method_missing_contact_info(self):
        result = self.validator.evaluate(
            strategy=RecoveryStrategy.UPDATE_PAYMENT_METHOD,
            failure_category="card_expired",
            case_state=RecoveryCaseState.AWAITING_DECISION,
            has_contact_info=False,
        )
        assert result.is_failed is True
        assert result.reason_code == "STRATEGY_PREREQUISITE_MISSING"

    def test_actionable_strategy_on_terminal_case(self):
        result = self.validator.evaluate(
            strategy=RecoveryStrategy.RETRY_LATER,
            failure_category="insufficient_funds",
            case_state=RecoveryCaseState.RECOVERED,
        )
        assert result.is_failed is True
        assert result.reason_code == "STRATEGY_CASE_STATE_MISMATCH"

    def test_no_action_strategy_permitted_on_terminal_case(self):
        result = self.validator.evaluate(
            strategy=RecoveryStrategy.NO_ACTION,
            failure_category="policy_blocked",
            case_state=RecoveryCaseState.CLOSED,
        )
        assert result.is_passed is True
        assert result.reason_code == "STRATEGY_VALID"

    def test_manual_review_strategy_permitted(self):
        result = self.validator.evaluate(
            strategy=RecoveryStrategy.MANUAL_REVIEW,
            failure_category="risk_blocked",
            case_state=RecoveryCaseState.AWAITING_DECISION,
        )
        assert result.is_passed is True
        assert result.reason_code == "STRATEGY_VALID"


# -------------------------------------------------------------------------
# 5. EscalationEvaluator Tests
# -------------------------------------------------------------------------
class TestEscalationEvaluator:
    """Test suite for EscalationEvaluator."""

    def setup_method(self):
        self.evaluator = EscalationEvaluator()
        self.config = PolicyConfig(high_value_escalation_threshold_minor=100_000)

    def test_transaction_below_threshold_no_escalation(self):
        result = self.evaluator.evaluate(
            amount_minor=50_000,
            currency="INR",
            config=self.config,
            ai_confidence=0.85,
            failure_category="insufficient_funds",
        )
        assert result.is_passed is True
        assert result.reason_code == "NO_ESCALATION_REQUIRED"

    def test_transaction_at_threshold_escalates(self):
        result = self.evaluator.evaluate(
            amount_minor=100_000,
            currency="INR",
            config=self.config,
            ai_confidence=0.90,
            failure_category="insufficient_funds",
        )
        assert result.needs_review is True
        assert result.reason_code == "HIGH_VALUE_REVIEW_REQUIRED"

    def test_currency_aware_jpy_threshold(self):
        # For JPY, default config threshold is 150,000 yen
        result_below = self.evaluator.evaluate(
            amount_minor=100_000,
            currency="JPY",
            config=self.config,
            ai_confidence=0.90,
            failure_category="insufficient_funds",
        )
        assert result_below.is_passed is True

        result_above = self.evaluator.evaluate(
            amount_minor=160_000,
            currency="JPY",
            config=self.config,
            ai_confidence=0.90,
            failure_category="insufficient_funds",
        )
        assert result_above.needs_review is True
        assert result_above.reason_code == "HIGH_VALUE_REVIEW_REQUIRED"

    def test_fraud_restriction_escalates(self):
        result = self.evaluator.evaluate(
            amount_minor=2_000,
            currency="INR",
            config=self.config,
            ai_confidence=0.95,
            failure_category="fraud_suspected",
        )
        assert result.needs_review is True
        assert result.reason_code == "FRAUD_RESTRICTION"

    def test_low_ai_confidence_escalates(self):
        result = self.evaluator.evaluate(
            amount_minor=2_000,
            currency="INR",
            config=self.config,
            ai_confidence=0.45,  # Below default min 0.60
            failure_category="insufficient_funds",
        )
        assert result.needs_review is True
        assert result.reason_code == "LOW_AI_CONFIDENCE"

    def test_missing_ai_confidence(self):
        result = self.evaluator.evaluate(
            amount_minor=2_000,
            currency="INR",
            config=self.config,
            ai_confidence=None,
            failure_category="insufficient_funds",
        )
        assert result.is_missing_info is True
        assert result.reason_code == "AI_CONFIDENCE_MISSING"

    def test_retry_exhausted_escalates(self):
        result = self.evaluator.evaluate(
            amount_minor=2_000,
            currency="INR",
            config=self.config,
            ai_confidence=0.85,
            failure_category="insufficient_funds",
            prior_retries_exhausted=True,
        )
        assert result.needs_review is True
        assert result.reason_code == "RETRY_EXHAUSTED"

    def test_conflicting_events_escalate(self):
        result = self.evaluator.evaluate(
            amount_minor=2_000,
            currency="INR",
            config=self.config,
            ai_confidence=0.85,
            failure_category="insufficient_funds",
            has_conflicting_events=True,
        )
        assert result.needs_review is True
        assert result.reason_code == "PAYMENT_EVENT_CONFLICT"

    def test_uncertain_outcome_escalates(self):
        result = self.evaluator.evaluate(
            amount_minor=2_000,
            currency="INR",
            config=self.config,
            ai_confidence=0.85,
            failure_category="insufficient_funds",
            has_uncertain_outcome=True,
        )
        assert result.needs_review is True
        assert result.reason_code == "PAYMENT_OUTCOME_UNCERTAIN"
