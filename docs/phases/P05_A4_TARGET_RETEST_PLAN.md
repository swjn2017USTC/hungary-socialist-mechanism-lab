# P05 Track A4 — demand-following target retest

The master plan orders a retest after A1–A3. Their zero/default path remains unchanged; A1
had no valid interest-transfer arm and the fiscal arm failed household guardrails; A2 priority
was falsified; A3 savings re-entry produced no T1/T2 passer. This retest therefore starts
from the unchanged historical F2 defaults and compares the two previously measured target
variants, now against the declared terminal floors and current circuit accounting.

- A4-B0: unchanged legacy production targets.
- A4-LN: `production_target_rule=lean_plan`; current implementation caps only
  non-stockable outputs to the lean plan.
- A4-LA: `production_target_rule=lean_plan` plus `demand_limited_targets=true`, which
  also applies the demand signal cap to all activities.

All arms run 116 ticks through 1985Q4. Record frozen gates, T1–T3, expiry, money and
commodity residuals, treasury, service ratios, household consumption/unmet availability,
transport and wage arrears. Reject any arm with a new residual or a household guardrail
regression. No target threshold or default is changed. A4 is a retest, not a validation
exercise; no arm passing both T1 and T2 means proceed to the master-plan A5/A7 decision.
