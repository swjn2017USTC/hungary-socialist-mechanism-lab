# H3B Independent Review

## Reviewer
Repository `phase-reviewer` subagent, read-only.  The reviewer did not edit
implementation files.  Actual model selector/effort/token/cost are `NOT_SET`;
no paid model call was made and no MiniMax selector is claimed.

## History
1. **PATCH** — round 1 found five defects:
   - payment identities were only economy-wide, not per buyer/seller/carrier
     and not bound to the raw `goods_payment` journal;
   - the standalone stock-continuity check dropped the sign of the gate
     residual, so created stock could pass;
   - direct `run_domestic_finance_step` accepted `credit_approval_caps` with
     `m2_neutral_credit=True` and emitted bank-lender journals;
   - small positive drawdowns/repayments (for example 1e-10) were treated as
     zero journal presence because the check used `ATOL`;
   - evidence exports compared different reproduce-arm parameters, omitted
     openings and full smoke journals, discarded failed diagnostics, and the
     report had one wrong upstream-unfunded value.
2. **PATCH** — round 2 verified repairs 1–4 and found two evidence defects:
   - the failure-export serializer handled only 1-D arrays and crashed on real
     multidimensional flows before writing `failure.json`;
   - opening metadata exported `fixture.parameters` rather than the executed
     parameters and hardcoded `1957Q1` for every smoke tick.
3. **PATCH** — round 3 verified both round-2 repairs and found only a stale
   resource paragraph in `REPORT.md` (16 runs / old maxima instead of the
   recorded 39 runs).
4. **PASS** — round 4, after the report numbers were reconciled with
   `runs/*/usage.json`.  No source defect was indicated.

## Final verdict
**PASS** — no reproducible blocking defect remains in the repaired H3B
implementation and evidence.

## Repairs between rounds
- `flow_funnel` now checks per-buyer purchases, per-seller/carrier receipts and
  `goods_payment` buyer→seller/carrier journal pair totals/amounts; missing or
  swapped payment evidence is rejected.
- `flow_funnel` compares `abs(stock_residual)` with the gate tolerance and
  rejects both stock creation and missing stock.
- `run_domestic_finance_step` rejects caps plus `m2_neutral_credit=True`
  before any state or flow mutation.
- Journal-presence rules use the producer's strict-positive amount rule while
  numeric comparisons keep `ATOL`; 1e-10 drawdown and principal cases pass.
- `_array` serializes arbitrary-dimensional arrays; `check_failure_export.py`
  exercised the real handler with `household_desired.shape == (1, 6)` and
  wrote `failure-export.json` with phase, cause, 117 flow fields, all eight
  trace keys and valid nested JSON.
- `_opening_payload` exports the executed parameters and the actual opening
  quarter/tick.  `final3/reproduce` exports the same 0.6/0.4 parameters for
  both arms with loan/deposits 12/16; `final3/smoke4` exports Q1–Q4 openings
  with matching policies and ticks.
- Added regressions for payment corruption, deleted goods journals, stock
  creation/deletion, direct-finance M2-neutral rejection, and small-positive
  drawdown/principal journals.
- Corrected the report's cap0/source0 upstream-unfunded value from 0 to 10 and
  reconciled the observed-resource paragraph with the final 39-run aggregate.

## Reviewer-executed verification (final rounds)
- Ran `tests/test_hist_procurement_credit.py`: **19 passed**.
- Ran the real failure-export reproducer with multidimensional flows:
  succeeded; `failure-export.json` retained phase `measurement`,
  `RuntimeError('audit')`, all 117 flow fields, all eight trace keys and nested
  `household_desired` shape `[1, 6]`.
- Inspected `final3/reproduce/reproduce.json`: identical openings and executed
  parameters 0.6/0.4; legacy loan/deposits 12/16; opt-in draw 12.
- Inspected `final3/smoke4/smoke4.json` and `smoke16`: opening, policy, result
  and tick quarters match for every tick.
- `verify_run_identity` passed for fresh `final3/C0` and `final3/C1`: 116
  ticks, 1985Q4, digests `92f9ea0a…` and `c4810481…`.
- Protected `BASELINE.md`, research-contract and lock hashes match the frozen
  values; final3 evidence checksum maps match.
- Confirmed no target/history access in the added modules or tracked changes,
  default-off legacy behavior, and honest `NOT_SET` budget/model usage.

## Known limits
- The implementation and evidence are synthetic/technical; the historical
  verdict remains `UNIDENTIFIED / NOT_RUN`.
- Formal H3B budgets and model usage are `NOT_SET`; observed local resources
  are not a budget-compliance certificate.
- The H3B adapter is default-off and not wired into the default runner.
