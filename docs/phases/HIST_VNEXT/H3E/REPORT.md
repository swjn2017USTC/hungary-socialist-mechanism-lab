# HIST_VNEXT H3E：有限信息 4Q 滚动规划 — 实现与证据报告

## 1. Status

[VERIFIED_BY_RUN｜技术] The compact H3E implementation and its local test
verification are complete.  Successive independent reviews returned
**REDESIGN**; the concrete P0/P1 defects recorded in `REVIEW.md` were repaired
and re-audited after each round.  The mandatory F2-scale four-quarter planning
profile remains `NOT_RUN` and is a blocking acceptance gap, not completed
evidence.  This file does not claim a reviewer PASS.  The latest verdict is
recorded in `REVIEW.md`.

- Scope: synthetic, legacy quarterly timing, four-quarter planning, three
  literal arms, first-quarter execution through one real `tick_material` call.
- Not claimed: historical identification, historical welfare, national
  causality, 16Q/116Q planning, or a full-engine replacement.

## 2. Authorization and deviations

[VERIFIED_BY_RUN｜流程] The user explicitly authorized coding, independent
review, repair until PASS, and a local commit, and stated that the budget is
ample.  The planning-time gate statements in `PLAN.md` are retained as
historical evidence of the planning snapshot.

[VERIFIED_BY_RUN｜流程] **Deviation.** `PLAN.md` required a single implementation
task explicitly selecting `minimax-code-cn/MiniMax-M3`.  The available task
interface exposes only configured agent roles and has no model-selector
parameter; the main session implemented the phase.  `.omp/config.yml` was not
changed and no paid fallback was invented.  This deviation is recorded, not
hidden.

[VERIFIED_BY_RUN｜流程] No numeric wall/RSS/output/token/cost cap was supplied.
The evidence supervisor uses explicit local caps (`max_wall_s=1800`,
`max_output_bytes=200,000,000`, `max_run_count=400`) and records them in
`ledger.json`.  Model token/cost usage is `NOT_MEASURED`; it is not written as
zero.

## 3. Scope and frozen boundaries

- `source_kind="synthetic"` everywhere.
- Legacy quarterly timing: only opening inventory can fund same-quarter
  outflow or consumption; ordinary production enters next quarter's opening
  stock; services are produced and used or lost in the same quarter.
- Four-quarter horizon; later quarters are
  `forecast_method="last_available_constant"` forecasts, never future kernel
  state or forcing arrays.
- Planning actions are additional procurement requests only.  The kernel's
  baseline endogenous orders remain intact.
- Full information is a technical comparison arm with the same model and
  action space; it receives current true balances, not future truth or
  historical targets.
- No target, session, callback, closure, file path or loader enters the
  planning containers.  Prohibited observation keys remain rejected by the H2A
  observation builder.

## 4. Files

- `src/hsm_lab/planning/proposals.py` — frozen declarations, observation and
  budget bindings, finance/service axes, redacted bounded inputs and
  `build_planning_inputs`.
- `src/hsm_lab/planning/rolling.py` — `plan_quarter`, joint legacy-timing
  rows, per-good service balances, funding/bank transitions, conserving
  reference rule, four lexicographic layers and certificates.
- `src/hsm_lab/measurement/plan_execution.py` — incremental H3E execution:
  mandatory frozen-input binding, sealed plan payload, one real tick,
  full-state rollback, commodity-resolved measurement and counterparty
  reconciliation.  Existing H3C names/semantics are unchanged.
- `tests/test_hist_bounded_planning.py` — 69-test H3E suite.

Evidence root (not committed): `outputs/hist-vnext-h3e-20261019-024126/`.

## 5. Repaired interfaces and behavior

### 5.1 Information and temporal boundary

[VERIFIED_BY_RUN｜测试] `build_planning_inputs` now:

- requires the decision date to fall inside the declared quarter and requires
  four consecutive real quarters;
- derives required reports from every edge seller/buyer, demand buyer, recipe
  organization and non-zero declared inventory/capacity, including service
  goods;
- rejects incomplete reports, duplicate/conflicting reports, missing
  funding-group or bank-prepayment reports, non-finite/negative values,
  publications after the decision date and mismatched currencies;
- binds funding-group reports to the organization's group and bank-prepayment
  reports to the named bank; conflicting channel reports are rejected;
- starts bounded inventory, cash, funding-group capacity and bank reserves
  from published reports only, and redacts true values from the bounded
  declarations container;
- marks the full-information arm `NOT_COMPARABLE` when reported resources
  exceed the true current envelope;
- freezes every array through an immutable byte buffer, so writeability cannot
  be re-enabled.

### 5.2 Physical and financial model

[VERIFIED_BY_RUN｜测试] The planner now has:

- a joint current-resource row per organization/good:
  `outflow + recipe consumption + demand use <= opening + purchases`.  Current
  production cannot fund the same-quarter double spend observed in the first
  review.
- per-service-good balances rather than one pooled service account.  Freight
  consumes the named carrier service good; recipe service inputs and service
  demands are separate; unused production and opening service stock are lost;
  a declared service split caps current use.
- wage and interest pre-deduction, a per-quarter revolving order-financing
  line, shared funding-group envelopes, and a bank-cash stock transition with
  cross-bank pre-funding.  Cross-bank trade without a bank report is blocked.
- gross demand as the shortage target and ordered demand as the executable
  cap; normalization uses the gross commodity denominator.  Production-input
  shortage is normalized in its own input commodity.
- planned purchases separated from declared baseline procurement; only the
  incremental first-quarter quantity becomes a kernel request.

### 5.3 Reference rule

[VERIFIED_BY_RUN｜测试] The historical rule is now a conserving sequential
simulation: production first consumes opening inputs and places ordinary
output in next-quarter stock; purchases draw down shared seller stock, edge
capacity, cash, order financing and the shared funding group; demands consume
remaining inventory or same-quarter service output; receipts and bank flows
are applied; every negative inventory, cash, funding, service-loss or bank
reserve is recorded as a check.  The certificate is `INFEASIBLE` when a check
fails, not an unconditional `FEASIBLE`.

### 5.4 Solver and execution binding

[VERIFIED_BY_RUN｜测试] `plan_quarter`:

- rejects a full-information arm fed bounded inputs and vice versa;
- catches solver exceptions as `ERROR` certificates;
- retains a timeout incumbent as diagnostic evidence but never executes it;
- enforces the shared hard deadline after the solve returns;
- fingerprints the current lex-lock rows per layer and binds the matrix hash to
  bounds and objective coefficients.

[VERIFIED_BY_RUN｜测试] `execute_rolling_proposal` now requires the plan's
frozen `PlanningInputs`, recomputes `inputs.digest()`, checks the sealed
`plan_hash`, input/observation/priority/forecast hashes, certificate input
hashes and read-only arrays.  It merges unrelated existing procurement
requests instead of discarding them.  It still ticks exactly once, rolls back
every state field on failure, and advances the clock once.

### 5.5 Round-2 repairs

[VERIFIED_BY_RUN｜测试] The second review round's P0/P1 defects were
repaired:

- early-service recipes now consume only opening inputs, so purchased fuel
  cannot finance the freight that delivers it; the service split row reduces
  available production by the declared share instead of relaxing it;
- bank cash is carried through every active quarter, and cross-currency
  seller/buyer/carrier combinations are rejected at declaration time;
- the reference rule deducts wage and interest, enforces handling capacity,
  uses a quarter-local financing draw, records post-production closing
  inventory and checks cash identity, handling, funding-group and service
  split residuals independently;
- `goods_is_service` is frozen and included in the input digest; the plan seal
  includes status and certificate identities; execution requires a complete,
  ordered, all-feasible certificate set;
- required reports now include service edges/demands/recipes and every recipe
  input, not just stockable goods;
- execution separates total planned, declared baseline and incremental request
  quantities, measures all procurement channels, and reports service
  production/use/loss by commodity from the activity-output matrix;
- the supervisor enforces runtime RSS/output caps, bounds the timeout by the
  remaining cumulative wall allowance, terminates detached descendants, and
  exercises timeout, nonzero-exit and grandchild controls.

### 5.6 Round-3 repairs

[VERIFIED_BY_RUN｜测试] The third review's remaining defects were repaired:

- early-service opening-input limits are aggregated per organization/input
  good across all service recipes, so multiple recipes cannot spend the same
  opening fuel pool;
- the reference rule enforces a pre-receipt funding check (wage/interest and
  purchases before sales receipts), in addition to its closing identities;
- certificate arrays are deeply frozen, the plan seal includes each
  certificate's full substantive digest, and execution independently rejects
  non-finite or wrong-axis certificate primal/row payloads;
- required reports include the carrier's service good and every cross-bank
  freight leg, and required bank reports include buyer-carrier differences;
- service conservation includes opening service cells even when current
  production is zero; total-plan gaps are computed across all planned
  procurement channels, including baseline-only channels, while incremental
  gaps remain separate;
- the supervisor enforces runtime RSS/output caps, bounds timeouts by the
  remaining cumulative wall allowance, terminates detached descendants and
  exercises timeout, nonzero-exit and grandchild controls.

### 5.7 Round-4 repairs

[VERIFIED_BY_RUN｜测试] The fourth review's P0 defects were repaired:

- early-service consumption is subtracted from the same opening pool that
  funds shipment, so purchased inflows cannot replace fuel already consumed by
  early service production;
- execution reconstructs the frozen LP rows, bounds and lex locks from the
  plan inputs, verifies every certificate witness independently, and derives
  the first-quarter payload from the final witness before ticking;
- published prices bind purchase affordability and settlement; the physical
  freight-service coefficient and the freight tariff are separate fields;
- total-plan gaps cover all planned channels, including baseline-only
  channels; service conservation includes opening-only service cells;
- required reports include carrier service goods and buyer-carrier
  cross-bank freight legs.

### 5.8 Round-5 repairs

[VERIFIED_BY_RUN｜测试] The fifth review's P0 defects were repaired:

- certificate verification now validates solver-success claims, reconstructed
  constraint hashes, row metadata, recorded activities/residuals/slacks, lex
  locks and the derived first-quarter payload; the reference rule's payload is
  also derived and compared to its forecast;
- the rule keeps a separate shipment-eligible opening pool, so purchases
  received in the same quarter cannot be resold, and early-service consumption
  reduces that pool;
- published prices are collected per good and conflicting reports are rejected
  before solving, removing observation-order dependence;
- service recipes carry explicit dependency tiers, allowing `fuel → heat →
  freight` same-quarter dependencies while forbidding higher-tier inputs.

### 5.9 Round-6 repairs

[VERIFIED_BY_RUN｜测试] The sixth review's P0 defects were repaired:

- `verify_plan_certificates` is invoked for every arm; the reference rule is
  re-simulated from frozen inputs and its certificate checks, purchases, cash
  and derived payload are compared to the plan before execution;
- certificate validation checks solver-success claims, reconstructed
  constraint hashes, row metadata, recorded activity/residual/slack, lex locks
  and the payload derived from the final witness;
- service dependency rows are aggregated per consumer tier, so tier-1
  consumers cannot collectively consume more than lower-tier production;
- service reservations are separated into logistics, productive and household
  channels with the three declared shares; intermediate service-tier inputs
  are excluded from the productive reservation, preserving acyclic chains;
- decisions in the reserved post-1985Q4 validation window are rejected, and
  any active terminal slot beyond 1985Q4 is rejected;
- the first full-information profile decision is now built from current kernel
  inventory, cash and bank reserves, not fixed declarations.

### 5.10 Round-7 repairs

[VERIFIED_BY_RUN｜测试] The seventh review's P0 defects were repaired:

- intermediate service draws are included in the physical service balance and
  joint-availability rows; dependency rows are cumulative across consumer
  tiers, so tier-1 consumers cannot collectively exceed lower-tier production;
- the reference rule expires non-stockable service inventory at every quarter
  boundary and records zero service closing stock;
- reference-certificate verification compares constraint hash, row metadata,
  RHS, activities, residuals, slacks, layer index, objective and dimensions
  against a fresh re-simulation;
- the full-information profile now builds its first decision from current
  kernel inventory, cash and bank reserves.

The remaining planned F2-scale four-quarter planning profile is still
`NOT_RUN`; the profile exercises the real compiled two-region kernel but its
planning declaration is a reduced single-commodity world.  This is recorded as
a scope blocker, not as completed F2 evidence.

### 5.11 Round-8 repairs

[VERIFIED_BY_RUN｜测试] The eighth review's P0/P1 defects were repaired:

- productive service inputs are included in the physical service balance and
  joint-availability rows, not only in the reservation row;
- opening service stock is usable in the current quarter by the LP, matching
  the reference rule and the legacy kernel; unused opening service still
  expires at quarter end;
- certificate scalar finiteness is checked for every arm before verification,
  so a NaN objective cannot bypass the reference comparison;
- tests increased to 62, including productive-service conservation,
  opening-service usability and service-expiry cases.

The F2-scale planning profile remains `NOT_RUN` and is recorded as a scope
blocker in the report, not as completed evidence.

### 5.12 Round-9 repairs

[VERIFIED_BY_RUN｜测试] The ninth review's P0/P1 defects were repaired:

- execution captures the real allocation boundary via `routing_trace` and
  reconciles payments against its actual edge unit prices; a genuine F2
  second-tick regression passes;
- the rule includes opening service in its reservation allowances, aligning
  mixed-share cases with the LP;
- the report and evidence counts were reconciled with the current candidate.

The full F2-scale planning profile remains `NOT_RUN` and is a blocking
acceptance gap.  A scalable F2 declaration/information/execution mapping is
required as a separate design; the compact profile is not substituted for it.

### 5.13 Round-10 repairs

[VERIFIED_BY_RUN｜测试] The tenth review's service-model defects were repaired:

- the reference rule processes recipes in dependency-tier order with
  commodity-specific remaining service availability; same-tier or higher-tier
  service cannot be borrowed;
- opening service is included in the LP dependency envelope and in the rule's
  tier-ordered availability;
- intermediate service draws are separated from purpose-specific productive
  reservations, while remaining in the physical balance;
- tests increased to 66, including same-tier cycle rejection and opening
  service feeding a tier-1 service recipe.

The mandatory F2-scale four-quarter planning profile remains `NOT_RUN`.  The
approved plan's contingency requires a separately scoped scalable design for
that profile; it is a blocking acceptance gap and is not replaced by the
compact profile or C0/C1.

### 5.14 Measurement

[VERIFIED_BY_RUN｜测试] Execution measurement now reports commodity-resolved
household realized/unmet and procurement requested/delivered/allocated
quantities, independently measures transport service production from
`activity_realized`, reconciles payments through the existing counterparty
and non-organization helpers (not only global totals), and uses the demand
destination cell for the price stage.

## 6. Verification evidence

All commands ran from the project root in `.venv`.

| Check | Result |
|---|---|
| `pytest tests/test_hist_bounded_planning.py` | **69 passed** |
| Related H3 suites (`tiny_execution`, `service_semantics`, `procurement_credit`, `routing_feasibility`, `lead_time`) | **175 passed** |
| Full `pytest` | **1,326 passed, 180 warnings in 100.76 s** |
| `ruff check --no-cache src tests` | **All checks passed** |
| `uv lock --check --offline` | **Resolved 101 packages in 12 ms** |
| `hsm baseline verify --json` | **status ok**, SHA256 `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` |

Protected hashes:

```text
BASELINE.md                   1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f
config/research_contract.json 6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82
uv.lock                       9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9
```

### 6.1 Reproduced counterexamples

[VERIFIED_BY_RUN｜技术] `reproduce.json`:

- transport opening 0: legacy `allocated=10`, `delivered=0`,
  `service_used=0`, `service_fee=0`;
- transport opening 1: legacy `allocated=10`, `delivered=10`,
  `service_used=1`, `service_fee=0.9090909090909091`;
- rule and bounded observation hashes equal;
- bounded and full-information plans are both feasible on the same
  declaration; when reports equal true balances the technical bound is
  identical (a legal null, not fabricated benefit).

### 6.2 Four-quarter, three-arm, three-seed execution

[VERIFIED_BY_RUN｜技术] `profile4.json` now runs the real two-region kernel for
**four consecutive executed quarters** per arm and seed, rebuilding
observations and re-planning before each later quarter.  Seeds 1729/1730/1731
are paired engineering replays, not stochastic historical replicates.

Results (identical across seeds because the fixture is deterministic):

| Arm | Q1 | Q2 | Q3 | Q4 |
|---|---|---|---|---|
| rule | EXECUTED | NO_REQUESTS | EXECUTED | NO_REQUESTS |
| bounded | EXECUTED | EXECUTED | EXECUTED | EXECUTED |
| full information | EXECUTED | EXECUTED | EXECUTED | EXECUTED |

Each record includes planned purchases/shortfall, submitted decisions, actual
delivery and settlement, commodity-resolved household realized/unmet,
service produced/used/lost/expiry, journal rows, gate ratios and residual
checks.  No arm is claimed to improve welfare: the records are the measured
actuals and any null is preserved.

### 6.3 C0/C1

[VERIFIED_BY_RUN｜技术] Both scenarios ran under a supervisor with seed 1729,
116 ticks, 1957Q1–1985Q4:

| Scenario | deterministic_replay_digest | parameter_hash |
|---|---|---|
| C0 `historical_f2_replay` | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` | `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445` |
| C1 `historical_f2_trade_scenario` | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` | `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90` |

Both manifests report `status="completed"`, `completed_ticks=116` and
`last_completed_quarter="1985Q4"`.

### 6.4 Supervisor controls

[VERIFIED_BY_RUN｜技术] `controls.json` reports `PASS` for exercised controls:
exclusive output-directory creation, run-count/wall/output pre-launch caps and
detached-descendant termination.  The supervisor counts generated artifacts,
samples process-tree RSS every 0.2 s, and reconciles the ledger output total to
the actual evidence-root bytes (`39,754,704` bytes, under the 200 MB cap).
Two early failed launches are retained under `matrix-failed-path` and
`reproduce-failed-path`; a later `--exec` separator mistake is retained as an
empty exec directory.  They are not presented as successful evidence.

## 7. Remaining reductions

- The planning world is a compact synthetic model over organizations,
  commodities, edges, demands and Leontief recipes.  It is not the full engine
  network compiler.
- Order financing is modelled as a per-quarter revolving authorized line plus
  a shared funding-group envelope and bank-cash transition.  The full H3B
  procurement-credit funnel is not reimplemented in the planning LP; the real
  kernel still applies its own finance rules during execution.
- One synthetic currency is modelled.  Cross-currency trades are rejected
  rather than converted implicitly.
- The planner's per-good service balance uses the declared current-use share;
  the engine's full staged tier masks are not reproduced in the compact
  planner.  Early-service production is restricted to opening inputs.
- The four-quarter execution profile runs on the real compiled two-region
  multi-commodity network, but a full F2-scale H3E planning world (all F2
  organizations/commodities and decision cells) is `NOT_RUN`; the C0/C1
  scenarios are regressions, not that profile.
- No micro-stage/lead-time adapter is used.  Legacy timing is explicit; H3D is
  not a dependency.
- Plan/actual gap is measured on the total procurement demand channel, not as
  an incremental counterfactual; baseline endogenous orders are retained.
- Full information is a technical bound for the declared model, not a
  historical behaviour or national upper bound.  Identical arm outcomes on
  accurate reports are reported as a null.
- 16Q and 116Q planning profiles are `NOT_RUN`; the four-quarter contract is
  the registered H3E scope.
- Model token/cost usage is `NOT_MEASURED`.

## 8. Reproduce commands

```sh
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_bounded_planning.py
.venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/python outputs/hist-vnext-h3e-20261019-024126/run_h3e.py --mode matrix
.venv/bin/python outputs/hist-vnext-h3e-20261019-024126/run_h3e.py --mode reproduce
.venv/bin/python outputs/hist-vnext-h3e-20261019-024126/run_h3e.py --mode profile4
.venv/bin/python outputs/hist-vnext-h3e-20261019-024126/run_h3e.py --mode controls
.venv/bin/python outputs/hist-vnext-h3e-20261019-024126/run_h3e.py --mode exec -- .venv/bin/hsm run --scenario historical_f2_replay --output-dir outputs/hist-vnext-h3e-20261019-024126/C0 --json
.venv/bin/python outputs/hist-vnext-h3e-20261019-024126/run_h3e.py --mode exec -- .venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir outputs/hist-vnext-h3e-20261019-024126/C1 --json
```

## 9. Review and commit

Successive independent reviews returned **REDESIGN**; each concrete P0/P1
defect was repaired and re-audited.  The latest review still identifies the
mandatory F2-scale four-quarter planning profile as missing.  Under the
approved plan's contingency, that scale-up requires a separate declaration/
information/execution design rather than a reduced profile or an expanded
whitelist; it is retained as a blocking acceptance gap.

No local commit is made while the verdict remains non-PASS.  The reviewable
diff is limited to the four whitelisted source/test paths plus the three H3E
phase documents.

The separately scoped H3G phase now supplies an F2 counterfactual procurement
profile with a PASS verdict.  It deliberately treats production as exogenous
baseline and establishes a structural-null household result; it does not fill
the full production-planning gap claimed here.
