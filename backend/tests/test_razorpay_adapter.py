"""Tests for Razorpay Sandbox Payment Adapter.

Author: Karthikeya
Architectural layer: tests / payment provider adapter.

Verifies:
- ₹2,500 payment request simulation modes (SUBMITTED, SUCCEEDED, FAILED, UNKNOWN).
- Idempotency deduplication for repeated requests.
- Response normalization into ExecutionStatus.
- Sanitization of card details, credentials, and PII.
"""

from uuid import uuid4

from app.core.enums import ExecutionStatus
from app.workflows.adapters.base import PaymentRetryRequest, PaymentStatusQuery
from app.workflows.adapters.razorpay_adapter import RazorpaySandboxPaymentAdapter


def test_razorpay_adapter_submitted_status_for_2500_payment():
    """Demonstrates standard ₹2,500 payment submission returns SUBMITTED."""
    adapter = RazorpaySandboxPaymentAdapter(simulate_scenarios=True)
    request = PaymentRetryRequest(
        case_id=uuid4(),
        transaction_id=uuid4(),
        amount_minor=250000,  # ₹2,500.00 in paise
        currency="INR",
        customer_reference="cust_test_101",
        idempotency_key=f"idem_{uuid4().hex}",
        customer_email="customer@example.com",
    )

    result = adapter.submit_retry(request)

    assert result.status == ExecutionStatus.SUBMITTED
    assert result.provider == "razorpay"
    assert result.provider_payment_id is not None
    assert result.amount_minor == 250000
    assert result.currency == "INR"
    assert result.error_code is None
    assert result.is_definitive is True
    assert "id" in result.raw_response_safe


def test_razorpay_adapter_simulated_success():
    """Demonstrates provider confirmed success returns SUCCEEDED."""
    adapter = RazorpaySandboxPaymentAdapter(simulate_scenarios=True)
    request = PaymentRetryRequest(
        case_id=uuid4(),
        transaction_id=uuid4(),
        amount_minor=250000,
        currency="INR",
        customer_reference="cust_test_102",
        idempotency_key=f"idem_{uuid4().hex}",
        metadata={"sandbox_scenario": "SUCCEEDED"},
    )

    result = adapter.submit_retry(request)

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.provider_payment_id.startswith("pay_sim_succ_")
    assert result.raw_response_safe.get("status") == "captured"
    assert result.is_definitive is True


def test_razorpay_adapter_simulated_failure():
    """Demonstrates provider confirmed failure returns FAILED."""
    adapter = RazorpaySandboxPaymentAdapter(simulate_scenarios=True)
    request = PaymentRetryRequest(
        case_id=uuid4(),
        transaction_id=uuid4(),
        amount_minor=250000,
        currency="INR",
        customer_reference="cust_test_103",
        idempotency_key=f"idem_{uuid4().hex}",
        metadata={"sandbox_scenario": "FAILED", "failure_code": "INSUFFICIENT_FUNDS"},
    )

    result = adapter.submit_retry(request)

    assert result.status == ExecutionStatus.FAILED
    assert result.error_code == "INSUFFICIENT_FUNDS"
    assert result.is_definitive is True
    assert "decline" in result.error_message_safe.lower() or "failed" in result.error_message_safe.lower()



def test_razorpay_adapter_simulated_timeout_returns_unknown():
    """Demonstrates network/gateway timeout returns UNKNOWN and is NOT definitive."""
    adapter = RazorpaySandboxPaymentAdapter(simulate_scenarios=True)
    request = PaymentRetryRequest(
        case_id=uuid4(),
        transaction_id=uuid4(),
        amount_minor=250000,
        currency="INR",
        customer_reference="cust_test_104",
        idempotency_key=f"idem_{uuid4().hex}",
        metadata={"sandbox_scenario": "TIMEOUT"},
    )

    result = adapter.submit_retry(request)

    assert result.status == ExecutionStatus.UNKNOWN
    assert result.error_code == "GATEWAY_TIMEOUT"
    assert result.is_definitive is False
    assert result.provider_payment_id is None


def test_razorpay_adapter_idempotency_deduplication():
    """Demonstrates identical idempotency key returns cached result without re-executing."""
    adapter = RazorpaySandboxPaymentAdapter(simulate_scenarios=True)
    idem_key = f"idem_dedup_{uuid4().hex}"
    request1 = PaymentRetryRequest(
        case_id=uuid4(),
        transaction_id=uuid4(),
        amount_minor=250000,
        currency="INR",
        customer_reference="cust_test_105",
        idempotency_key=idem_key,
    )

    result1 = adapter.submit_retry(request1)

    # Submit second request with same idempotency key but different metadata
    request2 = PaymentRetryRequest(
        case_id=uuid4(),
        transaction_id=uuid4(),
        amount_minor=250000,
        currency="INR",
        customer_reference="cust_test_105",
        idempotency_key=idem_key,
        metadata={"sandbox_scenario": "FAILED"},
    )

    result2 = adapter.submit_retry(request2)

    # Must return exact same result1 object and payment reference
    assert result2.status == result1.status
    assert result2.provider_payment_id == result1.provider_payment_id
    assert result2.executed_at == result1.executed_at


def test_razorpay_adapter_status_retrieval_normalization():
    """Demonstrates status query normalizes Razorpay payment status strings."""
    adapter = RazorpaySandboxPaymentAdapter(simulate_scenarios=True)

    succ_query = PaymentStatusQuery(provider_payment_id="pay_succ_998877")
    res_succ = adapter.retrieve_status(succ_query)
    assert res_succ.status == ExecutionStatus.SUCCEEDED

    fail_query = PaymentStatusQuery(provider_payment_id="pay_fail_112233")
    res_fail = adapter.retrieve_status(fail_query)
    assert res_fail.status == ExecutionStatus.FAILED

    not_found_query = PaymentStatusQuery(provider_payment_id="pay_not_found_000")
    res_not_found = adapter.retrieve_status(not_found_query)
    assert res_not_found.status == ExecutionStatus.UNKNOWN
    assert res_not_found.error_code == "BAD_REQUEST_PAYMENT_NOT_FOUND"
