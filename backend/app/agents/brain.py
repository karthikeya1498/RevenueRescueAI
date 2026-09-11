"""Bounded agent-brain orchestration for Phase 4.

Author: Karthikeya
Architectural layer: agent orchestration.
"""

from dataclasses import dataclass

from app.agents.contracts import AgentObservation, ValidatedAgentDecision, validate_decision
from app.agents.providers import ReasoningProvider


@dataclass(frozen=True)
class AgentRunResult:
    """A validated decision plus the provider model identifier when available."""

    decision: ValidatedAgentDecision
    provider_name: str


class AgentBrain:
    """Ask a provider for a decision and apply deterministic boundary checks."""

    def __init__(self, provider: ReasoningProvider, provider_name: str = "provider") -> None:
        self.provider = provider
        self.provider_name = provider_name

    def reason(self, observation: AgentObservation) -> AgentRunResult:
        """Produce one validated decision; provider failures propagate safely."""

        proposed = self.provider.decide(observation)
        validated = validate_decision(proposed, observation)
        return AgentRunResult(decision=validated, provider_name=self.provider_name)
