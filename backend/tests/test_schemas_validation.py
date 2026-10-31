"""Unit tests for Pydantic v2 DTO validation and input contracts.

Author: Karthikeya
Architectural layer: tests / validation.
"""

from decimal import Decimal
import pytest
from pydantic import ValidationError
from uuid import uuid4

from app.core.enums import ActionType, CustomerStatus, RecoveryCaseState, TransactionStatus
from app.schemas.agent_decisions import AgentDecisionCreateDTO, DecisionPreviewRequestDTO
from app.schemas.common import MoneyMinorUnits, PaginationParams
from app.schemas.customers import CustomerCreateDTO
from app.schemas.recovery_cases import CaseStateTransitionDTO, RecoveryCaseCreateDTO
from app.schemas.recovery_evidence import RecoveryEvidenceCreateDTO
from app.schemas.transactions import TransactionCreateDTO


def test_money_minor_units_positive_valid() -> None:
    """Valid positive minor units and 3-letter currency must be accepted."""
    money = MoneyMinorUnits(amount_minor=5000, currency="USD")
    assert money.amount_minor == 5000
    assert money.currency == "USD"


def test_money_minor_units_zero_allowed() -> None:
    """Zero amount is allowed for zero-value transactions or authorizations."""
    money = MoneyMinorUnits(amount_minor=0, currency="EUR")
    assert money.amount_minor == 0


def test_money_minor_units_negative_rejected() -> None:
    """Negative amount must be rejected by Pydantic validation."""
    with pytest.raises(ValidationError) as exc_info:
        MoneyMinorUnits(amount_minor=-100, currency="USD")
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("amount_minor",) for err in errors)


def test_currency_iso_format_enforced() -> None:
    """Invalid currencies (lowercase, wrong length, symbols) must be rejected."""
    # Lowercase rejected
    with pytest.raises(ValidationError):
        MoneyMinorUnits(amount_minor=1000, currency="usd")
    # Wrong length rejected
    with pytest.raises(ValidationError):
        MoneyMinorUnits(amount_minor=1000, currency="US")
    with pytest.raises(ValidationError):
        MoneyMinorUnits(amount_minor=1000, currency="USDD")
    # Number in currency rejected
    with pytest.raises(ValidationError):
        MoneyMinorUnits(amount_minor=1000, currency="U1D")


def test_extra_fields_forbidden() -> None:
    """Unrecognized/extra fields must be rejected (extra='forbid')."""
    with pytest.raises(ValidationError) as exc_info:
        CustomerCreateDTO(
            provider="stripe",
            external_customer_id="cus_123",
            recovered=True,  # Disallowed injected field
        )
    assert any("extra_forbidden" in str(err) for err in exc_info.value.errors())


def test_pagination_params_bounds() -> None:
    """Pagination parameters must enforce minimums and maximums."""
    valid = PaginationParams(page=2, size=25)
    assert valid.offset == 25
    assert valid.limit == 25

    # Page < 1 rejected
    with pytest.raises(ValidationError):
        PaginationParams(page=0, size=50)

    # Size < 1 rejected
    with pytest.raises(ValidationError):
        PaginationParams(page=1, size=0)

    # Size > 100 rejected
    with pytest.raises(ValidationError):
        PaginationParams(page=1, size=101)


def test_customer_email_validation() -> None:
    """Customer email must conform to regex pattern if provided."""
    # Valid email
    cust = CustomerCreateDTO(
        provider="stripe",
        external_customer_id="cus_abc",
        email="user@example.com",
    )
    assert cust.email == "user@example.com"

    # Invalid email rejected
    with pytest.raises(ValidationError):
        CustomerCreateDTO(
            provider="stripe",
            external_customer_id="cus_abc",
            email="invalid-email-address",
        )


def test_transaction_create_validation() -> None:
    """TransactionCreateDTO enforces exact integer minor units and status."""
    tx = TransactionCreateDTO(
        customer_id=uuid4(),
        provider="stripe",
        external_transaction_id="ch_12345",
        amount_minor=1499,
        currency="USD",
        status=TransactionStatus.FAILED,
        failure_code="insufficient_funds",
    )
    assert tx.amount_minor == 1499
    assert tx.currency == "USD"
    assert tx.status == TransactionStatus.FAILED


def test_agent_decision_confidence_bounds() -> None:
    """Agent decision confidence must be bounded between 0.0 and 1.0."""
    valid_dec = AgentDecisionCreateDTO(
        case_id=uuid4(),
        action_type=ActionType.RETRY_PAYMENT,
        reason_code="HIGH_RECOVERY_PROBABILITY",
        confidence=Decimal("0.85"),
    )
    assert valid_dec.confidence == Decimal("0.85")

    # Confidence > 1.0 rejected
    with pytest.raises(ValidationError):
        AgentDecisionCreateDTO(
            case_id=uuid4(),
            action_type=ActionType.RETRY_PAYMENT,
            reason_code="INVALID",
            confidence=Decimal("1.05"),
        )

    # Confidence < 0.0 rejected
    with pytest.raises(ValidationError):
        AgentDecisionCreateDTO(
            case_id=uuid4(),
            action_type=ActionType.RETRY_PAYMENT,
            reason_code="INVALID",
            confidence=Decimal("-0.1"),
        )


def test_recovery_evidence_validation() -> None:
    """Recovery evidence must enforce non-negative amount and ISO currency."""
    ev = RecoveryEvidenceCreateDTO(
        intervention_id="int_001",
        provider_event_id="evt_001",
        failed_transaction_id="tx_fail_1",
        successful_transaction_id="tx_succ_1",
        amount_minor=2999,
        currency="USD",
        attribution_reason="settled_within_72h",
        attributable=True,
    )
    assert ev.amount_minor == 2999
    assert ev.attributable is True
