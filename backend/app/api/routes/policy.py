"""HTTP REST API router for Recovery Policy Engine (Phase 2.9 Step 4).

Author: Karthikeya
Architectural layer: API controller / boundary.

Provides authenticated REST endpoints for:
- Evaluating recovery cases and AI recommendations against policy guardrails.
- Reviewing historical policy decisions and audit records for a case.
- Registering, querying, and revoking customer consent records.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_operator
from app.core.enums import ActorType
from app.core.errors import EntityNotFoundException
from app.models.domain import CustomerConsent, User
from app.policy.config import PolicyConfig
from app.policy.models import CustomerConsentRecord
from app.policy.service import PolicyEngineService, PolicyEvaluationRequest
from app.repositories import CustomerConsentRepository, PolicyDecisionRepository
from app.schemas.policy import (
    CustomerConsentCreateDTO,
    CustomerConsentResponseDTO,
    PolicyEvaluationRequestDTO,
    PolicyEvaluationResponseDTO,
    PolicyRuleCheckResponseDTO,
)

router = APIRouter(prefix="/api/v1/policy", tags=["policy-engine"])


def _to_consent_response(entity: CustomerConsent) -> CustomerConsentResponseDTO:
    """Helper converting an ORM CustomerConsent entity to CustomerConsentResponseDTO."""
    record = CustomerConsentRecord.from_domain(entity)
    return CustomerConsentResponseDTO(
        id=entity.id,
        customer_id=entity.customer_id,
        consent_type=entity.consent_type.value,
        status=entity.status.value,
        merchant_id=entity.merchant_id,
        granted_at=entity.granted_at,
        revoked_at=entity.revoked_at,
        expires_at=entity.expires_at,
        source=entity.source,
        evidence_reference=entity.evidence_reference,
        version=entity.version,
        is_valid=record.is_valid(),
    )


@router.post(
    "/evaluate",
    response_model=PolicyEvaluationResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Evaluate a recovery case recommendation against policy guardrails",
)
def evaluate_policy_recommendation(
    payload: PolicyEvaluationRequestDTO,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
) -> PolicyEvaluationResponseDTO:
    """Evaluate an AI recommendation for a recovery case.

    Synchronizes the recommendation validation status, advances the case FSM,
    and logs an authoritative immutable audit event.
    """
    service = PolicyEngineService(session=db, config=PolicyConfig())
    request = PolicyEvaluationRequest(
        case_id=payload.case_id,
        recommendation_id=payload.recommendation_id,
        proposed_action=payload.proposed_action,
        actor_type=ActorType.OPERATOR,
        actor_id=str(current_user.id),
        idempotency_key=payload.idempotency_key,
        communication_channel=payload.communication_channel,
        metadata=payload.metadata,
    )

    result = service.evaluate(request)

    rule_dtos = [
        PolicyRuleCheckResponseDTO(
            rule_name=r.rule_name,
            status=r.status.value,
            reason_code=r.reason_code,
            message=r.message,
            details=r.details,
        )
        for r in result.rule_results
    ]

    return PolicyEvaluationResponseDTO(
        decision_status=result.decision_status.value,
        case_id=result.case_id,
        recommendation_id=result.recommendation_id or payload.recommendation_id,
        proposed_action=result.proposed_action.value,
        policy_version=result.policy_version,
        is_approved=result.is_approved,
        validation_status=result.validation_status.value,
        reasons=result.reasons,
        rule_results=rule_dtos,
        evaluated_at=result.evaluated_at,
        metadata=result.metadata_json,
    )


@router.get(
    "/cases/{case_id}/decisions",
    response_model=list[PolicyEvaluationResponseDTO],
    summary="Retrieve audit trail of policy evaluations for a recovery case",
)
def get_case_policy_decisions(
    case_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_operator),
) -> list[PolicyEvaluationResponseDTO]:
    """Return historical policy evaluations conducted for a specific recovery case."""
    repo = PolicyDecisionRepository(db)
    records = repo.find_by_case(case_id)

    response_list = []
    for r in records:
        rule_dtos = [
            PolicyRuleCheckResponseDTO(
                rule_name=rule["rule_name"],
                status=rule["status"],
                reason_code=rule["reason_code"],
                message=rule["message"],
                details=rule.get("details", {}),
            )
            for rule in r.rule_results_json
        ]
        response_list.append(
            PolicyEvaluationResponseDTO(
                decision_status=r.decision_status.value,
                case_id=r.case_id,
                recommendation_id=r.recommendation_id,
                proposed_action=r.proposed_action.value,
                policy_version=r.policy_version,
                is_approved=r.decision_status.value == "approved",
                validation_status=r.decision_status.value,
                reasons=r.reasons_json,
                rule_results=rule_dtos,
                evaluated_at=r.evaluated_at,
                metadata=r.metadata_json,
            )
        )
    return response_list


@router.post(
    "/consents",
    response_model=CustomerConsentResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Register customer legal consent for billing or communication",
)
def create_customer_consent(
    payload: CustomerConsentCreateDTO,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_operator),
) -> CustomerConsentResponseDTO:
    """Record customer legal authorization for recurring billing, email, or SMS."""
    repo = CustomerConsentRepository(db)
    now = datetime.now(timezone.utc)

    consent = CustomerConsent(
        id=uuid4(),
        customer_id=payload.customer_id,
        consent_type=payload.consent_type,
        status=payload.status,
        merchant_id=payload.merchant_id,
        granted_at=now,
        expires_at=payload.expires_at,
        source=payload.source,
        evidence_reference=payload.evidence_reference,
        version=1,
    )
    repo.save(consent)
    db.commit()

    return _to_consent_response(consent)


@router.get(
    "/consents/{customer_id}",
    response_model=list[CustomerConsentResponseDTO],
    summary="List all legal consent records for a customer",
)
def list_customer_consents(
    customer_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_operator),
) -> list[CustomerConsentResponseDTO]:
    """List historical and active consent records associated with a customer."""
    repo = CustomerConsentRepository(db)
    entities = repo.find_by_customer(customer_id)
    return [_to_consent_response(e) for e in entities]


@router.post(
    "/consents/{consent_id}/revoke",
    response_model=CustomerConsentResponseDTO,
    summary="Revoke an existing customer legal consent",
)
def revoke_customer_consent(
    consent_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_operator),
) -> CustomerConsentResponseDTO:
    """Revoke a previously granted customer consent (fail-closed guardrail)."""
    repo = CustomerConsentRepository(db)
    record = repo.revoke_consent(consent_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consent record {consent_id} not found.",
        )
    db.commit()
    return _to_consent_response(record)
