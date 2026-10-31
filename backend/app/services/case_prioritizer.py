"""Deterministic case prioritization engine for RevenueRescueAI.

Author: Karthikeya
Architectural layer: domain service / prioritization.

Assigns explainable operational priority to recovery cases without using AI.
Priority is represented on an integer scale from 1 (highest urgency) to 1000 (lowest urgency),
matching the queue ordering invariant: order_by(RecoveryCase.priority.asc()).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.database import utc_now


@dataclass(frozen=True)
class PriorityResult:
    """Result of deterministic case priority calculation."""

    priority: int
    reason: str
    factors: dict[str, Any]


class CasePrioritizer:
    """Calculates explainable operational queue priority based on exposure and failure characteristics."""

    BASE_PRIORITY = 100

    @classmethod
    def calculate_priority(
        cls,
        *,
        amount_minor: int,
        currency: str,
        failure_code: str | None,
        event_type: str,
        opened_at: datetime | None = None,
        as_of: datetime | None = None,
    ) -> PriorityResult:
        """Compute an explainable, deterministic priority score in range [1, 1000]."""
        current_time = as_of or utc_now()
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        score = cls.BASE_PRIORITY
        rationale_parts: list[str] = []
        factors: dict[str, Any] = {
            "base_priority": cls.BASE_PRIORITY,
            "amount_minor": amount_minor,
            "currency": currency,
            "failure_code": failure_code,
            "event_type": event_type,
        }

        # 1. Financial Exposure Dimension (Larger amount = higher urgency = lower integer)
        if amount_minor >= 500000:  # >= $5,000 / ₹5,000
            score -= 50
            factors["exposure_adjustment"] = -50
            rationale_parts.append(f"Major exposure ({currency} {amount_minor / 100:,.2f}) requires top queue placement")
        elif amount_minor >= 100000:  # >= $1,000 / ₹1,000
            score -= 25
            factors["exposure_adjustment"] = -25
            rationale_parts.append(f"Significant exposure ({currency} {amount_minor / 100:,.2f}) prioritized")
        elif amount_minor >= 25000:  # >= $250 / ₹250
            score -= 10
            factors["exposure_adjustment"] = -10
            rationale_parts.append(f"Moderate exposure ({currency} {amount_minor / 100:,.2f})")
        elif amount_minor < 5000:  # < $50
            score += 15
            factors["exposure_adjustment"] = +15
            rationale_parts.append("Low transaction amount adjusted to standard queue")

        # 2. Failure Category Dimension
        clean_code = (failure_code or "").strip().lower()
        if clean_code in ("insufficient_funds",):
            score -= 20
            factors["failure_adjustment"] = -20
            rationale_parts.append("Transient balance shortage has high recovery probability via scheduled retry")
        elif clean_code in ("processing_error", "network_error", "timeout"):
            score -= 25
            factors["failure_adjustment"] = -25
            rationale_parts.append("Transient gateway/processing error prioritized for rapid re-attempt")
        elif clean_code in ("card_expired", "expired_card"):
            score += 15
            factors["failure_adjustment"] = +15
            rationale_parts.append("Expired card requires customer payment method update")
        elif clean_code in ("authentication_required", "3d_secure_required"):
            score += 10
            factors["failure_adjustment"] = +10
            rationale_parts.append("Authentication step-up required by cardholder")
        elif clean_code in ("fraud_suspected", "fraudulent"):
            score += 50
            factors["failure_adjustment"] = +50
            rationale_parts.append("Suspected fraud de-prioritized for automated retry and flagged for risk review")
        elif clean_code in ("do_not_honor", "card_declined"):
            score += 10
            factors["failure_adjustment"] = +10
            rationale_parts.append("Bank decline requires customer inquiry")

        # 3. Elapsed Age Dimension (Cases unresolved > 24 hours escalate in urgency)
        if opened_at is not None:
            case_time = opened_at
            if case_time.tzinfo is None:
                case_time = case_time.replace(tzinfo=timezone.utc)
            elapsed_hours = (current_time - case_time).total_seconds() / 3600.0
            if elapsed_hours >= 48:
                score -= 20
                factors["age_adjustment"] = -20
                rationale_parts.append(f"Unresolved for {int(elapsed_hours)}h; critical aging escalation")
            elif elapsed_hours >= 24:
                score -= 10
                factors["age_adjustment"] = -10
                rationale_parts.append(f"Unresolved for {int(elapsed_hours)}h; elevated priority")

        # Clamp between 1 and 1000
        final_priority = max(1, min(1000, score))
        factors["final_priority"] = final_priority
        full_reason = ". ".join(rationale_parts) if rationale_parts else "Default queue priority."

        return PriorityResult(
            priority=final_priority,
            reason=full_reason,
            factors=factors,
        )
