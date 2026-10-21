# H4B-EXEC — price/investment execution bridge and H4A runtime connection

Status: implementation authorized by the user's explicit 2026-10-21 instruction.
Scope: clear the two remaining H4B technical blockers without running Pilot A.

1. `PRICE_INVESTMENT_EXECUTION_MAPPING_ABSENT`
2. `H4A_RUNTIME_MEASUREMENT_NOT_CONNECTED`

Not in scope: Pilot A arms, H4C/H5, historical value admission, price/investment magnitude
estimation, cross-platform reproducibility, or rewriting the committed H4B blocker certificate.

## 1. Design

### Price bridge

- New `institutions/price_regimes.py`: a declared `PriceRegime` book maps each commodity to exactly
  one category with regime `fixed` or `authorized_adjustment`; missing/duplicate coverage fails
  closed.
- `engine/policy.py::compile_price_override` changes only the target commodity's administered price
  and recompiles the household catalog from the overridden material parameters. No global scalar is
  used.
- `execution_adapter.commit_proposal` dispatches `PriceProposalDecision`:
  1. require an explicit authority calendar and price regime;
  2. query `price_setting` authority at `decision_at`;
  3. reject `fixed` categories;
  4. run the baseline quarter and the overridden-price quarter through the real kernel;
  5. enforce the material/finance invariant gate with rollback;
  6. advance `completed_ticks` only on success and emit an old/new price trace.

### Investment bridge

- `TickControls.investment_approvals` carries `(organization_idx, capacity_units)` for one tick.
- `tick_material` caps `new_request` for listed organizations; cash, material and installation gates
  still apply. No cash is created and no state field is added.
- `commit_proposal` dispatches `InvestmentDecision`:
  1. query `investment_approval` authority at `decision_at`;
  2. resolve the organization crosswalk;
  3. convert the approved money amount at the current capital+construction unit cost;
  4. run baseline and approved quarters, enforce invariants, and trace approved capacity and
     realized capacity change.

This is an **organization-level approved capacity increment**, not a project-level capital ledger;
`project_id` is audit-only. The report states this limit.

### H4A runtime connection

- New `history/HIST_VNEXT/h4_sources/runtime_adapter.py`.
- Re-validates the H4A-1 declaration and approval through `experiment_admission`; refuses stale or
  missing approval.
- Applies the approved persons/households and each dwelling-ratio setting to a copy of the
  `historical_f2_replay` scenario, runs 4 quarters per setting with deterministic identity, and
  writes model-internal measurements.
- Writes `runtime_manifest.json` with `runtime_connected=true`, `consumed_by_model` (three records ×
  settings), run ids, and `historical_inputs_admitted=0`.
- Historical comparison remains `NOT_RUN`; the 1957 synthetic baseline is not renamed a historical
  initial state.

## 2. File whitelist

- `docs/phases/HIST_VNEXT/H4B-EXEC/{PLAN,REPORT,REVIEW}.md`, `RUNTIME_MANIFEST.json`
- `src/hsm_lab/institutions/price_regimes.py`
- `src/hsm_lab/institutions/execution_adapter.py`
- `src/hsm_lab/engine/policy.py`
- `src/hsm_lab/engine/material.py`
- `history/HIST_VNEXT/h4_sources/runtime_adapter.py`
- `config/price_regimes/hist_vnext_h4b_v1.json`
- `tests/test_hist_price_investment_execution.py`
- `tests/test_hist_h4a_runtime.py`

No BASELINE/research-contract/lock/scenario/recipe/target changes; no edits to the committed H4B
blocker package or H4A-1 declaration/approval.

## 3. Acceptance

1. Authorized price decision changes only the target commodity price; fixed category and missing
   authority/regime reject; state clock unchanged on rejection.
2. Authorized investment decision commits, caps new capacity, and leaves the invariant gate green;
   unauthorized org and missing calendar reject.
3. Legacy C0/C1 digests and parameter hashes remain the frozen pins.
4. H4A runtime adapter: exit 0 for the approved declaration, `runtime_connected=true`, three
   consumed records, runs completed, measurements present, `historical_comparison=NOT_RUN`;
   stale approval fails closed without creating an output directory.
5. New tests, full pytest, Ruff, baseline, lock.
6. Independent review PASS; commit only the whitelisted files.

## 4. Stop

If the independent review returns REDESIGN, an engine change outside the whitelist is required, a
legacy pin changes, or an invariant gate fails, stop with the failure record. Do not run Pilot A.
