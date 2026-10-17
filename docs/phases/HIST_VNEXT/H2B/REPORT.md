# H2B Report — validated decision → TickControls → material kernel

## Authorization
User explicitly authorized H2B Coding and Commit on 2026-10-18. The earlier
admission-blocking plan remains in the repository as the policy record.

## Prerequisite gates
| Phase | Independent verdict |
|---|---|
| H0A | PASS |
| H0B | PASS |
| H1B | PASS |
| H2A | PASS |

## Implemented bridge
- `src/hsm_lab/institutions/execution_adapter.py`:
  - accepts only decisions whose H2A `ValidationResult.is_legal` is true, whose
    `decision_id` matches, and whose quarter equals the kernel's
    `forcing.quarters[state.completed_ticks]`;
  - resolves the scenario-owned organization crosswalk explicitly (no name
    guessing) and the commodity index from the material network;
  - translates a procurement request into the existing `TickControls` surface,
    preserving any caller-supplied `material_parameters`, household parameters/
    catalog, `autonomy`, `central_target` and `policy`;
  - captures opening stocks, runs exactly one `tick_material`, runs
    `check_material_invariants` with the same controls, and advances
    `completed_ticks` only after the gate passes;
  - returns kernel flows and a trace (decision, control applied, requested,
    delivered, buyer payment, plan–actual gap, binding status, clock).
- `src/hsm_lab/engine/policy.py`: added `TickControls.procurement_requests`
  `((organization_idx, commodity_idx, quantity), ...)`.
- `src/hsm_lab/engine/material.py`: applies those requests to the procurement
  hub's commodity demand cells after the kernel computes its normal
  procurement orders. The kernel still owns ordering, allocation, delivery,
  payments and accounting; the control never writes stocks or accounts.

## Acceptance evidence
`tests/test_hist_tiny_execution.py` (20 tests):
- legal procurement delivers a nonzero quantity; buyer pays and the producer
  receives;
- CANCEL is a nonbinding zero request;
- illegal permission, quarter mismatch, unmapped institutional identity and
  unknown commodity are rejected without state/clock mutation;
- two quarters advance exactly once each; an out-of-quarter replay is rejected before the tick, and an injected invariant failure restores the opening state;
- zero buyer cash does not overdraw;
- existing `TickControls` autonomy/central target are preserved;
- `central_target=3` binds at `autonomy=0` and the local target 5 binds at
  `autonomy=1`;
- a two-region × two-commodity × two-quarter fixture delivers energy and food
  in successive quarters.

## Verification
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_hist_tiny_execution.py
# → 20 passed
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
# → 1100 passed
.venv/bin/ruff check --no-cache src tests
# → all checks passed
```

## Review repairs (2026-10-18)
| ID | Finding | Repair |
|---|---|---|
| R1 | Retrospective validation could execute | Execution requires `mode="admission"`, `admission_eligible=True`, and a matching decision payload digest |
| R2 | Failed ticks left mutated stocks/accounts | Tick + invariant gate are transactional: any exception or residual failure restores a deep copy of the pre-tick state |
| R3 | Organization-specific control could become another buyer's order | Kernel requires an owner-matched procurement cell; adapter rejects unwired destinations before ticking and requires an explicit crosswalk (no numeric fallback) |
| R4 | Trace conflated background and incremental activity | A baseline tick without the request is run on a copy; trace reports baseline, total and incremental delivery/payment and the incremental gap |
| R5 | Tests fabricated validation | New cases cover retrospective rejection, payload substitution, invariant rollback, wrong-destination rejection, and admission-bound validation |
| R6 | Payload binding could be bypassed by a shadowed `model_dump_json` | The exact-type/storage boundary runs before any decision serialization; undeclared/shadowed fields reject |
| R7 | Payment attribution used all-commodity organization purchases | Trace now derives commodity goods payment from delivered quantity × the commodity's compiled price, and reports organization-wide purchases separately |
| R8 | No execution test used real H2A admission | Added end-to-end observation/calendar/session admission execution and a revoked-authority rejection with state/clock isolation |
| R9 | Commodity-only procurement mask split an order across raw/ready channels | The kernel and adapter match the commodity's consumable stage; a raw-only destination is unwired |
| R10 | Unmatched `procurement_requests` were silently dropped | The kernel raises `ValueError` for an unmatched organization, commodity or zero-share destination; a regression covers the direct-control path |

## Known limits
- Only `ProcurementDecision` is bridged in this minimal phase; price,
  investment and household-need decisions report “no existing TickControls
  mapping” rather than writing state.
- The orthogonal transport-capacity, disconnected-edge and explicit
  future-stock probes remain documented acceptance work rather than passing
  tests; the kernel invariant gate still enforces conservation each tick.
- Institutional identities require an explicit scenario crosswalk; synthetic
  ids are labelled synthetic.
