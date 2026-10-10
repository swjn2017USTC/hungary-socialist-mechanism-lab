# Codex prompt — unblock the fork arms, then declare the reproduction crosswalk

Paste everything below the line into the local Codex session. Two work items, in this order,
then a clearance rerun. Work unattended; never ask a question.

---

Continue P06 in this repository (`hungary-socialist-mechanism-lab`, `main` at `d74ae83` or
later). Read first: `docs/phases/P06_RUN_REPORT.md`, `docs/phases/P06_CLEARANCE_LOG.md` (the
reviewer audit at the end is authoritative about what is blocked and why),
`docs/phases/P06_EXECUTION_PLAN.md` (W5–W8), `docs/phases/P06_FINAL_REPORT.md`, and
`config/calibration/p06_clearance.json`.

Two work items, then a clearance rerun. Keep every prohibition from the plan: the study is a
historical reproduction under declared behavioural assumptions, `calibrated = 0`, no block is
promoted to `identified`, no Sobol for unidentified parameters, no `SUPPORTED` verdict for a card
that depends on one, no fabricated series, the seven unadmitted target-role variables stay
unadmitted, hold-out unused, reserved window 1986Q1–1988Q4 closed. Commit one green commit per
item (`ruff check src tests` and `pytest -q -p no:cacheprovider` before each), append to
`docs/phases/P06_CLEARANCE_LOG.md`, never stage `.omp/config.yml`, never push/rebase/clean.

## W0.5 — unblock W5, W6, W7 (costs about a minute; both commands are already verified)

**Why it was blocked:** every `tick-0044` checkpoint on disk is `material-checkpoint-v3` while
`storage/checkpoint.py::CHECKPOINT_VERSION` is `material-checkpoint-v4`. The v3→v4 bump added
state arrays and six kernel fixes, so an upconverter would have to invent state — **do not write
one**. Mint a fresh parent instead; this is verified to work in 3 seconds.

1. Mint one parent run covering both fork boundaries:

```
.venv/bin/hsm run --scenario p04_endogenous --until 1973Q1 --checkpoint-every 4 \
  --output-dir outputs/p06-fork-parent --json
```

It writes `material-checkpoint-v4` checkpoints; `checkpoints/tick-0044` has `completed_ticks 44`
and `last_completed_quarter 1967Q4` (so the next tick is 1968Q1) and `checkpoints/tick-0064` has
`completed_ticks 64`, `last_completed_quarter 1972Q4` (next tick 1973Q1). Record the parent's
manifest digest, its wall time, and both checkpoint metadata files.

2. Fork each arm from the correct boundary. **The control for each family is the
   empty-intervention fork from the same checkpoint** (`config/interventions/hist-nem.json`,
   an empty list — do not invent a new control).

| family | checkpoint | arms (intervention files) |
|---|---|---|
| 1968 | `.../tick-0044` | `hist-nem.json` (control), `no-reform.json`, `nem-plus.json`, `nos-hu.json`, `digital-nem.json` |
| 1973 | `.../tick-0064` | control (empty), `1973-borrowing-smoothing.json`, `1973-consumption-restraint.json`, `1973-investment-restraint.json`, `1973-price-wage-compensation.json`, `1973-hard-budget.json` |
| political | `.../tick-0044` | control (empty), `p06-political-coalition-weights.json`, `p06-political-soviet-constraint.json`, `p06-political-consumer-import.json`, `p06-political-cultural-openness.json`, `p06-political-second-economy.json` |

Run each to the horizon with a bounded cost:

```
.venv/bin/hsm fork --checkpoint <checkpoint-dir> --intervention <file> \
  --until 1985Q4 --output-dir outputs/p06-arms/<family>/<arm> --json
```

Expected cost is 1–3 seconds per arm (a 56-tick fork measured 1 s); if any arm exceeds 10
minutes, apply the plan's degradation ladder (reduced arm set) and say so. If an arm fails a
gate or an invariant, **keep it in the table as rejected with its message** — never drop it
silently and never relax a gate to keep it.

3. Write a compact machine-readable summary `outputs/p06-arms/summary.json` with, per arm:
   family, arm id, intervention file, source checkpoint, completed ticks, last quarter,
   parameter hash, intervention hash, replay digest, and the metric set from the plan §3
   (material/household/shortage proxies/finance/political/opposition/information/departmental).
   Then write `docs/phases/P06_1968_FORK.md`, `docs/phases/P06_1973_SHOCK.md` and
   `docs/phases/P06_POLITICAL_COUNTERFACTUAL.md` reporting the tables. Mechanism verdicts may be
   recorded for M5/M6/M8/M9/M10 but **capped at CONDITIONAL or UNIDENTIFIED** where the card
   names an unidentified dependency, and every verdict states which arm produced it.

4. Close the three clearance items **by adding real checks, not by flipping a status and not by
   waiving**. In `config/calibration/p06_clearance.json` replace the `unsatisfied` entries
   `p06_1968_runs`, `p06_1973_runs`, `p06_political_runs` with checks that read
   `outputs/p06-arms/summary.json` (for example a `json_field` on an arm count, or a new
   `internal` check asserting the required arm ids are present with distinct digests). An item
   must pass only if the arms actually ran. If the summary is absent in a fresh clone the item
   is OPEN, which is correct — add a note saying how to regenerate it.

## W9 — declare the comparison crosswalk, then compute the numeric reproduction table

W8's final report records the like-for-like comparison as OPEN because **no commodity/unit
crosswalk, annual aggregation rule or error tolerance is declared**. Do not invent a mapping to
make a table appear. Declare it first, then compute only what the declaration supports.

1. Add `config/calibration/p06_reproduction_crosswalk.json`, referenced from
   `config/calibration/p05.json`, with one entry per admitted variable (the 14 in
   `data/manifests/p05_targets.yml`) decided **one of three ways**:
   - `mapped`: the model-side quantity is named (a simulation output and its commodity/stage,
     e.g. `national_accounts.production` for a commodity, `departments.actual_use_value` for a
     department split), with `target_unit`, `model_unit`, `comparison_rule` (`index_1960_100`
     normalization or a physical-unit match with a declared conversion), `annual_aggregation`
     (`mean` or `sum`, consistent with the variable registry), `comparison_window`
     (calibration 1960–69 and/or internal validation 1970–78) and the declared `error_tolerance`;
   - `no_counterpart`: with the reason (the model has no such quantity);
   - `blocked`: with exactly what is missing (unit conversion, commodity mapping, data).
   For index targets the model series must be **normalized to its own 1960 value** — state that
   this is a declared normalization, not a fit, and never adjust the model to match the index.
   The tolerance is a **declared research threshold** justified from the series' published
   precision (rounding, unit resolution), never tuned until a residual passes. Do not re-map a
   variable to make it pass, and keep the per-variable warnings from `data/manifests/variables.yml`
   (GDP is an index and gross material output must never be passed off as it; imports are an
   outcome, not a quota; television output is not media exposure).
2. Add `hsm calibration reproduction-table --output-dir <fresh dir>` that reads the crosswalk,
   runs the declared replay once, aggregates annually, and writes a per-(variable, year) table of
   target value, model value, residual, tolerance and verdict, plus per-variable summary rows,
   and prints how many variables are `mapped` / `no_counterpart` / `blocked`. It must refuse to
   emit a row for a variable that is not `mapped`, and it must read hold-out or reserved values
   only through the window protocol (which refuses them in this phase).
3. Update `docs/phases/P06_FINAL_REPORT.md`: replace the OPEN paragraph with the crosswalk
   summary and the resulting table, and report the three counts honestly. A table with few
   mapped variables is a **correct result**, not a failure to be worked around.

## Finish

Regenerate the evidence and the checklist:

```
.venv/bin/python -m pytest -q -p no:cacheprovider   # write outputs/p06-clearance/pytest.json
.venv/bin/hsm calibration p06-clearance --with-runs
```

Report in chat and in `docs/phases/P06_RUN_REPORT.md`: the parent run's wall time and both
checkpoint paths, the arm table (family, arm, digest, metrics, disposition), the crosswalk
counts (`mapped` / `no_counterpart` / `blocked`), the reproduction table's verdicts, the
clearance item table with any remaining OPEN item and its owner, the commit hashes, and the
`ruff`/`pytest` result. Report partial results as partial, falsified mechanisms as falsified,
and never describe anything as validated, calibrated or identified. Do not ask anything.
