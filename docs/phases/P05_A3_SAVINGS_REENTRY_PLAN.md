# P05 Track A3 — bounded household savings re-entry

Status: pre-registered experiment; default remains zero. The existing household budget
uses current receipts only and parks voluntary/forced savings in household cash. Test a
bounded share of opening cash above current-quarter receipts as additional purchase
capacity, debited only through the existing goods-payment path. The opening-cash balance is
the available proxy for accumulated savings; no separate synthetic deposit is created.

## Declaration and arms

Declare `household_savings_reentry_fraction: FiniteFraction = 0.0`, include it in
`MaterialParameters.flatten()` and the parameter registry, and classify it as `fixed`
(structural rule; not fitted). The already-declared `household_savings_draw` flow records
the portion of actual household spending above the current-income budget; do not add a
field to `MaterialTickFlows`.

- S0: 0.0 control.
- S025: 0.25 of opening cash above current receipts.
- S05: 0.50.
- S1: 1.00.

Budget never exceeds opening cash. Current-income spending is protected in the budget
calculation; savings are drawn only to the extent that goods are actually purchased above
that budget. Run 116 ticks through 1985Q4 only.

## Checks, guardrails, decision

Test zero-default omission from the parameter hash, bounded parameter validation, the
draw cap, and the household cash identity. Every arm must pass all existing accounting
gates with no new residual. Record all frozen gates and T1–T3, terminal production and
consumption, liveness, service ratios, expiry, treasury, transport, household unmet
availability, spending/cash, and wage arrears. An arm is guardrail-rejected if terminal
consumption falls below S0 or household unmet availability rises above S0.

H-A3: parked household balances constrain the terminal circuit. Support requires a valid
arm to improve both T1 and T2, with no guardrail regression. If no valid arm reaches both
terminal floors, continue to A4 as required by the master plan; do not add any unplanned
mechanism. No default change or calibration claim is allowed.
