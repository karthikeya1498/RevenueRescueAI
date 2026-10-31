"""Schema and Data Transfer Object (DTO) package.

Author: Karthikeya
Architectural layer: API DTO / external contract.

Exports all request and response DTOs for clean import across controller, service,
and mapper layers.
"""

from app.schemas.agent_decisions import (
    AgentDecisionCreateDTO,
    AgentDecisionResponseDTO,
    DecisionPreviewRequestDTO,
)
from app.schemas.audit_events import (
    AuditEventCreateDTO,
    AuditEventResponseDTO,
)
from app.schemas.auth import (
    ChangePasswordRequestDTO,
    RefreshTokenRequestDTO,
    TokenResponseDTO,
    UpdateProfileRequestDTO,
    UpdateUserRoleRequestDTO,
    UpdateUserStatusRequestDTO,
    UserLoginRequestDTO,
    UserRegisterRequestDTO,
    UserResponseDTO,
)
from app.schemas.common import (
    MoneyMinorUnits,
    PaginatedResponse,
    PaginationMetadata,
    PaginationParams,
    StatusResponseDTO,
)
from app.schemas.dashboard import (
    DashboardMetricsResponseDTO,
    RevenueTrendPointDTO,
    RevenueTrendResponseDTO,
    WorkflowStatusDistributionDTO,
)
from app.schemas.customers import (
    CustomerCreateDTO,
    CustomerResponseDTO,
    CustomerSummaryDTO,
    CustomerUpdateDTO,
)
from app.schemas.recovery_attempts import (
    RecoveryAttemptCreateDTO,
    RecoveryAttemptResponseDTO,
    RecoveryAttemptSummaryDTO,
)
from app.schemas.recovery_cases import (
    CaseDetailResponseDTO,
    CaseStateTransitionDTO,
    CaseSummaryItemDTO,
    ExecuteRetryRequestDTO,
    RecoveryCaseCreateDTO,
    RecoveryCaseResponseDTO,
    RecoveryCaseSummaryDTO,
    RecoveryCaseUpdateDTO,
    StopRecoveryRequestDTO,
)
from app.schemas.events import (
    CanonicalEventDTO,
    EventDetailDTO,
    EventIngestRequestDTO,
    EventIngestResponseDTO,
    EventSummaryDTO,
    PaginatedEventsDTO,
    SimulateFailureRequestDTO,
)
from app.schemas.recommendations import (
    CaseRecommendationDTO,
    StrategyEstimateDTO,
)
from app.schemas.recovery_evidence import (
    RecoveryEvidenceCreateDTO,
    RecoveryEvidenceResponseDTO,
)
from app.schemas.transactions import (
    TransactionCreateDTO,
    TransactionResponseDTO,
    TransactionSummaryDTO,
)

__all__ = [
    # Common
    "MoneyMinorUnits",
    "PaginationParams",
    "PaginationMetadata",
    "PaginatedResponse",
    "StatusResponseDTO",
    # Events & Ingestion
    "CanonicalEventDTO",
    "EventIngestRequestDTO",
    "SimulateFailureRequestDTO",
    "EventIngestResponseDTO",
    "EventSummaryDTO",
    "EventDetailDTO",
    "PaginatedEventsDTO",
    # Customers
    "CustomerCreateDTO",
    "CustomerUpdateDTO",
    "CustomerSummaryDTO",
    "CustomerResponseDTO",
    # Transactions
    "TransactionCreateDTO",
    "TransactionSummaryDTO",
    "TransactionResponseDTO",
    # Dashboard
    "DashboardMetricsResponseDTO",
    "RevenueTrendPointDTO",
    "RevenueTrendResponseDTO",
    "WorkflowStatusDistributionDTO",
    # Recovery Cases
    "RecoveryCaseCreateDTO",
    "RecoveryCaseUpdateDTO",
    "RecoveryCaseSummaryDTO",
    "RecoveryCaseResponseDTO",
    "CaseSummaryItemDTO",
    "CaseDetailResponseDTO",
    "CaseStateTransitionDTO",
    "ExecuteRetryRequestDTO",
    "StopRecoveryRequestDTO",
    # Recovery Attempts
    "RecoveryAttemptCreateDTO",
    "RecoveryAttemptSummaryDTO",
    "RecoveryAttemptResponseDTO",
    # Agent Decisions & Recommendations
    "DecisionPreviewRequestDTO",
    "AgentDecisionCreateDTO",
    "AgentDecisionResponseDTO",
    "CaseRecommendationDTO",
    "StrategyEstimateDTO",
    # Audit Events
    "AuditEventCreateDTO",
    "AuditEventResponseDTO",
    # Recovery Evidence
    "RecoveryEvidenceCreateDTO",
    "RecoveryEvidenceResponseDTO",
    # Authentication & User Management
    "UserRegisterRequestDTO",
    "UserLoginRequestDTO",
    "RefreshTokenRequestDTO",
    "ChangePasswordRequestDTO",
    "UpdateProfileRequestDTO",
    "UpdateUserRoleRequestDTO",
    "UpdateUserStatusRequestDTO",
    "UserResponseDTO",
    "TokenResponseDTO",
]

