"""Concrete controlled tools for Phase 5.

Author: Karthikeya
Architectural layer: tool adapters.
"""

from app.tools.contracts import (
    DraftRecoveryIntentInput,
    EscalateCaseInput,
    InspectRecoveryContextInput,
    ToolContext,
    ToolOutput,
)


class InspectRecoveryContextTool:
    """Return a bounded read-only context request; no external lookup yet."""

    name = "inspect_recovery_context"
    input_model = InspectRecoveryContextInput

    def execute(self, payload: InspectRecoveryContextInput, context: ToolContext) -> ToolOutput:
        """Produce a safe inspection result for a future repository adapter."""

        return ToolOutput(
            tool_name=self.name,
            status="planned",
            dry_run=context.dry_run,
            message="Context inspection is represented as a controlled intent in Phase 5.",
            data={"case_id": str(payload.case_id), "correlation_id": context.correlation_id},
        )


class DraftRecoveryIntentTool:
    """Create a typed, idempotent recovery intent without executing it."""

    name = "draft_recovery_intent"
    input_model = DraftRecoveryIntentInput

    def execute(self, payload: DraftRecoveryIntentInput, context: ToolContext) -> ToolOutput:
        """Return an action intent; policy and execution are separate future layers."""

        if not context.authorized:
            return ToolOutput(
                tool_name=self.name,
                status="rejected",
                dry_run=context.dry_run,
                message="Tool authorization is required before creating a recovery intent.",
                data={"case_id": str(payload.case_id)},
            )
        return ToolOutput(
            tool_name=self.name,
            status="planned",
            dry_run=context.dry_run,
            message="Recovery intent recorded as a dry-run plan; no provider was called.",
            data={
                "case_id": str(payload.case_id),
                "action": payload.action.value,
                "rationale": payload.rationale,
                "idempotency_key": payload.idempotency_key,
                "correlation_id": context.correlation_id,
            },
        )


class EscalateCaseTool:
    """Create an operator-review intent without sending a notification."""

    name = "escalate_recovery_case"
    input_model = EscalateCaseInput

    def execute(self, payload: EscalateCaseInput, context: ToolContext) -> ToolOutput:
        """Return a bounded escalation plan for a future operator workflow."""

        return ToolOutput(
            tool_name=self.name,
            status="planned",
            dry_run=context.dry_run,
            message="Operator escalation planned; no notification was sent.",
            data={
                "case_id": str(payload.case_id),
                "reason": payload.reason,
                "priority": payload.priority,
                "correlation_id": context.correlation_id,
            },
        )
