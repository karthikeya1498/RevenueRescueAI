"""Central Policy Engine Service for RevenueRescueAI Phase 2.9 Step 3.

Architectural layer: policy orchestration & guardrail boundary.

Coordinates the 5 independent policy rule evaluators, aggregates their results
using deterministic precedence, synchronizes AgentDecision validation status,
safely advances the RecoveryCase FSM, and records immutable audit records.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import (
    ActionType,
    ActorType,
    DecisionValidationStatus,
    PolicyDecisionStatus,
    RecoveryCaseState,
    RuleCheckStatus,
)
from app.models.domain import (
    AgentDecision,
    CaseStateTransition,
    CustomerConsent,
    PolicyDecision,
    RecoveryCase,
)
from app.policy.config import PolicyConfig
from app.policy.evaluators import (
    ConsentValidator,
    EligibilityEvaluator,
    EscalationEvaluator,
    RetryLimitEvaluator,
    StrategyValidator,
)
from app.policy.models import (
    CustomerConsentRecord,
    PolicyEvaluationResult,
    RuleCheckResult,
    map_policy_to_validation_status,
)
from app.repositories import (
    AgentDecisionRepository,
    AuditEventRepository,
    CustomerConsentRepository,
    CustomerRepository,
    PolicyDecisionRepository,
    RecoveryAttemptRepository,
    RecoveryCaseRepository,
    TransactionRepository,
)


@dataclass
class PolicyEvaluationRequest:
    """Request DTO specifying parameters for policy evaluation."""

    case_id: UUID
    recommendation_id: UUID
    proposed_action: ActionType | None = None
    actor_type: ActorType = ActorType.SYSTEM
    actor_id: str | None = None
    idempotency_key: str | None = None
    communication_channel: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PolicyEngineService:
    """Central orchestration service coordinating policy evaluators and FSM state."""

    def __init__(
        self,
        session: Session,
        config: PolicyConfig | None = None,
    ) -> None:
        self.session = session
        self.config = config or PolicyConfig()

        # Repositories
        self.case_repo = RecoveryCaseRepository(session)
        self.decision_repo = AgentDecisionRepository(session)
        self.tx_repo = TransactionRepository(session)
        self.attempt_repo = RecoveryAttemptRepository(session)
        self.consent_repo = CustomerConsentRepository(session)
        self.policy_decision_repo = PolicyDecisionRepository(session)
        self.audit_repo = AuditEventRepository(session)
        self.customer_repo = CustomerRepository(session)

        # Evaluators
        self.eligibility_evaluator = EligibilityEvaluator()
        self.consent_validator = ConsentValidator()
        self.retry_limit_evaluator = RetryLimitEvaluator()
        self.strategy_validator = StrategyValidator()
        self.escalation_evaluator = EscalationEvaluator()

    def evaluate(self, request: PolicyEvaluationRequest) -> PolicyEvaluationResult:
        """Execute complete policy evaluation workflow with transactional guardrails.

        Financial Safety Invariant:
        This method strictly performs evaluation and FSM authorization. It never
        executes payments, charges cards, calls gateways, or sends customer messages.
        """
        # 1. Idempotency Check: return existing result if key was previously evaluated
        if request.idempotency_key:
            existing = self.policy_decision_repo.find_by_idempotency_key(
                request.case_id, request.idempotency_key
            )
            if existing is not None:
                return self._to_evaluation_result(existing)

        # 2. Authoritative Data Loading
        case = self.case_repo.find_by_id(request.case_id)
        recommendation = self.decision_repo.find_by_id(request.recommendation_id)

        # 3. Handle Missing Case or Recommendation (Fail-Closed)
        if case is None or recommendation is None:
            missing_result = RuleCheckResult(
                rule_name="data_availability_check",
                status=RuleCheckStatus.MISSING_INFO,
                reason_code="CASE_NOT_FOUND" if case is None else "RECOMMENDATION_MISSING",
                message="Authoritative case or AI recommendation could not be loaded.",
            )
            return self._build_synthetic_result(
                request=request,
                status=PolicyDecisionStatus.INSUFFICIENT_INFORMATION,
                rule_results=[missing_result],
                reasons=[missing_result.reason_code],
            )

        # Determine proposed action (explicit or inferred from recommendation)
        proposed_action = request.proposed_action or recommendation.action_type

        # Load related entities
        trigger_tx = self.tx_repo.find_by_id(case.trigger_transaction_id)
        attempts = self.attempt_repo.find_by_case(case.id)
        customer = self.customer_repo.find_by_id(case.customer_id)
        raw_consents = self.consent_repo.find_by_customer(case.customer_id)
        consent_records = [CustomerConsentRecord.from_domain(c) for c in raw_consents]

        # Extract merchant id if present
        merchant_id = None
        if customer and customer.metadata_json:
            merchant_id = customer.metadata_json.get("merchant_id")

        now = datetime.now(timezone.utc)
        rule_results: list[RuleCheckResult] = []

        # 4. Invoke Evaluator 1: Eligibility
        eligibility_res = self.eligibility_evaluator.evaluate(
            case=case,
            recommendation=recommendation,
            customer_id=case.customer_id,
            expected_transaction_id=case.trigger_transaction_id,
        )
        rule_results.append(eligibility_res)

        # 5. Invoke Evaluator 2: Consent
        consent_res = self.consent_validator.evaluate(
            action_type=proposed_action,
            customer_id=case.customer_id,
            consents=consent_records,
            merchant_id=merchant_id,
            communication_channel=request.communication_channel,
            evaluation_time=now,
        )
        rule_results.append(consent_res)

        # 6. Invoke Evaluator 3: Retry Limit
        retry_res = self.retry_limit_evaluator.evaluate(
            action_type=proposed_action,
            attempts=attempts,
            config=self.config,
            current_time=now,
            proposed_idempotency_key=request.idempotency_key,
            failure_category=trigger_tx.failure_code if trigger_tx else None,
        )
        rule_results.append(retry_res)

        # 7. Invoke Evaluator 4: Strategy Feasibility
        strategy_res = self.strategy_validator.evaluate(
            strategy=proposed_action,
            failure_category=trigger_tx.failure_code if trigger_tx else None,
            case_state=case.state,
            has_contact_info=bool(customer and customer.email),
            is_retryable=True,
        )
        rule_results.append(strategy_res)

        # 8. Invoke Evaluator 5: Escalation Requirements
        consumed_attempts = [
            a for a in attempts
            if a.action_type is ActionType.RETRY_PAYMENT
            and a.status is not ActionType.NONE
        ]
        prior_retries_spent = not self.config.can_retry(len(consumed_attempts))
        has_uncertain = any(a.status.value == "uncertain" for a in attempts)

        escalation_res = self.escalation_evaluator.evaluate(
            amount_minor=trigger_tx.amount_minor if trigger_tx else 0,
            currency=trigger_tx.currency if trigger_tx else "INR",
            config=self.config,
            ai_confidence=recommendation.confidence,
            failure_category=trigger_tx.failure_code if trigger_tx else None,
            prior_retries_exhausted=prior_retries_spent,
            has_uncertain_outcome=has_uncertain,
        )
        rule_results.append(escalation_res)

        # 9. Aggregate Decisions (Deterministic 4-Tier Precedence)
        final_status, reasons = self._aggregate_decision(rule_results)

        # 10. Persist Policy Decision
        policy_decision = PolicyDecision(
            id=uuid4(),
            case_id=case.id,
            recommendation_id=recommendation.id,
            proposed_action=proposed_action,
            decision_status=final_status,
            policy_version=self.config.policy_version,
            rule_results_json=[
                {
                    "rule_name": r.rule_name,
                    "status": r.status.value,
                    "reason_code": r.reason_code,
                    "message": r.message,
                    "details": r.details,
                }
                for r in rule_results
            ],
            reasons_json=reasons,
            actor_type=request.actor_type,
            actor_id=request.actor_id,
            idempotency_key=request.idempotency_key,
            case_version=case.version,
            evaluated_at=now,
            metadata_json=request.metadata,
        )
        self.policy_decision_repo.save(policy_decision)

        # 11. Synchronize AgentDecision validation_status
        new_validation_status = map_policy_to_validation_status(final_status)
        recommendation.validation_status = new_validation_status
        self.decision_repo.save(recommendation)

        # 12. Synchronize RecoveryCase FSM State
        from_state = case.state
        to_state = self._determine_fsm_transition(final_status, case.state, reasons)
        if to_state is not None and to_state != case.state:
            case.state = to_state
            case.last_state_changed_at = now
            case.version += 1

            # Record Case State Transition
            current_max_seq = self.session.scalar(
                select(func.max(CaseStateTransition.sequence_number)).where(
                    CaseStateTransition.case_id == case.id
                )
            )
            next_seq = (current_max_seq or 0) + 1

            trans_record = CaseStateTransition(
                id=uuid4(),
                case_id=case.id,
                from_state=from_state,
                to_state=to_state,
                reason_code=reasons[0] if reasons else "POLICY_EVALUATION",
                actor_type=request.actor_type,
                correlation_id=request.idempotency_key or str(uuid4()),
                occurred_at=now,
                sequence_number=next_seq,
                metadata_json={
                    "policy_decision_id": str(policy_decision.id),
                    "policy_status": final_status.value,
                },
            )
            self.session.add(trans_record)

        # 13. Record Immutable Audit Event
        self.audit_repo.record(
            case_id=case.id,
            event_type="POLICY_EVALUATION_COMPLETED",
            actor_type=request.actor_type,
            correlation_id=request.idempotency_key or str(policy_decision.id),
            payload_safe={
                "policy_decision_id": str(policy_decision.id),
                "recommendation_id": str(recommendation.id),
                "decision_status": final_status.value,
                "validation_status": new_validation_status.value,
                "policy_version": self.config.policy_version,
                "reasons": reasons,
                "rule_count": len(rule_results),
            },
            from_state=from_state,
            to_state=case.state,
            actor_id=request.actor_id,
        )

        # 14. Commit Atomic Transaction
        self.session.commit()

        # 15. Return Structured Evaluation Result
        return PolicyEvaluationResult(
            decision_status=final_status,
            case_id=case.id,
            proposed_action=proposed_action,
            policy_version=self.config.policy_version,
            rule_results=rule_results,
            reasons=reasons,
            recommendation_id=recommendation.id,
            evaluated_at=now,
            metadata_json={
                "policy_decision_id": str(policy_decision.id),
                "case_state": case.state.value,
                "validation_status": new_validation_status.value,
            },
        )

    def _aggregate_decision(
        self, rule_results: list[RuleCheckResult]
    ) -> tuple[PolicyDecisionStatus, list[str]]:
        """Apply authoritative 4-tier decision precedence across rule results.

        Precedence:
        1. REJECTED: Any rule explicitly failed.
        2. INSUFFICIENT_INFORMATION: No failure, but missing mandatory information.
        3. REQUIRES_REVIEW: No failure or missing info, but human review required.
        4. APPROVED: All rules passed cleanly.
        """
        failed_rules = [r for r in rule_results if r.is_failed]
        if failed_rules:
            reasons = [r.reason_code for r in failed_rules]
            return PolicyDecisionStatus.REJECTED, reasons

        missing_rules = [r for r in rule_results if r.is_missing_info]
        if missing_rules:
            reasons = [r.reason_code for r in missing_rules]
            return PolicyDecisionStatus.INSUFFICIENT_INFORMATION, reasons

        review_rules = [r for r in rule_results if r.needs_review]
        if review_rules:
            reasons = [r.reason_code for r in review_rules]
            return PolicyDecisionStatus.REQUIRES_REVIEW, reasons

        # All rules passed
        return PolicyDecisionStatus.APPROVED, ["ALL_POLICY_GUARDRAILS_PASSED"]

    def _determine_fsm_transition(
        self,
        status: PolicyDecisionStatus,
        current_state: RecoveryCaseState,
        reasons: list[str],
    ) -> RecoveryCaseState | None:
        """Determine safe FSM transition without compromising case invariants."""
        # 1. APPROVED -> ACTION_PENDING
        if status is PolicyDecisionStatus.APPROVED:
            if current_state in {
                RecoveryCaseState.AWAITING_DECISION,
                RecoveryCaseState.RETRY_ELIGIBLE,
                RecoveryCaseState.DETECTED,
            }:
                return RecoveryCaseState.ACTION_PENDING
            return None

        # 2. REQUIRES_REVIEW -> ESCALATED
        if status is PolicyDecisionStatus.REQUIRES_REVIEW:
            if current_state not in {
                RecoveryCaseState.RECOVERED,
                RecoveryCaseState.CLOSED,
                RecoveryCaseState.STOPPED,
                RecoveryCaseState.ESCALATED,
            }:
                return RecoveryCaseState.ESCALATED
            return None

        # 3. REJECTED -> STOPPED (only on terminal rejection reasons)
        if status is PolicyDecisionStatus.REJECTED:
            terminal_reasons = {
                "RETRY_LIMIT_EXCEEDED",
                "CASE_ALREADY_RECOVERED",
                "CASE_CANCELLED",
                "CASE_CLOSED",
                "RETRY_NOT_SUPPORTED",
            }
            if any(r in terminal_reasons for r in reasons):
                if current_state not in {
                    RecoveryCaseState.RECOVERED,
                    RecoveryCaseState.CLOSED,
                    RecoveryCaseState.STOPPED,
                }:
                    return RecoveryCaseState.STOPPED
            return None

        # 4. INSUFFICIENT_INFORMATION -> No transition (remains in current non-actionable state)
        return None

    def _to_evaluation_result(self, record: PolicyDecision) -> PolicyEvaluationResult:
        """Convert a persisted PolicyDecision ORM entity to a PolicyEvaluationResult."""
        rule_results = [
            RuleCheckResult(
                rule_name=r["rule_name"],
                status=RuleCheckStatus(r["status"]),
                reason_code=r["reason_code"],
                message=r["message"],
                details=r.get("details", {}),
            )
            for r in record.rule_results_json
        ]
        return PolicyEvaluationResult(
            decision_status=record.decision_status,
            case_id=record.case_id,
            proposed_action=record.proposed_action,
            policy_version=record.policy_version,
            rule_results=rule_results,
            reasons=record.reasons_json,
            recommendation_id=record.recommendation_id,
            evaluated_at=record.evaluated_at,
            metadata_json={
                "policy_decision_id": str(record.id),
                "cached_idempotent_result": True,
            },
        )

    def _build_synthetic_result(
        self,
        request: PolicyEvaluationRequest,
        status: PolicyDecisionStatus,
        rule_results: list[RuleCheckResult],
        reasons: list[str],
    ) -> PolicyEvaluationResult:
        """Build fail-closed result when case or recommendation cannot be loaded."""
        return PolicyEvaluationResult(
            decision_status=status,
            case_id=request.case_id,
            proposed_action=request.proposed_action or ActionType.NONE,
            policy_version=self.config.policy_version,
            rule_results=rule_results,
            reasons=reasons,
            recommendation_id=request.recommendation_id,
            evaluated_at=datetime.now(timezone.utc),
            metadata_json={"error": "authoritative_entity_unavailable"},
        )
