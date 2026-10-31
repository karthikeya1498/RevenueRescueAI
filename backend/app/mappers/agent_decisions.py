"""Agent decision entity-to-DTO and DTO-to-entity pure mappers.

Author: Karthikeya
Architectural layer: mapper.

Rules:
- Maps recommendation outputs with strict confidence bounding.
- Avoids executing LLM reasoning or policy evaluation inside the mapper.
"""

from __future__ import annotations

from uuid import uuid4

from app.models.domain import AgentDecision
from app.schemas.agent_decisions import (
    AgentDecisionCreateDTO,
    AgentDecisionResponseDTO,
)


class AgentDecisionMapper:
    """Stateless transformation utility between AgentDecision entities and DTOs."""

    @staticmethod
    def to_response(entity: AgentDecision) -> AgentDecisionResponseDTO:
        """Convert an AgentDecision persistence entity into an AgentDecisionResponseDTO."""
        return AgentDecisionResponseDTO(
            id=entity.id,
            case_id=entity.case_id,
            attempt_id=entity.attempt_id,
            decision_version=entity.decision_version,
            action_type=entity.action_type,
            reason_code=entity.reason_code,
            rationale_safe=entity.rationale_safe,
            confidence=entity.confidence,
            raw_response_hash=entity.raw_response_hash,
            validation_status=entity.validation_status,
        )

    @staticmethod
    def to_entity(dto: AgentDecisionCreateDTO, decision_version: int = 1) -> AgentDecision:
        """Instantiate a new detached AgentDecision entity."""
        return AgentDecision(
            id=uuid4(),
            case_id=dto.case_id,
            attempt_id=dto.attempt_id,
            decision_version=decision_version,
            action_type=dto.action_type,
            reason_code=dto.reason_code,
            rationale_safe=dto.rationale_safe,
            confidence=dto.confidence,
            raw_response_hash=dto.raw_response_hash,
            validation_status=dto.validation_status,
        )
