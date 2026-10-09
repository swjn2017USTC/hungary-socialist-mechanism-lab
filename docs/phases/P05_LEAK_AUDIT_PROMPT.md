# Prompt for a local Codex — diagnose the P05/F2 per-tick value & money leak

Copy everything below the line into the local Codex session. The repo is
`hungary-socialist-mechanism-lab`, python `3.12`, venv at `.venv`, entry point
`.venv/bin/hsm`. Work from commit `2c9d413` or later on `main`.

---

You are diagnosing a **research simulation** in this repository. It is a
Hungary 1957Q1–1985Q4 quarterly material/finance/politics model (116 ticks).
Phase P05 built the historical F2 model; calibration and validation were **not**
achieved and the F2 economy contracts monotonically from the first quarters.

## Goal (one deliverable)

Find **where value and money leave the circuit each tick**, with evidence, or
prove that no leak exists and state what is actually happening instead. Write the
finding to `docs/phases/P05_LEAK_AUDIT.md` with reproducible commands, and commit
it. Do **not** fix anything unless you can prove a specific defect; if you do, it
must be a separate commit with a regression test.

## Hard constraints (do not violate)

1. **Diagnosis first.** Do not change `config/calibration/*`, any scenario JSON,
   `credit_envelope_fraction`, `WHOLESALE_HANDLING_TOTAL` / `RETAIL_HANDLING_TOTAL`,
   `F2_TRANSPORT_CAPACITY_TOTAL`, or any parameter default. Two sweeps already
   showed those do not fix the contraction (see §4).
2. **The reserved window is closed**: 1986Q1–1988Q4 must never be simulated or
   evaluated. Do not widen the run past 116 ticks.
3. **The hold-out registry is hashed only**; never use hold-out targets.
4. **Do not run ABC/pyABC inference.** `inference_status = NOT_RUN` and the
   parameter classification is `calibrated 0 / fixed 4 / weakly identified 0 /
   unidentified 6`; keep it that way.
5. **Read-only instrumentation is allowed** (new published columns or a new
   diagnostic artifact) as long as it changes **no** simulated value, seed draw or
   digest. Any behaviour change needs proof from §6.
6. Every 116-tick run costs ~8 s. Keep the whole investigation under ~20 minutes
   of compute; prefer 8–16 tick probes for the accounting traces.
7. Follow the repo conventions: `ruff check src tests` clean, `pytest -q` green
   (currently **344 passed**), no new dependencies, no Windows, Mac only.

## 1. What is already established (do not redo)

Baseline run: `outputs/p05-historical-replay` (116 ticks completes; artifacts
`national_accounts.parquet`, `aggregates.parquet`, `tick_diagnostics.parquet`,
`household_budgets.parquet`, `financial_accounts.parquet`, `stage_balances.parquet`).

Frozen acceptance gates on that run:

| gate | measured | threshold | verdict |
|---|---|---|---|
| liveness (last-10 / first-10 production) | 0.1116 | >= 0.8 | FAIL |
| household delivered / funded (g15 / g16 / g03) | 0.120 / 0.199 / 0.489 | >= 0.9 | FAIL |
| treasury cash | zero from tick 17-18 | self-financing | FAIL |
| accounting invariants | all enforced gates pass | unchanged | PASS |

Production is monotone-decaying: `324k → 130k → 111k → 116k → 69k → 52k → 47k →
41k` sampled every 15 ticks (`national_accounts.production` summed per tick).

`aggregates.parquet` over ticks 2–11, all commodities: ordered 1 107 726,
allocated 9 441 356, delivered 2 792 558, **physical_delivery_blocked 6 648 452**,
financial_delivery_blocked 346. The identity
`delivered + physical + financial == allocated` is enforced per demand cell in
`src/hsm_lab/engine/accounting.py` (gate `delivered_plus_blocked_is_allocated`).

`_group_factor` instrumented **by caller line** ranks the contractions:

| site | meaning | mean factor | zero-capacity groups | need |
|---|---|---|---|---|
| `material.py:1103` | producer cash for input orders | 0.606 | 14 851 | 20.8 M |
| `material.py:1307` / `1314` | source availability, tier rounds | 0.799 / 0.209 | 5 814 / 14 618 | 13.0 M / 4.2 M |
| `material.py:1328` | fallback sourcing round | 0.567 | 3 899 | 0.42 M |
| `material.py:1351` | transport logistics pool | 0.056 | 874 | 0.35 M |
| `1373` / `1391` / `1410` | wholesale/retail handling, bank reserves | ~1.000 | 0 | - |

**Excluded by measurement** (do not re-test): ordering/funding (`desired ~
ordered`), handling capacity (x2/x4/x8 changes nothing), the transport sector
being idle or input-starved (its 8 organisations: capacity 60 000, target 54 000,
realised 54 000 at tick 0; input requirement 0.052 per unit of output, several
quarters seeded).

## 2. Sweeps already run (do not redo)

```
hsm calibration axis-sweep --axis credit_envelope_fraction --points 0.5,0.75,1.0
hsm calibration axis-sweep --axis transport_capacity_scale --points 1,4,16
```

| credit_envelope_fraction | liveness | expired tail | treasury zero |
|---|---|---|---|
| 0.5 (declared) | 0.1116 | 11 273 | 18 |
| 0.75 | 0.1160 | 9 290 | 31 |
| 1.0 | 0.0396 | 5 160 | 48 |

| transport_capacity_scale | liveness | expired tail | treasury zero |
|---|---|---|---|
| 1 (declared) | 0.1116 | 11 273 | 18 |
| 4 | 0.2612 | 18 571 | 6 |
| 16 | 0.3190 | 32 448 | 4 |

Neither restores liveness; both only change how fast the same contraction is
reached. The tool is `src/hsm_lab/calibration/axis_sweep.py`; extend it rather
than writing throwaway probes.

## 3. The hypothesis to test

Production, delivered goods and the payment chain contract **together from the
first quarters**, so the suspected mechanism is a per-tick **value or money leak**
that no single parameter exposes. Candidate leak sites, in the order to check:

1. `tick_diagnostics.expired_services` — non-stockable output that expires.
   Measure it **per commodity** (the run currently publishes only an aggregate).
   Where does the matching revenue go in the same tick?
2. `national_accounts.total_stock_open/close` and `material_balance_residual` —
   is produced value conserved across the tick, or does stock vanish?
3. Household circuit (`household_budgets.parquet`): `voluntary_saving`,
   `forced_saving`, `deferred_open/close`, `cash_open/close`, `budget_available`
   versus `spending`. Does income become cash that is never spent again?
4. Treasury circuit: `treasury_cash` reaches zero at tick 17-18. What funds
   housing/exports, and is there any inflow that should refill it?
5. Credit circuit (`run_domestic_finance_step` in `src/hsm_lab/engine/finance.py`):
   `credit_envelope_fraction`, principal drawdown vs repayment, interest accrued vs
   paid, and `m2_neutral_credit`. Does principal outstand while cash disappears?
6. Bank reserves / cross-bank settlement factor at `material.py:~1452` — it was
   ~1.0, but check whether reserves drift down across the run.

**Money stock is not currently published** (`financial_accounts.parquet` carries
only `bank_*_loan_asset`, `foreign_cmea_settlement`, `foreign_usd_reserve`,
`treasury_cash`). Adding a per-tick money-stock artifact (currency in circulation,
deposit liabilities, credit fund, total) is an allowed read-only instrumentation
and is probably the single highest-value step: money conservation per tick is a
one-line identity that either holds or localises the leak immediately.

## 4. Method

1. Reproduce the baseline once and keep its artifacts.
2. Add the money-stock / per-commodity-expiry diagnostic (read-only), commit it
   only if it changes no behaviour — verify by re-running the baseline and
   confirming the run digest and gates are byte-identical.
3. Trace **one tick** (tick 5 is a good candidate: still liquid) end-to-end:
   produced → ordered → allocated → delivered → used → expired → stock; and
   money: wage bill → household cash → purchases → seller receipts → deposits →
   wages next tick. Build the flow table for that tick from the ledger.
4. Repeat for ticks 20 and 60 and show the leak term growing.
5. Falsify alternatives: if the leak is not money, prove value conservation holds
   and find the physical term that shrinks (name the artifact and column).

## 5. Deliverable

`docs/phases/P05_LEAK_AUDIT.md` containing:

* the tick-5 (and 20/60) flow table with every term and its source artifact;
* the identified leak, or an explicit "no leak; instead X" with the same evidence;
* falsified alternatives with the measurement that falsified them;
* the exact commands to reproduce every number;
* a proposed minimal fix with its expected effect **on the frozen gates**, clearly
  marked as proposed, not applied.

Reply in chat with: the leak (or its absence), the evidence table, commit hashes,
and `pytest -q` result. If you cannot localise the leak, say exactly which term
you could not close and what observation would close it. Do not tune parameters to
make the gates pass; that is explicitly out of scope.
