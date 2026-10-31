"""Recovery strategy catalogue and taxonomy for RevenueRescueAI.

Author: Karthikeya
Architectural layer: domain service / strategy catalog.

Defines the approved catalogue of recovery strategies, their preconditions,
applicable failure categories, and mappings to authoritative domain ActionTypes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.core.enums import ActionType


class RecoveryStrategy(StrEnum):
    """Approved recovery strategies for RevenueRescueAI."""

    RETRY_LATER = "RETRY_LATER"
    UPDATE_PAYMENT_METHOD = "UPDATE_PAYMENT_METHOD"
    CUSTOMER_REMINDER = "CUSTOMER_REMINDER"
    SUPPORT_ESCALATION = "SUPPORT_ESCALATION"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True)
class StrategyDefinition:
    """Specification of an approved recovery strategy."""

    strategy: RecoveryStrategy
    action_type: ActionType
    title: str
    description: str
    applicable_failure_categories: tuple[str, ...]
    preconditions: tuple[str, ...]
    estimated_cost_minor: int
    requires_policy_validation: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class StrategyCatalog:
    """Authoritative registry of approved recovery strategies."""

    CATALOG: dict[RecoveryStrategy, StrategyDefinition] = {
        RecoveryStrategy.RETRY_LATER: StrategyDefinition(
            strategy=RecoveryStrategy.RETRY_LATER,
            action_type=ActionType.RETRY_PAYMENT,
            title="Schedule Automated Payment Retry",
            description="Re-attempt charging the payment instrument after a cooling period.",
            applicable_failure_categories=(
                "insufficient_funds",
                "processing_error",
                "provider_timeout",
                "network_error",
            ),
            preconditions=(
                "failure_is_retryable",
                "prior_attempts_less_than_max",
                "risk_band_not_high",
            ),
            estimated_cost_minor=2,  # $0.02 gateway retry processing cost
            requires_policy_validation=True,
        ),
        RecoveryStrategy.UPDATE_PAYMENT_METHOD: StrategyDefinition(
            strategy=RecoveryStrategy.UPDATE_PAYMENT_METHOD,
            action_type=ActionType.SEND_REMINDER,
            title="Request Payment Method Update",
            description="Notify customer to update an expired or permanently declined card.",
            applicable_failure_categories=(
                "card_expired",
                "expired_card",
                "invalid_payment_details",
                "do_not_honor",
            ),
            preconditions=(
                "customer_contact_info_available",
                "case_not_terminal",
            ),
            estimated_cost_minor=15,  # $0.15 messaging/email delivery cost
            requires_policy_validation=True,
        ),
        RecoveryStrategy.CUSTOMER_REMINDER: StrategyDefinition(
            strategy=RecoveryStrategy.CUSTOMER_REMINDER,
            action_type=ActionType.SEND_REMINDER,
            title="Send Gentle Payment Reminder",
            description="Prompt customer regarding an abandoned checkout or overdue invoice.",
            applicable_failure_categories=(
                "abandoned_checkout",
                "overdue_invoice",
                "authentication_required",
            ),
            preconditions=(
                "customer_contact_info_available",
                "case_not_terminal",
            ),
            estimated_cost_minor=15,  # $0.15 delivery cost
            requires_policy_validation=True,
        ),
        RecoveryStrategy.SUPPORT_ESCALATION: StrategyDefinition(
            strategy=RecoveryStrategy.SUPPORT_ESCALATION,
            action_type=ActionType.REQUEST_OPERATOR_REVIEW,
            title="Escalate to High-Value Concierge Support",
            description="Route high-value account or critical failure to customer success team.",
            applicable_failure_categories=(
                "high_value_failure",
                "consecutive_declines",
                "vip_customer_failure",
            ),
            preconditions=(
                "case_not_terminal",
                "exposure_exceeds_threshold",
            ),
            estimated_cost_minor=250,  # $2.50 human operator review allocation
            requires_policy_validation=True,
        ),
        RecoveryStrategy.MANUAL_REVIEW: StrategyDefinition(
            strategy=RecoveryStrategy.MANUAL_REVIEW,
            action_type=ActionType.REQUEST_OPERATOR_REVIEW,
            title="Flag for Compliance and Risk Review",
            description="Escalate suspected fraud or uncertain decline code for human review.",
            applicable_failure_categories=(
                "fraud_suspected",
                "risk_blocked",
                "unknown_failure",
            ),
            preconditions=(
                "case_not_terminal",
            ),
            estimated_cost_minor=250,  # $2.50 operator review cost
            requires_policy_validation=True,
        ),
        RecoveryStrategy.NO_ACTION: StrategyDefinition(
            strategy=RecoveryStrategy.NO_ACTION,
            action_type=ActionType.STOP,
            title="Halt Recovery Workflow",
            description="Do not pursue recovery; case is terminal, restricted, or unrecoverable.",
            applicable_failure_categories=(
                "case_already_resolved",
                "customer_restricted",
                "policy_blocked",
            ),
            preconditions=(),
            estimated_cost_minor=0,
            requires_policy_validation=False,
        ),
    }

    @classmethod
    def get(cls, strategy: RecoveryStrategy) -> StrategyDefinition:
        """Retrieve strategy specification from registry."""
        return cls.CATALOG[strategy]

    @classmethod
    def all_strategies(cls) -> list[StrategyDefinition]:
        """Return list of all registered strategies."""
        return list(cls.CATALOG.values())

    @classmethod
    def map_to_action(cls, strategy: RecoveryStrategy) -> ActionType:
        """Map a high-level RecoveryStrategy to its domain ActionType."""
        return cls.CATALOG[strategy].action_type

    @classmethod
    def map_to_strategy(cls, action_type: ActionType) -> RecoveryStrategy:
        """Map a domain ActionType to a canonical RecoveryStrategy."""
        mapping = {
            ActionType.RETRY_PAYMENT: RecoveryStrategy.RETRY_LATER,
            ActionType.SEND_REMINDER: RecoveryStrategy.UPDATE_PAYMENT_METHOD,
            ActionType.REQUEST_OPERATOR_REVIEW: RecoveryStrategy.MANUAL_REVIEW,
            ActionType.STOP: RecoveryStrategy.NO_ACTION,
            ActionType.NONE: RecoveryStrategy.NO_ACTION,
        }
        return mapping.get(action_type, RecoveryStrategy.MANUAL_REVIEW)
