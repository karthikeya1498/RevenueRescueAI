"""Connected vertical slice: detected case through policy, tool, and audit.

Author: Karthikeya
This workflow is provider-neutral and dry-run by default. It demonstrates the
actual control flow without pretending a draft intent is verified revenue.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.agents.brain import AgentBrain
from app.agents.contracts import AgentObservation, ValidatedAgentDecision
from app.core.database import utc_now
from app.core.enums import ActorType, RecoveryCaseState
from app.models.domain import AuditEvent, CaseStateTransition, Customer, RecoveryCase, Transaction
from app.policy.safety import PolicyContext, PolicyDecision, SafetyPolicy
from app.tools.contracts import ToolContext
from app.tools.registry import ToolRegistry

_ALLOWED_TRANSITIONS: dict[RecoveryCaseState, frozenset[RecoveryCaseState]] = {
    RecoveryCaseState.DETECTED: frozenset(
        {RecoveryCaseState.CONTEXT_READY, RecoveryCaseState.ESCALATED, RecoveryCaseState.STOPPED}
    ),
    RecoveryCaseState.CONTEXT_READY: frozenset(
        {RecoveryCaseState.AWAITING_DECISION, RecoveryCaseState.ESCALATED}
    ),
    RecoveryCaseState.AWAITING_DECISION: frozenset(
        {RecoveryCaseState.ACTION_PENDING, RecoveryCaseState.ESCALATED, RecoveryCaseState.STOPPED}
    ),
    RecoveryCaseState.ACTION_PENDING: frozenset(
        {
            RecoveryCaseState.VERIFICATION_PENDING,
            RecoveryCaseState.ESCALATED,
            RecoveryCaseState.STOPPED,
        }
    ),
    RecoveryCaseState.VERIFICATION_PENDING: frozenset(
        {RecoveryCaseState.RECOVERED, RecoveryCaseState.RETRY_ELIGIBLE, RecoveryCaseState.ESCALATED}
    ),
    RecoveryCaseState.RETRY_ELIGIBLE: frozenset(
        {RecoveryCaseState.ACTION_PENDING, RecoveryCaseState.ESCALATED, RecoveryCaseState.STOPPED}
    ),
    RecoveryCaseState.RECOVERED: frozenset({RecoveryCaseState.CLOSED}),
    RecoveryCaseState.ESCALATED: frozenset({RecoveryCaseState.CLOSED}),
    RecoveryCaseState.STOPPED: frozenset({RecoveryCaseState.CLOSED}),
    RecoveryCaseState.CLOSED: frozenset(),
}


@dataclass(frozen=True)
class TransitionResult:
    case_id: UUID
    from_state: RecoveryCaseState
    to_state: RecoveryCaseState
    sequence_number: int
    reason_code: str
    correlation_id: str


class CaseTransitionService:
    """The only service allowed to mutate recovery-case lifecycle state."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def transition(
        self,
        case: RecoveryCase,
        to_state: RecoveryCaseState,
        *,
        reason_code: str,
        actor_type: ActorType = ActorType.SYSTEM,
        actor_id: str | None = None,
        correlation_id: str | None = None,
        at: datetime | None = None,
    ) -> TransitionResult:
        now = at or utc_now()
        correlation = correlation_id or str(uuid4())
        from_state = case.state
        if to_state not in _ALLOWED_TRANSITIONS.get(from_state, frozenset()):
            raise ValueError(f"invalid recovery transition: {from_state.value} -> {to_state.value}")
        previous = (
            self.session.query(CaseStateTransition)
            .filter(CaseStateTransition.case_id == case.id)
            .count()
        )
        sequence = previous + 1
        case.state = to_state
        case.version += 1
        case.last_state_changed_at = now
        if to_state is RecoveryCaseState.CLOSED:
            case.closed_at = now
        self.session.add(
            CaseStateTransition(
                case_id=case.id,
                from_state=from_state,
                to_state=to_state,
                reason_code=reason_code,
                actor_type=actor_type,
                correlation_id=correlation,
                occurred_at=now,
                metadata_json={"version": case.version},
            )
        )
        self.session.add(
            AuditEvent(
                case_id=case.id,
                event_type=f"case.{to_state.value}",
                from_state=from_state,
                to_state=to_state,
                actor_type=actor_type,
                actor_id=actor_id,
                correlation_id=correlation,
                event_time=now,
                payload_safe={"reason_code": reason_code, "version": case.version},
                sequence_number=sequence,
            )
        )
        self.session.flush()
        return TransitionResult(case.id, from_state, to_state, sequence, reason_code, correlation)


@dataclass(frozen=True)
class VerticalWorkflowResult:
    case_id: UUID
    decision: ValidatedAgentDecision
    policy: PolicyDecision
    tool_status: str
    final_state: RecoveryCaseState
    audit_event_count: int


class VerticalRecoveryWorkflow:
    """Connect detection output, bounded reasoning, policy, tool, and audit."""

    def __init__(
        self,
        session: Session,
        brain: AgentBrain,
        *,
        policy: SafetyPolicy | None = None,
        tools: ToolRegistry | None = None,
    ) -> None:
        self.session = session
        self.brain = brain
        self.policy = policy or SafetyPolicy()
        self.tools = tools or ToolRegistry()
        self.transitions = CaseTransitionService(session)

    def run(
        self,
        case: RecoveryCase,
        transaction: Transaction,
        customer: Customer | None,
        *,
        risk_reason_codes: list[str],
        correlation_id: str = "vertical-slice",
    ) -> VerticalWorkflowResult:
        self.transitions.transition(
            case,
            RecoveryCaseState.CONTEXT_READY,
            reason_code="context_collected",
            correlation_id=correlation_id,
        )
        self.transitions.transition(
            case,
            RecoveryCaseState.AWAITING_DECISION,
            reason_code="awaiting_bounded_agent",
            correlation_id=correlation_id,
        )
        observation = AgentObservation(
            case_id=case.id,
            transaction_id=transaction.id,
            transaction_status=transaction.status.value,
            amount_minor=transaction.amount_minor,
            currency=transaction.currency,
            customer_context_available=customer is not None,
            risk_reason_codes=risk_reason_codes,
            current_state=case.state,
            prior_attempt_count=len(case.attempts),
            allowed_actions=list(self.policy.config.allowed_actions),
        )
        decision = self.brain.reason(observation).decision
        policy = self.policy.evaluate(
            PolicyContext(
                case_state=case.state,
                transaction_status=transaction.status,
                action=decision.action,
                retry_attempt_count=len(case.attempts),
                idempotency_key=f"{case.id}:workflow:{len(case.attempts) + 1}",
            )
        )
        if policy.should_escalate or policy.should_stop or policy.outcome.value == "reject":
            target = (
                RecoveryCaseState.ESCALATED if policy.should_escalate else RecoveryCaseState.STOPPED
            )
            self.transitions.transition(
                case, target, reason_code=policy.reason.value, correlation_id=correlation_id
            )
            return VerticalWorkflowResult(
                case.id, decision, policy, "not_executed", case.state, len(case.audit_events)
            )
        self.transitions.transition(
            case,
            RecoveryCaseState.ACTION_PENDING,
            reason_code="policy_allowed",
            correlation_id=correlation_id,
        )
        tool_name = (
            "escalate_recovery_case" if decision.requires_human_review else "draft_recovery_intent"
        )
        if tool_name == "escalate_recovery_case":
            payload = {"case_id": case.id, "reason": decision.rationale, "priority": case.priority}
        else:
            payload = {
                "case_id": case.id,
                "action": decision.action,
                "rationale": decision.rationale,
                "idempotency_key": f"{case.id}:workflow:{len(case.attempts) + 1}",
            }
        output = self.tools.execute(
            tool_name,
            payload,
            ToolContext(authorized=True, dry_run=True, correlation_id=correlation_id),
        )
        self.transitions.transition(
            case,
            RecoveryCaseState.VERIFICATION_PENDING,
            reason_code="action_requires_provider_verification",
            correlation_id=correlation_id,
        )
        return VerticalWorkflowResult(
            case.id, decision, policy, output.status, case.state, len(case.audit_events)
        )
