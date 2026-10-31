"""AI-Powered Recovery Intelligence Engine Package.

Author: Karthikeya
Architectural layer: Intelligence Service Module.

Components:
- FailureAnalyzer: Categorizes payment failure reasons into normalized failure mechanisms.
- RiskAssessor: Computes bounded risk scores and risk bands (low, medium, high).
- RecoveryEstimatorAdapter / LogisticRecoveryEstimator: Bounded probability estimation.
- StrategyCatalog / StrategySelector: Evaluates expected net recovery value across catalogue.
- ExplanationService: Generates factual, evidence-backed explanations.
- IntelligenceOrchestrator: Coordinates end-to-end evaluation, persistence, and audit.
- Legacy Baseline: Preserves preview and regression compatibility (classify_failure, analyze_recovery).
"""

from app.services.intelligence.explanation_service import (
    ExplanationService,
    RecommendationExplanation,
)
from app.services.intelligence.failure_analyzer import (
    FailureAnalysisResult,
    FailureAnalyzer,
)
from app.services.intelligence.legacy import (
    ACTIONS,
    ActionEstimate,
    DecisionAnalysis,
    ExpectedValueEngine,
    FailureClassification,
    RecoveryProbabilityModel,
    RiskAssessment,
    RiskEngine,
    analyze_recovery,
    classify_failure,
    compare_strategies,
)
from app.services.intelligence.model_adapter import RecoveryEstimatorAdapter
from app.services.intelligence.orchestrator import IntelligenceOrchestrator
from app.services.intelligence.probability_estimator import LogisticRecoveryEstimator
from app.services.intelligence.risk_assessor import (
    RiskAssessmentResult,
    RiskAssessor,
)
from app.services.intelligence.strategy_catalog import (
    RecoveryStrategy,
    StrategyCatalog,
    StrategyDefinition,
)
from app.services.intelligence.strategy_selector import (
    CandidateEstimate,
    StrategyCandidateEstimate,
    StrategySelectionResult,
    StrategySelector,
)

__all__ = [
    # Phase 2.8 Production Architecture
    "CandidateEstimate",
    "ExplanationService",
    "FailureAnalysisResult",
    "FailureAnalyzer",
    "IntelligenceOrchestrator",
    "LogisticRecoveryEstimator",
    "RecommendationExplanation",
    "RecoveryEstimatorAdapter",
    "RecoveryStrategy",
    "RiskAssessmentResult",
    "RiskAssessor",
    "StrategyCandidateEstimate",
    "StrategyCatalog",
    "StrategyDefinition",
    "StrategySelectionResult",
    "StrategySelector",
    # Backward-Compatible Baseline API
    "ACTIONS",
    "ActionEstimate",
    "DecisionAnalysis",
    "ExpectedValueEngine",
    "FailureClassification",
    "RecoveryProbabilityModel",
    "RiskAssessment",
    "RiskEngine",
    "analyze_recovery",
    "classify_failure",
    "compare_strategies",
]
