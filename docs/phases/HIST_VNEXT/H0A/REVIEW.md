# H0A Phase Review

## Reviewer
Independent automated phase-reviewer (GPT-6.1-SOL:high)

## Verdict
**PATCH** — Core run identity verification substantially improved; remaining P0 items deferred by user decision.

## Summary of Fixes Implemented

### Core Identity Verification
| Issue | Fix | Status |
|-------|-----|--------|
| run_id mismatch | `verify_evidence_manifest_runs` now verifies returned `RunManifest.run_id` matches `EvidenceRunReference.run_id` | ✅ FIXED |
| Duplicate actual runs | Track distinct runs by `(resolved_path, digest)`; reject duplicates toward `minimum_replicates` | ✅ FIXED |
| Card SHA verification | `_verify_record_cards` computes SHA of `config/p06/cards/{mech}.json` and `config/mechanisms/v2/{mech}.json` | ✅ FIXED |
| StudyManifest card existence | `verify_study_manifest_cards` verifies card files exist for all declared mechanism IDs | ✅ FIXED |
| Parameter hash recomputation | Step 15 recomputes `parameter_hash` from scenario spec via `material_parameter_vector` + `compute_parameter_hash` | ✅ FIXED |
| Snapshot window bounds | All three quarters must be within [1957Q1, 1985Q4] | ✅ FIXED |
| SHA non-zero | All SHA fields reject all-zeros via field validators | ✅ FIXED |
| Cross-card borrowing | `_linked_cards_identity` verifies linked cards map to same mechanism | ✅ FIXED |
| Deterministic replay digest non-zero | Added to zero-check in `verify_run_identity` step 8 | ✅ FIXED |

### Test Coverage
- **596 tests pass** (was 586; 10 new adversarial regression tests added)
- Ruff clean
- Baseline SHA256 verified
- uv lock check ok

## Residual P0 Items (Deferred to H1/H2 by User Decision)

| ID | Description | User Decision |
|----|-------------|---------------|
| R1 | `baseline_hash` verification against actual baseline | DEFERRED |
| R2 | `initial_recipe_hash` verification against actual recipe | DEFERRED |
| R3 | `input_artifact_hashes` verification through `DataRegistry` | DEFERRED |
| R4 | Sidecar SHA cross-verification against `studies/M*/study_decl.json` | DEFERRED |
| R5 | Seed override handling in scenario hash computation | DEFERRED |
| R6 | Independent stochastic replicate distinction (same seed ≠ independent) | DEFERRED |

## Implementation Quality
- All modifications within scope of `src/hsm_lab/evidence/` and `tests/`
- No engine, lock, or storage changes
- No dead code; no skipped tests; no validator bypasses
- Real C0/C1 runs pass identity verification
- Fabricated runs with wrong run_id, digest, parameter_hash are rejected

## Commit Readiness
**Ready to commit** — Core run identity verification is implemented and working. Remaining P0 items are documented and deferred per user decision.

### Files Changed
- `src/hsm_lab/evidence/schemas.py` — snapshot bounds, SHA validators, cross-card validator
- `src/hsm_lab/evidence/provenance.py` — step 8 fix, step 14-15 parameter verification
- `src/hsm_lab/evidence/loader.py` — `verify_evidence_manifest_runs`, StudyManifest verification
- `tests/test_hist_identity_guards.py` — 10 new adversarial regression tests
