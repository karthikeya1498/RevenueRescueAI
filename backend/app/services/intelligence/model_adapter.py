"""Model adapter interface for recovery probability estimation.

Author: Karthikeya
Architectural layer: domain service / ML adapter.

Defines the pluggable interface through which future machine learning models
(Logistic Regression, Decision Trees, Random Forests, XGBoost) can be integrated
without refactoring the service layer or REST API contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from app.core.enums import ActionType


class RecoveryEstimatorAdapter(ABC):
    """Abstract adapter interface for recovery probability estimators."""

    @property
    @abstractmethod
    def model_version(self) -> str:
        """Return the model identifier and version string."""

    def get_model_version(self) -> str:
        """Return the model identifier and version string."""
        return self.model_version

    def get_model_metadata(self) -> dict[str, Any]:
        """Return metadata regarding model provenance, features, and evaluation."""
        return {"version": self.model_version}

    @abstractmethod
    def estimate_recovery_probability(
        self,
        *,
        action_type: ActionType,
        failure_category: str,
        is_retryable: bool,
        amount_minor: int,
        prior_attempts: int,
        customer_success_rate: float = 0.5,
        alternate_method_available: bool = True,
        risk_score: int = 0,
        features: dict[str, Any] | None = None,
    ) -> Decimal:
        """Estimate the conditional probability of successful revenue recovery.

        Returns:
            Decimal bounded in [0.0100, 0.9900].
        """
