"""Provider interfaces and structured-output adapter for agent reasoning.

Author: Karthikeya
Architectural layer: agent provider adapter.
"""

import json
from dataclasses import dataclass
from typing import Protocol

from app.agents.contracts import AgentDecisionOutput, AgentObservation, decision_json_schema


class ReasoningProvider(Protocol):
    """Provider-neutral interface for bounded decision generation."""

    def decide(self, observation: AgentObservation) -> AgentDecisionOutput:
        """Return one structured decision for an observation."""


@dataclass(frozen=True)
class OpenAIReasoningConfig:
    """Configuration for the OpenAI-compatible structured-output proxy."""

    model: str = "gpt-5-mini"
    reasoning_effort: str = "low"
    max_completion_tokens: int = 1200


class OpenAIReasoningProvider:
    """Call an OpenAI-compatible provider and validate its JSON response."""

    def __init__(self, config: OpenAIReasoningConfig | None = None, client=None) -> None:
        self.config = config or OpenAIReasoningConfig()
        self._client = client

    def _get_client(self):
        """Load the SDK lazily so tests can use fakes without credentials."""

        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI()
        return self._client

    def decide(self, observation: AgentObservation) -> AgentDecisionOutput:
        """Request one strict decision; malformed output fails closed."""

        response = self._get_client().chat.completions.create(
            model=self.config.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a bounded revenue-recovery reasoning component. "
                        "Return exactly one JSON decision. Choose only from allowed_actions. "
                        "Never invent tools, amounts, credentials, or actions."
                    ),
                },
                {"role": "user", "content": observation.model_dump_json()},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "revenue_recovery_decision",
                    "strict": True,
                    "schema": decision_json_schema(),
                },
            },
            max_completion_tokens=self.config.max_completion_tokens,
            extra_body={"reasoning": {"effort": self.config.reasoning_effort}},
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("reasoning provider returned empty structured output")
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("reasoning provider returned invalid JSON") from exc
        return AgentDecisionOutput.model_validate(payload)
