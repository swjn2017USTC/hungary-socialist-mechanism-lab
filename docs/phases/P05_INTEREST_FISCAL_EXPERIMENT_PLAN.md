# P05 — Structural experiment plan 2: the interest sink and the treasury circuit

**This file specifies execution; it does not implement it.** No engine default, scenario
value or published artifact changes until Phase 1 is separately approved and Phase 0 has
proved legacy reproduction.

- Base commit: `f4439b3`.
- Suite baseline: **354 passed**, `ruff` clean, `.venv` python 3.12, Mac only.
- Legacy replay digest (5 000 households / 400 organizations / seed 1729, 116 ticks):
  `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`.
- Predecessors: experiment plan 1 (`P05_INPUT_CREDIT_EXPERIMENT_PLAN.md`, executed — partial,
  nothing adopted) and the circuit audit (`P05_LEAK_AUDIT.md`, all identities closed).

---

## 1. Why this experiment

The audit proved there is **no accounting leak** and localized three modelled withdrawals.
Two of them are in one place — money that leaves the circuit and never comes back:

**a. Interest destroys deposits.** In `engine/finance.py::run_domestic_finance_step` the
accrual books bank revenue (`bank_interest_receivable += interest_due`,
`bank_equity += due_by_bank`) and the payment destroys the matching deposits:

```python
state.bank_deposit_liability = state.bank_deposit_liability - interest_paid_by_bank
state.bank_interest_receivable = state.bank_interest_receivable - interest_paid_by_bank
```

Nothing afterwards pays bank revenue out (`bank_equity` only grows). Measured over 116
ticks: interest paid grows 2 700.818 (tick 5) → 49 333.795 (tick 60), **5 314 921.154 in
total**, with bank equity at 2 676 045.641 by tick 60 and no wage, purchase or dividend
path.

**b. The treasury is a strictly spending account.** `treasury_deposit` is seeded at
83 100.200 (`initial_recipe.treasury_deposit_quarters` × national wage bill) and the only
other entries over the whole run are **70.662** of housing/export procurement and
**83 029.538** of rescue grants in `run_bailout_step`; there is **no inflow**. It first
closes at zero at tick 18 and never refills, so the rescue channel that clears wage and
interest arrears stops after 18 quarters of a 116-quarter run.

**Hypothesis under test:** the contraction is a *monetary* circuit problem — deposits are
destroyed (interest) and one spending agent is drained without a return path (treasury) —
so **making those flows conservation-neutral transfers instead of destructions** should
raise the terminal level where the funding-channel experiment (which doubled delivered
goods) did not.

## 2. Design principle: transfers, never printing

Both mechanisms are pure transfers between existing deposit accounts, so total money is
unchanged by the policy itself:

- interest paid: borrower deposit → **recipient** (treasury deposit, or household cash)
  instead of → destroyed;
- turnover remittance: organization deposit → treasury deposit.

This keeps the audit's money identity exact once it is stated correctly. The audit's
current identity is `M_close = M_open + credit_drawn − principal_repaid − interest_paid`;
with a remittance the last term splits:

```
M_close = M_open + credit_drawn − principal_repaid − interest_destroyed
          (interest_paid = interest_destroyed + interest_remitted)
```

Updating that identity and its test is **part of Phase 1**, not an afterthought: an arm
that fails the residual gate is rejected.

## 3. Falsifiable hypotheses (pre-registered thresholds)

| id | hypothesis | falsification criterion |
|---|---|---|
| **H1** | with the best fiscal arm the treasury never reaches zero | treasury closes at 0 in any tick ≤ 115 |
| **H2** | the interest sink is closed: deposits stop shrinking | the quarter-over-quarter change in M is not strictly better than legacy in every quarter after tick 20 |
| **H3** | the **terminal** state improves, not just the shape | any of the terminal criteria T1–T3 below is not met |
| **H4** | the mechanism is sufficient | any frozen gate (§4) still fails ⇒ partial, report as partial |

Terminal criteria, declared **before** the run and anchored on the legacy baseline
(A0 = the current default), because `liveness = last10 / first10` is a *shape* metric that
penalises policies which start higher (measured in experiment 1: earmarking doubled
deliveries while the ratio fell):

| id | criterion | legacy baseline | declared pass bar |
|---|---|---:|---:|
| T1 | mean production over the last 10 ticks | 28 074 | ≥ 35 092 (+25%) |
| T2 | mean household consumption over the last 10 ticks | 1 668 | ≥ 2 085 (+25%) |
| T3 | treasury solvent at tick 115, or zero rescue grants in the last 20 ticks | fails (zero from tick 18) | passes |

These thresholds are **research declarations**, not fitted values; they exist so a policy
cannot "win" by front-loading activity.

Pre-registered kill condition: if no arm meets T1 **and** T2, the interest/fiscal circuit is
not the binding constraint either; record it as measured-and-rejected and move to the
third audit candidate (savings re-entry), which is a **separate plan**.

## 4. Frozen acceptance gates (unchanged)

Liveness ≥ 0.8; household delivered/funded ≥ 0.9 for g03/g15/g16; treasury self-financing;
per-commodity expiry ≤ 0.20 of available services; every accounting invariant passing. All
thresholds stay exactly as declared; nothing is relaxed for this experiment.

## 5. Minimal implementation design

### 5.1 Declaration

Two new fields on `MaterialParameters` (`contract/material.py`, next to
`credit_envelope_fraction`), both defaulting to exact legacy behaviour:

- `interest_sink_remittance_fraction: FiniteFraction = 0.0` — share of *paid* interest
  redirected instead of destroyed;
- `interest_sink_recipient: Literal["treasury", "households"] = "treasury"` — destination
  of the redirected flow (the contrast arm needs the alternative);
- `fiscal_turnover_remittance_fraction: FiniteFraction = 0.0` — share of quarterly sales
  receipts transferred to the treasury.

All three **must** be added to `MaterialParameters.flatten()`. The default-zero omission
rule in `material_parameter_vector` already exists and is now pinned by a test; if these
fields follow the same convention, Phase 0 must show the legacy digest is unchanged and
the omission is tested for each new field.

Registry entries in `config/calibration/p05_parameters.yml` with
`literature_refs` stating these are **structural design rules** (the Hungarian credit and
budget institutions), and `identification` entries in `config/calibration/p05.json` as
`fixed` — never `calibrated`; `calibrated` stays 0.

### 5.2 Mechanism

In `run_domestic_finance_step`, at the interest-payment block: split
`interest_paid = destroyed + remitted` by the fraction, and route `remitted` as a
conservation-neutral transfer (borrower deposit debit, recipient deposit credit) through
the existing journal so the paired legs and the interbank legs are appended exactly as
wages are. Add a fiscal-remittance block transferring
`fraction × sales receipts` from each organization's deposit to `treasury_deposit`, using
the same journal path; it must be junior to wages and input payments so it can never
starve the goods circuit (the transfer uses cash that remains after those payments).

Neither block may change: the wage/input payment order, the goods budget, or the delivery
step. `bank_equity` keeps accruing as a memo (the dividend question stays out of scope).

### 5.3 Invariants that must not move

- `check_material_invariants` gates all pass, no new residual.
- The money identity closes with the split term (§2), residual < 1e-6, in every arm.
- `national_accounts.expiry` still equals `tick_diagnostics.expired_services` exactly.
- No derived ndarray may be added to `MaterialTickFlows` (it changes the behaviour digest
  even when behaviour is unchanged — measured during the expiry fix).
- A zero fraction on every new field reproduces the legacy digest bit-for-bit.

## 6. Arms and controls

| arm | interest remittance | recipient | turnover remittance | purpose |
|---|---|---|---|---|
| B0 | 0.0 | – | 0.0 | control; must reproduce `92f9ea0a…` |
| I1 | 0.5 | treasury | 0.0 | half the sink closed |
| I2 | 1.0 | treasury | 0.0 | sink fully closed, funds the rescue channel |
| I3 | 1.0 | households | 0.0 | destination contrast: is it the flow or the recipient? |
| F1 | 0.0 | – | 0.02 | treasury refill without touching the sink |
| C1 | 1.0 | treasury | 0.02 | both, to test additivity |
| N1 | 0.0 (envelope 1.0) | – | 0.0 | continuity control from experiment 1 (liveness 0.0396) |

I3 vs I2 separates *destination*; F1 vs I2 separates *source*; C1 vs I2∪F1 tests
additivity. Every arm is recorded with its parameter hash and replay digest.

## 7. Metrics

Per arm, compact outputs only:

1. frozen gates (§4) and the terminal criteria T1–T3 (§3);
2. circuit metrics: treasury `cash_open/close` path and first-zero tick; rescue grants and
   arrears; interest paid vs destroyed vs remitted; M path and its identity residual;
   total deposits, household cash, bank equity;
3. physical metrics: transport `realized`, delivered, expiry, freight pool ÷ need;
4. guardrails: household availability unmet and terminal consumption must not fall below
   the legacy baseline; no arm may load cost onto households to win a treasury metric.

## 8. Execution order (each phase is a gate)

- **Phase 0 — declaration only.** Add the three fields with defaults, the flatten entries
  and the registry/identification entries. Assert the legacy digest, the gate table and
  byte-identical original Parquet files. Stop on any movement.
- **Phase 1 — mechanism + identity.** Implement both transfers behind the parameters; update
  the audit's money identity with the split term and its test. Tests must cover: legacy
  digest unchanged; fraction 0 on all fields is a no-op; a 1.0 interest remittance moves
  exactly `interest_paid` from destruction to the recipient and leaves M unchanged; the
  turnover transfer is junior to wages/inputs; no new flows field.
- **Phase 2 — arms.** Extend `axis_sweep` with both axes; run B0, I1–I3, F1, C1, N1 for 116
  ticks; record the §7 table.
- **Phase 3 — mechanism trace.** For the best arm verify H1/H2 directly (treasury path,
  M path, identity residual), quantify how the transfer changes the goods circuit, and
  decide T1–T3.
- **Phase 4 — report and decision.** `docs/phases/P05_INTEREST_FISCAL_EXPERIMENT.md` with the
  tables, hypothesis verdicts, and the §9 outcome. State explicitly whether H4 held.

Stop conditions: any Phase-0 digest change; any new accounting residual; any arm whose
guardrails regress.

## 9. Decision rules

| outcome | action |
|---|---|
| H1–H3 hold and H4 holds (all frozen gates + T1–T3) | propose adopting the values as F2 defaults, registry entries, manifest version bump; classification stays `fixed`/`weakly identified`, `calibrated` unchanged |
| H1–H3 hold, H4 partial | adopt nothing; name the residual failing gate and the next candidate |
| H3 fails (terminals do not improve) | reject the direction, record the arm table, and move to the savings-re-entry plan |
| a treasury arm wins only via household metrics falling | reject the arm; the tension is the finding |

## 10. Deliverables, budget, non-goals

- Code: the three declared fields + both transfers + tests (Phase 1); the audit identity
  update with its test.
- Data: per-arm compact outputs under git-ignored `outputs/` (one directory, no superseded
  rounds — experiment 1's stale round caused a citation error).
- Documents: `docs/phases/P05_INTEREST_FISCAL_EXPERIMENT.md`; a short §E8 in `P05_REPORT.md`.
- Commits: `feat(p05): declare the interest-sink and fiscal-remittance parameters`,
  `feat(p05): route the interest sink and the turnover remittance as transfers`,
  `docs(p05): record the interest and fiscal circuit experiment`.
- Budget: one 116-tick run ≈ 8 s; seven arms ≈ 2 min; suite ≈ 50 s. Mac only, no Windows,
  no ABC/pyABC, no hold-out targets.
- **Non-goals:** no savings-re-entry mechanism (separate plan); no change to
  `credit_envelope_fraction`, `bailout_envelope_fraction` or the earmark default; no bank
  wage/purchase loop (the payout is the declared transfer only); no printing (transfers
  only); no calibration claim; 1986Q1–1988Q4 stays closed.

---

## 11. Execution prompt (paste into a local Codex)

```text
Execute Phase 0..4 of docs/phases/P05_INTEREST_FISCAL_EXPERIMENT_PLAN.md in this repository
(commit f4439b3 or later, main). Read the plan, docs/phases/P05_LEAK_AUDIT.md §1 and §3 and
docs/phases/P05_INPUT_CREDIT_EXPERIMENT.md (including its independent re-analysis) before
writing code.

Hard constraints:
- Phase 0 must prove the legacy path is untouched: same deterministic_replay_digest
  (92f9ea0a…), same frozen gate table, byte-identical original Parquet files. Stop if not.
- Every new mechanism is a TRANSFER between existing deposits; never print money. Update
  the audit money identity with the destroyed/remitted split and keep its residual < 1e-6.
- Defaults (fraction 0) reproduce today's behaviour exactly; never change a default to pass
  a gate. Declare every field in MaterialParameters AND flatten(), plus the registry and
  identification entries (status "fixed", never "calibrated").
- Do not add any derived ndarray to MaterialTickFlows.
- Keep the wage/input payment order and the goods budget unchanged; the fiscal remittance is
  junior to them.
- Evaluate the pre-registered terminal criteria T1-T3 as well as the frozen gates; a ratio
  gain bought by front-loading is not a gain.
- No ABC/pyABC, no hold-out targets, never simulate past 1985Q4, Mac only, ruff clean.
- Report partial results as partial; falsified hypotheses stay falsified.

For each phase run the check that proves it, then commit with the message listed in the plan.
Final reply: the arm table (frozen gates + T1-T3 + circuit metrics + guardrails), H1-H4
verdicts, the residual failing gate, commit hashes, and pytest.
```
