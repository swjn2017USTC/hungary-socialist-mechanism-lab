# Codex prompt 1 of 2 — P06 Part 1: label corrections only (no new experiments)

Copy everything below the line into the local Codex session. This prompt is deliberately short:
three small edits and one commit, no new runs, no mechanism work.

---

Work in `hungary-socialist-mechanism-lab` (`main`, base `8c393a8`). This is **Part 1 only** of
`docs/phases/P06_TRADE_TRANSMISSION_PLAN.md`; do not start Part 2 (the trade scenario) in this
session. Read `docs/phases/P06_CLEARANCE_LOG.md`'s reviewer audit entry (R9/R10) and
`config/calibration/p06_reproduction_crosswalk.json` first.

Make exactly these three edits, then commit once with a message naming Part 1 and the three edits.

1. **R9 — relabel the two trade volume indices `blocked`.** In
   `config/calibration/p06_reproduction_crosswalk.json`, set the `status` of
   `trade_export_volume_index` and `trade_import_volume_index` from `no_counterpart` to `blocked`.
   Keep their existing `reason`, `candidate_model_quantity` and `methodological_difference` text and
   set `comparison_grade` to `blocked`. Append to the reason that the model *has* the trade machinery
   but `config/scenarios/historical_f2_replay.json` declares all four trade-demand vectors
   (`cmea_desired_imports`, `convertible_desired_imports`, `cmea_export_demands`,
   `convertible_export_demands`) as zero, so imports and exports are identically zero and a
   model-own-1960 index has no base; and that the missing item is a declared **non-circular**
   trade-demand scenario — the admitted KSH trade index must **never** be fed back as a demand
   vector.

2. **R10 — assert invariants, not this run's counts.** In
   `tests/test_p06_reproduction_table.py::test_reproduction_crosswalk_covers_exactly_the_admitted_target_variables`,
   delete the count assertions (`statuses.count("mapped") == 1`, `count("no_counterpart") == 13`,
   `count("blocked") == 0`), the `mapped["variable_id"] == "consumption"` /
   `comparison_grade == "normalized_index"` / `error_tolerance == 0.5` pins, and the
   `comparison_grade == "normalized_index"` count. Replace them with: the crosswalk covers exactly
   the 14 admitted variables; every `status` is in `{"mapped", "no_counterpart", "blocked"}`; every
   `mapped` entry carries a non-empty `comparison_grade`, `source`, `comparison_window` and
   `error_tolerance`; any entry with `allocation_assumed` also lists artifact digests. Keep the
   checks that the two trade entries still declare their `candidate_model_quantity` and the
   "CMEA versus convertible composition is not inferred" wording, but assert their **status vocabulary
   membership**, not a specific status.

3. **Minor — reconcile `bank_circuit`.** In `docs/phases/P06_EXECUTION_PLAN.md`, in the
   available-artifacts list, annotate `bank_circuit` as available to leak-audit observers but not
   emitted by compact fork output (matching `P06_POLITICAL_COUNTERFACTUAL.md`), or drop it.

House rules: reproduction scope, `calibrated = 0`, no block promoted to identified, no fabricated
data, hold-out unused, reserved window 1986Q1–1988Q4 closed. Do not touch engine code, scenarios,
parameter defaults or frozen registries. Never stage `.omp/config.yml`; never push, rebase or
clean. Run `.venv/bin/ruff check src tests` and `.venv/bin/python -m pytest -q -p no:cacheprovider`
before committing — the commit must be green. Append one entry to
`docs/phases/P06_CLEARANCE_LOG.md` naming R9, R10 and the minor edit with their file paths.

Finish by running `.venv/bin/hsm calibration p06-clearance --with-runs`, regenerating
`outputs/p06-clearance/pytest.json`, and reporting: the three edits with file paths, the
crosswalk status counts after the relabel, the clearance item table, the commit hash and the
ruff/pytest result. Do not ask anything.