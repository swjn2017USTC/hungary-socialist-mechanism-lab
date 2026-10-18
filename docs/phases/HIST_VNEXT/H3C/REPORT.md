# H3C Report — explicit routes, sources and transport feasibility certificates (v2)

## Status

**PASS — independent v2 review complete; committed candidate.**  The v1
full-demand plan was BLOCKED at the real F2 1957Q1 boundary.  The user
authorized a redesign on 2026-10-18.  v2 adds an
explicit non-negative shortfall vector `s[D]`, minimises `sum(s)` as a
technical routing objective, and distinguishes:

- `EXECUTED` — zero shortfall, full witness;
- `PARTIAL` — positive shortfall with exact non-household edge execution and
  `shortfall[d] = demand[d] - delivered[d]`.

The real `historical_f2_replay` 1957Q1–1957Q4 profile now completes four ticks
as `PARTIAL`, with zero edge gap, zero stock residual, bank residual below
`1.8e-10`, and exact shortfall reconciliation.  No demand, initial resource,
forcing or kernel rule was changed.  The shortfall is exported, not hidden.

## Authorization and execution contract

The user authorized coding, commit and the redesign:

> 好，我授权修订。按你自己觉得最合适的REDESIGN方案进行，再重新跑独立 review → PASS → commit。

v2 execution contract (prospective, recorded in `PLAN.md`):

- implementation model selector `deepseek/deepseek-flash`;
- `reasoning_effort = NOT_SET`; `input_tokens`/`output_tokens = NOT_MEASURED`
  (not a false zero); `paid_cost_cap = 0.0`; no paid model call;
- operational limits `max_wall_s=3600`, `max_rss_bytes=4 GiB`,
  `max_new_output_bytes=512 MiB`, `max_run_count=80`, sampled every 0.2 s and
  enforced by the evidence runner;
- the v1 MiniMax-M3/main-session prohibition is superseded by the user’s
  explicit redesign authorization.

The original v1 budgets remain `NOT_SET`; v2 does not retroactively certify
the v1 run as budget-compliant.

## Implemented interfaces

### Material boundary hook (`tick_material`)

- Keyword-only `routing_allocator: Callable[[Mapping[str, Any]], np.ndarray]`
  and `routing_trace: dict[str, Any] | None`; default `None` preserves the
  legacy allocation path.
- Boundary built only at the real step-5 allocation point, after orders,
  finance, trade and the recomputed service price.  Every array is an
  independent read-only copy.
- Exports canonical edge/source/demand/cell axes, `stock_open`, `import_into`,
  `produced_into`, `source_available`, `logistics_pool`,
  `handling_capacity`/`handling_work_per_unit`, service split, complete
  `desired`/`gross`/`ordered`, real `edge_unit_price`, transport per-unit,
  self-haul flags, funding groups/cash, plot pool, Treasury cash, bank
  reserves, buyer/seller/carrier banks, and the early-service metadata.
- Imports are counted once: `source_available` is exactly boundary
  `state.stock_value` (`realize_imports` already credited the import cells).
- Fallback validator/rows constrain prior-tier + fallback shipments by
  `stock_open + import_into`.
- The real pre-allocation `flows` reference is published before the callback,
  so a rejected certificate still exports prelude flows/journals.
- Trace-only mode is byte-identical to the legacy path; invalid allocator
  vectors raise `HIST_H3C_ROUTING` before stock moves.

### Feasibility (`planning/feasibility.py`)

- Shared axis `x[M]`, `u[S]`, `v[D]`, `s[D]`.
- `sum(x by demand) + v + s = demand`; `s >= 0`, `s <= demand`.
- LP-0: free transfer; LP-1: `u=v=0` + physical/release/logistics/handling/
  service-cell rows; LP-2: LP-1 + ordered/funding/bank rows.
- Objective: minimise `sum(s)` (technical shortfall, not welfare).
- `solve_routing_feasibility` recomputes every row residual/slack and all
  variable bounds; statuses `FEASIBLE / INFEASIBLE / TIMEOUT / ERROR`.
- `verify_certificate` rebuilds rows/hashes/fingerprints and validates
  `x/u/v/s` shapes, finiteness, non-negativity, bounds and `no_demand`.
- `compare_routing_certificates` rebuilds prefixes and sends each feasible
  witness back to lower levels.

### Execution and measurement (`measurement/plan_execution.py`)

- One real `tick_material` call per arm, then the existing material gate,
  optional H3B procurement funnel, and read-only measurement.
- LP-2 `EXECUTED`/`PARTIAL` commits only when:
  - no free flow, no projection;
  - every non-household delivered edge equals planned `x`;
  - `shortfall[d] = demand[d] - delivered[d]`;
  - payment/stock/bank reconciliation passes.
- LP-0/LP-1 project downward, measure the real kernel attempt and restore
  the pre-tick state.  `NO_DEMAND` does not advance the clock.
- Payment reconciliation decodes raw journals through
  `build_account_directory`; organization purchases/receipts and
  buyer→seller/carrier pairs are checked; household checkout is separated
  from routed procurement; plot funding uses the represented
  household→clearing leg and exact regional payer identity; Treasury/plot
  counterparties are checked by payer group.
- Failure evidence retains phase, cause, failed flows (including prelude),
  trace, certificates and arbitrary-dimensional arrays.

## Test matrix (26 passed)

`tests/test_hist_routing_feasibility.py` covers the v2 matrix and review
regressions:

| Case | Observed |
|---|---|
| transport opening 0 | legacy 10/0/0; LP-0 `RELAXATION_ONLY`; LP-1/2 zero real flow with shortfall 10; LP-2 `PARTIAL` |
| positive transport | LP-2 `EXECUTED`; delivered 10, service use 1, fee 0.909…, seller 10, carrier fee, buyer 10+fee, shortfall 0 |
| broken unique edge | LP-0 free transfer, shortfall 0; LP-1/2 zero real flow, shortfall 10 |
| carrier capacity 0 / logistics pool 0 | LP-0 shortfall 0; LP-1/2 shortfall 10 |
| current production vs next quarter | Q1 `PARTIAL` shortfall 5; Q2 `EXECUTED` |
| cash only for goods, not freight | LP-2 `PARTIAL`; delivered < 10; exact shortfall |
| wage/interest prelude | boundary cash 2.0; LP-2 `PARTIAL`; LP-1 execution reports a gap |
| zero buyer-bank reserve | LP-2 `PARTIAL` zero delivery; funded control `EXECUTED` |
| shared source/carrier | two demands share one source/carrier without overcommitment; real LP-2 execution |
| swapped goods recipient | measurement rejects the tampered journal |
| bad certificate | NaN `u` / modified `constraint_hash` rejected; state rolled back |
| no-demand flag | derived from the problem; relabelled certificate rejected |
| nested comparison | same problem nested; changed price `nested=false` |
| trace-only vs default | canonical bytes identical; invalid vectors rejected |
| zero demand | `NO_DEMAND`, clock unchanged |
| full gross | `problem.demand == boundary["demand_gross"]` |
| imports | `source_available` = boundary `state.stock_value`, not double-counted |
| fallback | prior-tier + fallback rejected when opening supply is exhausted |
| mixed channels | 6-unit procurement + 4-unit household checkout, zero payment residual |
| weighted plot | weight 2 / size 1 funding, zero residual |
| regional clearing | R0→R1 clearing-account swap rejected by exact payer identity |
| wage LP-1 | LP-1 witness executed on the same pre-tick state |
| account kind | seller receipt redirected to loan liability is rejected |
| suboptimal certificate | modified shortfall witness rejected by optimality recheck |

Evidence: `matrix/matrix.json` reports `26 passed in 0.90s`.

## Real F2 4-quarter profile

`profile4/profile4.json`, seed 1729, complete gross demand, all four ticks:

| quarter | status | shortfall | edge gap | shortfall residual | stock residual | bank residual |
|---|---|---:|---:|---:|---:|---:|
| 1957Q1 | PARTIAL | 30,576.498 | 5.7e-14 | 1.1e-13 | 0.0 | 5.8e-11 |
| 1957Q2 | PARTIAL | 16,848.749 | 2.8e-14 | 1.1e-13 | 0.0 | 1.2e-10 |
| 1957Q3 | PARTIAL | 36,665.006 | 2.8e-13 | 2.8e-13 | 0.0 | 1.5e-10 |
| 1957Q4 | PARTIAL | 49,158.479 | 2.8e-14 | 2.8e-14 | 0.0 | 1.7e-10 |

The shortfall is the real boundary shortfall, not a demand reduction: the
complete gross vector is unchanged, and the minimised `sum(s)` is a technical
maximal-delivery bound.  The Q1 physical deficits remain visible as
`g09_basic_food` 9,463.739 and `g10_animal_food` 11,868.750 in the exported
per-demand shortfall vector; later quarters have their own partial shortfalls.

## Tiny 4-quarter closure

`tiny4/tiny4.json`: 40 opening energy, 4 carrier fuel, no mid-run injection;
all four LP-2 ticks `EXECUTED` with delivered 10, shortfall 0, nine journal
rows, source stock 30/20/10/0.  LP-0/LP-1 certificates are executed on
same-pre-tick copies and recorded.

## Verification

| Check | Result |
|---|---|
| `pytest -q -p no:cacheprovider` | **1154 passed** |
| `pytest tests/test_hist_routing_feasibility.py` | **26 passed** |
| `ruff check --no-cache src tests` | clean |
| `uv lock --check --offline` | `Resolved 101 packages` |
| `hsm baseline verify --json` | `status=ok`, `1f5b23…` |
| C0 116 ticks, seed 1729 | `92f9ea0a…a42d`, parameter hash `e27ade…0445` |
| C1 116 ticks, seed 1729 | `c4810481…18d5`, parameter hash `632ee6…3b90` |
| protected files before/after | unchanged |
| v2 operational limits | process-group supervisor; no violation recorded |
| verification commands | recorded in `verification/verification.json`; not claimed under the hard supervisor (narrow v2 contract) |

The hard-limit supervisor covers the four `run_h3c.py` modes.  Final pytest,
ruff, lock, baseline and C0/C1 commands are recorded with hashes in
`verification/verification.json`; they are not retroactively claimed as
hard-limit-enforced.  The v2 evidence root is
`outputs/hist-vnext-h3c-20261018-140000/`; the earlier blocked v1 candidate is
preserved under the prior root.

## Technical / structural / historical ledger

- **Technical**: matrix, counterexample, tiny4, profile4, payment/nesting/
  rollback and C0/C1 are `VERIFIED_BY_RUN`.
- **Structural**: new modules/docs are `VERIFIED_BY_CODE`; default-off hook
  remains, no CLI/default-runner integration.
- **Historical**: `UNIDENTIFIED / NOT_RUN`.  This is a synthetic
  full-information technical routing/shortfall bound, not a historical
  planner or a national infeasibility proof.

## Commit status

The v1 blocked candidate is preserved under the prior evidence roots.  The v2
candidate received the independent PASS above and is committed as a local
small commit; no push.
