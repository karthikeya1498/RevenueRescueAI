"""Allow-listed tool registry for Phase 5.

Author: Karthikeya
Architectural layer: tool boundary.
"""

from typing import Any

from app.tools.contracts import ControlledTool, ToolContext, ToolInput, ToolOutput
from app.tools.recovery import (
    DraftRecoveryIntentTool,
    EscalateCaseTool,
    InspectRecoveryContextTool,
)


class ToolRegistry:
    """Resolve and execute only explicitly registered controlled tools."""

    def __init__(self, tools: list[ControlledTool] | None = None) -> None:
        selected = tools or [
            InspectRecoveryContextTool(),
            DraftRecoveryIntentTool(),
            EscalateCaseTool(),
        ]
        self._tools = {tool.name: tool for tool in selected}

    def names(self) -> tuple[str, ...]:
        """Return registered tool names in deterministic order."""

        return tuple(sorted(self._tools))

    def execute(self, name: str, payload: dict[str, Any], context: ToolContext) -> ToolOutput:
        """Validate input and execute one allow-listed tool."""

        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"tool is not registered: {name}")
        typed_payload: ToolInput = tool.input_model.model_validate(payload)
        return tool.execute(typed_payload, context)
