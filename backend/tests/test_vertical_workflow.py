"""End-to-end dry-run vertical workflow tests.
Author: Karthikeya
"""

from app.agents.brain import AgentBrain
from app.agents.contracts import AgentDecisionOutput
from app.core.database import Base
from app.core.enums import ActionType, RecoveryCaseState
from app.services.seed_service import build_synthetic_dataset
from app.workflows.vertical_recovery import CaseTransitionService, VerticalRecoveryWorkflow
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class FakeProvider:
    def decide(self, observation):
        return AgentDecisionOutput(
            case_id=observation.case_id,
            action=ActionType.SEND_REMINDER,
            reason_code="alternate_method_recommended",
            rationale="Customer context is available and a reminder is policy-permitted.",
            confidence=0.86,
            requires_human_review=False,
        )


def make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_transition_service_rejects_terminal_state_reversal():
    session = make_session()
    fixture = build_synthetic_dataset(42)
    session.add_all(fixture.customers + fixture.transactions + fixture.cases)
    session.flush()
    service = CaseTransitionService(session)
    case = fixture.cases[0]
    service.transition(case, RecoveryCaseState.CONTEXT_READY, reason_code="context_collected")
    service.transition(case, RecoveryCaseState.AWAITING_DECISION, reason_code="ready")
    service.transition(case, RecoveryCaseState.ACTION_PENDING, reason_code="approved")
    service.transition(case, RecoveryCaseState.VERIFICATION_PENDING, reason_code="pending")
    service.transition(case, RecoveryCaseState.RECOVERED, reason_code="provider_verified")
    try:
        service.transition(case, RecoveryCaseState.ACTION_PENDING, reason_code="unsafe_reversal")
    except ValueError as exc:
        assert "invalid recovery transition" in str(exc)
    else:
        raise AssertionError("terminal state reversal was accepted")


def test_vertical_workflow_connects_agent_policy_tool_and_audit():
    session = make_session()
    fixture = build_synthetic_dataset(42)
    session.add_all(fixture.customers + fixture.transactions + fixture.cases)
    session.flush()
    case = fixture.cases[0]
    workflow = VerticalRecoveryWorkflow(session, AgentBrain(FakeProvider(), provider_name="fake"))
    result = workflow.run(
        case, fixture.transactions[0], fixture.customers[0], risk_reason_codes=["payment_failed"]
    )
    assert result.policy.outcome.value == "allow"
    assert result.tool_status == "planned"
    assert result.final_state is RecoveryCaseState.VERIFICATION_PENDING
    assert result.audit_event_count >= 4
    assert case.state is RecoveryCaseState.VERIFICATION_PENDING
