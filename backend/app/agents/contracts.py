"""Structured contracts for the bounded RevenueRescue AI agent brain.

Author: Karthikeya
Architectural layer: agent boundary.

The agent proposes an action from a caller-provided allow-list. It never owns
policy approval and never receives arbitrary tool authority.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import ActionType, RecoveryCaseState


class AgentObservation(BaseModel):
    """Minimal, sanitized facts supplied to the reasoning provider."""

    model_config = ConfigDict(extra="forbid")

    case_id: UUID
    transaction_id: UUID
    transaction_status: str
    amount_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    customer_context_available: bool
    risk_reason_codes: list[str] = Field(min_length=1, max_length=10)
    current_state: RecoveryCaseState
    prior_attempt_count: int = Field(ge=0)
    allowed_actions: list[ActionType] = Field(min_length=1, max_length=10)


class AgentDecisionOutput(BaseModel):
    """Strict structured output proposed by the agent provider."""

    model_config = ConfigDict(extra="forbid")

    case_id: UUID
    action: ActionType
    reason_code: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    requires_human_review: bool
    stop_reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason_code")
    @classmethod
    def normalize_reason_code(cls, value: str) -> str:
        """Keep reason codes stable for audit and evaluation."""

        return value.strip().lower().replace(" ", "_")


class ValidatedAgentDecision(AgentDecisionOutput):
    """Decision after deterministic boundary validation."""

    validation_status: str = "valid"


def decision_json_schema() -> dict[str, Any]:
    """Return the strict JSON schema sent to structured-output providers."""

    schema = AgentDecisionOutput.model_json_schema()
    schema["additionalProperties"] = False
    return schema


def validate_decision(
    decision: AgentDecisionOutput,
    observation: AgentObservation,
) -> ValidatedAgentDecision:
    """Reject decisions that exceed the observation's explicit action allow-list."""

    if decision.case_id != observation.case_id:
        raise ValueError("agent decision case_id does not match observation")
    if decision.action not in observation.allowed_actions:
        raise ValueError(f"agent proposed action outside allow-list: {decision.action}")
    if decision.action is ActionType.STOP and not decision.stop_reason:
        raise ValueError("stop decisions require stop_reason")
    if decision.action is not ActionType.STOP and decision.stop_reason:
        raise ValueError("stop_reason is only valid for stop decisions")
    return ValidatedAgentDecision(**decision.model_dump(), validation_status="valid")
