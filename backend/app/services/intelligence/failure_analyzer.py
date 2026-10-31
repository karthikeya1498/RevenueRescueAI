"""Payment failure analysis and evidence extraction engine.

Author: Karthikeya
Architectural layer: domain service / failure analysis.

Analyzes normalized payment failure events and recovery cases to categorize the
underlying revenue loss mechanism and extract verifiable supporting evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.core.enums import CanonicalEventType


@dataclass(frozen=True)
class FailureAnalysisResult:
    """Structured outcome of payment failure analysis."""

    failure_category: str
    retryable: bool
    confidence: Decimal
    explanation: str
    evidence: list[str] = field(default_factory=list)
    raw_code: str | None = None
    analysis_version: str = "rules-v1"

    @property
    def category(self) -> str:
        """Alias for failure_category."""
        return self.failure_category


class FailureAnalyzer:
    """Analyzes failure codes, diagnostics, and event types into actionable categories."""

    VERSION = "failure-rules-v1"

    # Category matching rules: tuple of (keywords, category_id, is_retryable, base_confidence, explanation_template)
    RULES = (
        (
            ("insufficient_funds", "insufficient", "balance", "not_enough_funds"),
            "insufficient_funds",
            True,
            Decimal("0.9500"),
            "Payment declined due to temporary insufficient balance. Retryable upon scheduled cooling period.",
        ),
        (
            ("expired", "card_expired", "card_has_expired"),
            "expired_card",
            False,
            Decimal("0.9500"),
            "Payment instrument has expired. Requires customer to input updated expiration/card.",
        ),
        (
            ("authentication_required", "3ds", "3d_secure", "auth_required", "challenge_required"),
            "authentication_required",
            True,
            Decimal("0.9000"),
            "Step-up 3D-Secure or SCA customer authentication required.",
        ),
        (
            ("fraud", "fraudulent", "risk_blocked", "stolen_card", "lost_card"),
            "fraud_suspected",
            False,
            Decimal("0.9800"),
            "Flagged by payment gateway or bank security filters for suspected fraud or lost instrument.",
        ),
        (
            ("timeout", "timed_out", "network", "gateway_error", "processing_error"),
            "provider_timeout",
            True,
            Decimal("0.8500"),
            "Transient gateway network error or provider timeout during transaction processing.",
        ),
        (
            ("do_not_honor", "card_declined", "generic_decline", "issuer_declined"),
            "bank_decline",
            True,
            Decimal("0.8500"),
            "Issuer bank declined the transaction without specific diagnostic code.",
        ),
        (
            ("invalid_number", "invalid_cvc", "invalid_expiry", "invalid_account"),
            "invalid_payment_details",
            False,
            Decimal("0.9500"),
            "Customer submitted invalid payment instrument details.",
        ),
    )

    @classmethod
    def analyze(
        cls,
        *,
        failure_code: str | None = None,
        failure_message: str | None = None,
        event_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        code: str | None = None,
        message: str | None = None,
    ) -> FailureAnalysisResult:
        """Categorize payment failure and compile verifiable evidence."""
        actual_code = failure_code if failure_code is not None else code
        actual_message = failure_message if failure_message is not None else message
        failure_code = actual_code
        failure_message = actual_message
        meta = metadata or {}
        evidence: list[str] = []

        code_clean = (failure_code or "").strip().lower()
        msg_clean = (failure_message or "").strip().lower()
        event_clean = (event_type or "").strip().upper()

        combined_text = f"{code_clean} {msg_clean}"

        # 1. Event Type Specific Handling
        if event_clean == CanonicalEventType.CHECKOUT_ABANDONED.value:
            evidence.append(f"Source event type: {CanonicalEventType.CHECKOUT_ABANDONED.value}")
            return FailureAnalysisResult(
                failure_category="abandoned_checkout",
                retryable=False,
                confidence=Decimal("0.9500"),
                explanation="Customer abandoned high-intent checkout session before completion.",
                evidence=evidence,
                raw_code=failure_code,
                analysis_version=cls.VERSION,
            )

        if event_clean == CanonicalEventType.INVOICE_OVERDUE.value:
            evidence.append(f"Source event type: {CanonicalEventType.INVOICE_OVERDUE.value}")
            return FailureAnalysisResult(
                failure_category="overdue_invoice",
                retryable=False,
                confidence=Decimal("0.9500"),
                explanation="B2B invoice has passed its payment due date without settlement.",
                evidence=evidence,
                raw_code=failure_code,
                analysis_version=cls.VERSION,
            )

        # 2. Keyword Rule Evaluation
        if failure_code:
            evidence.append(f"Gateway failure code: {failure_code}")
        if failure_message:
            evidence.append(f"Gateway message: {failure_message}")

        for keywords, category, retryable, conf, explanation in cls.RULES:
            if any(kw in combined_text for kw in keywords):
                return FailureAnalysisResult(
                    failure_category=category,
                    retryable=retryable,
                    confidence=conf,
                    explanation=explanation,
                    evidence=evidence,
                    raw_code=failure_code,
                    analysis_version=cls.VERSION,
                )

        # 3. Fallback: Unknown / Missing Failure Reason
        evidence.append("No recognized diagnostic code provided by gateway.")
        return FailureAnalysisResult(
            failure_category="unknown_failure",
            retryable=False,
            confidence=Decimal("0.5000"),
            explanation="Unclassified failure code; insufficient evidence for automated categorization.",
            evidence=evidence,
            raw_code=failure_code,
            analysis_version=cls.VERSION,
        )
