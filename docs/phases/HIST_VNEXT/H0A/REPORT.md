# H0A Report: P07身份、时间、缺失与证据晋级修复

## Delivery summary
All whitelisted files modified and passing. Phase gate: ✅ 586 tests, ruff clean, baseline verify ok, lock check ok.

## Files modified

### src/hsm_lab/evidence/schemas.py
| Change | Description |
|--------|-------------|
| `MissingPolicy` enum | ABORT/SKIP/INTERPOLATE — zero_fill rejected at type level |
| `canonical_mechanism_id()` / `study_mechanism_id()` | Reversible M1–M11 ↔ M01–M11 normalisation |
| `TimeWindow._study_window` | 1957Q1–1985Q4 ordinal bounds; future/1956Q4 rejected |
| `ObservedState` | `extra="forbid"`, `available_at`+`decision_at`, ordering validator |
| `EvidenceRunReference` | Strict seed:int (bool rejected via `mode="before"`), digest pattern |
| `EvidenceRecord._supported_requires_runs` | Non-empty, unique run_ids, unique (run_id,seed) pairs, minimum_replicates counted over DISTINCT seeds |
| `StudyDeclaration` / `StudyManifest` | Intent form, card_id property, self-card identity |

### src/hsm_lab/evidence/loader.py
| Change | Description |
|--------|-------------|
| `validate_evidence_manifest` | Strict dispatch: EvidenceManifest requires `hypothesis` field, StudyManifest requires `intent` |
| `load_all_evidence_records` | Union return type |
| `write_evidence_manifest` | Rejects StudyManifest; re-validates via `model_validate_json`; O_EXCL no-clobber |
| `verify_evidence_manifest_runs` | Run identity per reference, `run_id` match, duplicate actual-run rejection, and only DISTINCT seeds count as independent replicates |
| `_verify_study_sidecar` / `_verify_sidecar_content` | Sidecar is read and cross-verified: canonical `mechanism_id`, `intent`, `status`, canonical `linked_cards`, `phase` (record phase, else manifest phase), and card-bound `v1_card_sha256` |

### src/hsm_lab/evidence/run_adapter.py
| Change | Description |
|--------|-------------|
| Removed `build_stub_evidence_record` | No production callers |
| `verify_digest_unchanged` | Delegates to `verify_run_identity` |

### src/hsm_lab/evidence/provenance.py
| Change | Description |
|--------|-------------|
| `verify_run_identity` | Full gate: run_kind, completed, seed strict, scenario_hash, non-zero hashes, output tree, lock_hash, data_manifest_hash |

### tests/test_hist_identity_guards.py (NEW — 71 tests)
| Class | Tests |
|-------|-------|
| `TestCanonicalStudyMechanismId` | 9 (M1–M11 round-trips, invalid) |
| `TestMissingPolicy` | 7 (enum, string rejection, zero_fill variants) |
| `TestTimeWindowBounds` | 8 (1957Q1–1985Q4, 1956Q4, future) |
| `TestObservedState` | 7 (availability ordering, extra=forbid) |
| `TestEvidenceRunReference` | 7 (valid, invalid, bool seed) |
| `TestSupportedRequiresRuns` | 8 (structural gate, distinct-seed replicate gate) |
| `TestSameSeedReplicateGate` | 4 (same-seed publish gate, JSON parse path, distinct-seed control) |
| `TestVerifyRunIdentity` | 13 (boundary tests) |
| `TestStudyDeclarationManifest` | 10 (intent form, dispatch) |
| `TestInterventionBinding` | 4 (quarter bounds) |

## Phase reviewer results
- Pass 1: PATCH (7 P0, 5 P1)
- Pass 2: PATCH (5 P0, 2 P1)
- Pass 3: PATCH (4 P0, 2 P1)

### Fixed in this implementation
✅ P0: EvidenceRunReference seed bool coercion (mode="before" validator)
✅ P0: write_evidence_manifest no-clobber (O_EXCL atomic exclusive create)
✅ P0: write_evidence_manifest re-validation (model_validate_json before write)
✅ P0: SUPPORTED structural gate (non-empty, unique, minimum_replicates)
✅ P0: verify_run_identity scenario_id verification (load_scenario → compute_scenario_hash)
✅ P1: InterventionBinding quarter lower bound (1957Q1 minimum)

### P0 closure follow-up (REVIEW.md residual R6 + sidecar content)
✅ P0: Independent stochastic replicate distinction — `_supported_requires_runs` and
`verify_evidence_manifest_runs` count replicates over DISTINCT seeds; two references
sharing a seed are deterministic replays and are rejected with an explicit same-seed
message, however many distinct run_ids/pairs/output dirs they contribute.
✅ P0: Sidecar content cross-verification — `_verify_study_sidecar` reads
`studies/<id>/study_decl.json` and requires its `intent`, `status`, canonical
`linked_cards` and `phase` (record phase, else the containing manifest's phase) to
match the declaration, alongside the existing canonical `mechanism_id` and
card-bound `v1_card_sha256` checks. Missing content keys are errors, never skipped.
Reason texts (`declared_reason`/`blocked_reason`) are deliberately NOT compared
full-text: the plan records that the manifest and sidecar word them differently.

Regression tests: 17 added (2 in `TestSupportedRequiresRuns`, 4 in
`TestSameSeedReplicateGate`, 11 sidecar-content tests in
`TestStudyManifestCardVerification`, including real-data content binding).
Full suite: 647 passed; ruff clean; `hsm baseline verify` ok.

### Known limitations (out of H0A scope)
⏳ P0: Parameter/recipe hash recomputation from actual material_parameter_vector — requires scenario spec access
⏳ P0: Recomputing the accounting residuals from run tables (balance identities) — requires domain-specific checks; the run's own certification block IS verified, and table/column/window/selector/unit content binding IS covered (see the closure sections below)
⏳ P1: 11-card semantic mapping and historical support scoring — H1 scope
⏳ P1: Mechanism ID cross-card uniqueness and supersedes chain — H2 scope

## Test results
```
586 passed, 108 warnings in 49.32s
All ruff checks passed
uv lock --check --offline: Resolved 101 packages
hsm baseline verify: SHA256 matches frozen audit anchor
```

## P0-2 / P0-3 closure (metric content + fabricated trajectories)

Two residual P0s from the upgrade review — "metric content verification" and
"fabricated trajectories" — are closed. Both extend gates that were already the
single choke points, so no new bypass path is introduced.

### P0-2: metric content verification (`loader.py`)
`verify_supported_record_runs` now ends with `verify_supported_metric_content`,
which checks **every** `metric_specs` entry against the output of **every** run
the record references (not just the first replicate):

| Check | Behaviour |
|-------|-----------|
| Table/sidecar existence | `_metric_artifact_path` resolves `<name>.parquet` at the run root or under `trajectory_tables/`, a file `<name>`, or sidecar `<name>.json`; results outside the run directory are refused |
| Column existence | Parquet: column must be in the table schema. Sidecar: key must be present with a non-null value |
| Actual data (TARGET / CANDIDATE_LINKAGE) | The column may not be entirely null/NaN — a placeholder column is not a measurement |
| Time-window coverage | Every quarter in the declared `time_window` must appear in the table's `quarter` column (ordinal arithmetic, inclusive) |
| Selector coverage | Declared `commodity_axis`/`region_axis` values must all appear in the table's `commodity_id`/`region_id` column; the enricher's `all_20_regions` alias is expanded |

Errors name the record, metric, artifact and run directory. A metric declared
in one replicate but absent from another is rejected.

### P0-3: fabricated trajectories (`provenance.py::_verify_material_tick_data`)
Material runs must now ship content, not just files:

| Artefact | Requirement |
|----------|-------------|
| `summary.json` | Must carry the identity fields a completed material run records (`run_kind`, `scenario_id`, `seed`, `planned_ticks`, `completed_ticks`, `households`, `commodity_ids`, `region_ids`, `parameter_hash`, `initial_recipe_hash`, `deterministic_replay_digest`, `input_artifact_hashes`, `row_counts`), each typed and bound to the manifest by the existing mirrored-field check — a `{"run_id": "test"}` placeholder is rejected |
| `initial_recipe.json` | Non-empty object, non-empty `declaration`, an `initial_recipe_hash` equal to `manifest.initial_recipe_hash`, and a `scenario_id` equal to the summary's — `{}` is rejected |
| Trajectory tables | The material runner's schema, not `tick,value`: `tick` + `quarter` keys, the table's axis key columns (`region_id`/`commodity_id`/`stage`, from the F2 registry), and ≥3 columns — enforced for 0-row tables too |
| Universe coverage | Every non-empty axis table must contain every `manifest.commodity_ids` / `manifest.region_ids` value |

Existing checks (trajectory store or non-empty `trajectory_tables/`, declared
row counts, `tick` column, tick coverage of every completed tick) are unchanged.

### Regression tests (30 added, `tests/test_hist_identity_guards.py`)
- `TestVerifyRunIdentityFabricatedArtefacts` (12): `tick,value` stub, missing
  axis columns, missing `quarter` key, stub schema on a 0-row table, table
  covering one of 16 commodities, empty `{}` recipe, declaration-less recipe,
  recipe hash mismatch, recipe from another scenario, placeholder summary,
  summary without `scenario_id`, summary with an empty commodity universe.
- `TestSupportedMetricContentBinding` (16): positive control (four bound
  metrics + sidecar), publish-gate path, missing table, missing column, empty
  table, uncovered window, uncovered commodity selector, region selector on an
  axis-less table, quarter-less table, sidecar missing column, sidecar null
  value, all-null column, all-NaN column, metric present in only one of two
  replicates, the exact P0-2 fabrication (plausible table/column no run wrote),
  and the real-C0 whole-gate binding control.
- Real-run controls: `test_real_audit_run_still_verifies[C0,C1]` re-verifies the
  frozen audit runs with the hardened schema checks, and
  `test_real_audit_run_metric_bindings_pass` drives the whole SUPPORTED gate
  over the real C0 output (6 metric bindings across 5 tables).
- The shared fixture `_write_self_consistent_material_run` now writes the
  material runner's table schema, the scenario's commodity/region universe, a
  real recipe declaration and the full summary identity set (the old fixture
  wrote `tick,value` tables and `{}` recipes, i.e. exactly the fabrication
  P0-3 was raised about).

Full suite: 679 passed, 0 failed; `ruff check src tests` clean;
`hsm baseline verify` ok; real C0/C1 digests still verify.

## P0-1 / P0-2 / P0-3 residual closure (joint coverage, recipe content, linked snapshots)

Three remaining H0A P0 residuals are closed. All three harden gates that were
already the single choke point, so no new bypass path or public API is added.

### P0-1: quarter × selector coverage is joint (`loader.py`)

Window coverage and selector coverage were checked independently, so a table
could carry every declared quarter *and* every declared commodity/region while
having no row for a declared commodity in part of the window (e.g. no
`g09_basic_food` rows in `1957Q1`). `_verify_metric_parquet_content` now ends
with `_verify_joint_coverage`, which requires a row for **every** declared
quarter × commodity × region combination of the metric's axes (an undeclared
axis stays unrestricted). Missing combinations are reported by name, and the
`missing_policy` is echoed in the error.

### P0-2: recipe declaration is content-bound (`provenance.py`)

`initial_recipe.json` was only checked to be non-empty and to agree on hash and
scenario. The recipe hash binds the scenario's organization/technology/route
recipe — *not* the initial-state declaration — so a hand-written declaration
rode along on a correct hash. `_verify_material_tick_data` (now receiving the
loaded `ScenarioSpec`) validates the declaration against the
`MaterialInitialRecipe` schema (unknown fields, wrong literals and wrong types
are rejected) and then requires it to equal the recipe the scenario actually
declares, reporting the differing fields. Verified runs cannot present an
initial state the scenario never declared.

### P0-3: linked observed states are root-backed (`loader.py`)

`linked_observed_states` was never consulted, so a SUPPORTED record could link
snapshots of runs and quarters that do not exist. `verify_supported_record_runs`
now collects the `_VerifiedRun`s produced by `verify_run_identity` and calls
`_verify_linked_observed_states`:

| Check | Behaviour |
|-------|-----------|
| Non-empty linkage | A SUPPORTED record must link at least one observed state |
| `source_run_id` | Must name one of the record's verified runs |
| `source_scenario` | Must be that run's verified scenario |
| `source_digest` | Must be the digest the run verified with |
| `source_checkpoint_quarter` | Must appear in the source run's own output, read from the `quarter` columns of the tables its `summary.json` declares (`_run_output_quarter_labels`) |

### Regression tests (14 added, `tests/test_hist_identity_guards.py`)
- `TestSupportedJointQuarterSelectorCoverage` (4): commodity missing in one
  declared quarter, region missing in one declared quarter, missing
  commodity × region pair, and the intact-run control.
- `TestSupportedLinkedObservedStates` (6): no linked state, unverified
  `source_run_id`, wrong `source_scenario`, wrong `source_digest`, checkpoint
  quarter absent from the source run's output, and the real-C0 control
  (`1985Q4` checkpoint over the real run).
- `TestVerifyRunIdentityFabricatedArtefacts` (+4): fabricated declaration value,
  unknown declaration field, wrong declaration `role`, and the unmodified-recipe
  control.

The shared SUPPORTED fixture now carries a valid linked observed state (the
gate requires one), so the existing positive controls exercise the new check.

Full suite: 693 passed, 0 failed; `ruff check src tests` clean;
`hsm baseline verify` ok; real C0/C1 runs still verify.

## P0-1 / P0-2 / P0-3 residual closure (non-finite data, layer/unit binding, certification)

The last three H0A P0 residuals are closed. All three harden gates that were
already the single choke point, so no new bypass path or public API is added.

### P0-1: non-finite metric values are not data (`loader.py`)

`_verify_metric_parquet_content`'s data check for TARGET/CANDIDATE_LINKAGE
metrics rejected an *entirely* null/NaN column but accepted `inf`/`-inf`, which
aggregate into an infinite metric. The check now also rejects any infinite
value in the column (`_is_nonfinite_value`, `math.isfinite`), reported with the
count, an example, and the row count, so one infinite cell cannot ride along
behind finite ones. NaN stays classified as missing data (its own message).

### P0-2: metric fidelity and unit are bound to the run (`loader.py`)

`_verify_supported_metric_fidelity` only rejected `no_counterpart` metrics;
nothing tied a metric's declared `fidelity`/`unit` to the run it claims to be
measured in. `verify_supported_metric_content` now checks, per referenced run:

| Check | Behaviour |
|-------|-----------|
| Run layer | `_run_declared_layer` reads `fidelity` from the run's own `manifest.json` (`ontology_id` prefix when absent, the rule `p05_manifest_fields` applies); a run declaring neither is refused rather than assumed |
| Metric fidelity | `_RUN_LAYER_METRIC_FIDELITIES` maps `f1` → `F1_intermediate_8` and `f2` → `F2_run`/`F2_diagnostic`; an F1 metric against an F2 run (or the reverse), or a `synthetic` probe (no run layer), is rejected |
| Metric unit | `_verify_metric_unit_binding` requires the declared `unit` to be one of the units the model declares for the `(table, column)` pair (`metric_table_units()`, derived from the enricher's map); an unregistered pair (sidecar, custom column) has no declared unit and is left to the content checks |

Unit binding is checked after the artefact-level checks, so a record is never
rejected on its unit claim for an artefact that was never there.

### P0-3: the run's accounting certification is verified (`provenance.py`)

`summary.json`'s `invariants` block was never read. `_verify_material_tick_data`
now requires it to be present and self-consistent — the residual/tolerance
fields the runner's certification records (finite, non-negative), tolerance
ratios at or below the 1.0 ceiling, and `checked_ticks` equal to the
`completed_ticks` the run reports (already bound to the manifest). This checks
the certification the run reports; it does not recompute the accounting
(`verify_run_identity` is read-only and the residuals are the engine's).

### Regression tests (29 added, `tests/test_hist_identity_guards.py`)
- `TestSupportedMetricContentBinding` (+15): all-infinite column, one `inf` /
  `-inf` among finite values, finite-extreme control, F1 metric against an F2
  run, F2 metric against an F1 run, synthetic probe against a run, run without
  a declared layer, ontology-implies-layer control, unit mismatch, registry-unit
  control, unregistered-pair control.
- `TestVerifyRunIdentityAccountingInvariants` (+17): certified-run control,
  ratio-at-the-ceiling control, missing block, empty block, missing field, ratio
  above the ceiling (both ratios), non-finite values (NaN/±inf), non-numeric
  values, negative value, partial `checked_ticks`, non-integer `checked_ticks`.
- The shared fixture now writes the certification block and declares the run's
  layer (`fidelity="f2"`, `ontology_id="f2_v1"`, as the real C0 run does); two
  positive controls that declared a `count` column in `M_forint` now declare it
  in its registry unit.

All 416 material run summaries in the repository satisfy the certification
check (`checked_ticks` == `completed_ticks`, ratios < 1.0), and the real C0/C1
runs still verify.

Full suite: 722 passed, 0 failed; `ruff check src tests` clean;
real C0/C1 runs still verify.

---

## Round-2 independent-audit repairs (2026-10-18)

The prior PASS was re-audited on the current revision; the following defects
were reproduced and repaired. Independent re-review is pending.

| ID | Finding | Repair |
|---|---|---|
| R2-1 (P0) | A material scenario could self-declare `run_kind=synthetic_engine_smoke` and skip material tick-data checks | `verify_run_identity` binds `run_kind` to the loaded scenario kind; material checks key off the scenario, not the manifest |
| R2-2 (P0) | Quantitative Parquet metrics accepted arbitrary strings | Quantitative units reject non-numeric cells; categorical units (`binding_constraint_label`) require strings |
| R2-3 (P0) | JSON sidecars bypassed unit/type/temporal/selector semantics | Sidecars must declare `__metric_bindings__` with exact unit, value type, temporal extent and empty selectors; untyped sidecars cannot support a record |
| R2-4 (P1) | `MetricSpec` and its `TimeWindow` could declare different missing policies; `data_role` bypassed data checks | Policy equality enforced in the schema; data checks run for every role |
| R2-5 (P1) | Seeds `"1729"`/`1729.0`/`true` were coerced | `EvidenceRunReference` and raw manifest seeds require exact non-negative ints before coercion |
| R2-6 (P1) | ID normalisation accepted lowercase/whitespace/M010 and could not round-trip M10/M11; canonical duplicates and DAG joins were inconsistent | Exact M1–M11/M01–M11 forms only, all eleven round-trip, canonical uniqueness on manifests, canonical DAG lookup |
| R2-7 (P1) | Git-only/fresh-run evidence depended on legacy outputs and skipped when absent | Added a real Git-only 4-quarter runner fixture path and fresh C0/C1 replay evidence (see `evidence/h0a-fresh-20261018/`); no skip-based positive control |
| R2-8 (P1) | Delivered H0A diff included files outside the frozen whitelist | Reconciliation recorded: `src/hsm_lab/evidence/__init__.py`, `tests/test_evidence_schemas.py` and `tests/test_hist_identity_guards.py` were subsequently authorized under H0B N1; `metric_enricher.py` belongs to H0B, not H0A. Historical attribution corrected without reverting later work |

### Round-2 verification
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_hist_identity_guards.py tests/test_evidence_schemas.py \
  tests/test_evidence_run_adapter.py tests/test_evidence_manifest_verification.py
# → 310 passed
.venv/bin/ruff check --no-cache src tests
# → all checks passed
```

Fresh-run evidence and the Git-only snapshot are recorded in
`docs/phases/HIST_VNEXT/H0A/evidence/h0a-fresh-20261018/`.

### Round-3 re-audit repairs
| ID | Finding | Repair |
|---|---|---|
| R3-1 (P0) | A sidecar could declare `value_type` contradicting its unit (string under a monetary unit; number under a label unit) | Sidecar `value_type` must agree with unit semantics: quantitative units require `number`, categorical units require `string` |
| R3-2 (P1) | Distinct seeds over deterministic zero-draw runs counted as stochastic replicates | Replicate gate inspects verified manifests' `rng_draws_count`/`rng_draws_by_module`/`stochastic_modules_active`; `minimum_replicates > 1` requires that many stochastic runs |

Round-3 verification: H0A four-file subset **309 passed**; Git-only snapshot
**309 passed, 0 skipped**; ruff clean.

### Round-4 custody repairs
| ID | Finding | Repair |
|---|---|---|
| R4-1 (P0) | Replicate count used distinct seeds across all refs while counting stochastic runs separately | Count distinct seeds among verified stochastic runs; duplicate seeds among active runs do not satisfy `minimum_replicates` |
| R4-2 (P0) | RNG fields were not bound to the hashed summary; active modules could contradict module counts | Manifest/summary RNG fields are mirrored; active modules must equal modules with positive draw counts |
| R4-3 (P0) | Manifest could shrink the commodity/region universe | Material manifests must match the loaded scenario's universes; table checks use that universe |
| R4-4 (P1) | `parameters.json.declaration` content was not validated | Declaration must validate against `MaterialParameters` and equal the scenario declaration |
| R4-5 (P1) | Output symlinks could escape the run directory | Every output entry must resolve inside the run; outward symlinks reject |
| R4-6 (P1) | Output scenario labels were only checked against each other | Summary/parameters/recipe labels must equal the requested scenario |

Round-4 verification: H0A four-file subset **316 passed**; ruff clean.

### Round-5 custody repairs
| ID | Finding | Repair |
|---|---|---|
| R5-1 (P0) | Missing summary RNG fields bypassed RNG/summary binding | Material summaries must contain all four RNG fields with exact types |
| R5-2 (P0) | `row_counts` table names could traverse outside the run or name unhashed files | Table names must be `[A-Za-z0-9_]+`, resolve inside the run, and appear in `manifest.output_hashes` |
| R5-3 (P1) | Raw boolean RNG counters became integers before validation | Raw manifest and summary RNG counters are exact-type checked before Pydantic/coercion |

Round-5 verification: H0A four-file subset **316 passed**; ruff clean.

### Round-6 artefact-custody repair
| ID | Finding | Repair |
|---|---|---|
| R6-1 (P0) | Metric artifacts were not required to be covered by the verified run's output hashes; unhashed `.tmp-*` staging files could support SUPPORTED evidence | Every consumed Parquet/sidecar artifact must resolve inside the run and appear in `manifest.output_hashes`; staging paths are rejected |

Round-6 verification: H0A four-file subset **320 passed**; ruff clean.
