# P05 Track A3 — bounded household savings re-entry

**Result: rejected; no default adopted.** Four 116-tick arms completed through 1985Q4.
S0 reproduces the legacy replay digest. Every arm passes existing accounting tolerances;
none passes the frozen economic gates or both terminal floors.

| arm | re-entry fraction | frozen gates | T1 | T2 | T3 | production last 10 | consumption last 10 | liveness | savings draw total | household cash close | spending total | unmet availability | transport pool/freight | blocked share | wage arrears | max money residual | guardrails |
|---|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| S0 | 0 | accounting only | fail | fail | pass | 28,074.08 | 1,667.96 | .1116 | 0 | 10,234,850.83 | 735,344.17 | 2,811,432.29 | .5397 | .7042 | 865,740.56 | 2.24e-9 | pass |
| S025 | .25 | accounting only | fail | fail | pass | 27,972.99 | 1,671.25 | .1107 | 246.81 | 10,239,362.77 | 733,367.96 | 2,815,219.69 | .5428 | .7050 | 863,191.57 | 3.26e-9 | fail: unmet availability |
| S05 | .5 | accounting only | fail | fail | pass | 27,972.99 | 1,671.25 | .1107 | 246.81 | 10,239,362.77 | 733,367.96 | 2,815,219.69 | .5428 | .7050 | 863,191.57 | 3.26e-9 | fail: unmet availability |
| S1 | 1 | accounting only | fail | fail | pass | 27,972.99 | 1,671.25 | .1107 | 246.81 | 10,239,362.77 | 733,367.96 | 2,815,219.69 | .5428 | .7050 | 863,191.57 | 3.26e-9 | fail: unmet availability |

The three nonzero settings are behaviorally indistinguishable on these aggregate outcomes:
the physical availability ceiling limits actual draw to only 246.81 weighted currency units
over the run. Consumption rises by 3.29 but production falls by 101.09, and unmet household
availability rises by 3,787.40. Thus the one small consumption gain does not meet T2 and
comes with a guardrail regression; H-A3 is falsified as a sufficient binding mechanism.

Frozen liveness, service-delivery, treasury-self-financing, and expiry gates remain blocked.
No arm reaches T1 or T2. No calibration or validation claim is made. The opening cash is a
proxy for accumulated savings because this model has no separate household savings account.
Raw compact runs are ignored under `outputs/p05-a3-savings-reentry/`.
