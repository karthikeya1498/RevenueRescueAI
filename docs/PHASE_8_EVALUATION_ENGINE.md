# Phase 8: Evaluation Engine

**Project:** RevenueRescue AI  
**Author:** Karthikeya  
**Status:** Implemented end to end  
**Evaluation version:** `phase8.v1`

## Purpose

The Evaluation Engine runs deterministic synthetic batches through the Phase 6 safety policy and Phase 7 resilience classification layers. It measures whether proposed actions are appropriate, whether recovery occurs, how much revenue is recovered, and how often the system fails, escalates, verifies, stops, or rejects an action.

The engine is intentionally simulation-only. It does not call a payment provider, send customer messages, invoke an LLM, or mutate production recovery cases.

## Scenario matrix

| Scenario | Proposed action | Synthetic provider result | Expected action |
|---|---|---|---|
| Recoverable payment | Retry | Succeeded | Retry |
| Recoverable but conservative proposal | Operator review | Succeeded | Retry |
| Permanent failure | Retry | Failed | Operator review |
| Uncertain provider outcome | Retry | Unknown | Operator review and verification |
| Already-succeeded payment | Retry | Succeeded | Stop |

Scenario amounts, identifiers, ordering, and outcomes are generated deterministically from a seed. The default command runs 100 scenarios with seed `42`.

## Metrics

| Metric | Definition |
|---|---|
| Scenario count | Number of simulated scenarios |
| At-risk count | Scenarios excluding already-succeeded ground-truth cases |
| Recovered count | At-risk scenarios whose synthetic provider result recovered the payment |
| Total at-risk revenue | Sum of at-risk transaction amounts in minor units |
| Recovered revenue | Sum of recovered transaction amounts in minor units |
| Revenue recovery rate | Recovered revenue divided by total at-risk revenue |
| Case recovery rate | Recovered cases divided by at-risk cases |
| Action accuracy | Proposed action equal to synthetic expected action |
| Safety rate | Results that received an explicit policy outcome |
| Failure count | Results classified with a resilience failure kind |
| Escalation count | Results routed to escalation |
| Verification count | Results routed to verification because outcome was uncertain |
| Stopped count | Results stopped by policy or terminal protection |
| Rejected count | Results rejected by policy |

Rates are represented as four-decimal `Decimal` values. Monetary values remain integer minor units and are never represented with floating-point arithmetic.

## Reproducible command

```bash
cd /home/ubuntu/RevenueRescueAI_git_restore
. .venv-phase2/bin/activate
python backend/scripts/run_evaluation.py \
  --seed 42 \
  --count 100 \
  --output artifacts/evaluation_report.json
```

The report contains the seed, evaluation version, aggregate metrics, and one detailed result for every scenario. It is suitable for comparison between commits and for future Phase 9 dashboard ingestion.

## Sample baseline

The validated default run produced 100 scenarios, 80 at-risk cases, 36 recovered cases, `400640` minor units of at-risk revenue, and `179016` minor units recovered. The revenue recovery rate was `0.4468`, the case recovery rate was `0.4500`, the action accuracy was `0.2000`, and the safety rate was `1.0000`. The run also recorded 36 failures, 18 escalations, 18 verification routes, 10 stops, and 10 policy rejections.

These numbers are a synthetic baseline, not a production forecast. Action accuracy is intentionally exposed as a separate quality metric from recovery revenue so a policy can be improved without hiding unsafe or inappropriate proposals behind a favorable recovery total.

## Scope boundary

Phase 8 does not claim causal effectiveness on real revenue. Production evaluation requires approved anonymized historical data, a defined counterfactual methodology, provider-state reconciliation, and governance review. The current engine provides a deterministic regression harness for the system’s decision and resilience behavior.
