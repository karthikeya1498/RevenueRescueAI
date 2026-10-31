"""Consent Policy Rule Validator for Phase 2.9 Step 2.

Architectural layer: policy evaluator.

Validates that legally required customer consent is active, unrevoked, unexpired,
and correctly scoped to the customer, merchant, and communication/billing channel.
"""

from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from app.core.enums import ActionType, ConsentStatus, ConsentType, RuleCheckStatus
from app.policy.models import CustomerConsentRecord, RuleCheckResult


class ConsentValidator:
    """Validates legal consent requirements with fail-closed semantics."""

    RULE_NAME = "customer_consent_validation"

    def evaluate(
        self,
        *,
        action_type: ActionType,
        customer_id: UUID | str,
        consents: Sequence[CustomerConsentRecord],
        merchant_id: str | None = None,
        communication_channel: str | None = None,
        evaluation_time: datetime | None = None,
    ) -> RuleCheckResult:
        """Evaluate customer consent for the proposed recovery action.

        Args:
            action_type: Proposed domain recovery ActionType.
            customer_id: Target customer identifier.
            consents: Available consent records for this customer.
            merchant_id: Optional merchant identifier for multi-tenant isolation.
            communication_channel: "email" or "sms" when action_type is SEND_REMINDER.
            evaluation_time: Reference timestamp for evaluating expirations and revocations.

        Returns:
            RuleCheckResult with PASSED or FAILED status and appropriate reason code.
        """
        now = evaluation_time or datetime.now(timezone.utc)
        target_cid = str(customer_id)

        # 1. Determine required consent type based on action
        required_type = self._determine_required_consent(action_type, communication_channel)

        # If no customer consent is legally required (e.g., internal operator review, stop)
        if required_type is None:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.PASSED,
                reason_code="NO_CONSENT_REQUIRED",
                message=f"Action {action_type.value} is an internal/system action requiring no external consent.",
                details={"action_type": action_type.value},
            )

        # 2. Filter consents for matching customer, type, and merchant
        matching_consents = [c for c in consents if str(c.customer_id) == target_cid]
        if not matching_consents and consents:
            # Consents were supplied, but belonged to a different customer
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.FAILED,
                reason_code="CONSENT_CUSTOMER_MISMATCH",
                message="Consent records do not match the target customer identifier.",
                details={"target_customer_id": target_cid},
            )

        # 3. Filter strictly by required consent type (email and sms are independent)
        type_consents = [c for c in matching_consents if c.consent_type == required_type]
        if not type_consents:
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.FAILED,
                reason_code="CONSENT_MISSING",
                message=f"No consent record found for required consent type: {required_type.value}.",
                details={"required_consent_type": required_type.value},
            )

        # 4. Check merchant boundary if merchant_id is specified
        if merchant_id is not None:
            merchant_consents = [
                c for c in type_consents if c.merchant_id is None or c.merchant_id == merchant_id
            ]
            if not merchant_consents:
                return RuleCheckResult(
                    rule_name=self.RULE_NAME,
                    status=RuleCheckStatus.FAILED,
                    reason_code="CONSENT_MERCHANT_MISMATCH",
                    message="Consent record is bound to a different merchant.",
                    details={"target_merchant_id": merchant_id},
                )
            eval_candidates = merchant_consents
        else:
            eval_candidates = type_consents

        # 5. Evaluate candidates with fail-closed rules
        # Sort so we inspect the most recently granted record first
        sorted_candidates = sorted(eval_candidates, key=lambda c: c.granted_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        for candidate in sorted_candidates:
            # Timestamp validity & integrity check
            if candidate.granted_at is None:
                return RuleCheckResult(
                    rule_name=self.RULE_NAME,
                    status=RuleCheckStatus.FAILED,
                    reason_code="CONSENT_INVALID",
                    message="Consent record is invalid: missing granted_at timestamp.",
                )

            # Revocation check
            if candidate.status == ConsentStatus.REVOKED or candidate.revoked_at is not None:
                rev_time = candidate.revoked_at or candidate.granted_at
                rev_time = self._ensure_utc(rev_time)
                now_utc = self._ensure_utc(now)
                if now_utc >= rev_time:
                    return RuleCheckResult(
                        rule_name=self.RULE_NAME,
                        status=RuleCheckStatus.FAILED,
                        reason_code="CONSENT_REVOKED",
                        message=f"Customer consent for {required_type.value} was revoked on {rev_time.isoformat()}.",
                        details={"revoked_at": rev_time.isoformat()},
                    )

            # Expiration check
            if candidate.status == ConsentStatus.EXPIRED or candidate.expires_at is not None:
                if candidate.expires_at is not None:
                    exp_time = self._ensure_utc(candidate.expires_at)
                    now_utc = self._ensure_utc(now)
                    if now_utc >= exp_time:
                        return RuleCheckResult(
                            rule_name=self.RULE_NAME,
                            status=RuleCheckStatus.FAILED,
                            reason_code="CONSENT_EXPIRED",
                            message=f"Customer consent for {required_type.value} expired on {exp_time.isoformat()}.",
                            details={"expires_at": exp_time.isoformat()},
                        )

            # Status check
            if candidate.status != ConsentStatus.GRANTED:
                return RuleCheckResult(
                    rule_name=self.RULE_NAME,
                    status=RuleCheckStatus.FAILED,
                    reason_code=f"CONSENT_STATUS_{candidate.status.value.upper()}",
                    message=f"Consent record has non-active status: {candidate.status.value}.",
                )

            # If all checks pass for candidate, consent is fully valid
            return RuleCheckResult(
                rule_name=self.RULE_NAME,
                status=RuleCheckStatus.PASSED,
                reason_code="CONSENT_VALID",
                message=f"Legally active consent confirmed for {required_type.value}.",
                details={
                    "consent_id": str(candidate.id) if candidate.id else None,
                    "consent_type": required_type.value,
                    "source": candidate.source,
                },
            )

        # Fallback if no valid candidate found
        return RuleCheckResult(
            rule_name=self.RULE_NAME,
            status=RuleCheckStatus.FAILED,
            reason_code="CONSENT_MISSING",
            message=f"No valid consent available for {required_type.value}.",
        )

    def _determine_required_consent(
        self, action_type: ActionType, communication_channel: str | None
    ) -> ConsentType | None:
        """Map action type and communication channel to the required consent type."""
        if action_type is ActionType.RETRY_PAYMENT:
            return ConsentType.RECURRING_BILLING

        if action_type is ActionType.SEND_REMINDER:
            ch = (communication_channel or "email").strip().lower()
            if ch == "sms":
                return ConsentType.COMMUNICATION_SMS
            return ConsentType.COMMUNICATION_EMAIL

        # Internal operator review, stop, or none require no customer-facing consent
        return None

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        """Normalize datetime to UTC timezone."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
