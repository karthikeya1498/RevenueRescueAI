"""Razorpay Sandbox Payment Execution Adapter.

Author: Karthikeya
Architectural layer: workflow adapters / Razorpay provider integration.

Provides sandbox execution, deterministic test scenario simulation (including ₹2,500 tests),
safe timeout handling, idempotency deduplication, and normalized error mapping.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

import requests

from app.core.config import get_settings
from app.core.database import utc_now
from app.core.enums import ExecutionStatus
from app.services.event_normalizer import EventNormalizer
from app.workflows.adapters.base import (
    ExecutionResult,
    PaymentExecutionAdapter,
    PaymentRetryRequest,
    PaymentStatusQuery,
)


class RazorpaySandboxPaymentAdapter(PaymentExecutionAdapter):
    """Payment execution adapter targeting the Razorpay Sandbox API.

    In sandbox/mock mode:
    - Simulates authentic Razorpay request/response semantics.
    - Honors deterministic test triggers passed in request metadata or amount.
    - Accurately captures latency, gateway references, and failure reasons.
    - Idempotently prevents double-submission using idempotency keys.
    """

    PROVIDER_NAME = "razorpay"

    def __init__(
        self,
        *,
        key_id: str | None = None,
        key_secret: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        simulate_scenarios: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.key_id = key_id or settings.payment_provider_key_id
        self.key_secret = key_secret or settings.payment_provider_key_secret
        self.base_url = (base_url or settings.payment_provider_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.payment_provider_timeout_seconds
        self.simulate_scenarios = (
            simulate_scenarios
            if simulate_scenarios is not None
            else settings.payment_simulate_scenarios
        )

        # In-memory idempotency store for sandbox simulation
        self._sandbox_submissions: dict[str, ExecutionResult] = {}
        self._lock = Lock()

    def submit_retry(self, request: PaymentRetryRequest) -> ExecutionResult:
        """Submit a payment retry attempt to Razorpay."""
        start_time = time.perf_counter()

        # 1. Enforce idempotency check before any action
        with self._lock:
            existing = self._sandbox_submissions.get(request.idempotency_key)
            if existing is not None:
                # Return existing result without re-executing
                return existing

        # 2. Check if we should use sandbox deterministic simulation
        if self.simulate_scenarios or self._is_test_placeholder_key(self.key_id):
            result = self._simulate_sandbox_execution(request, start_time)
            with self._lock:
                self._sandbox_submissions[request.idempotency_key] = result
            return result

        # 3. Live HTTP call to Razorpay Sandbox
        result = self._execute_live_razorpay_request(request, start_time)
        with self._lock:
            self._sandbox_submissions[request.idempotency_key] = result
        return result

    def retrieve_status(self, query: PaymentStatusQuery) -> ExecutionResult:
        """Fetch current payment status from Razorpay."""
        start_time = time.perf_counter()

        if self.simulate_scenarios or self._is_test_placeholder_key(self.key_id):
            return self._simulate_status_retrieval(query, start_time)

        return self._execute_live_status_query(query, start_time)

    # -------------------------------------------------------------------------
    # Internal Sandbox Simulator
    # -------------------------------------------------------------------------

    def _simulate_sandbox_execution(
        self, request: PaymentRetryRequest, start_time: float
    ) -> ExecutionResult:
        """Simulate realistic Razorpay sandbox behaviors based on metadata or amounts."""
        scenario = str(request.metadata.get("sandbox_scenario", "")).upper()
        now = utc_now()

        # Deterministic scenario overrides
        if scenario == "TIMEOUT" or request.metadata.get("simulate_timeout") is True:
            latency_ms = int((time.perf_counter() - start_time) * 1000) + 15
            return ExecutionResult(
                status=ExecutionStatus.UNKNOWN,
                provider=self.PROVIDER_NAME,
                provider_payment_id=None,
                provider_order_id=None,
                amount_minor=request.amount_minor,
                currency=request.currency,
                error_code="GATEWAY_TIMEOUT",
                error_message_safe="Gateway request timed out after sandbox threshold.",
                raw_response_safe={"error": {"code": "GATEWAY_TIMEOUT", "description": "Request timed out"}},
                latency_ms=latency_ms,
                executed_at=now,
                is_definitive=False,
            )

        if scenario == "FAILED" or request.metadata.get("simulate_failure") is True:
            latency_ms = int((time.perf_counter() - start_time) * 1000) + 12
            error_code = str(request.metadata.get("failure_code", "BAD_REQUEST_PAYMENT_FAILED"))
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                provider=self.PROVIDER_NAME,
                provider_payment_id=f"pay_sim_failed_{uuid4().hex[:10]}",
                provider_order_id=f"order_sim_{uuid4().hex[:10]}",
                amount_minor=request.amount_minor,
                currency=request.currency,
                error_code=error_code,
                error_message_safe="Simulated payment decline in sandbox environment.",
                raw_response_safe={
                    "status": "failed",
                    "error": {"code": error_code, "description": "Payment failed in sandbox simulation."},
                },
                latency_ms=latency_ms,
                executed_at=now,
                is_definitive=True,
            )

        if scenario == "SUCCEEDED" or request.metadata.get("simulate_success") is True:
            latency_ms = int((time.perf_counter() - start_time) * 1000) + 10
            pay_id = f"pay_sim_succ_{uuid4().hex[:10]}"
            order_id = f"order_sim_{uuid4().hex[:10]}"
            return ExecutionResult(
                status=ExecutionStatus.SUCCEEDED,
                provider=self.PROVIDER_NAME,
                provider_payment_id=pay_id,
                provider_order_id=order_id,
                amount_minor=request.amount_minor,
                currency=request.currency,
                error_code=None,
                error_message_safe=None,
                raw_response_safe={
                    "id": pay_id,
                    "entity": "payment",
                    "amount": request.amount_minor,
                    "currency": request.currency,
                    "status": "captured",
                    "order_id": order_id,
                    "method": request.payment_method or "card",
                },
                latency_ms=latency_ms,
                executed_at=now,
                is_definitive=True,
            )

        # Default Sandbox submission: gateway accepts request for processing -> SUBMITTED
        latency_ms = int((time.perf_counter() - start_time) * 1000) + 8
        pay_id = f"pay_sim_sub_{uuid4().hex[:10]}"
        order_id = f"order_sim_{uuid4().hex[:10]}"
        return ExecutionResult(
            status=ExecutionStatus.SUBMITTED,
            provider=self.PROVIDER_NAME,
            provider_payment_id=pay_id,
            provider_order_id=order_id,
            amount_minor=request.amount_minor,
            currency=request.currency,
            error_code=None,
            error_message_safe=None,
            raw_response_safe={
                "id": pay_id,
                "entity": "payment",
                "amount": request.amount_minor,
                "currency": request.currency,
                "status": "created",
                "order_id": order_id,
            },
            latency_ms=latency_ms,
            executed_at=now,
            is_definitive=True,
        )

    def _simulate_status_retrieval(
        self, query: PaymentStatusQuery, start_time: float
    ) -> ExecutionResult:
        """Simulate fetching payment status by reference."""
        pay_id = query.provider_payment_id
        now = utc_now()
        latency_ms = int((time.perf_counter() - start_time) * 1000) + 5

        # Check existing submissions for this payment ID
        for res in self._sandbox_submissions.values():
            if res.provider_payment_id == pay_id:
                return res

        # Unknown reference simulation
        if "not_found" in pay_id.lower() or "invalid" in pay_id.lower():
            return ExecutionResult(
                status=ExecutionStatus.UNKNOWN,
                provider=self.PROVIDER_NAME,
                provider_payment_id=pay_id,
                provider_order_id=None,
                amount_minor=0,
                currency="INR",
                error_code="BAD_REQUEST_PAYMENT_NOT_FOUND",
                error_message_safe="Payment reference not found on gateway.",
                raw_response_safe={"error": {"code": "BAD_REQUEST_ERROR", "description": "Payment not found"}},
                latency_ms=latency_ms,
                executed_at=now,
                is_definitive=True,
            )

        # Default fallback status query
        status = ExecutionStatus.SUCCEEDED if "succ" in pay_id else (
            ExecutionStatus.FAILED if "fail" in pay_id else ExecutionStatus.SUBMITTED
        )
        return ExecutionResult(
            status=status,
            provider=self.PROVIDER_NAME,
            provider_payment_id=pay_id,
            provider_order_id=f"order_{pay_id[-8:]}",
            amount_minor=250000,
            currency="INR",
            error_code=None if status != ExecutionStatus.FAILED else "PAYMENT_FAILED",
            error_message_safe=None if status != ExecutionStatus.FAILED else "Simulated decline",
            raw_response_safe={"id": pay_id, "status": "captured" if status == ExecutionStatus.SUCCEEDED else "created"},
            latency_ms=latency_ms,
            executed_at=now,
            is_definitive=True,
        )

    # -------------------------------------------------------------------------
    # Live HTTP Implementation (when real sandbox keys are supplied)
    # -------------------------------------------------------------------------

    def _execute_live_razorpay_request(
        self, request: PaymentRetryRequest, start_time: float
    ) -> ExecutionResult:
        """Issue live HTTP order/payment request to Razorpay Sandbox endpoint."""
        now = utc_now()
        url = f"{self.base_url}/orders"
        payload = {
            "amount": request.amount_minor,
            "currency": request.currency.upper(),
            "receipt": request.idempotency_key[:40],
            "notes": {
                "case_id": str(request.case_id),
                "transaction_id": str(request.transaction_id),
            },
        }

        try:
            resp = requests.post(
                url,
                json=payload,
                auth=(self.key_id, self.key_secret),
                timeout=self.timeout_seconds,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            if resp.status_code in (200, 201):
                data = resp.json()
                safe_data = EventNormalizer.sanitize_metadata(data)
                order_id = data.get("id")
                return ExecutionResult(
                    status=ExecutionStatus.SUBMITTED,
                    provider=self.PROVIDER_NAME,
                    provider_payment_id=None,
                    provider_order_id=order_id,
                    amount_minor=data.get("amount", request.amount_minor),
                    currency=data.get("currency", request.currency),
                    error_code=None,
                    error_message_safe=None,
                    raw_response_safe=safe_data,
                    latency_ms=latency_ms,
                    executed_at=now,
                    is_definitive=True,
                )
            else:
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                safe_data = EventNormalizer.sanitize_metadata(data)
                err = safe_data.get("error", {})
                err_code = err.get("code", f"HTTP_{resp.status_code}")
                err_desc = err.get("description", "Razorpay order creation rejected.")
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    provider=self.PROVIDER_NAME,
                    provider_payment_id=None,
                    provider_order_id=None,
                    amount_minor=request.amount_minor,
                    currency=request.currency,
                    error_code=err_code,
                    error_message_safe=err_desc,
                    raw_response_safe=safe_data,
                    latency_ms=latency_ms,
                    executed_at=now,
                    is_definitive=True,
                )

        except requests.Timeout:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return ExecutionResult(
                status=ExecutionStatus.UNKNOWN,
                provider=self.PROVIDER_NAME,
                provider_payment_id=None,
                provider_order_id=None,
                amount_minor=request.amount_minor,
                currency=request.currency,
                error_code="GATEWAY_TIMEOUT",
                error_message_safe=f"Connection to Razorpay timed out after {self.timeout_seconds}s.",
                raw_response_safe={"error": {"code": "GATEWAY_TIMEOUT"}},
                latency_ms=latency_ms,
                executed_at=now,
                is_definitive=False,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return ExecutionResult(
                status=ExecutionStatus.UNKNOWN,
                provider=self.PROVIDER_NAME,
                provider_payment_id=None,
                provider_order_id=None,
                amount_minor=request.amount_minor,
                currency=request.currency,
                error_code="NETWORK_ERROR",
                error_message_safe=f"Failed to communicate with Razorpay: {exc}",
                raw_response_safe={"error": {"code": "NETWORK_ERROR"}},
                latency_ms=latency_ms,
                executed_at=now,
                is_definitive=False,
            )

    def _execute_live_status_query(
        self, query: PaymentStatusQuery, start_time: float
    ) -> ExecutionResult:
        """Fetch payment details from live Razorpay API."""
        now = utc_now()
        url = f"{self.base_url}/payments/{query.provider_payment_id}"

        try:
            resp = requests.get(
                url,
                auth=(self.key_id, self.key_secret),
                timeout=self.timeout_seconds,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            if resp.status_code == 200:
                data = resp.json()
                safe_data = EventNormalizer.sanitize_metadata(data)
                raw_status = data.get("status", "").lower()
                status = self._normalize_razorpay_status(raw_status)
                return ExecutionResult(
                    status=status,
                    provider=self.PROVIDER_NAME,
                    provider_payment_id=data.get("id"),
                    provider_order_id=data.get("order_id"),
                    amount_minor=int(data.get("amount", 0)),
                    currency=str(data.get("currency", "INR")).upper(),
                    error_code=data.get("error_code"),
                    error_message_safe=data.get("error_description"),
                    raw_response_safe=safe_data,
                    latency_ms=latency_ms,
                    executed_at=now,
                    is_definitive=True,
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.UNKNOWN,
                    provider=self.PROVIDER_NAME,
                    provider_payment_id=query.provider_payment_id,
                    provider_order_id=None,
                    amount_minor=0,
                    currency="INR",
                    error_code=f"HTTP_{resp.status_code}",
                    error_message_safe="Gateway failed to return payment status.",
                    raw_response_safe={},
                    latency_ms=latency_ms,
                    executed_at=now,
                    is_definitive=True,
                )
        except requests.Timeout:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return ExecutionResult(
                status=ExecutionStatus.UNKNOWN,
                provider=self.PROVIDER_NAME,
                provider_payment_id=query.provider_payment_id,
                provider_order_id=None,
                amount_minor=0,
                currency="INR",
                error_code="GATEWAY_TIMEOUT",
                error_message_safe="Timeout querying Razorpay payment status.",
                raw_response_safe={},
                latency_ms=latency_ms,
                executed_at=now,
                is_definitive=False,
            )

    @staticmethod
    def _normalize_razorpay_status(raw_status: str) -> ExecutionStatus:
        """Map Razorpay official payment entity status strings to ExecutionStatus."""
        mapping = {
            "created": ExecutionStatus.SUBMITTED,
            "authorized": ExecutionStatus.PENDING,
            "captured": ExecutionStatus.SUCCEEDED,
            "failed": ExecutionStatus.FAILED,
            "refunded": ExecutionStatus.CANCELLED,
        }
        return mapping.get(raw_status, ExecutionStatus.UNKNOWN)

    @staticmethod
    def _is_test_placeholder_key(key: str | None) -> bool:
        if not key:
            return True
        return "placeholder" in key.lower() or key.startswith("rzp_test_placeholder")
