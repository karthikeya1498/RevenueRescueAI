"""Phase 4 and Phase 5 agent-brain and tool-boundary tests.

Author: Karthikeya
"""

from uuid import uuid4

import pytest
from app.agents.brain import AgentBrain
from app.agents.contracts import (
    AgentDecisionOutput,
    AgentObservation,
    validate_decision,
)
from app.core.enums import ActionType, RecoveryCaseState
from app.tools.contracts import ToolContext
from app.tools.registry import ToolRegistry


class FakeReasoningProvider:
    """Deterministic fake provider for unit tests."""

    def __init__(self, payload: AgentDecisionOutput) -> None:
        self.payload = payload

    def decide(self, observation: AgentObservation) -> AgentDecisionOutput:
        return self.payload


def make_observation(*, allowed_actions: list[ActionType] | None = None) -> AgentObservation:
    """Build a sanitized observation with an explicit action allow-list."""

    return AgentObservation(
        case_id=uuid4(),
        transaction_id=uuid4(),
        transaction_status="failed",
        amount_minor=4999,
        currency="INR",
        customer_context_available=True,
        risk_reason_codes=["payment_failed"],
        current_state=RecoveryCaseState.AWAITING_DECISION,
        prior_attempt_count=0,
        allowed_actions=allowed_actions or [ActionType.REQUEST_OPERATOR_REVIEW, ActionType.STOP],
    )


def test_agent_brain_returns_validated_allow_list_decision() -> None:
    """A valid provider response becomes a validated bounded decision."""

    observation = make_observation()
    proposed = AgentDecisionOutput(
        case_id=observation.case_id,
        action=ActionType.REQUEST_OPERATOR_REVIEW,
        reason_code="high_risk_payment_failure",
        rationale="The failed payment should be reviewed before any retry.",
        confidence=0.92,
        requires_human_review=True,
    )

    result = AgentBrain(FakeReasoningProvider(proposed), provider_name="fake").reason(observation)

    assert result.provider_name == "fake"
    assert result.decision.validation_status == "valid"
    assert result.decision.action is ActionType.REQUEST_OPERATOR_REVIEW


def test_agent_brain_rejects_action_outside_allow_list() -> None:
    """The agent cannot escape the caller-provided permitted action set."""

    observation = make_observation(allowed_actions=[ActionType.STOP])
    proposed = AgentDecisionOutput(
        case_id=observation.case_id,
        action=ActionType.REQUEST_OPERATOR_REVIEW,
        reason_code="review",
        rationale="Review is appropriate.",
        confidence=0.8,
        requires_human_review=True,
    )

    with pytest.raises(ValueError, match="outside allow-list"):
        AgentBrain(FakeReasoningProvider(proposed)).reason(observation)


def test_stop_decision_requires_stop_reason() -> None:
    """A stop output without a reason is invalid at the deterministic boundary."""

    observation = make_observation(allowed_actions=[ActionType.STOP])
    proposed = AgentDecisionOutput(
        case_id=observation.case_id,
        action=ActionType.STOP,
        reason_code="unsafe",
        rationale="The case cannot proceed safely.",
        confidence=0.99,
        requires_human_review=False,
    )

    with pytest.raises(ValueError, match="stop decisions require stop_reason"):
        validate_decision(proposed, observation)


def test_tool_registry_exposes_only_allow_listed_tools() -> None:
    """Unknown tool names are rejected and registered tools are discoverable."""

    registry = ToolRegistry()

    assert registry.names() == (
        "draft_recovery_intent",
        "escalate_recovery_case",
        "inspect_recovery_context",
    )
    with pytest.raises(ValueError, match="not registered"):
        registry.execute("call_arbitrary_url", {}, ToolContext())


def test_draft_intent_requires_authorization_and_stays_dry_run() -> None:
    """Tool execution is authorization-gated and never calls a provider."""

    registry = ToolRegistry()
    case_id = uuid4()
    payload = {
        "case_id": str(case_id),
        "action": "retry_payment",
        "rationale": "A future policy-approved retry could be considered.",
        "idempotency_key": "test-case-001-attempt-001",
    }

    rejected = registry.execute("draft_recovery_intent", payload, ToolContext(authorized=False))
    planned = registry.execute(
        "draft_recovery_intent",
        payload,
        ToolContext(authorized=True, dry_run=True, correlation_id="test-correlation"),
    )

    assert rejected.status == "rejected"
    assert planned.status == "planned"
    assert planned.dry_run is True
    assert planned.data["idempotency_key"] == "test-case-001-attempt-001"


def test_escalation_tool_does_not_send_notification() -> None:
    """Escalation produces a plan only; delivery belongs to a future tool adapter."""

    result = ToolRegistry().execute(
        "escalate_recovery_case",
        {"case_id": str(uuid4()), "reason": "uncertain provider outcome", "priority": 90},
        ToolContext(),
    )

    assert result.status == "planned"
    assert result.dry_run is True
    assert "notification" in result.message
