# Codex prompt 2 of 2 — P06 Part 2: declared trade scenario and transmission test

Run this **only after** prompt 1 (Part 1) has been committed. Copy everything below the line into
the local Codex session.

---

Work in `hungary-socialist-mechanism-lab` (`main`). This is **Part 2 only** of
`docs/phases/P06_TRADE_TRANSMISSION_PLAN.md`. Confirm first that Part 1 landed: the crosswalk's two
trade entries have `status: "blocked"`, the crosswalk test asserts invariants rather than counts,
and `docs/phases/P06_CLEARANCE_LOG.md` has the Part 1 entry. If any of that is missing, do Part 1
first.

**Purpose.** The historical replay declares every trade-demand vector as zero, so the model's
external channel is never exercised and two admitted trade indices cannot be compared. Build one
**declared, non-circular** trade-demand scenario and run a short transmission ladder to answer one
question: **does the external channel transmit at all under the current structure?**

**Rules (non-negotiable).** The trade vectors must come from the registered external pack and the
declared `p04.external_recipe` base demand levels, the declared admin prices
(`build_material_prices(parameters).standard`) and the declared credit envelopes — **never** from the
admitted KSH trade volume indices or any target series, which would make the comparison circular.
Reproduction scope stands: `calibrated = 0`, no block promoted to identified, hold-out unused,
reserved window closed, no fabricated data, no tolerance tuned to fit.

**Steps.**

1. **Read the mechanics first.** `engine/trade.py::realize_imports` scales CMEA imports by
   `cmea_credit_envelope + cmea_settlement_balance` and convertible imports by the USD budget;
   `engine/trade.py::build_export_demands` scales desired exports by the Treasury's payable cash.
   `engine/material.py`'s trade pre-pass wires the import pool. Know these before choosing values.

2. **Declare the scenario.** Add `config/scenarios/historical_f2_trade_scenario.json` as a copy of
   `historical_f2_replay` with nonzero per-commodity `cmea_desired_imports`,
   `convertible_desired_imports`, `cmea_export_demands` and `convertible_export_demands`, sourced
   from the external pack / `external_recipe` levels, with a `notes` field stating that provenance.
   Register its id in `AVAILABLE_SCENARIOS`. Set `cmea_credit_envelope`, `convertible_loan_limit`,
   `cmea_opening_reserve`, `convertible_opening_reserve` and `convertible_opening_principal` high
   enough to be **non-binding** so the test measures the trade channel and not credit rationing; if a
   value trips the existing `distribution working capital exceeds the Treasury's opening deposit`
   guard, record that guard as the binding constraint and use the largest value that does not.

3. **Run the ladder.** C0 = `historical_f2_replay` (trade identically zero; already known, but record
   it). C1 = the new trade scenario, 116 ticks to 1985Q4. C2 only if C1 shows trade arriving but the
   delivery chain still blocks it: a knife-edge wage-factor variant, clearly labelled a diagnostic
   and not a remedy. Every run records parameter hash, seed, scenario id, replay digest and the
   per-commodity import/export volumes with CMEA and convertible kept as separate channels.

4. **Decide from the evidence.**
   - **C1 yields zero imports/exports despite nonzero declared demand:** the external channel does
     not transmit. Find the cause (demand vector not reaching the right commodity cell, financing
     scaled to zero, import-pool or Treasury path blocked) and set both trade indices to
     **`no_counterpart` permanently** with that cause. This is a **first-class result**, not a
     failure.
   - **C1 yields nonbinding trade:** set both indices to **`mapped`** with
     `comparison_grade: normalized_index` (or an allocated grade if a share was needed), a `source` of
     type `scenario_declared_trade_vectors` carrying the scenario id and digest and the
     non-circularity note. Extend `src/hsm_lab/calibration/reproduction_table.py` to accept that
     source type **for these two variables only**, while still refusing any `mapped` row without a
     source, and add tests. Report the resulting numeric rows as reproduction under declared inputs,
     never as a fit.
   - Report the household-consumption failure **first and in full regardless**: a trade success says
     nothing about consumption.

5. **Clearance.** Add a `p06_trade_transmission` item to
   `config/calibration/p06_clearance.json` as an `internal` check that reads the run summary (no
   hard-coded status). Regenerate `outputs/p06-clearance/pytest.json` and run
   `.venv/bin/hsm calibration p06-clearance --with-runs`.

House rules: never stage `.omp/config.yml`; never push, rebase or clean; run
`.venv/bin/ruff check src tests` and `.venv/bin/python -m pytest -q -p no:cacheprovider` before each
commit; append one entry per step to `docs/phases/P06_CLEARANCE_LOG.md`. Report partial results as
partial and never describe anything as validated, calibrated or identified.

Finish by updating `docs/phases/P06_RUN_REPORT.md` and reporting in chat: the scenario definition and
its provenance (with the source of every trade vector), the C0/C1/C2 outcome, the located cause if
the channel did not transmit (or the numeric rows if it did), the crosswalk's final status counts, the
clearance item table, the commit hashes and the ruff/pytest result. Do not ask anything.