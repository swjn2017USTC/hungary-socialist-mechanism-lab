# P06 — step-1 label fixes and Plan C (declared trade-demand scenario, transmission test)

Run Plan C after the R9/R10 label corrections. The scenario-declared trade vectors in
`historical_f2_replay.json` are all zero, so the model never exercises its import or export
machinery on the historical replay; the reproduction table can only compare one of fourteen
admitted series, and that one fails in all informative years. Plan C asks: **can an independent,
declared trade-demand scenario activate the external channel, and does the model then reproduce
the two admitted trade volume indices?** It does not attempt to fit anything — it is a
transmission test under the reproduction scope.

Base: `3df2f85`, 412 passed, `ruff` clean, clearance green (23 PASS / 4 WAIVED / 0 OPEN with
`--with-runs`). Standing prohibitions unchanged: reproduction scope, `calibrated = 0`, no block
promoted to identified, no Sobol for unidentified parameters, no SUPPORTED verdict for a
calibration-dependent card, no fabricated series or mapping, the seven unadmitted target-role
variables stay unadmitted, hold-out unused, reserved window 1986Q1–1988Q4 closed.

---

## Part 1 — the R9, R10 and minor label corrections (do first; these are small)

**R9.** In `config/calibration/p06_reproduction_crosswalk.json`, reclassify
`trade_export_volume_index` and `trade_import_volume_index` from `no_counterpart` to `blocked`.
Keep their existing honest `reason`, `candidate_model_quantity` and `methodological_difference`
text, and append the precise missing item and the circularity trap, for example:

> status `blocked`; reason: the model has the trade machinery, but
> `config/scenarios/historical_f2_replay.json` declares all four trade-demand vectors
> (`cmea_desired_imports`, `convertible_desired_imports`, `cmea_export_demands`,
> `convertible_export_demands`) as zero, so `national_accounts.imports`/`exports` are identically
> zero for the whole replay and a model-own-1960 index has no base. Missing: a declared,
> **non-circular** trade-demand scenario (Plan C). Do **not** feed the admitted KSH trade volume
> index back in as a demand vector — that would make the later comparison circular.

**R10.** In `tests/test_p06_reproduction_table.py`, replace the count assertions
(`mapped == 1`, `no_counterpart == 13`, `blocked == 0`) with invariant assertions: the crosswalk
covers exactly the 14 admitted variables; every `status` is in `{"mapped", "no_counterpart",
"blocked"}`; every `mapped` row carries a non-empty `comparison_grade`, `source`, `comparison_window`
and `error_tolerance`; and any row with `allocation_assumed` also lists artifact digests. Drop the
`mapped == consumption` and `grade == normalized_index` pins.

**Minor.** In `docs/phases/P06_EXECUTION_PLAN.md`, reconcile `bank_circuit` in the artifact
inventory with the arm documents: state that it is available to leak-audit observers but **not**
emitted by compact fork output, or drop it.

Commit Part 1 alone.

---

## Part 2 — Plan C: a declared, non-circular trade-demand scenario and transmission test

**Purpose.** Determine whether the external channel transmits at all in the current structure, and
whether a declared independent trade scenario lets the two trade volume indices become comparable.
This is a **structural transmission test**, not a fit: the trade vectors are declared inputs chosen
from the model's own external forcing (`external_recipe` base demand levels, the registered external
pack, and the declared CMEA/convertible prices and credit envelopes), **never from the admitted KSH
trade index or any target series**.

**The scenario.** Add `config/scenarios/historical_f2_trade_scenario.json` as a declared scenario (add
its id to `AVAILABLE_SCENARIOS`). Copy `historical_f2_replay` and set:
- `cmea_desired_imports`, `convertible_desired_imports`, `cmea_export_demands`,
  `convertible_export_demands` to nonzero per-commodity vectors, sourced from the registered
  external pack / `p04.external_recipe` base levels, not from targets. Declare their provenance in the
  scenario `notes`.
- Confirm the financing the scenario needs: `realize_imports` scales CMEA imports by
  `cmea_credit_envelope + cmea_settlement_balance` and convertible imports by the USD budget; the
  scenario must declare `cmea_credit_envelope`, `convertible_loan_limit`, `cmea_opening_reserve`,
  `convertible_opening_reserve` and `convertible_opening_principal` high enough to be **non-binding**
  so the transmission test measures the trade channel, not a credit ration. If raising them trips the
  existing `distribution working capital exceeds the Treasury's opening deposit` guard, report that
  guard as the binding constraint and proceed with the largest non-infringing values.

**The transmission ladder** (every arm records parameter hash, seed, scenario id, replay digest and
the per-commodity import/export volumes):

| run | scenario | purpose |
|---|---|---|
| C0 | `historical_f2_replay` | baseline: trade identically zero (already known) |
| C1 | `historical_f2_trade_scenario` | does any import/export volume appear at all? |
| C2 | trade scenario + **wage floor raised** | a knife-edge test only: does an already-wages-crippled circuit deliver externally sourced goods? |

The intervention for C2 uses `policy.wage_factor` via the fork mechanism if convenient, or is run as
a full-window scenario variant; record which.

**Metrics** (compact outputs only): per-commodity and total `imports`/`exports` (CMEA vs convertible
channels separately, never summed across channels), whether each channel is non-binding
(imports/credits equal to their declared demand), and the reproduction-table verdict for
`trade_export_volume_index` and `trade_import_volume_index` if the crosswalk is updated to map them.

**Success criteria and honest outcomes.**
- If C1 produces **zero** imports/exports despite nonzero declared demand: the external channel does
  not transmit under the current structure. Record the cause (demand vector not reaching the right
  commodity cell, financing scale zero, import-pool/treasury path blocked) and mark both trade
  indices **permanently `no_counterpart`** with that reason. **This is a first-class result**, not a
  failure.
- If C1 produces nonbinding imports/exports: reclassify both trade indices to `mapped` with
  `comparison_grade: normalized_index` (or `allocated` if the vector needed an external share), a
  declared `source` of type `scenario_declared_trade_vectors` (distinct from
  `admitted_target_artifacts`, with the scenario id and digest), and the scenario-not-circularity
  note. Update `reproduction_table.py` to accept the new source type **only** for these two
  variables and to keep rejecting a `mapped` row without a source. Report the resulting numeric rows
  as reproduction under declared inputs, not a fit.
- The consumption failure is reported first and in full regardless; a trade-scenario success says
  nothing about consumption.
- If C2 is needed, report it as a knife-edge diagnostic, not a remedy.

Add a clearance item `p06_trade_transmission` that checks the transmission summary exists (as an
`internal` check over the run summary), not a hard-coded status.

Commit Part 2 alone.

---

## Execution prompt (paste into a local Codex)

```text
Execute docs/phases/P06_TRADE_TRANSMISSION_PLAN.md in this repository
(hungary-socialist-mechanism-lab, main at 3df2f85 or later). Read first: the plan, the reviewer
audit at the end of docs/phases/P06_CLEARANCE_LOG.md, config/calibration/p06_reproduction_crosswalk.json,
tests/test_p06_reproduction_table.py, and engine/trade.py::realize_imports plus engine/material.py's
trade pre-pass for the import mechanics.

Do Part 1 (R9/R10/minor label corrections), commit, then Part 2 (Plan C), commit. Keep every
standing prohibition: reproduction scope, calibrated = 0, no block promoted to identified, no Sobol for
unidentified parameters, no fabricated series or mapping, the trade vectors must NOT be derived from
the admitted KSH trade index or any target series (that is circular), hold-out unused, reserved
window 1986Q1-1988Q4 closed. Append to the clearance log, never stage .omp/config.yml, never
push/rebase/clean, run ruff and the suite before each commit, and regenerate
outputs/p06-clearance/pytest.json plus `hsm calibration p06-clearance --with-runs` at the end.

Part 1: reclassify the two trade indices to blocked with the non-circular missing-item reason;
replace the crosswalk count assertions with invariant assertions in
tests/test_p06_reproduction_table.py; reconcile bank_circuit in the plan inventory. Commit.

Part 2: add config/scenarios/historical_f2_trade_scenario.json (register it in AVAILABLE_SCENARIOS)
with nonzero per-commodity CMEA/convertible import and export demand vectors sourced from the
registered external pack / p04.external_recipe base levels and declared prices, never from targets;
declare credit envelopes/reserves/loans high enough to be non-binding (report if the
distribution-working-capital guard trips). Run C0 (baseline), C1 (trade scenario), and only if
needed C2 (a wage-factor knife-edge diagnostic). Every run records parameter hash, seed, scenario id,
replay digest and per-commodity import/export volumes by channel. Then: if C1 yields zero imports or
exports, mark both trade indices permanently no_counterpart with that cause and treat it as a result;
if C1 yields nonbinding trade, reclassify both to mapped (normalized_index or allocated), add a
scenario_declared_trade_vectors source with the scenario digest, teach reproduction_table.py to accept
that source type only for these two variables while still rejecting source-less mapped rows, and report
the numeric rows as reproduction under declared inputs. Report the consumption failure first and in
full regardless; a trade success says nothing about consumption.

Finish by regenerating the evidence and checklist, then report in chat and in
docs/phases/P06_RUN_REPORT.md: the Part 1 corrections with file paths, the scenario definition and its
provenance, the C0/C1/C2 outcome with the cause if the channel did not transmit (or the numeric rows
if it did), the crosswalk final counts by status, the clearance item table, the commit hashes, and the
ruff/pytest result. Report partial results as partial and never describe anything as validated,
calibrated or identified. Do not ask anything.
```