"""Centralized Policy Engine Configuration for Phase 2.9.

Architectural layer: policy configuration.

IMPORTANT FINANCIAL & REGULATORY NOTICE:
- The default values provided here are provisional development defaults and are
  explicitly marked with `is_production_approved = False`.
- In production, these limits must be reviewed and signed off by finance, legal,
  and risk teams before deployment.
- Retry count clarification: `max_retry_attempts = 3` means exactly 3 retries
  AFTER the initial transaction failure, permitting at most 4 total payment attempts
  (1 initial failure + 3 recovery retries).
- Minor currency units: Thresholds are currency-aware. Minor unit amounts (e.g., paise
  vs cents vs zero-decimal yen) must NEVER be directly compared across different currencies.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class PolicyConfig:
    """Centralized, immutable policy engine configuration.
    
    Attributes:
        max_retry_attempts: Number of payment retries allowed *after* initial failure.
            Default is 3 (yielding max 4 total attempts).
        max_total_attempts: Total allowed attempts including the initial failed payment.
            Default is 4.
        retry_cooldown_hours: Minimum hours that must elapse before another payment retry
            is permissible for the same recovery case. Default is 4 hours.
        high_value_escalation_threshold_minor: Baseline fallback minor-unit threshold
            triggering human operator review. Default is 100,000 minor units.
        policy_version: Version identifier string for audit tracking and policy immutability.
            Default is "policy-v1.0".
        is_production_approved: Boolean flag indicating whether these business rules
            have received formal stakeholder sign-off. Default is False (provisional defaults).
        currency_thresholds_minor: Currency-specific escalation thresholds in minor units.
            Prevents invalid cross-currency minor unit comparisons.
    """

    max_retry_attempts: int = 3
    max_total_attempts: int = 4
    retry_cooldown_hours: int = 4
    high_value_escalation_threshold_minor: int = 100_000
    policy_version: str = "policy-v1.0"
    is_production_approved: bool = False
    currency_thresholds_minor: dict[str, int] = field(
        default_factory=lambda: {
            "INR": 100_000,  # ₹1,000.00 (100,000 paise)
            "USD": 100_000,  # $1,000.00 (100,000 cents)
            "EUR": 100_000,  # €1,000.00 (100,000 cents)
            "GBP": 100_000,  # £1,000.00 (100,000 pence)
            "JPY": 150_000,  # ¥150,000 (0 decimal currency)
            "AUD": 100_000,  # A$1,000.00
            "CAD": 100_000,  # C$1,000.00
            "SGD": 100_000,  # S$1,000.00
        }
    )

    def get_high_value_threshold(self, currency: str) -> int:
        """Return currency-specific minor-unit threshold for human escalation.
        
        Args:
            currency: Three-letter ISO currency code (case-insensitive).
            
        Returns:
            Threshold in minor currency units (paise, cents, yen, etc.).
        """
        curr = currency.upper().strip()
        return self.currency_thresholds_minor.get(
            curr, self.high_value_escalation_threshold_minor
        )

    def is_high_value(self, amount_minor: int, currency: str) -> bool:
        """Determine whether an amount exceeds the high-value threshold for its currency.
        
        Args:
            amount_minor: Transaction exposure amount in minor currency units.
            currency: Three-letter ISO currency code.
            
        Returns:
            True if amount meets or exceeds the currency-aware threshold.
        """
        threshold = self.get_high_value_threshold(currency)
        return amount_minor >= threshold

    def can_retry(self, prior_retry_count: int) -> bool:
        """Check whether another payment retry attempt is allowed under policy limits.
        
        Args:
            prior_retry_count: Number of retries already executed AFTER the initial failure.
            
        Returns:
            True if prior_retry_count is strictly less than max_retry_attempts.
        """
        return prior_retry_count < self.max_retry_attempts

    def is_cooldown_elapsed(
        self,
        last_attempt_at: datetime,
        current_time: datetime | None = None,
    ) -> bool:
        """Evaluate whether required cooldown period has elapsed since last attempt.
        
        Args:
            last_attempt_at: Timestamp of the most recent recovery attempt.
            current_time: Current evaluation time (defaults to datetime.now(timezone.utc)).
            
        Returns:
            True if elapsed time >= retry_cooldown_hours.
        """
        now = current_time or datetime.now(timezone.utc)
        # Ensure timezone compatibility
        if last_attempt_at.tzinfo is None and now.tzinfo is not None:
            last_attempt_at = last_attempt_at.replace(tzinfo=timezone.utc)
        elif last_attempt_at.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        elapsed_seconds = (now - last_attempt_at).total_seconds()
        cooldown_seconds = self.retry_cooldown_hours * 3600
        return elapsed_seconds >= cooldown_seconds
