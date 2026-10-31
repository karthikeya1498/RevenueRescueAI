"""Comprehensive unit test suite for Recovery Policy Engine Phase 2.9 Step 1.

Verifies:
1. PolicyDecisionStatus enum and mapping to DecisionValidationStatus.
2. RuleCheckResult model and RuleCheckStatus semantics.
3. CustomerConsentRecord fail-closed evaluation, expiry, revocation, and independent channels.
4. Relational persistence of CustomerConsent and CustomerConsentRepository.
5. PolicyConfig centralized configuration, retry count definitions, and currency-aware thresholds.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.enums import (
    ActionType,
    ConsentStatus,
    ConsentType,
    CustomerStatus,
    DecisionValidationStatus,
    PolicyDecisionStatus,
    RuleCheckStatus,
)
from app.models.domain import Customer, CustomerConsent
from app.policy.config import PolicyConfig
from app.policy.models import (
    CustomerConsentRecord,
    PolicyEvaluationResult,
    RuleCheckResult,
    map_policy_to_validation_status,
)
from app.repositories.customer_consents import CustomerConsentRepository


@pytest.fixture
def db_session():
    """Isolated SQLite database session enforcing foreign keys for consent testing."""
    engine = create_engine("sqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


class TestPolicyDecisionStatus:
    """Validate PolicyDecisionStatus enum values and lifecycle synchronization mapping."""

    def test_all_four_policy_statuses_exist(self):
        statuses = {s.value for s in PolicyDecisionStatus}
        assert statuses == {
            "approved",
            "rejected",
            "requires_review",
            "insufficient_information",
        }

    def test_status_mapping_to_decision_validation_status(self):
        # APPROVED -> VALID
        assert (
            map_policy_to_validation_status(PolicyDecisionStatus.APPROVED)
            == DecisionValidationStatus.VALID
        )
        # REJECTED -> REJECTED_BY_POLICY
        assert (
            map_policy_to_validation_status(PolicyDecisionStatus.REJECTED)
            == DecisionValidationStatus.REJECTED_BY_POLICY
        )
        # REQUIRES_REVIEW -> NOT_VALIDATED
        assert (
            map_policy_to_validation_status(PolicyDecisionStatus.REQUIRES_REVIEW)
            == DecisionValidationStatus.NOT_VALIDATED
        )
        # INSUFFICIENT_INFORMATION -> INVALID
        assert (
            map_policy_to_validation_status(PolicyDecisionStatus.INSUFFICIENT_INFORMATION)
            == DecisionValidationStatus.INVALID
        )


class TestRuleCheckResult:
    """Verify RuleCheckResult outcome representation and helper methods."""

    def test_rule_check_statuses_exist(self):
        statuses = {s.value for s in RuleCheckStatus}
        assert statuses == {"passed", "failed", "needs_review", "missing_info"}

    def test_rule_check_result_properties(self):
        passed = RuleCheckResult(
            rule_name="consent_check",
            status=RuleCheckStatus.PASSED,
            reason_code="CONSENT_VALID",
            message="Valid recurring billing consent active",
        )
        assert passed.is_passed is True
        assert passed.is_failed is False
        assert passed.needs_review is False
        assert passed.is_missing_info is False

        failed = RuleCheckResult(
            rule_name="retry_limit_check",
            status=RuleCheckStatus.FAILED,
            reason_code="RETRY_LIMIT_EXCEEDED",
            message="Maximum retries reached",
            details={"max": 3, "actual": 3},
        )
        assert failed.is_passed is False
        assert failed.is_failed is True
        assert failed.details["max"] == 3

        review = RuleCheckResult(
            rule_name="high_value_escalation",
            status=RuleCheckStatus.NEEDS_REVIEW,
            reason_code="HIGH_VALUE_EXPOSURE",
            message="Amount exceeds ₹1,000 threshold",
        )
        assert review.needs_review is True

        missing = RuleCheckResult(
            rule_name="consent_check",
            status=RuleCheckStatus.MISSING_INFO,
            reason_code="CUSTOMER_NOT_FOUND",
            message="Customer profile does not exist",
        )
        assert missing.is_missing_info is True


class TestCustomerConsentRecord:
    """Validate CustomerConsentRecord business rules, fail-closed semantics, and independence."""

    def test_consent_types_exist(self):
        types = {t.value for t in ConsentType}
        assert types == {
            "recurring_billing",
            "communication_email",
            "communication_sms",
        }

    def test_consent_statuses_exist(self):
        statuses = {s.value for s in ConsentStatus}
        assert statuses == {"granted", "revoked", "expired"}

    def test_valid_active_consent(self):
        record = CustomerConsentRecord(
            customer_id=uuid4(),
            consent_type=ConsentType.RECURRING_BILLING,
            status=ConsentStatus.GRANTED,
            granted_at=datetime.now(timezone.utc) - timedelta(days=10),
            revoked_at=None,
            expires_at=None,
        )
        assert record.is_valid() is True
        assert record.get_validity_reason() == "CONSENT_VALID"

    def test_revoked_consent_fails_closed(self):
        now = datetime.now(timezone.utc)
        record = CustomerConsentRecord(
            customer_id=uuid4(),
            consent_type=ConsentType.RECURRING_BILLING,
            status=ConsentStatus.GRANTED,
            granted_at=now - timedelta(days=30),
            revoked_at=now - timedelta(days=1),
        )
        assert record.is_valid() is False
        assert record.get_validity_reason() == "CONSENT_REVOKED"

    def test_expired_consent_fails_closed(self):
        now = datetime.now(timezone.utc)
        record = CustomerConsentRecord(
            customer_id=uuid4(),
            consent_type=ConsentType.COMMUNICATION_EMAIL,
            status=ConsentStatus.GRANTED,
            granted_at=now - timedelta(days=60),
            expires_at=now - timedelta(minutes=5),
        )
        assert record.is_valid() is False
        assert record.get_validity_reason() == "CONSENT_EXPIRED"

    def test_future_expiry_is_currently_valid(self):
        now = datetime.now(timezone.utc)
        record = CustomerConsentRecord(
            customer_id=uuid4(),
            consent_type=ConsentType.COMMUNICATION_SMS,
            status=ConsentStatus.GRANTED,
            granted_at=now - timedelta(days=5),
            expires_at=now + timedelta(days=25),
        )
        assert record.is_valid(at_time=now) is True
        # But in 30 days it will be expired:
        future = now + timedelta(days=30)
        assert record.is_valid(at_time=future) is False
        assert record.get_validity_reason(at_time=future) == "CONSENT_EXPIRED"

    def test_independent_email_and_sms_channels(self):
        """Email and SMS consent must be evaluated independently."""
        cust_id = uuid4()
        now = datetime.now(timezone.utc)

        email_consent = CustomerConsentRecord(
            customer_id=cust_id,
            consent_type=ConsentType.COMMUNICATION_EMAIL,
            status=ConsentStatus.GRANTED,
            granted_at=now,
        )
        sms_consent = CustomerConsentRecord(
            customer_id=cust_id,
            consent_type=ConsentType.COMMUNICATION_SMS,
            status=ConsentStatus.REVOKED,
            granted_at=now - timedelta(days=5),
            revoked_at=now - timedelta(days=1),
        )

        assert email_consent.is_valid() is True
        assert sms_consent.is_valid() is False
        # Email consent cannot be used to justify SMS communication
        assert email_consent.consent_type != sms_consent.consent_type

    def test_domain_entity_conversion_roundtrip(self):
        cid = uuid4()
        record = CustomerConsentRecord(
            id=uuid4(),
            customer_id=cid,
            consent_type=ConsentType.RECURRING_BILLING,
            status=ConsentStatus.GRANTED,
            merchant_id="merchant_abc",
            source="user_portal",
            evidence_reference="audit_log_456",
            version=2,
        )
        domain = record.to_domain()
        assert domain.customer_id == cid
        assert domain.merchant_id == "merchant_abc"
        assert domain.source == "user_portal"
        assert domain.version == 2

        roundtrip = CustomerConsentRecord.from_domain(domain)
        assert roundtrip.customer_id == cid
        assert roundtrip.merchant_id == "merchant_abc"
        assert roundtrip.version == 2


class TestPolicyConfig:
    """Validate centralized PolicyConfig defaults, retry semantics, and currency-aware thresholds."""

    def test_provisional_defaults_are_explicitly_unapproved(self):
        config = PolicyConfig()
        assert config.is_production_approved is False
        assert config.policy_version == "policy-v1.0"

    def test_retry_attempts_clarification(self):
        """max_retry_attempts represents retries AFTER the initial failed payment."""
        config = PolicyConfig()
        assert config.max_retry_attempts == 3
        assert config.max_total_attempts == 4

        # If 0 retries executed, retry is permitted
        assert config.can_retry(0) is True
        # If 1 retry executed, retry is permitted
        assert config.can_retry(1) is True
        # If 2 retries executed, retry is permitted
        assert config.can_retry(2) is True
        # If 3 retries executed, retry is NOT permitted
        assert config.can_retry(3) is False
        assert config.can_retry(4) is False

    def test_currency_aware_threshold_handling(self):
        config = PolicyConfig()

        # INR threshold: 100,000 paise (₹1,000)
        assert config.get_high_value_threshold("INR") == 100_000
        assert config.is_high_value(99_999, "INR") is False
        assert config.is_high_value(100_000, "INR") is True
        assert config.is_high_value(250_000, "INR") is True

        # JPY threshold: 150,000 yen (zero decimal currency)
        assert config.get_high_value_threshold("JPY") == 150_000
        assert config.is_high_value(100_000, "JPY") is False
        assert config.is_high_value(150_000, "JPY") is True

        # USD threshold: 100,000 cents ($1,000)
        assert config.get_high_value_threshold("USD") == 100_000

        # Unconfigured currency falls back safely to default minor threshold
        assert config.get_high_value_threshold("XYZ") == 100_000

    def test_retry_cooldown_evaluation(self):
        config = PolicyConfig(retry_cooldown_hours=4)
        now = datetime.now(timezone.utc)

        # Attempted 2 hours ago: cooldown NOT elapsed
        recent_attempt = now - timedelta(hours=2)
        assert config.is_cooldown_elapsed(recent_attempt, now) is False

        # Attempted 4 hours ago: cooldown elapsed
        boundary_attempt = now - timedelta(hours=4)
        assert config.is_cooldown_elapsed(boundary_attempt, now) is True

        # Attempted 10 hours ago: cooldown elapsed
        old_attempt = now - timedelta(hours=10)
        assert config.is_cooldown_elapsed(old_attempt, now) is True


class TestCustomerConsentPersistence:
    """Verify SQLAlchemy persistence and CustomerConsentRepository operations."""

    def test_persist_and_find_consent(self, db_session):
        repo = CustomerConsentRepository(db_session)

        # Create customer
        customer = Customer(
            provider="stripe",
            external_customer_id="cust_test_1",
            email="consent_test@example.com",
            status=CustomerStatus.ACTIVE,
        )
        db_session.add(customer)
        db_session.flush()

        consent = CustomerConsent(
            customer_id=customer.id,
            consent_type=ConsentType.RECURRING_BILLING,
            status=ConsentStatus.GRANTED,
            merchant_id="merchant_123",
            granted_at=datetime.now(timezone.utc),
            source="checkout_v1",
            evidence_reference="ip:127.0.0.1;toc:accepted",
        )
        repo.save(consent)
        db_session.commit()

        found = repo.find_by_id(consent.id)
        assert found is not None
        assert found.customer_id == customer.id
        assert found.merchant_id == "merchant_123"
        assert found.evidence_reference == "ip:127.0.0.1;toc:accepted"

    def test_find_active_consent_fail_closed_queries(self, db_session):
        repo = CustomerConsentRepository(db_session)
        now = datetime.now(timezone.utc)

        customer = Customer(
            provider="stripe",
            external_customer_id="cust_test_active",
            status=CustomerStatus.ACTIVE,
        )
        db_session.add(customer)
        db_session.flush()

        # 1. No consent records -> returns None
        active = repo.find_active_consent(customer.id, ConsentType.RECURRING_BILLING)
        assert active is None

        # 2. Add an expired recurring billing consent
        expired_consent = CustomerConsent(
            customer_id=customer.id,
            consent_type=ConsentType.RECURRING_BILLING,
            status=ConsentStatus.GRANTED,
            granted_at=now - timedelta(days=90),
            expires_at=now - timedelta(days=1),
        )
        repo.save(expired_consent)
        db_session.commit()

        # Still None because expired
        assert repo.find_active_consent(customer.id, ConsentType.RECURRING_BILLING) is None

        # 3. Add valid recurring billing consent
        valid_consent = CustomerConsent(
            customer_id=customer.id,
            consent_type=ConsentType.RECURRING_BILLING,
            status=ConsentStatus.GRANTED,
            granted_at=now,
            expires_at=now + timedelta(days=365),
        )
        repo.save(valid_consent)
        db_session.commit()

        active = repo.find_active_consent(customer.id, ConsentType.RECURRING_BILLING)
        assert active is not None
        assert active.id == valid_consent.id

        # 4. Independent channel: SMS consent is NOT active even though recurring billing is
        sms_active = repo.find_active_consent(customer.id, ConsentType.COMMUNICATION_SMS)
        assert sms_active is None

        # 5. Revoke the valid consent
        repo.revoke_consent(valid_consent.id)
        db_session.commit()

        # Now active should return None
        assert repo.find_active_consent(customer.id, ConsentType.RECURRING_BILLING) is None


class TestPolicyEvaluationResult:
    """Verify PolicyEvaluationResult immutability and FSM status mapping."""

    def test_approved_policy_evaluation_result(self):
        case_id = uuid4()
        rec_id = uuid4()
        rule1 = RuleCheckResult(
            rule_name="consent_check",
            status=RuleCheckStatus.PASSED,
            reason_code="CONSENT_VALID",
            message="Valid recurring billing consent",
        )
        rule2 = RuleCheckResult(
            rule_name="retry_limit_check",
            status=RuleCheckStatus.PASSED,
            reason_code="RETRY_LIMIT_OK",
            message="1 of 3 retries used",
        )

        result = PolicyEvaluationResult(
            decision_status=PolicyDecisionStatus.APPROVED,
            case_id=case_id,
            recommendation_id=rec_id,
            proposed_action=ActionType.RETRY_PAYMENT,
            policy_version="policy-v1.0",
            rule_results=[rule1, rule2],
            reasons=["ALL_RULES_PASSED"],
        )

        assert result.is_approved is True
        assert result.validation_status == DecisionValidationStatus.VALID
        assert result.policy_version == "policy-v1.0"
        assert len(result.rule_results) == 2
