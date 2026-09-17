"""HTTP boundary for explainable recovery intelligence and provider verification.
Author: Karthikeya
"""

from __future__ import annotations

import json
import os
from hashlib import sha256
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.webhook_events import WebhookEventRepository
from app.services.intelligence import DecisionAnalysis, analyze_recovery, compare_strategies
from app.services.verification import verify_signature

router = APIRouter(prefix="/api/v1/recovery", tags=["recovery-intelligence"])


class DecisionPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    failure_code: str | None = Field(default=None, max_length=100)
    failure_message: str | None = Field(default=None, max_length=500)
    prior_attempts: int = Field(default=0, ge=0, le=20)
    customer_success_rate: float = Field(default=0.5, ge=0, le=1)
    alternate_method_available: bool = True
    unusual_velocity: bool = False
    customer_restricted: bool = False


class WebhookResult(BaseModel):
    accepted: bool
    duplicate: bool
    event_id: str
    event_type: str
    reason: str
    verified: bool


def _analysis_dict(analysis: DecisionAnalysis) -> dict[str, Any]:
    return {
        "failure_classification": {
            "category": analysis.classification.category,
            "retryable": analysis.classification.retryable,
            "confidence": str(analysis.classification.confidence),
            "explanation": analysis.classification.explanation,
        },
        "risk": {
            "score": analysis.risk.score,
            "band": analysis.risk.band,
            "reasons": list(analysis.risk.reasons),
            "action_limit": analysis.risk.action_limit,
        },
        "recommendation": {
            "action": analysis.recommended_action,
            "confidence": str(analysis.confidence),
            "rationale": list(analysis.rationale),
        },
        "action_estimates": [
            {
                "action": row.action,
                "probability": str(row.probability),
                "amount_minor": row.amount_minor,
                "recovery_value_minor": row.recovery_value_minor,
                "cost_minor": row.cost_minor,
                "expected_value_minor": row.expected_value_minor,
                "explanation": list(row.explanation),
            }
            for row in analysis.estimates
        ],
    }


@router.post("/decision-preview")
def decision_preview(payload: DecisionPreviewRequest) -> dict[str, Any]:
    """Return a transparent recommendation; this endpoint executes no payment action."""
    values = payload.model_dump()
    values.pop("currency")
    analysis = analyze_recovery(**values)
    return {
        "mode": "decision_preview",
        "currency": payload.currency,
        "model_version": "deterministic-logistic-v1",
        "policy_authority": "deterministic",
        **_analysis_dict(analysis),
    }


@router.post("/strategy-comparison")
def strategy_comparison(payloads: list[DecisionPreviewRequest]) -> dict[str, Any]:
    """Compare strategies using expected values, not unverified recovery claims."""
    if len(payloads) > 1000:
        raise HTTPException(status_code=413, detail="maximum 1000 scenarios per comparison")
    analyses = []
    for payload in payloads:
        values = payload.model_dump()
        values.pop("currency")
        analyses.append(analyze_recovery(**values))
    return {
        "scenario_count": len(analyses),
        "strategies": compare_strategies(analyses),
        "measurement": "expected_value_estimate_not_verified_revenue",
    }


@router.post("/webhooks/provider", response_model=WebhookResult)
async def provider_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_event_id: str | None = Header(default=None),
    x_signature: str | None = Header(default=None),
) -> WebhookResult:
    """Verify and deduplicate a provider event before any downstream processing."""
    body = await request.body()
    event_id = x_event_id or request.headers.get("x-razorpay-event-id")
    if not event_id:
        raise HTTPException(status_code=400, detail="missing event id")
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    verified = verify_signature(
        body, x_signature or request.headers.get("x-razorpay-signature", ""), secret
    )
    if not verified:
        raise HTTPException(status_code=401, detail="invalid provider signature")
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("webhook payload must be a JSON object")
        event_type = str(payload.get("event", "unknown"))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="invalid JSON payload") from None
    safe_payload = {
        key: payload[key]
        for key in ("event", "id", "entity")
        if key in payload and isinstance(payload[key], (str, int, bool, type(None)))
    }
    receipt = WebhookEventRepository(db).record(
        provider="razorpay",
        event_id=event_id,
        event_type=event_type,
        payload_hash=sha256(body).hexdigest(),
        signature_verified=True,
        payload_safe=safe_payload,
    )
    db.commit()
    return WebhookResult(
        accepted=receipt.accepted,
        duplicate=receipt.duplicate,
        event_id=event_id,
        event_type=event_type,
        reason=receipt.reason,
        verified=True,
    )
