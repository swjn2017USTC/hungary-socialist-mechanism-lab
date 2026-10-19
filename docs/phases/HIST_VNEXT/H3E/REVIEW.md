# H3E Independent Review

Reviewer: repository `phase-reviewer` subagent, read-only.  It did not edit
implementation files.  This document records the independent verdicts and the
repair trail; the implementer does not self-sign a PASS.

## Round 1 — REDESIGN

The first review returned **REDESIGN** against the initial compact
implementation.  The prioritized defects were:

1. P0 information/temporal boundary: unreported bank reserves leaked into
   bounded inputs; funding channels collapsed; full-information mode accepted
   bounded inputs; late reports and non-consecutive quarters were not gated.
2. P0 legacy timing: separate source-release and availability rows allowed the
   same opening stock to fund two uses, with current production covering the
   double spend; service production was pooled across unlike services and
   service demands/edges were prohibited.
3. P0 finance: interest, order financing, shared funding groups, currencies and
   bank-reserve evolution were missing.
4. P0 reference rule: non-conserving arithmetic could forecast consumption
   without deducting seller stock and could clamp cash.
5. P0 demand/objective: `demand_gross` was unused; input shortage used the
   output good's denominator; planned purchases were not separated from
   baseline endogenous orders.
6. P0 execution binding: input/priority/forecast checks were optional, arrays
   could be made writable, and unrelated controls were discarded.
7. P1 measurement: service production was inferred, household quantities were
   scalar totals, settlement was checked only globally, and the price stage
   used a demand index.
8. P1 solver/deadline: exceptions escaped, timeout incumbents were discarded,
   and the deadline was not enforced after the solve.
9. P1 evidence: no four-quarter kernel execution, no three-seed replay, no F2
   profile, and missing replanning/rollback tests.
10. P1 controls: the supervisor asserted success without measuring artifact
    bytes, process-tree RSS, or the failure controls.

## Repairs applied

- Bounded inputs now require and bind funding-group and bank-prepayment
  reports; true balances are redacted; reports and quarters are gated;
  arrays are frozen through immutable byte buffers.
- Added a joint current-resource row, per-good service balances, service split,
  wage/interest pre-deduction, per-quarter order financing, shared funding
  groups and a bank-cash transition.
- Replaced the reference rule with a conserving sequential simulation and a
  certificate that can be `INFEASIBLE`.
- Used gross demand for shortage and its commodity denominator; normalized
  input shortage in the input good; separated baseline procurement.
- Made execution binding mandatory (frozen inputs, sealed plan hash,
  certificate/hash checks) and preserved unrelated controls.
- Added commodity-resolved measurement, independent service production,
  counterparty reconciliation and the corrected stage index.
- Added solver-exception, deadline, timeout-incumbent and hard-deadline
  handling; per-layer constraint fingerprints and bounds/objective matrix
  hashing.
- Added second-quarter replanning, full-state rollback, tampered-input,
  competing-use, unlike-service, cross-bank, shared-group and wage/interest
  tests (40 total).
- Reworked the evidence supervisor to measure process-tree RSS, generated
  artifact bytes and exercised controls, and added a four-quarter three-arm
  three-seed real-kernel profile.

## Round 2 — REDESIGN

The second review returned **REDESIGN**.  The remaining prioritized defects
were:

1. P0 early-service recipes could consume same-quarter purchased fuel,
   creating a zero-time freight-finances-fuel cycle; the service split row
   relaxed production instead of reducing it.
2. P0 bank cash was not carried across quarters; cross-currency trades were
   accepted.
3. P0 the reference rule did not deduct wage/interest, ignored handling, used
   cumulative financing, checked only selected negatives and recorded
   pre-production inventory.
4. P0 `goods_is_service` was writable and unhashed; the plan seal omitted
   certificates/status; execution accepted an empty certificate set.
5. P1 required-report discovery skipped service goods and service-recipe
   inputs.
6. P1 total plan, baseline and incremental request quantities were conflated;
   service measurement was transport-scalar.
7. P1 the F2/full-information profile reused fixed opening balances and the
   planning world was not multi-commodity/F2.
8. P1 supervisor controls were asserted rather than exercised.

## Round 3 repairs applied

- Early-service recipes now consume only opening inputs; the split row uses
  the declared share on production and inflow.
- Bank cash is a carried stock; cross-currency seller/buyer/carrier
  combinations are rejected at declaration time.
- The rule deducts wage/interest, enforces handling, uses a quarter-local
  financing draw, records post-production closing inventory and checks cash
  identity, handling, funding-group and split residuals.
- `goods_is_service` is frozen and hashed; the plan seal includes status and
  certificate identities; execution requires complete ordered all-feasible
  certificates.
- Required reports include service edges/demands/recipes and every recipe
  input.
- Execution records total planned, baseline and incremental quantities, all
  procurement channels, and commodity-resolved service production/use/loss.
- The supervisor enforces runtime RSS/output caps, bounds timeouts by the
  remaining wall allowance, terminates detached descendants, and exercises
  timeout, nonzero-exit and grandchild controls.
- Tests increased to 49, including circular-fuel, split, bank-continuity,
  cross-currency, rule-resource, missing-certificate, semantic-array mutation,
  service-report and baseline-gap cases.

## Round 3 — REDESIGN

The third review returned **REDESIGN**.  Remaining defects:

1. P0 early-service opening-input limits were per recipe, so multiple
   service recipes could spend one opening fuel pool.
2. P0 the reference rule checked only closing cash and could pay wages from
   same-quarter sales receipts.
3. P0 certificate arrays were writable and their contents were not hashed or
   independently validated.
4. P1 required reports omitted the carrier service good and buyer-carrier
   cross-bank freight reports.
5. P1 service loss ignored opening-only service cells; baseline-only planned
   channels were omitted from the plan gap.

## Round 4 repairs applied

- Aggregate early-service opening-input rows per organization/input good.
- Added a pre-receipt funding residual to the rule certificate.
- Deeply froze certificate arrays, included full certificate digests in the
  plan seal, and validate certificate primal/row contents before ticking.
- Added carrier-service and buyer-carrier bank requirements.
- Included opening service cells in service conservation and computed
  total-plan gaps across all planned channels, with incremental gaps separate.
- Tests increased to 52, including shared-fuel, pre-receipt-wage and
  certificate-content mutation cases.

## Round 4 — REDESIGN

The fourth review returned **REDESIGN**:

1. P0 early-service consumption did not reduce the opening stock eligible for
   shipment, so purchased inflows could replenish the same pool.
2. P0 certificate contents were hashed but not independently validated.
3. P0 published prices did not bind executable edge tariffs; freight service
   quantity and freight price were conflated.
4. P1 the full F2 four-quarter planning profile remained `NOT_RUN`, and the
   compact service split/currency interface did not reproduce the legacy
   tier/reservation and currency-channel semantics.

## Round 5 repairs applied

- Early-service consumption is included in the source-release row, so it
  reduces the opening stock that can be shipped.
- Added `verify_plan_certificates`: execution reconstructs base rows, bounds,
  lex locks and objectives and verifies every witness and the derived
  first-quarter payload before ticking.
- Published prices drive purchase affordability, receipts, bank flows and the
  cost objective; `edge_freight_price` is separate from the physical
  `edge_freight_per_unit` service coefficient.
- Total-plan gaps cover all planned channels; opening-only service cells are
  included in service conservation; carrier-service and freight-bank reports
  are required.
- Tests increased to 54, including shared opening fuel, finite invalid
  certificate, and published-price affordability cases.

## Round 5 — REDESIGN

The fifth review returned **REDESIGN**:

1. P0 certificate metadata/residuals and the reference-rule payload were not
   independently validated.
2. P0 the rule could resell same-quarter purchases because it sold from the
   mutable inventory rather than an opening-only shipment pool.
3. P0 published-price conflicts were resolved by report order.
4. P0 service dependency tiers and purpose-specific reservations were missing.

## Round 6 repairs applied

- Certificate validation now checks solver status, reconstructed constraint
  hash, row names/senses/rhs, recorded activity/residual/slack, lex locks and
  the payload derived from the final witness; the rule payload is derived from
  its first-quarter forecast and compared.
- The rule maintains a shipment-eligible opening pool; purchases are not
  resold in the same quarter, and early-service consumption reduces the pool.
- Prices are collected per good and conflicting reports are rejected before
  solving.
- Recipes carry explicit tiers; service-input early recipes may consume only
  lower-tier same-quarter service production, enabling the
  `fuel → heat → freight` chain while blocking cycles.
- Tests increased to 56, including finite-invalid-certificate, shared opening
  pool, price-conflict/order, and service-tier cases.

## Round 6 — REDESIGN

The sixth review returned **REDESIGN**:

1. P0 rule certificates bypassed independent verification; the rule verifier
   trusted editable forecasts.
2. P0 service dependency tiers were not cumulative, and reservations were not
   purpose-specific.
3. P0 the post-1985Q4 reserved validation window was not terminal-masked.
4. P1 the first full-information profile decision still used invented opening
   finances.
5. P1 the full F2 four-quarter planning profile remained `NOT_RUN`.

## Round 7 repairs applied

- Certificate verification runs for every arm; the rule is re-simulated from
  frozen inputs and its checks, purchases, cash and payload are compared.
- Certificate metadata, reconstructed constraint hash, recorded residuals and
  lex locks are validated before execution.
- Service dependency consumption is aggregated per consumer tier; service
  reservations are separated into logistics/productive/household shares, with
  intermediate tier inputs excluded from the productive reservation.
- Decisions in the reserved window and active slots beyond 1985Q4 are
  rejected.
- The full-information profile builds its first decision from current kernel
  inventory, cash and bank reserves.
- Tests increased to 58.

## Round 7 — REDESIGN

The seventh review returned **REDESIGN**:

1. P0 cumulative service tiers were not truly cumulative; intermediate service
   draws were omitted from the physical balance.
2. P0 the reference rule carried non-stockable service inventory across
   quarters.
3. P0 reference-certificate metadata/residuals were not independently
   validated.
4. P1 the required F2 four-quarter planning profile remained `NOT_RUN`.

## Round 8 repairs applied

- Intermediate service draws are in the physical balance and joint rows;
  dependency constraints are cumulative across consumer tiers.
- The rule expires service inventory at each quarter boundary and records zero
  service closing stock.
- Reference certificate metadata, RHS, activities, residuals, slacks, layer
  index, objective and dimensions are compared to a fresh re-simulation.
- Full-information Q1 profile balances come from current kernel state.
- Tests increased to 60, including service conservation, rule expiry and
  conflicting-tier cases.

The F2-scale planning profile is still `NOT_RUN` and is recorded as a scope
blocker in the report; it is not claimed as completed evidence.

## Round 8 — REDESIGN

The eighth review returned **REDESIGN**:

1. P0 productive service inputs were omitted from physical conservation.
2. P0 the LP and rule disagreed on opening-service availability.
3. P1 reference-certificate NaN scalars bypassed verification.
4. P1 the F2-scale planning profile remained `NOT_RUN`.

## Round 9 repairs applied

- Productive service inputs are in `service_balance` and `service_joint`, so
  all service channels share the same physical envelope.
- Opening service stock is usable in the current quarter in both arms; unused
  stock still expires at quarter close.
- Certificate scalar/array finiteness is checked for all arms before
  verification.
- Tests increased to 62.

The F2-scale planning profile is still `NOT_RUN` and is recorded as a scope
blocker; it is not claimed as completed evidence.

## Round 9 — REDESIGN

The ninth review returned **REDESIGN**:

1. P0 the mandatory F2-scale four-quarter planning profile remained `NOT_RUN`.
2. P0 H3E payment measurement failed on a genuine invariant-checked second F2
   tick because it used reconstructed rather than actual allocation prices.
3. P1 the rule computed opening-service reservations from current production
   only, so mixed-share opening service was rejected by the rule but accepted
   by the LP.
4. P2 the report still cited stale test counts, review rounds and supervisor
   caps.

## Round 10 repairs applied

- H3E execution captures the real allocation boundary through
  `routing_trace` and uses its `edge_unit_price` for counterparty settlement;
  a real F2 second-tick regression now reconciles within `ATOL`.
- The rule includes opening service in each reservation allowance, matching
  the LP envelope for mixed shares.
- The report status, test counts, full-suite evidence and supervisor caps were
  reconciled with the current candidate.
- Tests increased to 64.

The mandatory F2-scale planning profile is still not implemented.  The plan's
contingency requires a separate scalable declaration/information/execution
design for that profile; the current compact profile is not presented as a
substitute.  This remains a blocking acceptance gap.

## Round 10 — REDESIGN

The tenth review returned **REDESIGN**:

1. P0 the mandatory F2-scale four-quarter planning profile remains `NOT_RUN`.
2. P0 reference-rule service production could borrow same-tier service.
3. P1 opening service was unavailable to early-service recipes in both
   planning arms.

## Round 11 repairs applied

- Rule production is tier-ordered and uses commodity-specific remaining
  service availability, with opening service included.
- LP dependency rows allow opening service and remain cumulative across tiers.
- Intermediate service draws are separated from purpose-specific reservations
  while remaining in the physical balance.
- Tests increased to 66.

## Final status — BLOCKED

The compact H3E contract is repaired and locally verified, but the mandatory
F2-scale four-quarter planning profile has not been implemented.  The approved
plan's contingency requires a separately scoped scalable declaration/
information/execution design for that profile.  No PASS is claimed and no
local commit is made while this acceptance gap remains.
