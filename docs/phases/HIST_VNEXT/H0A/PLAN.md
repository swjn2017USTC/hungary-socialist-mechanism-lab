# H0A Plan: P07身份、时间、缺失与证据晋级修复

## Phase identity
- **ID**: H0A
- **Objective**: P07 identity, time, missing and evidence promotion fix
- **Dependencies**: 本审计 + 单步授权
- **Plan date**: 2026-10-15
- **Status**: IMPLEMENTED

## File whitelist (候选范围)
- `src/hsm_lab/evidence/schemas.py`
- `src/hsm_lab/evidence/loader.py`
- `src/hsm_lab/evidence/adapter.py` (read-only)
- `src/hsm_lab/evidence/run_adapter.py`
- `src/hsm_lab/evidence/provenance.py`
- `tests/test_evidence_schemas.py`
- `tests/test_evidence_run_adapter.py`
- `tests/test_evidence_manifest_verification.py`
- `tests/test_hist_identity_guards.py` (新增)

## What was implemented

### 1. schemas.py
- `MissingPolicy` enum: `ABORT`, `SKIP`, `INTERPOLATE` — no zero_fill variants
- `canonical_mechanism_id(value)` / `study_mechanism_id(value)`: strict reversible M1–M11 / M1–M9 normalisation
- `TimeWindow._study_window`: ordinal bounds 1957Q1–1985Q4
- `TimeWindow.missing_policy` / `MetricSpec.missing_policy`: now `MissingPolicy` type
- `ObservedState`: `extra="forbid"`, added `available_at` + `decision_at`, `_availability_order` validator (source_checkpoint_quarter ≤ available_at ≤ decision_at)
- `EvidenceRunReference`: strict run handle (run_id, scenario_id, seed:int, output_dir:Path, digest)
- `EvidenceRecord.run_references` + `_supported_requires_runs`: non-empty, unique run_ids, unique (run_id,seed) pairs, minimum_replicates count counted over DISTINCT seeds (same-seed runs are deterministic replays, not independent replicates)
- `StudyDeclaration` / `StudyManifest`: intent/linked_cards form, `card_id` property, self-card identity validation

### 2. loader.py
- `validate_evidence_manifest` / `validate_study_manifest`: strict dispatch by `intent`/`hypothesis` field in first record
- `load_evidence_manifest`: returns `EvidenceManifest | StudyManifest` union
- `load_all_evidence_records`: returns `list[StudyDeclaration | EvidenceRecord]`
- `write_evidence_manifest`: rejects StudyManifest; re-validates via `model_validate_json` before write; O_EXCL no-clobber publication
- `_verify_metric_parquet_content` + `_verify_joint_coverage`: a declared window and a declared commodity/region selector are checked at their intersection — every declared quarter must carry rows for every declared selector
- `_verify_linked_observed_states` (+ `_VerifiedRun`, `_run_output_quarter_labels`): a SUPPORTED record links at least one observed state, and each one names a verified run (id/scenario/digest) and a checkpoint quarter that run's own output contains

### 3. run_adapter.py
- Removed `build_stub_evidence_record` (no production callers)
- `verify_digest_unchanged`: delegates to `verify_run_identity` with try/except → bool

### 4. provenance.py
- `verify_run_identity`: full manifest validation — run_kind (non-politics material), status=completed, completed_ticks==ticks, strict seed int, scenario_id→load_scenario→compute_scenario_hash match, non-zero hashes, output tree integrity, required files, lock_hash, data_manifest_hash
- `_verify_material_tick_data`: the `initial_recipe.json` declaration must validate as a `MaterialInitialRecipe` *and* equal the recipe the scenario declares (the recipe hash binds the organization/technology/route recipe, not the declaration)

## Test coverage
- `test_hist_identity_guards.py`: 71 new tests
  - ID normalisation round-trips (M1↔M01, M1↔M9)
  - MissingPolicy enum, zero_fill rejection
  - TimeWindow 1957Q1–1985Q4 bounds, reversed window
  - ObservedState availability ordering, extra=forbid
  - EvidenceRunReference validation, bool seed rejection
  - SUPPORTED structural gate (non-empty, unique run_ids, minimum replicates)
  - StudyDeclaration / StudyManifest schemas and dispatch
  - verify_run_identity boundary (nonexistent dir, wrong seed, wrong digest, incomplete status, failure_message, zero hash, missing files)

## Verification gate
- 586 tests pass (517 original + 71 new)
- ruff: All checks passed
- uv lock --check --offline: Resolved 101 packages
- hsm baseline verify: SHA256 matches frozen audit anchor

## Known limitations (H0B scope)
- Parameter/recipe hash recomputation from actual material_parameter_vector
- Comprehensive run output content validation (tables, accounting invariants)
- 11-card semantic mapping and historical support scoring
- Full run reference runtime verification via verify_run_identity in loader context
