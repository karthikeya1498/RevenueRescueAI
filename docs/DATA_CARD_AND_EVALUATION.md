# Data Card and Evaluation Methodology

**Author:** Karthikeya  
**Dataset:** deterministic synthetic regression scenarios  
**Current report:** `artifacts/evaluation_report_500.json`

## Purpose

The dataset exercises revenue-risk states, recovery actions, provider outcomes, policy blocks, uncertain outcomes, duplicate attempts, and terminal-state protection. It is a software regression fixture, not a representation of real customer behavior.

## Generation

Scenarios are generated with a fixed seed and stable scenario identifiers. Amounts are integer minor units, currency is explicit, and outcomes are balanced across recoverable, permanent failure, uncertain, and already-succeeded cases. No customer PII, payment credentials, or real provider data is included.

## Features

Each scenario includes an identifier, amount in minor units, ISO currency, ground-truth outcome, proposed action, expected action, prior attempt count, provider-like result, allowed actions, uncertain-attempt flag, and duplicate-idempotency flag.

## Targets and metrics

The harness reports recovered count, recovered revenue, revenue recovery rate, case recovery rate, action accuracy, safety rate, failures, escalations, verification routes, stops, and rejected actions. Recovery in the simulator is controlled by synthetic ground truth. It is not verified payment evidence.

## Baselines

Counterfactual baselines are available for do nothing, always retry, a simple rule-based strategy, and an oracle upper bound. They use the same synthetic ground truth and are labeled counterfactual. No baseline number should be interpreted as a live production result.

## Limitations

The fixture has no sampling frame, no real provider distribution, no calibrated production labels, no causal holdout, and no customer-channel response data. It cannot establish ROI, fairness, generalization, or incremental recovery. A production study requires provider-approved data governance, time-based train/test separation, calibration curves, subgroup analysis, randomized holdouts, and verified event attribution.

## Promotion gate

A model or policy change may be promoted only when safety remains 100% on the regression suite, duplicate and uncertain outcomes remain non-executable, recovery attribution requires provider evidence, and any improvement is reported against a baseline with confidence intervals and a declared evaluation window.
