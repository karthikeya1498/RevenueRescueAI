"""Controlled tool contracts for Phase 5.

Author: Karthikeya
Architectural layer: tool boundary.

Tools accept typed inputs and return typed results. They do not call payment
providers or customer channels in this phase.
"""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ActionType


class ToolInput(BaseModel):
    """Base input contract with strict unknown-field rejection."""

    model_config = ConfigDict(extra="forbid")


class ToolOutput(BaseModel):
    """Base output contract for controlled tool execution."""

    tool_name: str
    status: str
    dry_run: bool
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class InspectRecoveryContextInput(ToolInput):
    """Input for a read-only context inspection tool."""

    case_id: UUID


class DraftRecoveryIntentInput(ToolInput):
    """Input for a no-side-effect recovery intent tool."""

    case_id: UUID
    action: ActionType
    rationale: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=1, max_length=250)


class EscalateCaseInput(ToolInput):
    """Input for an operator-review escalation tool."""

    case_id: UUID
    reason: str = Field(min_length=1, max_length=500)
    priority: int = Field(ge=0, le=100)


@dataclass(frozen=True)
class ToolContext:
    """Execution context supplied by the workflow boundary."""

    authorized: bool = False
    dry_run: bool = True
    correlation_id: str = "phase5-local"


class ControlledTool(Protocol):
    """Protocol implemented by every controlled tool."""

    name: str
    input_model: type[ToolInput]

    def execute(self, payload: ToolInput, context: ToolContext) -> ToolOutput:
        """Validate and execute a bounded operation."""
