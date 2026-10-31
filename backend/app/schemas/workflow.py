"""Pydantic DTOs for Recovery Workflows, Bounded Steps, and Reconciliation.

Author: Karthikeya
Architectural layer: API schemas / data transfer objects.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ActionType,
    ExecutionStatus,
    ReconciliationStatus,
    WorkflowStatus,
    WorkflowStepStatus,
    WorkflowStepType,
)


class WorkflowCreateRequestDTO(BaseModel):
    """Payload to instantiate a bounded recovery workflow from an approved policy decision."""

    policy_decision_id: UUID = Field(..., description="ID of the APPROVED PolicyDecision")
    cooldown_hours: int = Field(default=4, ge=0, le=168, description="Cooldown wait period in hours")
    max_workflow_hours: int = Field(default=72, ge=1, le=720, description="Workflow expiration threshold in hours")


class WorkflowExecuteRequestDTO(BaseModel):
    """Payload to trigger execution of pending workflow steps."""

    execute_all: bool = Field(default=True, description="Whether to sequentially run all ready steps")
    step_metadata_override: dict[str, Any] = Field(
        default_factory=dict, description="Optional metadata overrides (e.g. sandbox test triggers)"
    )


class RecoveryExecutionDTO(BaseModel):
    """DTO summarizing a single gateway execution dispatch."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_id: UUID
    case_id: UUID
    provider: str
    external_reference: str | None
    status: ExecutionStatus
    amount_minor: int
    currency: str
    idempotency_key: str
    error_code: str | None
    error_message_safe: str | None
    latency_ms: int | None
    executed_at: datetime


class WorkflowStepDTO(BaseModel):
    """DTO representing a discrete workflow step."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_index: int
    step_type: WorkflowStepType
    status: WorkflowStepStatus
    idempotency_key: str
    action_type: ActionType
    payload_json: dict[str, Any]
    execution_result_json: dict[str, Any]
    error_message: str | None
    executed_at: datetime | None
    executions: list[RecoveryExecutionDTO] = Field(default_factory=list)


class WorkflowDetailDTO(BaseModel):
    """Comprehensive representation of a recovery workflow and its execution steps."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    policy_decision_id: UUID
    status: WorkflowStatus
    strategy: str
    current_step_index: int
    max_steps: int
    scheduled_for: datetime | None
    expires_at: datetime | None
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    steps: list[WorkflowStepDTO] = Field(default_factory=list)


class ReconciliationRequestDTO(BaseModel):
    """Payload to initiate payment status reconciliation for a case."""

    case_id: UUID = Field(..., description="RecoveryCase identifier")
    auto_resolve: bool = Field(default=True, description="Whether to update internal state upon detected mismatch")


class ReconciliationResponseDTO(BaseModel):
    """Result of payment status reconciliation."""

    case_id: UUID
    transaction_id: UUID
    internal_status: str
    provider_status: str
    status: ReconciliationStatus
    discrepancies: list[str]
    resolution_action: str | None
    reconciled_at: datetime
    details: dict[str, Any]
