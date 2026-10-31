# Recovery Probability Estimation Model & Adapter Architecture

## 1. Mathematical Formulation

The [`LogisticRecoveryEstimator`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/intelligence/probability_estimator.py) (version `deterministic-logistic-v1`) models the conditional probability $P(\text{Recovery} \mid \text{Action}, \text{Features})$ using a generalized logistic function:

$$z = w_0 + w_{\text{attempts}} \cdot x_{\text{attempts}} + w_{\text{history}} \cdot (x_{\text{cust}} - 0.5) + w_{\text{action}} \cdot x_{\text{action}} + w_{\text{risk}} \cdot x_{\text{risk}}$$

$$P(\text{Recovery}) = \frac{1}{1 + e^{-z}}$$

To prevent degenerate probabilities ($0.0$ or $1.0$), all estimations are clamped strictly to:
$$P \in [0.0100, 0.9900]$$

---

## 2. Transparent Weight Coefficients

| Coefficient Key | Symbol | Calibrated Value | Operational Interpretation |
| :--- | :---: | :---: | :--- |
| `bias` | $w_0$ | **-0.65** | Conservative base intercept (~34.3% recovery probability without favorable signals). |
| `low_attempts_bonus` | $w_{\text{low}}$ | **+0.42** | Prior attempts $\le 1$ reflects early-stage, recoverable incidents. |
| `repeated_attempts_penalty`| $w_{\text{repeat}}$ | **-0.25** | Per-attempt decay for prior attempts $\ge 2$ (up to 4 attempts). |
| `customer_history_weight` | $w_{\text{history}}$| **+0.55** | Historical success rate boosts probability when customer has proven reliability. |
| `retryable_action_bonus` | $w_{\text{retry}}$ | **+0.45** | Automated retry on transient errors (`insufficient_funds`, `provider_timeout`). |
| `alternate_method_bonus` | $w_{\text{alt}}$ | **+0.25** | Customer reminder when alternate card is registered on file. |
| `high_risk_penalty` | $w_{\text{risk}}$ | **-1.20** | Score $\ge 70$ severely penalizes automated recovery feasibility. |
| `operator_review_bonus` | $w_{\text{review}}$| **+0.10** | High-touch concierge manual review improves resolution odds for complex B2B cases. |
| `stop_penalty` | $w_{\text{stop}}$ | **-0.45** | Passive halting does not generate active recovery. |

---

## 3. Machine Learning Pluggability Interface (`RecoveryEstimatorAdapter`)

The backend interacts with the probability model exclusively through the [`RecoveryEstimatorAdapter`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/intelligence/model_adapter.py) abstract base class.

```python
class RecoveryEstimatorAdapter(ABC):
    @property
    @abstractmethod
    def model_version(self) -> str:
        ...

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
        ...
```

When production historical data accumulates, trained models (scikit-learn `LogisticRegression`, `RandomForestClassifier`, or LightGBM) can be plugged in by implementing this single class without modifying the [`IntelligenceOrchestrator`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/intelligence/orchestrator.py) or REST controllers.
