# P05 Track A2 — source-tier priority experiment

**Result: rejected; no default adopted.** The existing `allocation_order` contrast was run
for 116 ticks on historical F2 through 1985Q4. The paired control reproduces the frozen
legacy replay digest, confirming that the current reference is still intact.

| Arm | order | frozen gates | T1 production ≥35,092 | T2 consumption ≥2,085 | T3 | production last 10 | consumption last 10 | liveness | transport realized | pool / freight need | blocked share | household unmet | wage arrears final | money residual |
|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A2-B0 | production_first | accounting only | fail | fail | pass | 28,074.08 | 1,667.96 | .1116 | 272,066.29 | .5397 | .7042 | 2,811,432.29 | 865,740.56 | 2.24e-9 |
| A2-I | investment_first | accounting only | fail | fail | pass | 2,523.75 | 991.57 | .0103 | 248,585.23 | .5648 | .7437 | 2,933,257.51 | 830,420.66 | 3.52e-9 |

Both arms satisfy the accounting invariants. `investment_first` raises the freight-pool ratio
slightly, but worsens terminal production and consumption, physical blocking, and household
availability unmet. The modest arrears reduction does not compensate for those regressions.

**H-A2 is falsified.** Source-tier priority is not a sufficient binding rule under this
contrast. No arm reaches T1 or T2; A3 is therefore next under the master plan. Frozen
liveness, household service funding, treasury self-financing, and expiry gates remain blocked.
No validation or calibration claim is made.

Reproduction artifacts: ignored compact runs under `outputs/p05-a2-source-priority/`.
