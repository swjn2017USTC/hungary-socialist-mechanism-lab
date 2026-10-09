# P06 structural review — Track A7 honest exit

**Outcome: P06 is blocked by a structural design question.** Track A1–A4 have been
measured through 1985Q4 with their declared controls and guardrails. No valid arm meets
both declared terminal floors (T1 production ≥35,092 and T2 household consumption ≥2,085).
No scenario default was changed, and no validation claim is made. Track A5 was ineligible:
its prerequisite of at least two individually terminal-improving candidates did not occur.
Track A6 therefore cannot run.

## Combined arm disposition

“Frozen” lists the five unchanged gates in order: liveness, household service funding,
treasury self-financing, expiry, accounting. T1/T2/T3 are the separate terminal criteria.

| arm | frozen gates | T1/T2/T3 | mechanism result | household guardrails | decision |
|---|---|---|---|---|---|
| A1 input credit 0.25 | F/F/F/F/P | F/F/P | pool/freight .7163; transport zero tick 19 | physical delivery improved, but liveness .0566 | partial; no default |
| A1 input credit 1.0 (A3) | F/F/F/F/P | F/F/P | pool/freight .7163; transport zero tick 19 | liveness .0471; does not close the circuit | partial; no default |
| A1 interest baseline B0 | F/F/F/F/P | F/F/P | interest destroyed 5.315M; Treasury zero tick 18 | unmet 2.811M; consumption 1,668 | control |
| A1 interest remittance I1/I2/I3/C1 | rejected | — | negative bank reserves at ticks 77/50/92/52 | not evaluated after residual | reject arms |
| A1 fiscal-only F1 | F/F/P/F/P | F/F/P | Treasury never zero; fiscal transfer 100,612 | consumption 319; unmet 2.874M | guardrail reject |
| A1 envelope control N1 | F/F/F/F/P | F/F/P | freight pool/need 3.071 | production 13,500; consumption 1,115 | negative control |
| A2 investment-first | F/F/F/F/P | F/F/P | pool/freight .5648, transport 248,585 | consumption 992; unmet 2.933M | falsifies H-A2 |
| A3 savings 0.25–1.0 | F/F/F/F/P | F/F/P | max realized draw 246.81; pool/freight .5428 | consumption 1,671; unmet +3,787 vs control | falsifies H-A3; guardrail reject |
| A4 lean-plan non-stockable | F/F/F/F/P | F/F/P | transport 7,650; pool/freight .0153 | consumption 210; unmet 3.738M | reject target rule |
| A4 lean-plan plus all-activity cap | F/F/F/F/P | F/F/P | transport 3,829; pool/freight .0087 | consumption 212; unmet 3.746M | reject target rule |

Detailed data and remaining metrics are in `P05_INPUT_CREDIT_EXPERIMENT.md`,
`P05_INTEREST_FISCAL_EXPERIMENT.md`, `P05_A2_SOURCE_PRIORITY_EXPERIMENT.md`,
`P05_A3_SAVINGS_REENTRY_EXPERIMENT.md`, and `P05_A4_TARGET_RETEST_EXPERIMENT.md`.

## Hypothesis verdicts

- **H1 (interest/fiscal plan): conditional observation only.** F1 kept Treasury above zero,
  but it violated the household consumption and unmet-availability guardrails; it is not an
  acceptable arm.
- **H2 (interest sink closed): untestable with valid full-horizon evidence.** Every arm that
  changed the interest destination developed negative bank reserves and was rejected. The
  complete non-interest arms improved on legacy money-stock growth in only 51/96 (F1) and
  45/96 (N1) quarters after tick 20, so they do not support H2.
- **H3 (terminal state improves): falsified.** No valid candidate reached T1 and T2.
- **H4 (mechanism sufficient): partial / not met.** Frozen liveness, household service,
  treasury self-financing and expiry gates remain blocked for valid arms; all interest
  transfer arms are rejected on the reserve invariant.
- **H-A2:** falsified; investment-first worsened terminal production, consumption, blocking,
  and household unmet availability despite a small pool/freight increase.
- **H-A3:** falsified as a sufficient mechanism; actual household draw was capped by physical
  availability, no terminal floor passed, and unmet availability regressed.
- **H-A4:** falsified as a route to the terminal floors; both demand-following variants
  collapsed physical and household outcomes.

## Residual blockers and next structural question

The four economic frozen gates still fail: liveness, household service funding, Treasury
self-financing, and expiry. Accounting identities pass on valid arms (money residuals remain
on the order of 10⁻⁹); the interest-transfer arms introduce negative bank reserves and are
rejected. The measured circuits point to binding interactions among source/routing limits,
transport capacity, household access, and financing order. The next work requires redesign
and re-audit of one named mechanism that can connect source availability to feasible regional
delivery while preserving household cash and bank-reserve accounting. The current A1–A4
ladder does not authorize an extra mechanism or parameter search.

Track B remains blocked at B1 pending the user's parameter-to-target linkage; B3 inference
was not run. B2, B4 and D5 are infrastructure-only and do not clear identification,
hold-out, reserved-window, or P06 validation prerequisites. C1 and D1/D2 have their own
clearance records; this structural result does not clear Gate 1 or authorize P06 mechanism
verdicts on historical F2.
