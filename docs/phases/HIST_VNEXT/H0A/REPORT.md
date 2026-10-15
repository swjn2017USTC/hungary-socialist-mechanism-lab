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
| `EvidenceRecord._supported_requires_runs` | Non-empty, unique run_ids, unique (run_id,seed) pairs, minimum_replicates |
| `StudyDeclaration` / `StudyManifest` | Intent form, card_id property, self-card identity |

### src/hsm_lab/evidence/loader.py
| Change | Description |
|--------|-------------|
| `validate_evidence_manifest` | Strict dispatch: EvidenceManifest requires `hypothesis` field, StudyManifest requires `intent` |
| `load_all_evidence_records` | Union return type |
| `write_evidence_manifest` | Rejects StudyManifest; re-validates via `model_validate_json`; O_EXCL no-clobber |

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
| `TestSupportedRequiresRuns` | 6 (structural gate) |
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

### Known limitations (out of H0A scope)
⏳ P0: Parameter/recipe hash recomputation from actual material_parameter_vector — requires scenario spec access
⏳ P0: Comprehensive run output content validation (tables, accounting) — requires domain-specific checks
⏳ P1: 11-card semantic mapping and historical support scoring — H1 scope
⏳ P1: Mechanism ID cross-card uniqueness and supersedes chain — H2 scope

## Test results
```
586 passed, 108 warnings in 49.32s
All ruff checks passed
uv lock --check --offline: Resolved 101 packages
hsm baseline verify: SHA256 matches frozen audit anchor
```
