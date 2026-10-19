# H3F-D1 REVIEW — independent phase-reviewer

## Verdict

**PASS** (second independent review, after one PATCH round).

## Round 1 — PATCH

The first read-only audit found four blocking defects:

1. the credit limit was checked only after debt service, so an over-limit
   opening book could be serviced and partially re-drawn;
2. a supplied batch was not checked against the clock, the regime draw window,
   or the frozen term;
3. `credit_limit` / `annual_rate` used lax pydantic floats and coerced
   booleans and strings;
4. a maturity tick could repay the old principal and draw a replacement in the
   same tick (economic rollover).

It also noted that the maturity/rate schedule was out of band (checkpoint
escape), that the `treasury_d1_cash` diagnostic was misleading, and that the
direct-vs-adapter comparison did not cover a service tick or `per_ledger`.

## Fixes applied

- Preflight rejects `principal > credit_limit`, a batch drawn at/after the
  current tick, an out-of-window draw tick, a maturity other than
  `draw_tick + term_quarters`, and state/book schedule disagreement.
- Regime numerics now use `StrictFiniteFloat` (`strict=True`,
  `allow_inf_nan=False`).
- Any tick with a matured/overdue batch sets `rollover_blocked` and cannot
  draw; a new draw requires zero outstanding principal.
- `MaterialState` now carries `treasury_loan_maturity_tick` and
  `treasury_loan_rate`; `book=None` reconstructs the single outstanding batch,
  and the checkpoint spec stores all four D1 scalars. Multi-batch facilities
  are rejected.
- The misleading residual is renamed `non_d1_treasury_net_outlay` and
  documented as non-zero by construction.
- The direct-vs-adapter test now covers a draw tick and a maturity tick and
  compares every state/flow field, the journal columns, and `per_ledger`; the
  adapter observation includes the read-only D0 legacy observation.

## Round 2 — PASS

The second independent audit confirmed each prior finding closed, replayed the
over-limit and rollover repros, exercised multi-batch/out-of-window/maturity
mismatch rejection, ran a real checkpoint save/load roundtrip with non-zero D1
scalars, and re-ran the evidence:

- D1 tests: 20 passed;
- target set: 100 passed;
- checkpoint + evidence adapter: 31 passed;
- full suite: 1396 passed;
- ruff clean; `uv lock --check --offline` resolved; baseline verify ok;
- C0 `92f9ea0a…8a42d` and C1 `c4810481…218d5` reproduced exactly;
- accounting identities, default-off behavior, and rollback all passed.

No blocking findings remain. Historical D1 identification remains
UNIDENTIFIED; the PASS applies only to the synthetic, default-off engineering
implementation.
