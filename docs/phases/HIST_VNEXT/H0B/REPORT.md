# H0B Report: 11卡语义、真实metric、单位与研究状态overlay

## Delivery summary
H0B registers all 11 legacy cards and all 41 metrics they declare, corrects the table
registry to the model's real output schema, denominates physical flows in the
commodity's own ontology unit, reports per-run observability with distinct failure
modes, and revises the research status through an overlay. The independent phase
review then returned **PATCH** with two P1 and two P2 findings; this round fixes each
finding at its source, adds a regression that reproduces it, and re-runs the gate.

Phase gate: **796 tests pass** (791 before the repair, 5 new regression tests), ruff
clean, `hsm baseline verify` matches the frozen audit anchor, overlay JSON valid.

## Files modified (this repair round)

### src/hsm_lab/evidence/adapter.py
| Change | Description |
|--------|-------------|
| `ObservationStatus.DATATYPE_MISMATCH` | New status for a column whose datatype contradicts the metric's declared semantics; the status docstring now lists the wrongly typed column among the distinct failure modes |
| `CATEGORICAL_UNITS` | The declared-unit set whose values are categories (`binding_constraint_label`), imported from `metric_enricher`; every other declared unit is a quantity |
| `_observe_parquet` selector application | The declared `commodity_id`/`region_id` selectors are now collected once and applied to the row set **before** any value is read, for a one-axis metric exactly as a joint one (previously the filter ran only when more than one axis was declared) |
| `_observe_parquet` datatype binding | A metric declaring a quantity unit whose column is non-numeric is reported `datatype_mismatch` instead of being read as labels; an all-null column still falls through to `null_values`; a metric declaring a label unit is observed as labels regardless of dtype |
| `MetricObservation.labels` / `_observe_categorical` docstrings | Describe the declared-label semantics instead of "a column that is not numeric" |

### studies/HIST_VNEXT/declarations/research_status_overlay.json
| Change | Description |
|--------|-------------|
| `reference_run` block | Names the run the frequencies were counted against: path, `run_id`, `scenario_id`, `seed`, `ticks`, deterministic replay digest, manifest SHA-256, and the global observability tally |
| `observability_in_reference_run` (11 records) | Replaced the partial tallies with the genuine per-card frequency of `observe_registry`; each record's frequencies now sum to its `metrics_total` |
| `observability_note` | Records that the frequencies are an observability report read from the reference run and that they raise no structural or historical verdict |
| `summary.observability_in_reference_run` | The global tally (`observable` 10, `semantics_blocked` 23, `sidecar_absent` 4, `table_empty` 4 = 41) |

### tests/test_hist_semantic_registry.py (5 new regression tests)
| Test | Finding |
|------|---------|
| `TestSelectorAndDatatypeBinding::test_a_single_axis_selector_excludes_undeclared_rows` | P1-2: 20 declared regions at `0.0` plus an undeclared region at `999.0` is a measured zero, not `(0.0, 999.0)` |
| `TestSelectorAndDatatypeBinding::test_an_undeclared_null_cannot_unmeasure_the_declared_window` | P1-2: a null in an excluded row cannot turn a measured zero into `null_values` under `missing_policy=abort` |
| `TestSelectorAndDatatypeBinding::test_a_numeric_metric_rejects_a_non_numeric_column` | P1-1: `household_consumption` with string values is `datatype_mismatch`, not `observable` with labels |
| `TestSelectorAndDatatypeBinding::test_a_label_metric_with_a_numeric_column_is_still_read_as_labels` | P1-1: a declared label metric is never coerced to `float`, whatever the dtype |
| `TestH0BOverlays::test_overlay_observability_frequencies_equal_the_reference_run` | P2-1: every per-card frequency equals `observe_registry` on the reference run, sums to `metrics_total`, and the `reference_run`/`summary` tallies equal `observation_counts`; the run identity is checked against its own `manifest.json` |

### docs/phases/HIST_VNEXT/H0B/{PLAN,REPORT,REVIEW}.md (new)
The required phase delivery evidence: the executed scope and whitelist, this report,
and the preserved independent review with its findings.

## Repair round: reproductions and results

### P1-1 — a numeric metric read as categorical
Reproduced on `M1#0 household_consumption` with the 16 declared commodity IDs and a
string `household_consumption` column: the old branch treated every non-numeric
datatype as a valid categorical measurement and returned
`status='observable', values=None, labels=('not_a_quantity',)`. The branch is now
bound to the metric's declared unit:
`status='datatype_mismatch', observable=False, values=None, labels=None`
(detail: *"metric declares the numeric unit 'f2_v1_commodity_physical_unit' but column
'household_consumption' is string: a declared quantity is not a category"*).
`M9#1 policy_decisions.binding_constraints` (declared `binding_constraint_label`)
keeps being observed as labels, including when a producer writes numeric codes.

### P1-2 — a single-axis selector did not filter
Reproduced on `M1#1 household_budgets.spending` with the 20 declared regions at `0.0`
plus an undeclared region at `999.0`: the old code returned
`status='observable', values=(0.0, 999.0)`. The declared selector is now applied
before any value is read, for the one-axis case too:
`status='observable_zero', values=(0.0,)`. An undeclared row's null no longer
converts the declared window's measured zero into `null_values`.

### P2-1 — overlay frequencies disagreed with the reference run
M01 recorded `{observable: 1, table_empty: 1}` against an actual
`{observable: 3, table_empty: 2}`; M11 recorded `{observable: 1, semantics_blocked: 1}`
against an actual `{observable: 1, semantics_blocked: 5}`. The overlay now carries the
genuine per-card frequency for all 11 records, and the new test asserts equality
against `observe_registry`/`observation_counts` on
`outputs/hist-vnext-audit-20261015/C0-r1` (run `ebe44a8a7af2423e9de6eb85fd2ffb24`,
seed `1729`, 116 ticks, digest `92f9ea0a…a42d`).

### P2-2 — missing phase artifacts
`docs/phases/HIST_VNEXT/H0B/{PLAN,REPORT,REVIEW}.md` are recorded. The root
`HIST_VNEXT_H0B_PLAN.md` stays as the frozen plan of record; the phase PLAN states the
executed scope against it, and the REVIEW preserves the independent PATCH.
Successful regression tests are not presented as research approval.

## Repair round 2 (independent audit follow-up)

A second independent read of the H0B slice reported two remaining defects. This round
fixes each at its source and adds slice-scoped regressions. It is **not** an
independent verdict on H0B.

### P1 — a scalar JSON artifact could substitute for a registered table quantity
`observe_metric` routed every resolved non-Parquet artifact to `_observe_sidecar`,
which read one key as a number without checking the metric's registered
commodity/region selectors, its 1957Q1–1985Q4 quarter window, or its declared unit.
Three reproduced counterexamples:

| artifact | old result | repaired result |
| --- | --- | --- |
| `national_accounts.json` `{"household_consumption": 0.0}` | `observable_zero`, `values=(0.0,)` | `artifact_unbound`, `observable=False`, `values=None` |
| `household_budgets.json` `{"spending": 999.0}` | `observable`, `values=(999.0,)` | `artifact_unbound`, `observable=False`, `values=None` |
| `policy_decisions.json` `{"binding_constraints": 7}` | `observable`, `labels=None` | `artifact_unbound`, `observable=False`, `labels=None` |

`_observe_sidecar` now requires the evidence gate's own typed `__metric_bindings__`
declaration for the column: exact `unit`, `value_type`, the declared temporal extent,
and an empty selector list consistent with the spec (a scalar cannot satisfy a
declared commodity/region selector). A declared label unit is reported as
`labels=(...)`; a numeric sidecar binding under a label unit is `datatype_mismatch`,
never `labels=None` with `values`. Unmeasured physical consumption is therefore
`artifact_unbound`, distinct from the genuine `observable_zero` that a real Parquet
table of zeros yields.

Regression coverage: `TestSidecarSubstitution` (8 tests), including the three
counterexamples, the typed-binding acceptance path (the refusal is not blanket), a
selector-bearing spec, a mismatched window, a typed label, and a numeric label binding.

### P2 — NaN/inf in a numeric label column became labels
`_observe_categorical` converted every non-`None` value with `str()`, so a float NaN
became the label `"nan"` and bypassed the metric's `missing_policy=abort`; infinity
became `"inf"`. Missing (`None`/NaN) and non-finite cells are now classified before
label conversion: NaN is `null_values`, inf is `nonfinite_values`, and finite numeric
labels remain labels. Regression coverage: `TestCategoricalMissingValues` (4 tests:
NaN, all-NaN, inf, and a finite-float positive control), alongside the existing
integer-label positive control.

### Round-2 verification
| check | argv | result |
| --- | --- | ---: |
| H0B tests | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_semantic_registry.py` | 72 passed |
| lint | `.venv/bin/ruff check --no-cache src/hsm_lab/evidence/adapter.py tests/test_hist_semantic_registry.py` | All checks passed |

Only the H0B test file was run in this repair round; the full suite was **NOT_RUN**
here, as was the independent review. The 12 new regressions (8 sidecar + 4
categorical) account for the file's 72 cases; the reference-run frequencies are
unchanged because the frozen run's core tables are Parquet and its label column has
no NaN.

## Reference-run observability (unchanged by the repairs)
| Card | observable | table_empty | sidecar_absent | semantics_blocked |
| --- | ---: | ---: | ---: | ---: |
| M01 | 3 | 2 | – | – |
| M02 | 1 | – | 1 | 2 |
| M03 | – | – | – | 3 |
| M04 | 2 | – | – | 2 |
| M05 | 1 | – | 1 | 2 |
| M06 | 1 | – | 1 | 2 |
| M07 | – | – | – | 2 |
| M08 | – | 1 | – | 1 |
| M09 | 1 | 1 | – | 1 |
| M10 | – | – | 1 | 3 |
| M11 | 1 | – | – | 5 |
| **total** | **10** | **4** | **4** | **23** |

The registry is 11 cards / 41 metrics, 14 mapped and 27 blocked. The repairs change
no reference-run frequency: the frozen run's axes already match the declared
selectors exactly (16 commodities, 20 regions), and no mapped quantity column is
non-numeric there.

## Round-1 test results (full suite)
```
796 passed, 172 warnings in 86.71s
All checks passed!                      # ruff check --no-cache src tests
{"status": "ok", "sha256": "1f5b233f…"} # hsm baseline verify --json
```

## Round-1 evidence ledger
| step | argv | cwd | exit | result |
| --- | --- | --- | ---: | --- |
| full suite | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` | repo root | 0 | 796 passed |
| lint | `.venv/bin/ruff check --no-cache src tests` | repo root | 0 | All checks passed |
| baseline | `.venv/bin/hsm baseline verify --json` | repo root | 0 | status `ok`, SHA-256 `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` |

No simulation was launched for this phase: the reference run is read, never re-run.
Its digest is the frozen audit value `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`
and was not recomputed or altered here.

## Known limitations
- Registrations are keyed on the legacy cards' frozen SHA-256; a future edit to a card
  is a new identity and must be registered deliberately.
- The reference-run observability is an artefact reading, not a measurement of any
  mechanism: an observable metric is not evidence of the mechanism's behaviour.
- Structural results stay `NOT_RUN` and historical identification stays `UNIDENTIFIED`;
  source admission (H1) and experiments (H5) remain out of scope.
- 172 pytest warnings were pre-existing in the round-1 full suite; the round-2
  slice-scoped test run emitted none.

## Round-3 re-audit repairs (2026-10-18)

| ID | Finding | Repair |
|---|---|---|
| R3-1 | Parquet categorical observations stringified numbers, booleans, lists and structs into labels | After missing/nonfinite classification, only exact `str` cells are labels; other datatypes return `datatype_mismatch` |
| R3-2 | Window membership accepted annual values (`"1958"`, `1958`) and malformed quarters (`"1957Q10"`, `"1960Q9"`) | Row labels are parsed with the strict `Quarter.parse` before window comparison; invalid labels cannot become observations |

Round-3 verification: `tests/test_hist_semantic_registry.py` **81 passed**;
ruff clean. Reference-run counts remain 10 observable / 23 semantics-blocked /
4 sidecar-absent / 4 table-empty.

### Round-4 adapter repairs (2026-10-18)
| ID | Finding | Repair |
|---|---|---|
| R4-1 | Partial quarter × commodity coverage was reported as measured zero | The observer requires a row for every declared quarter × selector combination before returning an observable status |
| R4-2 | `Quarter.parse` normalized trailing-newline/Unicode-digit labels | Labels must already be the canonical ASCII `YYYYQ[1-4]` string; no normalization |
| R4-3 | Present blocked-registration sidecars were reported absent | The declared sidecar is resolved before classification; present-but-unsupported is `semantics_blocked`, absent remains `sidecar_absent` |

Round-4 verification: `tests/test_hist_semantic_registry.py` **85 passed**;
ruff clean. Positive one-quarter fixtures now declare one-quarter windows.

### Round-5 temporal-binding repairs
| ID | Finding | Repair |
|---|---|---|
| R5-1 | `TimeWindow` accepted noncanonical bounds (Unicode digits) and the observer compared text | Bounds must be canonical ASCII `YYYYQ[1-4]`; window membership compares parsed ordinals |
| R5-2 | Out-of-window/reserved rows could influence values | Ordinal membership excludes them before values/labels/missing classification |

Round-5 verification: focused suite **87 passed**; ruff clean.

## Current verification (2026-10-18, supersedes round-1 count)
The round-1 `796 passed` figure is historical. The current full suite is
**1100 passed**, ruff clean; `tests/test_hist_semantic_registry.py` is
**87 passed**. The reference-run observability counts are unchanged.
