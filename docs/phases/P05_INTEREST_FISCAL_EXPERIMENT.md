# P05 A1 — interest sink and treasury circuit

**Result: no mechanism adopted; the candidate is partial and blocked by accounting and
household guardrails.** All runs use 116 ticks through 1985Q4. Default B0 retains the
legacy digest `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`.

| arm | result | frozen gates | T1/T2/T3 | liveness | service ratios g03/g15/g16 | treasury zero tick | max expiry | interest destroyed / remitted | fiscal remitted | production / consumption last 10 | transport / pool-freight | blocked share | household unmet | wage arrears | max money residual | guardrails |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| B0 | measured | accounting only | F/F/P | .1116 | .0095/.2195/.3379 | 18 | .9423 | 5,314,921 / 0 | 0 | 28,074 / 1,668 | 272,066 / .5397 | .7042 | 2,811,432 | 865,741 | 2.24e-9 | pass |
| I1 | rejected: negative bank reserves at tick 77 | rejected | — | — | — | — | — | — | — | — | — | — | — | — | residual | n/a |
| I2 | rejected: negative bank reserves at tick 50 | rejected | — | — | — | — | — | — | — | — | — | — | — | — | residual | n/a |
| I3 | rejected: negative bank reserves at tick 92 | rejected | — | — | — | — | — | — | — | — | — | — | — | — | residual | n/a |
| F1 | measured; guardrail rejected | liveness/service/expiry fail; Treasury + accounting pass | F/F/P | .1082 | .0094/.2230/.3294 | never | .9429 | 5,419,536 / 0 | 100,612 | 26,603 / 319 | 253,530 / .5192 | .7064 | 2,873,997 | 814,170 | 3.06e-9 | fail: consumption and unmet availability |
| C1 | rejected: negative bank reserves at tick 52 | rejected | — | — | — | — | — | — | — | — | — | — | — | — | residual | n/a |
| N1 | measured negative control | accounting only | F/F/P | .0396 | .0086/.1788/.2584 | 48 | .9478 | 5,393,678 / 0 | 0 | 13,500 / 1,115 | 1,470,032 / 3.0711 | .4775 | 2,207,287 | 322,128 | 3.26e-9 | fail: terminal consumption |

The four interest-remittance arms (I1–I3 and C1) fail closed on a genuine new invariant:
bank reserves become negative before the horizon. They are rejected and supply no
full-horizon mechanism evidence. The fiscal-only F1 keeps the treasury positive throughout,
but cuts terminal household consumption from 1,668 to 319 and increases unmet availability;
it is rejected by the registered guardrail. N1's envelope-only contrast has lower unmet
availability but much worse production, consumption, liveness, and service ratios.

For H2, among the complete runs, quarter-on-quarter money-stock growth exceeded B0 in only
51/96 post-tick-20 quarters for F1 and 45/96 for N1; these arms do not operate the interest
remittance rule. No accepted interest arm supplies the full trace needed to test H2. Therefore
H2 is **not established and not validly testable with the rejected transfer arms**. H1 is
observed for F1 (treasury never reached zero), but that arm is guardrail-rejected. H3 is
falsified: no valid arm reaches both T1 and T2. H4 is partial: liveness, service, treasury
self-financing, and expiry remain blocked on valid measured arms. No validation claim is made.

Raw compact outputs: ignored under `outputs/p05-interest-fiscal-arms/`.
