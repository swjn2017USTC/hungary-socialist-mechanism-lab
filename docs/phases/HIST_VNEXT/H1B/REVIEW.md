# H1B Review

## Phase
HIST_VNEXT H1B — synthetic regime calendar with authority queries

## Scope of This Document
This file records the round-2 audit findings relayed for H1B and the repairs made
in response. It is **not** an independent verdict: the auditor performed the review,
the findings are treated as ground truth, and the implementation team has not
re-run an independent review.

## Findings and Repairs

| # | Severity | Finding | Repair | Regression evidence |
|---|---|---|---|---|
| 1 | P1 | Decision dates inside an uncertain enactment interval were skipped (`decision < enactment.latest → continue`), so a revoke could be treated as not yet effective when it might already be effective. | `_start_status()` classifies definitively-future versus possibly-elapsed boundaries. Possibly-elapsed enactment/start makes a revoke possible (unknown overall) and a grant uncertain. | `TestUncertainEnactmentIntervals` (two tests: uncertain revoke; uncertain independent grant) |
| 2 | P1 | Early uncertain-grant branches returned before checking `effective_to`, so a definitely expired grant could turn a revoked verdict into unknown. | Definite expiry, definite future start, and definite future enactment are applied before any uncertainty classification. | `TestDefiniteExpirationBeforeUncertainty` (unknown enactment and unknown effective start variants) |
| 3 | P2 | Effective-window validation required `effective_from.latest <= effective_to.earliest`, rejecting a feasible overlapping window. | Validation now requires existence of a feasible chronology: `effective_from.earliest < effective_to.latest` under half-open semantics. | `TestEffectiveWindowFeasibility` (accept overlap; reject impossible and zero-length) |
| 4 | P2 | month/quarter/year labels accepted arbitrary bounds. | `DateInterval` itself requires exact natural-period bounds; arbitrary bounded uncertainty uses `range`. | `TestNaturalPeriodBounds` (three negatives plus positive controls) |
| 5 | P2 | Actual-implementation evidence guard probed a nonexistent `known_true_for` field, so observed implementation loaded without evidence. | Guard now checks `observed_implementation_at` and requires non-empty `synthetic:`-prefixed evidence ids, or an unknown observation. | `TestObservationEvidenceGuard` (reject no evidence, reject non-synthetic prefix, accept synthetic, accept unknown) |
| 6 | P2 | `RegimeCalendar.model_validate({})` created an empty calendar and dangling revokes loaded silently. | `events` is required (explicit `[]` still legal); dangling revoke targets raise `ConfigError`. | `TestCalendarDeclarationIntegrity` and the rewritten `test_revoke_nonexistent_target_rejected` |
| 7 | P2 | Documentation claimed inverted ranges, listed absent fixtures, used a nonexistent `denied` status, and carried stale counts/hashes; smoke output lacked inputs, traces, and a manifest. | PLAN/REPORT/REVIEW corrected; smoke now writes a revision-bound manifest and per-query inputs/results. | `smoke_output.json` manifest (14 checks), test run below |

## Verification Observed
- `tests/test_hist_regime_calendar.py`: 57 passed
- `tests/test_hist_observation_authority.py` + `tests/test_hist_tiny_execution.py`: 135 passed
- Ruff on changed files: clean
- Smoke: 14/14 passed
- Full suite: NOT_RUN this round
- C0/C1 replay: NOT_RUN; no replay claim is made

## Residual Limitations
1. Lifecycle ordering checks adjacent interval feasibility, not a joint chronology
   across all five lifecycle intervals.
2. Authority resolution is per (org, sector, geo, permission); it does not aggregate
   permissions or synthesize a default rule.

## Independent re-audit round 3 (2026-10-18) — PASS
The three P2 findings above were re-probed against current code:
- PLAN and code now state the same lifecycle lower-bound feasibility rule.
- `effective_to.precision="unknown"` is rejected; `None` is the only
  unbounded spelling.
- The synthetic-evidence guard applies unconditionally to `source_ids` and
  `implementation_evidence_ids`, including events with no observation.
- Smoke hashes and revision are current; 6-event calendar resolves unchanged.
- Focused H1B + observation authority 198 passed.

P3-1/P3-2/P3-3 remain documented limitations and produce no unsound
`granted` result. Verdict: **PASS**.
