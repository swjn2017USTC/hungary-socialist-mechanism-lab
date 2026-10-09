# P05 Track A4 — demand-following target retest

**Result: both target variants rejected; no defaults adopted.** All three arms completed
116 ticks through 1985Q4 and passed accounting residual checks. A4-B0 reproduces the
legacy digest.

| arm | target setting | frozen gates | T1 | T2 | T3 | production last 10 | consumption last 10 | liveness | max expiry | unmet availability | pool/freight | blocked share | wage arrears | max money residual | guardrails |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A4-B0 | legacy | accounting only | fail | fail | pass | 28,074.08 | 1,667.96 | .1116 | .9423 | 2,811,432.29 | .5397 | .7042 | 865,740.56 | 2.24e-9 | pass |
| A4-LN | lean_plan, non-stockable outputs | accounting only | fail | fail | pass | 59.94 | 210.43 | .0008 | .9790 | 3,737,828.27 | .0153 | .9437 | 667,423.41 | 2.33e-9 | fail: household consumption and unmet availability |
| A4-LA | lean_plan + all-activity demand cap | accounting only | fail | fail | pass | 44.30 | 212.20 | .0008 | .9756 | 3,746,063.91 | .0087 | .9599 | 602,844.16 | 2.15e-9 | fail: household consumption and unmet availability |

Both target variants drive physical activity and the delivery circuit below the legacy
control. H-A4 is falsified as a route to the declared terminal floors. The experiment does
not relax thresholds or change defaults. A5 is ineligible: fewer than two independent
candidates improved a terminal criterion. Since no arm from A1–A4 passes both T1 and T2,
the master plan's honest A7 review is required.

Raw compact runs are ignored under `outputs/p05-a4-target-retest/`.
