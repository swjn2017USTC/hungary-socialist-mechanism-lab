# HIST_VNEXT H3G: counterfactual procurement action space

## Context

H3E's compact planner conflated controlled procurement with endogenous
production and demand.  H3F tried to project the full F2 network into the same
axes; independent review rejected that run because the decision organizations
owned no production capacity, demand shares were used as tonnages, and the
household metric was decision-invariant.  H3G replaces the projection premise:

- production is **exogenous baseline**, not a planning variable;
- demand quantities come from a real baseline kernel tick, not demand shares;
- the controlled action space is only incremental procurement on edges whose
  buyer is a registered procurement organization;
- every arm is compared with a **counterfactual no-plan tick** on the same
  opening state and forcing.

This is a new phase.  It does not claim a full F2 production-planning model.

## Verified facts

- [VERIFIED_BY_RUN] The four baseline ticks move 53,727.74 units in total on
  the 142 controlled edges (17,647.52 in Q1); the submitted arm channel moves
  529–1,332 units over four ticks.
- [VERIFIED_BY_RUN] The baseline demand rows carry real ordered/desired
  quantities; the profile subtracts baseline delivery to obtain residual
  demand.
- [VERIFIED_BY_RUN] The controlled LP has 400 organizations, 16 goods, 142
  edges, 431 demand rows (220 household-final) and no recipes; one four-layer
  solve is feasible in about two seconds.
- [VERIFIED_BY_CODE] `PlanningDeclarations.edge_baseline` is a per-quarter
  lower bound.  Non-controlled edges are fixed at baseline; controlled edges
  may add up to the seller's remaining stock after the baseline trade.
- [VERIFIED_BY_CODE] Baseline trades are settled into opening inventory before
  the LP: seller stock is decremented, buyer stock incremented.  The LP
  therefore does not re-fund or re-settle the baseline.

## Action space

| Element | Treatment |
|---|---|
| production/recipes | exogenous; no planning recipe variables |
| baseline edge flows | settled into opening inventory |
| controlled edges | buyer in `ORG-ENT-A`/`ORG-ENT-B`; lower bound zero, upper bound remaining seller stock |
| other edges | not in the planning axis |
| demand | residual real kernel demand: `max(0, ordered - delivered)` and `max(0, desired - delivered)` |
| decisions | incremental purchases only; `baseline_procurement` is zero because baseline is already in inventory |
| household outcome | measured on a counterfactual baseline tick and the plan tick on the same opening state |

## Arms

1. `historical_rule_based` with bounded inputs.
2. `bounded_planning` with bounded inputs.
3. `full_information_upper_bound` with full-information declarations.

Each arm starts from a fresh F2 state.  For each quarter the evidence runner:

1. copies the opening state and runs one no-plan `tick_material` on the copy;
2. reads that baseline's ordered/desired/delivered demand and edge flows;
3. builds the H3G world and plans;
4. executes the first-quarter decisions on the real state with one
   `tick_material` call;
5. records the plan-minus-baseline household and procurement deltas.

## Acceptance

- All arms complete four ticks; execution is `EXECUTED`, `PARTIAL` or
  `NO_REQUESTS`.
- Every certificate is `FEASIBLE`; no timeout or solver error.
- Material/finance ratios ≤ 1; payment/stock/bank residuals within 1e-9.
- The plan's residual demand is derived from real baseline quantities and is
  strictly below the baseline ordered demand where baseline delivery is
  positive.
- Counterfactual deltas are recorded per tick; a null delta is reported as
  null, not as a planning benefit.
- A forced-order invariance sweep is retained: if large admissible requests
  move edge deliveries but not household realized/unmet, the household metric
  is declared **not comparable** for this action space.  A null is then the
  expected result, and a non-null is a transmission change to investigate.
- `tests/test_hist_counterfactual_profile.py` and the affected H3E suite pass;
  full repository suite and evidence verifier are rerun before commit.
- Source/network/forcing hashes, crosswalk, witnesses and journals are
  retained.

## Limits

- The profile is a procurement sub-model; it does not optimize production or
  investment.
- Baseline and plan ticks share the same opening state and forcing; the plan
  can add procurement but cannot remove the kernel's endogenous baseline
  orders.
- Bounded and full arms currently receive the same opening reports; the phase
  measures action-space effects, not a private-information gap.
- No historical verdict is upgraded.
