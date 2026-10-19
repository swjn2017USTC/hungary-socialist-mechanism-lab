# H3F-D1 REPORT — limited-term trade working-capital loan

## 1. Authorization and scope

Executed under the user's explicit authorization of budget, coding and commit for
`H3F_D1_外贸工作资本贷款_PLAN.md`. The plan's frozen REDESIGN blockers (no
Treasury loan-liability accounts/state, no term state, no accounting/material
hook) were resolved by a minimal scalar/ledger extension described below; the
D1 feature remains synthetic and default-off. No historical identification is
claimed. The untracked root plan files remain user files and are excluded from
the commit.

## 2. Implementation

### 2.1 State and flows (`engine/state.py`)

Added four scalars at the end of `MaterialState` (and the opening snapshot):

- `treasury_loan_principal` — outstanding D1 term principal with the lending bank;
- `treasury_interest_arrears` — unpaid D1 interest;
- `treasury_loan_maturity_tick` — `-1` when no facility is outstanding;
- `treasury_loan_rate` — the outstanding contract rate.

The schedule scalars make the facility checkpoint-resumable: with
`book=None`, the adapter reconstructs the single batch from state and checks it
against the regime term/window. Only one facility may be outstanding at a time.

Added five flow scalars: `treasury_loan_drawn`, `treasury_principal_paid`,
`treasury_interest_due`, `treasury_interest_paid`, `treasury_export_outlay`.
All default to zero in `_new_flows`; the first four enter the replay header only
when non-zero, so legacy C0/C1 bytes are unchanged.

### 2.2 Accounts (`engine/finance.py`)

`TREASURY_TERM_ACCOUNT_KINDS = (loan_liability, interest_payable,
interest_expense)` with `treasury_term_account_id`. The block is appended
**after** the plot-clearing block, so every legacy treasury/foreign/plot account
id is unchanged. The term accounts are registered in
`build_account_directory`.

### 2.3 Kernel hook (`engine/material.py`)

- New opt-in keyword `treasury_housing_payable: float | None = None`. `None`
  preserves the legacy budget; a number caps the housing budget independently of
  the actual Treasury cash, so a D1 draw can only fund export procurement.
- `treasury_export_outlay` accumulates the goods+fee actually paid by the
  Treasury on export-purpose edges (legacy and staged paths).
- The digest headers include the D1 loan terms only when non-zero. The derived
  `treasury_export_outlay` is deliberately excluded so C1 (which has exports but
  no D1 loan) keeps its frozen digest.

### 2.4 Accounting (`engine/accounting.py`)

Extended formulas (all zero on legacy paths): bank loan-asset continuity, bank
interest-receivable continuity, bank equity interest accrual, Treasury deposit
continuity. Added:

- `treasury_loan_liability_continuity`;
- `treasury_interest_arrears_continuity`;
- `treasury_export_outlay_rule` (outlay == export goods value + export fees);
- four `journal_treasury_working_capital_*_vs_flow` gates.

D1 amounts are attributed to a bank through the journal legs, not through an
adapter-supplied index.

### 2.5 Checkpoint (`storage/checkpoint.py`)

Added the two scalars to `_STATE_SCALAR_SPEC` / `_STATE_NON_NEGATIVE`, refused
negative values on load, and bumped `CHECKPOINT_VERSION` to
`material-checkpoint-v5` so old payloads fail explicitly rather than being
silently misread. `MATERIAL_STATE_VERSION` stays `material-state-v4` because
that string is part of the frozen C0/C1 identity; the state change is additive
scalars only (no array field changed).

### 2.6 D1 adapter (`institutions/trade_working_capital_adapter.py`)

- Strict regime JSON: bank 0, credit limit, annual rate, term, inclusive draw
  window; synthetic only. Numeric fields use `strict=True`, so booleans and
  strings are rejected rather than coerced.
- `TradeWorkingCapitalBook` holds the immutable batch draw/maturity/rate and
  unpaid interest; the caller may pass it from tick to tick, or pass `None`
  after a checkpoint and let the state scalars reconstruct it.
- Preflight rejects an opening principal above the limit, a batch drawn at or
  after the current tick, a draw tick outside the regime window, a maturity
  that is not `draw_tick + term_quarters`, or schedule scalars that disagree
  with the book.
- Service at tick start: interest accrues on opening principal (new draw never
  accrues in its draw tick), interest is paid first, then matured principal;
  unpaid amounts stay in the same batch/bank.
- Draw sizing: two real-kernel probes on discarded copies measure export outlay
  with no loan and at the remaining limit; the draw is `min(limit,
  outlay_at_limit - outlay_without_loan)`. The admitted tick must increase real
  export outlay by exactly the draw, otherwise it is rejected.
- Limits are outstanding-principal limits. Only one facility may be
  outstanding; a tick with any matured/overdue batch cannot draw a replacement
  (no same-tick rollover), and a draw is allowed only inside the window and
  only for a measured procurement gap.
- The admitted tick runs the real `tick_material`, records service/draw journal
  entries, runs the ordinary gate plus the D1 gates, reuses the frozen D0
  observer read-only for the legacy trade part, and advances the clock only on a
  full pass.
- Any failure restores every `MaterialState` field, leaves the book and clock
  unchanged, and raises `TradeWorkingCapitalFailure` with failed artifacts.
- `m2_neutral_credit=True` and any bank index other than the Treasury's bank 0
  are rejected before mutation.

### 2.7 Config and tests

- `config/trade_regimes/hist_vnext_v1/limited_trade_working_capital.json`
  (synthetic, bank 0, limit 4, rate .04, term 1, draw window 0).
- `tests/test_hist_trade_working_capital.py` (20 tests): full draw, maturity and
  interest, partial/unpaid maturity, non-binding limit, zero limit, no stock, no
  demand, draw window, limit-bound delivery, loader rejection (including
  boolean/string coercion), over-limit opening principal, future-dated batch,
  maturity-tick rollover prohibition, checkpoint-scalar book reconstruction,
  bank/book rejection with rollback, m2-neutral rejection, account-id stability,
  direct orchestration vs adapter (draw and maturity ticks, per-ledger), and
  fabricated-flow rejection.

## 3. Verification (VERIFIED_BY_RUN)

Commands run in the project root with `.venv`:

| Check | Result |
|---|---|
| `pytest tests/test_hist_trade_working_capital.py` | 20 passed |
| `pytest tests/test_hist_export_finance.py tests/test_hist_trade_working_capital.py tests/test_material_finance.py tests/test_material.py` | 100 passed |
| `pytest tests/test_checkpoint.py tests/test_evidence_run_adapter.py` | 31 passed |
| `pytest -q` (full suite) | 1396 passed, 180 pre-existing deprecation warnings |
| `ruff check --no-cache src tests` | clean |
| `uv lock --check --offline` | resolved 101 packages |
| `hsm baseline verify --json` | status ok, SHA256 matches `1f5b…6f` |
| `hsm run --scenario historical_f2_replay` | 116 ticks, digest `92f9ea0a…8a42d` (frozen C0) |
| `hsm run --scenario historical_f2_trade_scenario` | 116 ticks, digest `c4810481…218d5` (frozen C1) |

## 4. Limits and residual risks

- Synthetic engineering evidence only; historical D1 remains UNIDENTIFIED.
- Draw sizing runs two full probe ticks per active draw tick. Probes operate on
  discarded copies and never enter the admitted state, but they are a cost and
  are documented as such.
- The Treasury's domestic deposit is contractually at dense bank 0; a loan from
  another bank would need explicit interbank reserve settlement, which this
  regime rejects.
- The schedule is part of `MaterialState` and the checkpoint spec; a resumed
  state reconstructs the single outstanding batch. Multi-batch facilities are
  deliberately rejected (one outstanding facility at a time).
- No separate evidence root/supervisor bundle was created (no output
  authorization); the evidence above is the exact command output.
