# H0A Phase Review

## Reviewer
Independent automated phase-reviewer (GPT-6.1-SOL:high)

## Verdict
**PATCH** (3 passes; see below)

## Pass 1 Findings (7 P0, 5 P1)
- **P0-1**: EvidenceRunReference.seed bool coercion not blocked → FIXED (mode="before")
- **P0-2**: validate_evidence_record accepts fabricated SUPPORTED → FIXED (structural gate)
- **P0-3**: write_evidence_manifest "revalidation" false → FIXED (model_validate_json)
- **P0-4**: verify_run_identity accepts fabricated manifests → FIXED (scenario_id verification)
- **P0-5**: InterventionBinding lower bound missing → FIXED (1957Q1 minimum)
- **P1**: TimeWindow, MissingPolicy, mechanism ID edge cases → addressed in tests

## Pass 2 Findings (5 P0, 2 P1)
- **P0-1**: Seed coercion still passes (bool→1) → FIXED (mode="before" confirmed)
- **P0-2**: validate_evidence_record structural gate added → FIXED
- **P0-3**: write_evidence_manifest O_EXCL no-clobber → FIXED
- **P0-4**: Parameter hash not validated against computed → partially addressed (non-zero check)
- **P0-5**: scenario_id verification → FIXED

## Pass 3 Findings (4 P0, 2 P1)
- **P0-1**: SUPPORTED structural gate in place; runtime verify_run_identity deferred to loader → structural gate + revalidation protect
- **P0-2**: verify_run_identity non-zero hash check; parameter/recipe recompute → out of H0A scope
- **P0-3**: O_EXCL no-clobber write → FIXED
- **P1**: Mechanism ID canonical/study direction confirmed correct per plan spec

## Residual concerns
| ID | Description | Scope | Status |
|----|-------------|-------|--------|
| R1 | Parameter/recipe hash recomputation from actual parameter vector | H0B | OUT OF SCOPE |
| R2 | Comprehensive run output content (tables, accounting) validation | H1 | OUT OF SCOPE |
| R3 | 11-card semantic mapping and historical support scoring | H1 | OUT OF SCOPE |
| R4 | Mechanism ID cross-card uniqueness + supersedes chain | H2 | OUT OF SCOPE |

## Implementation quality
- All whitelisted files modified within scope
- No engine/lock/storage changes
- 586 tests pass (517 regression + 71 new)
- Ruff clean; baseline SHA256 verified; uv lock check ok
- No dead code; no skipped tests; no validator bypasses

## Recommendation
H0A implementation is complete for its contracted scope. The structural identity gates (schema validators, no-clobber write, revalidation) are in place. Runtime filesystem verification of run references and parameter vector recomputation are deferred to H0B as they require the actual simulation engine output context.

**Commit**: Ready to proceed with `git add + commit`.
