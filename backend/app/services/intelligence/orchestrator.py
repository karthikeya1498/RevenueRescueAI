"""Intelligence Orchestrator for Phase 2.8 AI-Powered Recovery Intelligence.

Author: Karthikeya
Architectural layer: Application Service / Orchestrator.

Coordinates failure analysis, risk assessment, probability estimation, strategy selection,
and factual explanation generation. Persists recommendations as AgentDecision domain entities
(validation_status = NOT_VALIDATED, pending Phase 2.9 policy validation) and records immutable
audit events.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import (
    ActionType,
    ActorType,
    CustomerStatus,
    DecisionValidationStatus,
    RecoveryCaseState,
)
from app.core.errors import EntityNotFoundException
from app.models.domain import (
    AgentDecision,
    AuditEvent,
    CaseStateTransition,
    RecoveryCase,
)
from app.repositories.agent_decisions import AgentDecisionRepository
from app.repositories.audit_events import AuditEventRepository
from app.repositories.recovery_cases import RecoveryCaseRepository
from app.schemas.agent_decisions import DecisionPreviewRequestDTO
from app.schemas.recommendations import CaseRecommendationDTO, StrategyEstimateDTO
from app.services.intelligence.explanation_service import ExplanationService
from app.services.intelligence.failure_analyzer import FailureAnalyzer
from app.services.intelligence.model_adapter import RecoveryEstimatorAdapter
from app.services.intelligence.probability_estimator import LogisticRecoveryEstimator
from app.services.intelligence.risk_assessor import RiskAssessor
from app.services.intelligence.strategy_catalog import RecoveryStrategy, StrategyCatalog
from app.services.intelligence.strategy_selector import StrategySelector


class IntelligenceOrchestrator:
    """Coordinates deterministic, explainable AI recovery decision intelligence."""

    def __init__(
        self,
        session: Session,
        *,
        failure_analyzer: FailureAnalyzer | None = None,
        risk_assessor: RiskAssessor | None = None,
        probability_estimator: RecoveryEstimatorAdapter | None = None,
        strategy_selector: StrategySelector | None = None,
        explanation_service: ExplanationService | None = None,
    ) -> None:
        self.session = session
        self.failure_analyzer = failure_analyzer or FailureAnalyzer()
        self.risk_assessor = risk_assessor or RiskAssessor()
        self.probability_estimator = probability_estimator or LogisticRecoveryEstimator()
        self.strategy_selector = strategy_selector or StrategySelector(
            estimator=self.probability_estimator
        )
        self.explanation_service = explanation_service or ExplanationService()

        self.case_repo = RecoveryCaseRepository(session)
        self.decision_repo = AgentDecisionRepository(session)
        self.audit_repo = AuditEventRepository(session)

    def generate_recommendation(
        self,
        case_id: UUID,
        *,
        current_user_id: str | None = None,
    ) -> CaseRecommendationDTO:
        """Analyse an active or pending recovery case, generate and persist recommendation.

        Note: Recommendations are persisted with validation_status = NOT_VALIDATED.
        They do not execute payment retries, charge cards, or send communications.
        Actual execution requires Phase 2.9 Policy Engine validation.
        """
        case = self.case_repo.find_by_id(case_id)
        if case is None:
            raise EntityNotFoundException("RecoveryCase", str(case_id))

        # 1. Extract case and transaction context
        txn = case.trigger_transaction
        amount_minor = txn.amount_minor if txn else 0
        currency = txn.currency if txn else "USD"
        failure_code = txn.failure_code if txn else None
        failure_message = txn.failure_message_safe if txn else None

        prior_attempts = len(case.attempts) if case.attempts else 0
        is_subscription = bool(
            case.metadata_json.get("is_subscription")
            or (txn and txn.metadata_json.get("is_subscription"))
        )
        unusual_velocity = bool(case.metadata_json.get("unusual_velocity", False))
        customer_restricted = bool(
            case.customer and case.customer.status != CustomerStatus.ACTIVE
        )
        customer_success_rate = (
            float(case.customer.metadata_json.get("success_rate", 0.5))
            if case.customer
            else 0.5
        )
        alternate_method_available = (
            bool(case.customer.metadata_json.get("has_alternate_method", True))
            if case.customer
            else True
        )
        is_terminal = case.state in {
            RecoveryCaseState.RECOVERED,
            RecoveryCaseState.STOPPED,
            RecoveryCaseState.CLOSED,
        }

        # 2. Pipeline Execution
        # Step A: Failure Analysis
        failure_result = self.failure_analyzer.analyze(
            code=failure_code, message=failure_message
        )

        # Step B: Risk Assessment
        risk_result = self.risk_assessor.assess(
            failure_category=failure_result.category,
            amount_minor=amount_minor,
            prior_attempts=prior_attempts,
            is_subscription=is_subscription,
            unusual_velocity=unusual_velocity,
            customer_restricted=customer_restricted,
        )

        # Step C: Strategy Selection (Expected-Value Ranking)
        selection_result = self.strategy_selector.select_strategy(
            amount_minor=amount_minor,
            failure_result=failure_result,
            risk_result=risk_result,
            prior_attempts=prior_attempts,
            is_terminal_case=is_terminal,
            is_subscription=is_subscription,
            customer_success_rate=customer_success_rate,
            alternate_method_available=alternate_method_available,
        )

        winner_estimate = next(
            (
                est
                for est in selection_result.estimates
                if est.strategy == selection_result.selected_strategy
            ),
            selection_result.estimates[0],
        )

        # Step D: Factual Explanation Generation
        explanation = self.explanation_service.generate_explanation(
            strategy=selection_result.selected_strategy,
            failure_result=failure_result,
            risk_result=risk_result,
            selected_estimate=winner_estimate,
            case_context={
                "case_key": case.case_key,
                "amount_minor": amount_minor,
                "currency": currency,
                "prior_attempts": prior_attempts,
                "is_terminal": is_terminal,
            },
        )

        # 3. Determine Sequential Decision Version
        latest_decision = self.decision_repo.find_latest_by_case(case.id)
        decision_version = (latest_decision.decision_version + 1) if latest_decision else 1

        # 4. Formulate DTO and Candidate Estimates
        candidate_dtos = [
            StrategyEstimateDTO(
                strategy=est.strategy.value,
                action_type=est.action_type,
                probability=est.probability,
                recovery_value_minor=est.gross_recovery_minor,
                cost_minor=est.cost_minor,
                expected_value_minor=est.expected_value_minor,
                permitted=est.permitted,
                reasons=est.rejection_reasons,
            )
            for est in selection_result.estimates
        ]

        now = datetime.now(timezone.utc)
        decision_id = uuid4()

        raw_payload = {
            "case_id": str(case.id),
            "decision_version": decision_version,
            "recommended_strategy": selection_result.selected_strategy.value,
            "action_type": selection_result.selected_action.value,
            "failure_category": failure_result.category,
            "risk_band": risk_result.band,
            "risk_score": risk_result.score,
            "recovery_probability": str(winner_estimate.probability),
            "confidence": str(selection_result.confidence),
            "expected_value_minor": winner_estimate.expected_value_minor,
            "model_version": self.probability_estimator.get_model_version(),
            "generated_at": now.isoformat(),
        }
        raw_hash = hashlib.sha256(json.dumps(raw_payload, sort_keys=True).encode()).hexdigest()

        # 5. Persist Domain Entity AgentDecision
        decision = AgentDecision(
            id=decision_id,
            case_id=case.id,
            attempt_id=None,
            decision_version=decision_version,
            action_type=selection_result.selected_action,
            reason_code=f"{failure_result.category}:{selection_result.selected_strategy.value.lower()}",
            rationale_safe=explanation.summary[:2000],
            confidence=selection_result.confidence,
            raw_response_hash=raw_hash,
            validation_status=DecisionValidationStatus.NOT_VALIDATED,
        )
        self.decision_repo.save(decision)

        # 6. Record Compliance Audit Event
        audit_payload = {
            "recommendation_id": str(decision_id),
            "decision_version": decision_version,
            "recommended_strategy": selection_result.selected_strategy.value,
            "action_type": selection_result.selected_action.value,
            "failure_category": failure_result.category,
            "risk_band": risk_result.band,
            "risk_score": risk_result.score,
            "recovery_probability": str(winner_estimate.probability),
            "confidence": str(selection_result.confidence),
            "expected_value_minor": winner_estimate.expected_value_minor,
            "explanation": explanation.summary,
            "supporting_evidence": explanation.supporting_evidence,
            "limitations": explanation.limitations,
            "model_version": self.probability_estimator.get_model_version(),
            "validation_status": DecisionValidationStatus.NOT_VALIDATED.value,
            "candidate_strategies": [dto.model_dump(mode="json") for dto in candidate_dtos],
        }

        self.audit_repo.record(
            case_id=case.id,
            event_type="RECOMMENDATION_GENERATED",
            actor_type=ActorType.SYSTEM,
            actor_id=current_user_id or "system_intelligence",
            correlation_id=str(decision_id),
            payload_safe=audit_payload,
            from_state=case.state,
            to_state=case.state,
        )

        # 7. Advance Case State from DETECTED -> AWAITING_DECISION if applicable
        if case.state == RecoveryCaseState.DETECTED:
            from_state = case.state
            to_state = RecoveryCaseState.AWAITING_DECISION
            case.state = to_state
            case.last_state_changed_at = now
            case.version += 1

            current_trans_max = self.session.scalar(
                select(func.max(CaseStateTransition.sequence_number)).where(
                    CaseStateTransition.case_id == case.id
                )
            )
            next_trans_seq = (current_trans_max or 0) + 1

            transition = CaseStateTransition(
                id=uuid4(),
                case_id=case.id,
                from_state=from_state,
                to_state=to_state,
                reason_code="AI_RECOMMENDATION_FORMULATED",
                actor_type=ActorType.SYSTEM,
                correlation_id=str(decision_id),
                occurred_at=now,
                sequence_number=next_trans_seq,
                metadata_json={"decision_id": str(decision_id), "version": decision_version},
            )
            self.session.add(transition)

            self.audit_repo.record(
                case_id=case.id,
                event_type="STATE_TRANSITION",
                actor_type=ActorType.SYSTEM,
                actor_id="system_intelligence",
                correlation_id=str(decision_id),
                payload_safe={
                    "reason_code": "AI_RECOMMENDATION_FORMULATED",
                    "from_state": from_state.value,
                    "to_state": to_state.value,
                    "sequence_number": next_trans_seq,
                },
                from_state=from_state,
                to_state=to_state,
            )

        # 8. Store latest snapshot in case metadata for fast retrieval
        case_meta = dict(case.metadata_json)
        case_meta["latest_recommendation"] = audit_payload
        case.metadata_json = case_meta

        self.session.commit()

        return CaseRecommendationDTO(
            id=decision_id,
            case_id=case.id,
            decision_version=decision_version,
            recommended_strategy=selection_result.selected_strategy.value,
            action_type=selection_result.selected_action,
            failure_category=failure_result.category,
            risk_band=risk_result.band,
            risk_score=risk_result.score,
            recovery_probability=winner_estimate.probability,
            confidence=selection_result.confidence,
            expected_value_minor=winner_estimate.expected_value_minor,
            explanation=explanation.summary,
            supporting_evidence=explanation.supporting_evidence,
            limitations=explanation.limitations,
            analysis_method="hybrid_expected_value",
            model_version=self.probability_estimator.get_model_version(),
            validation_status=DecisionValidationStatus.NOT_VALIDATED,
            generated_at=now,
            candidate_strategies=candidate_dtos,
        )

    def get_latest_recommendation(self, case_id: UUID) -> CaseRecommendationDTO | None:
        """Retrieve the most recently generated recommendation for a recovery case."""
        case = self.case_repo.find_by_id(case_id)
        if case is None:
            raise EntityNotFoundException("RecoveryCase", str(case_id))

        latest_decision = self.decision_repo.find_latest_by_case(case_id)
        if latest_decision is None:
            return None

        return self._reconstitute_recommendation(case, latest_decision)

    def get_recommendation_history(self, case_id: UUID) -> list[CaseRecommendationDTO]:
        """Retrieve all previous recommendations formulated for a recovery case."""
        case = self.case_repo.find_by_id(case_id)
        if case is None:
            raise EntityNotFoundException("RecoveryCase", str(case_id))

        decisions = self.decision_repo.find_by_case(case_id)
        return [self._reconstitute_recommendation(case, dec) for dec in decisions]

    def preview_recommendation(
        self,
        preview_req: DecisionPreviewRequestDTO,
    ) -> CaseRecommendationDTO:
        """Perform a dry-run decision simulation without database writes or case mutations."""
        failure_result = self.failure_analyzer.analyze(
            code=preview_req.failure_code,
            message=preview_req.failure_message,
        )

        risk_result = self.risk_assessor.assess(
            failure_category=failure_result.category,
            amount_minor=preview_req.amount_minor,
            prior_attempts=preview_req.prior_attempts,
            is_subscription=False,
            unusual_velocity=preview_req.unusual_velocity,
            customer_restricted=preview_req.customer_restricted,
        )

        selection_result = self.strategy_selector.select_strategy(
            amount_minor=preview_req.amount_minor,
            failure_result=failure_result,
            risk_result=risk_result,
            prior_attempts=preview_req.prior_attempts,
            is_terminal_case=False,
            is_subscription=False,
            customer_success_rate=preview_req.customer_success_rate,
            alternate_method_available=preview_req.alternate_method_available,
        )

        winner_estimate = next(
            (
                est
                for est in selection_result.estimates
                if est.strategy == selection_result.selected_strategy
            ),
            selection_result.estimates[0],
        )

        explanation = self.explanation_service.generate_explanation(
            strategy=selection_result.selected_strategy,
            failure_result=failure_result,
            risk_result=risk_result,
            selected_estimate=winner_estimate,
            case_context={
                "case_key": "SIMULATION_PREVIEW",
                "amount_minor": preview_req.amount_minor,
                "currency": preview_req.currency,
                "prior_attempts": preview_req.prior_attempts,
                "is_terminal": False,
            },
        )

        candidate_dtos = [
            StrategyEstimateDTO(
                strategy=est.strategy.value,
                action_type=est.action_type,
                probability=est.probability,
                recovery_value_minor=est.gross_recovery_minor,
                cost_minor=est.cost_minor,
                expected_value_minor=est.expected_value_minor,
                permitted=est.permitted,
                reasons=est.rejection_reasons,
            )
            for est in selection_result.estimates
        ]

        now = datetime.now(timezone.utc)
        return CaseRecommendationDTO(
            id=uuid4(),
            case_id=uuid4(),
            decision_version=1,
            recommended_strategy=selection_result.selected_strategy.value,
            action_type=selection_result.selected_action,
            failure_category=failure_result.category,
            risk_band=risk_result.band,
            risk_score=risk_result.score,
            recovery_probability=winner_estimate.probability,
            confidence=selection_result.confidence,
            expected_value_minor=winner_estimate.expected_value_minor,
            explanation=explanation.summary,
            supporting_evidence=explanation.supporting_evidence,
            limitations=explanation.limitations,
            analysis_method="hybrid_expected_value_simulation",
            model_version=self.probability_estimator.get_model_version(),
            validation_status=DecisionValidationStatus.NOT_VALIDATED,
            generated_at=now,
            candidate_strategies=candidate_dtos,
        )

    def _reconstitute_recommendation(
        self,
        case: RecoveryCase,
        decision: AgentDecision,
    ) -> CaseRecommendationDTO:
        """Reconstitute a CaseRecommendationDTO from persisted AgentDecision and AuditEvent."""
        # Find corresponding audit event by correlation_id
        audit_records = self.audit_repo.find_by_correlation_id(str(decision.id))
        rec_audit = next(
            (ev for ev in audit_records if ev.event_type == "RECOMMENDATION_GENERATED"),
            None,
        )

        if rec_audit and isinstance(rec_audit.payload_safe, dict):
            payload = rec_audit.payload_safe
            candidate_dtos = [
                StrategyEstimateDTO(**item)
                for item in payload.get("candidate_strategies", [])
            ]
            return CaseRecommendationDTO(
                id=decision.id,
                case_id=case.id,
                decision_version=decision.decision_version,
                recommended_strategy=payload.get(
                    "recommended_strategy",
                    StrategyCatalog.map_to_strategy(decision.action_type).value,
                ),
                action_type=decision.action_type,
                failure_category=payload.get(
                    "failure_category", decision.reason_code.split(":")[0]
                ),
                risk_band=payload.get("risk_band", "medium"),
                risk_score=payload.get("risk_score", 50),
                recovery_probability=(
                    Decimal(str(payload["recovery_probability"]))
                    if payload.get("recovery_probability") is not None
                    else None
                ),
                confidence=decision.confidence,
                expected_value_minor=payload.get("expected_value_minor", 0),
                explanation=payload.get("explanation", decision.rationale_safe or ""),
                supporting_evidence=payload.get("supporting_evidence", []),
                limitations=payload.get("limitations", []),
                analysis_method="hybrid_expected_value",
                model_version=payload.get("model_version", "deterministic-logistic-v1"),
                validation_status=decision.validation_status,
                generated_at=rec_audit.event_time,
                candidate_strategies=candidate_dtos,
            )

        # Fallback reconstruction if audit record missing
        strategy = StrategyCatalog.map_to_strategy(decision.action_type)
        return CaseRecommendationDTO(
            id=decision.id,
            case_id=case.id,
            decision_version=decision.decision_version,
            recommended_strategy=strategy.value,
            action_type=decision.action_type,
            failure_category=decision.reason_code.split(":")[0],
            risk_band="medium",
            risk_score=50,
            recovery_probability=Decimal("0.5000"),
            confidence=decision.confidence or Decimal("0.8000"),
            expected_value_minor=0,
            explanation=decision.rationale_safe or "Persisted recovery recommendation.",
            supporting_evidence=[f"Reason code: {decision.reason_code}"],
            limitations=["Historical snapshot reconstructed without full audit payload."],
            analysis_method="persisted_record_fallback",
            model_version="deterministic-logistic-v1",
            validation_status=decision.validation_status,
            generated_at=datetime.now(timezone.utc),
            candidate_strategies=[],
        )
