# H3B Report — upstream procurement credit and bank approval closure

## Authorization and scope
The user authorized H3B coding and commit on 2026-10-18, including the
review → repair loop until an independent PASS.  The phase remained inside the
Plan whitelist:

- new `src/hsm_lab/institutions/procurement_credit_adapter.py`
- new `src/hsm_lab/measurement/flow_funnel.py`
- new `tests/test_hist_procurement_credit.py`
- opt-in keyword interfaces in `src/hsm_lab/engine/finance.py` and
  `src/hsm_lab/engine/material.py`
- `docs/phases/HIST_VNEXT/H3B/{PLAN,REPORT,REVIEW}.md`
- throwaway evidence under `outputs/hist-vnext-h3b-20261018-105503/`

No bank, account, clock, stock, storage schema, CLI, scenario, contract,
`BASELINE.md`, research contract or lockfile was added or changed.  The legacy
Treasury-credit path remains the default and its C0/C1 digests are unchanged.

### Authorization deviations, stated explicitly
The Plan's formal H3B budget fields (`max_wall_s`, `max_rss_bytes`,
`max_new_output_bytes`, `max_run_count`, model tokens, paid-cost cap, MiniMax
`reasoning_effort`) were **NOT_SET**; the user supplied coding and commit
authorization, not phase budget values.  Following the H3A precedent:

- no paid model call was made;
- no MiniMax-M3 selector or effort is claimed;
- the implementation and local runs were executed by the main session;
- `runs/*/usage.json` records observed local wall/RSS/output and marks
  `resource_budget_status="NOT_SET"` and `model_usage_status="NOT_SET"`.

These observations are not a budget-compliance certificate and do not inherit
H3A's 600 s / 4 GiB / 512 MiB / 30 runs / $5 values.

## Implemented interfaces
### Finance (`run_domestic_finance_step`)
- Added keyword-only `credit_approval_caps: np.ndarray | None = None`.
- `None` preserves every legacy entry and journal byte.
- Non-None caps are validated before any journal entry: shape `(O,)`, finite,
  non-negative, and exactly zero for banks or organizations without a bank.
- The cap is applied after the existing envelope, stock-cap and earmark rules:
  `total_approved = min(existing_approve, request, cap)`, with the earmarked
  tranche reduced to the approved total and the general tranche as the
  remainder.
- The opt-in drawdown journal is
  `Dr enterprise cash / Cr its bank deposit liability` and
  `Dr its bank loan asset / Cr enterprise loan liability`.
- The opt-in principal journal is
  `Dr enterprise loan liability / Cr enterprise cash` and
  `Dr its bank deposit liability / Cr its bank loan asset`.
- No Treasury cash or Treasury loan leg is created in the opt-in path.
- The docstring's step order was corrected; scheduling itself is unchanged.

### Material (`tick_material`)
- Added keyword-only `credit_approval_caps` and `procurement_trace`.
- Both are validated before any state mutation: caps shape/finite/negative/
  invalid-borrower checks, `m2_neutral_credit=True` rejection, trace must be a
  plain empty `dict`, and trace requires caps.
- Caps are passed to finance; the trace copies the real pre-scaling arrays
  `credit_approval_caps`, `demand_unit_cost`, `input_order_cost`,
  `old_project_cost`, `new_investment_request_cost`,
  `cash_available_for_goods`, `input_credit_earmarked` and
  `edge_unit_price`.  No trace is captured when the argument is `None`.

### Adapter and funnel
- `ProcurementCreditPolicy` is a frozen synthetic policy with
  `schema_version="hist-procurement-credit-policy-v1"`,
  `source_kind="synthetic"`, domestic currency only and an explicit
  `unlisted_default_zero=True` export.  Unlisted enterprises get a zero cap.
- Policy validation rejects empty policy id, wrong schema/source/currency,
  wrong quarter, `available_at > decision_at`, decision/information dates after
  the simulated quarter, duplicate/unknown enterprises, unknown/mismatched
  banks, banks as borrowers, negative/non-finite amounts, and
  `m2_neutral_credit=True`.
- `execute_procurement_credit_tick` takes one pre-tick deep copy and opening
  snapshot, constructs dense caps and an empty trace, runs exactly one
  `tick_material`, runs the original `check_material_invariants(...,
  controls=controls)`, then the new funnel, and only then increments
  `completed_ticks`.
- On any tick/gate/measurement exception it copies the failed flows/trace,
  restores every mutable state field, does not advance the clock, and raises
  `ProcurementCreditFailure(phase, failed_flows, failed_trace)` preserving the
  original cause.
- `flow_funnel.measure_procurement_credit_tick` is read-only.  It emits frozen
  `CreditBudgetRow`, `ProcurementInputRow`, `ProcurementEdgeRow` and raw
  journal rows; validates the trace, all-cell stock continuity via the gate's
  own `_reconstruct` and `tolerance_for`, gross/ordered/allocated/delivered/
  used identities, edge sums, buyer/seller payment totals, principal/wage/
  interest-arrears continuity, bank assets/liabilities, deposit composition,
  loan/interest/equity continuity, reserves and the actual lender journal.

## Before → after: the red counterexample
`reproduce_before.json` (run before the production edit) shows the legacy
12/10/0 fixture passing the original finance gate with
`max_finance_tolerance_ratio=0` while the `loan_drawdown` journal names the
Treasury as the creditor:

| legacy field | value |
|---|---:|
| loan asset | 12 |
| borrower principal | 12 |
| bank deposits | 16 |
| reserves | 24 |
| equity | 20 |
| household receipts | 10 |
| material output | 0 |
| actual bank lender | **false** |
| verdict | `FAIL_LEGACY_TREASURY_COUNTERPART` |

The opt-in H3B run of the same fixture keeps every stock/finance amount and
changes the journal counterpart to the real bank.  This is the intended
"correct counterexample": zero output is preserved, not "fixed".

## 2×2 closure (seed 1729, deterministic tiny fixture)
| arm | drawn | ordered | allocated | delivered | used | buyer output | buyer principal | buyer cash | source stock | upstream unfunded |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cap0/source0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 10 |
| cap0/source10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 10 | 10 |
| cap10/source0 | 10 | 10 | 0 | 0 | 0 | 0 | 10 | 10 | 0 | 0 |
| cap10/source10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 0 | 0 | 0 |

In cap10/source10 the seller receives 10, buyer purchases are 10, and the
buyer's principal is 10.  In cap0/source10 the terminal
`financial_delivery_blocked` is 0 but `upstream_unfunded=10`; the funnel does
not misread that as adequate financing.

## Debt priority, scheduled principal and two banks
Priority fixture (opening cash 12, principal 12, annual rate .04, wage rate 1,
zero cap, full scheduled repayment):

| item | value |
|---|---:|
| wage due / paid | 10 / 10 |
| interest due / paid | .12 / .12 |
| principal paid | 0 |
| goods budget → delivered/used | 1.88 |
| buyer output | 1.88 |
| closing buyer cash | 0 |
| closing principal | 12 |

Full-due fixture (opening cash/deposits 20, reserves 28, loan 12, equity 20):
interest .12, principal paid 12, closing cash/deposits 7.88, loan/principal 0,
equity 20.12.  Insufficient-cash fixture (cash/deposits .05, reserves 8.05):
interest paid .05, interest arrears .07, principal paid 0, principal stays 12,
cash 0, deposits 0, equity 20.12.  Zero cash produces no drawdown and no
principal journal.

Two-bank fixture (source bank 1, buyer bank 0):

| buyer-bank reserves | drawn | delivered | buyer cash | bank0 loan/deposits/reserves/equity | bank1 deposits/reserves |
|---:|---:|---:|---:|---|---|
| 0 | 10 | 0 | 10 | 10 / 10 / 0 / 0 | 0 / 0 |
| 10 | 10 | 10 | 0 | 10 / 0 / 0 / 10 | 10 / 10 |

Both bank balance sheets close and reserves are non-negative.  The starved arm
still creates the loan/deposit but cannot settle across banks; the funded arm
moves the deposit and reserves to the seller's bank.

## Smoke: 4Q and 16Q
Observed arm: source opening 40 (4Q) or 160 (16Q), cap 10 each quarter, zero
wage/interest/repayment, no mid-run injection.  Control arm: same opening,
cap 0.

| arm | ticks | per-quarter draw/delivered | cumulative output | closing principal | closing source stock |
|---|---:|---|---:|---:|---:|
| observed 4Q | 4 | 10/10 each | 40 | 40 | 0 |
| control 4Q | 4 | 0/0 each | 0 | 0 | 40 |
| observed 16Q | 16 | 10/10 each | 160 | 160 | 0 |
| control 16Q | 16 | 0/0 each | 0 | 0 | 160 |

This is a small initial-resource closure, not long-run reproduction and not
multi-seed statistical evidence.

## Independent review round 1 → PATCH → repairs
The repository `phase-reviewer` returned **PATCH** with five findings; all were
repaired before the second review:

| Finding | Repair |
|---|---|
| payment identities were only economy-wide, not per counterparty/journal | added per-buyer purchases, per-seller/carrier receipts and `goods_payment` buyer→seller/carrier journal-pair reconciliation; added swapped-purchase and deleted-journal regressions |
| stock-continuity check dropped the sign of the gate residual | now compares `abs(stock_residual)` to the gate tolerance; added stock-creation and missing-stock regressions |
| direct finance opt-in accepted `m2_neutral_credit=True` and emitted bank-lender journals | finance now rejects the combination before any state/flow mutation; added a direct-call state-invariance test |
| small positive approvals were treated as zero journal presence | journal-presence rules now use `> 0` (the producer's positive-amount rule) while numerical comparisons keep `ATOL`; added 1e-10 drawdown and principal regressions |
| evidence exports omitted openings, full smoke journals, failure diagnostics, and the legacy arm used different parameters | reproduce now applies the same `_case8_parameters` to both arms; openings/policies are exported per arm/tick; smoke stores full per-tick result+journal; failure JSON stores failed flows/trace; report upstream-unfunded corrected to 10 |

## Independent review round 2 → PATCH → repairs
The second review confirmed round-1 repairs 1–4 and found two remaining
evidence defects:

| Finding | Repair |
|---|---|
| `_flows_payload` passed every ndarray through a 1-D-only serializer, so a real failure could crash before writing `failure.json` | `_array` now returns JSON-safe nested lists for any ndim; `check_failure_export.py` exercised the real handler with a `(1, 6)` `household_desired` field and wrote `failure-export.json` preserving phase, cause, all 117 flow fields and all 8 trace keys |
| opening metadata exported `fixture.parameters` instead of the executed parameters and hardcoded `1957Q1` for every smoke tick | `_opening_payload` now takes the executed parameters and the actual opening quarter/tick; reproduce exports 0.6/0.4 (matching execution), and smoke ticks 0–3 export Q1–Q4 openings with matching policies |

All repaired evidence was regenerated in
`outputs/hist-vnext-h3b-20261018-105503/final3/`; `failures.json`-style
diagnostics are exercised by `failure-export.json`.

## Verification (repaired final candidate)
All commands ran from the repository root with `PYTHONDONTWRITEBYTECODE=1`,
pytest `-p no:cacheprovider`, ruff `--no-cache`.

| Check | Result |
|---|---|
| new H3B tests | **19 passed** |
| focused regression (new + material/material_finance/tiny/service/P05/retail/households/historical) | **116 passed** |
| full suite | **1128 passed, 180 warnings** |
| lint | **All checks passed** |
| lock | `uv lock --check --offline` exit 0 |
| baseline | **ok**, SHA-256 `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` |
| C0 | digest `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`, 116 ticks, 1985Q4 |
| C1 | digest `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`, 116 ticks, 1985Q4 |
| C0/C1 identity | `verify_run_identity` passed for both fresh `final3/C0` and `final3/C1` directories |

C0 parameter hash `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445`;
C1 parameter hash `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90`;
recipe hash `10655b0706fae7960a6a7b6dec660d160b9c6670186bec7adf82743870432b82`.

Protected hashes remain:
`BASELINE.md=1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`,
`config/research_contract.json=6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`,
`uv.lock=9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`.

### Observed local resources (not a budget certificate)
`run_logged.py` recorded 39 runs with `resource_budget_status="NOT_SET"`:
max wall 100.84 s (full suite after the PATCH repairs), max sampled
process-tree RSS 1,139,703,808 B (same run), max new output 20,111,471 B
(`final-C0`), no nonzero exit codes.  The maximum observed
`rusage_children_maxrss` across the recorded runs is 806,436,864 B raw on
macOS (from `full-suite-final1`); it is a cumulative children high-water, not a
per-run peak.  These are observed local values, not compliance with an approved
H3B cap.

Tracked diff: only `src/hsm_lab/engine/finance.py` and
`src/hsm_lab/engine/material.py`; the rest is new white-listed source/test/docs.
No lock, contract, baseline, scenario, old output or H2/H3A file changed.

## Verdicts
- **technical: PASS** — all final gates, tests, lint, lock, baseline and
  C0/C1 replay identities passed on the candidate bytes.
- **structural: PASS for the implemented closure** — request → cap/approval →
  drawdown → wage/interest/principal priority → goods funding → delivery →
  actual use/output is separated and conserved in the exercised fixtures, with
  the lender identity bound to the actual bank journal.
- **historical: UNIDENTIFIED / NOT_RUN** — the policy is synthetic
  (`source_kind="synthetic"`), no historical source or target was opened, and
  no historical claim is made.

## Known limits
- The adapter is default-off and is not wired into the default runner.
- The policy is a synthetic institution, not a historical Hungarian bank
  contract; no maturity book, interbank market or general credit-term schema
  was added.
- Formal H3B budgets and model usage are `NOT_SET`; observed local resource
  values are recorded without claiming compliance.
- The 2×2 and smoke fixtures are deterministic technical closures, not
  calibrated historical results.
- The independent review verdict is **PASS**; the round history and repairs are
  recorded in `REVIEW.md`.
