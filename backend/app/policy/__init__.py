"""Policy engine package for RevenueRescue AI Phase 2.9.

Centralizes safety guardrails, customer consent evaluation, retry limits,
and action authorization rules.
"""

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
    PolicyDecisionStatus,
    PolicyEvaluationResult,
    RuleCheckResult,
    RuleCheckStatus,
    map_policy_to_validation_status,
)
from app.policy.service import PolicyEngineService, PolicyEvaluationRequest

__all__ = [
    "PolicyConfig",
    "CustomerConsentRecord",
    "PolicyDecisionStatus",
    "PolicyEvaluationResult",
    "RuleCheckResult",
    "RuleCheckStatus",
    "map_policy_to_validation_status",
    "ConsentValidator",
    "EligibilityEvaluator",
    "EscalationEvaluator",
    "RetryLimitEvaluator",
    "StrategyValidator",
    "PolicyEngineService",
    "PolicyEvaluationRequest",
]

