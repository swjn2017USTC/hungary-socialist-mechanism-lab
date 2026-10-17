# H1B Report

## Phase
HIST_VNEXT H1B — synthetic regime calendar with authority queries

## What Was Done
Implemented a synthetic regime calendar and read-only authority query API for the
Hungary Socialist Mechanism Lab: schema validation, JSON loading, event visibility,
three-valued authority resolution, and evidence/declaration integrity checks.

## Deliverables

### 1. Schema (`src/hsm_lab/institutions/schemas.py`)
- `DateInterval`: precision-aware validation (day/range/month/quarter/year/unknown).
  Natural-period precisions require exact period bounds, and bounded windows must
  admit at least one feasible half-open `[from, to)` chronology.
- `AuthorityScope`: sector/organization/geography permission container.
- `InstitutionEvent`: full lifecycle (proposal→approval→enactment→effective_from/effective_to),
  synthetic-only gating, actual-implementation evidence requirements.
- `RegimeCalendar`: required explicit `events` declaration, duplicate-id rejection,
  dangling-revoke rejection, scope containment validation.
- `AuthorityResult`: `granted` / `revoked` / `unknown` with `reason` and active ids.

### 2. Calendar Loader (`src/hsm_lab/institutions/calendar.py`)
- `load_calendar(path)`: JSON loader with validation errors wrapped as `ConfigError`
- `event_as_of(calendar, event_id, decision_at)`: source-availability visibility

### 3. Authority Resolution (`src/hsm_lab/institutions/authority.py`)
- `authority_at(calendar, ...)`: permission resolution with three-valued uncertainty
- `_start_status()` / `_end_status()`: classify interval boundaries as definitely
  future/elapsed, definitely active/expired, or uncertain
- `_active_grants_at()`: definite nonactivity first, then definite/uncertain grants
- `_effective_revokes()`: definite/possible revokes with the same ordering
- `_resolve_authority()`: per-grant revocation tracking and final status aggregation
- `_check_revoke_scope()`: sector/organization/geography containment validation

### 4. Synthetic Calendar (`institutions/HIST_VNEXT/h1b_synthetic_calendar.json`)
Six synthetic events:
- NEM procurement grant (quarter-precision effective start, observed implementation)
- NEM investment-approval grant (organisation/sector scoped)
- NEM price-setting grant (agriculture excluded)
- NEM procurement revoke scoped to ORG-ENT-B
- CMEA pre-1975 price rule (ends at 1975-01-01)
- CMEA post-1975 price rule (1975-01-01 to 1980-01-01)

### 5. Tests (`tests/test_hist_regime_calendar.py`)
57 tests covering lifecycle separation, interval precision and feasibility, scope
filtering, revoke isolation, source availability, CMEA boundaries, JSON loading,
declaration integrity, evidence guards, and uncertainty regressions.

### 6. Smoke Evidence (`institutions/HIST_VNEXT/H1B/evidence/h1b-smoke-001/`)
`run_smoke.py` executes 14 checks and writes `smoke_output.json` containing:
- a revision-bound manifest (git revision, SHA-256 for the calendar, schemas,
  loader, authority module, and smoke script)
- per-query inputs, observed result (`status`, active ids, reason), and expected result
- aggregate pass/fail labels

## Verification Results (round 2 repair)
| Check | Result |
|---|---|
| `tests/test_hist_regime_calendar.py` (57) | PASS |
| `tests/test_hist_observation_authority.py` + `tests/test_hist_tiny_execution.py` (135) | PASS |
| Ruff on changed files | Clean |
| Smoke (14/14) | PASS |
| Full repository suite | NOT_RUN this round |
| C0/C1 replay | NOT_RUN; not claimed |

## Round 2 Repairs

1. **P1 uncertain enactment intervals** — `_start_status()` now distinguishes
   definitely-future enactment from possibly-elapsed enactment. A decision inside a
   declared enactment/effective-start window produces uncertainty instead of being
   skipped. Regressions cover both an uncertain revoke (unknown at 1970, revoked after
   the windows close) and an independent uncertain grant alongside a revoked old grant.
2. **P1 unknown dates bypassing definite expiration** — definite expiry, definite
   future start, and definite future enactment are applied before residual uncertainty.
   Regressions cover expired grants with unknown enactment and with unknown effective
   start; both leave the established grant's definite revocation intact.
3. **P2 feasible uncertain windows** — the lifecycle validator now requires existence
   of a feasible chronology (`effective_from.earliest < effective_to.latest`) rather
   than `from.latest <= to.earliest`. Feasible overlap is accepted; impossible and
   zero-length windows are rejected.
4. **P2 natural-period labels** — `DateInterval` itself enforces exact month, quarter,
   and year bounds for every use. Arbitrary bounded uncertainty must use `range`.
   Negative tests cover all three mislabelled cases.
5. **P2 actual-implementation evidence** — the obsolete `known_true_for` probe was
   replaced with a check on `observed_implementation_at`. A known observation now
   requires non-empty `synthetic:`-prefixed evidence ids; rejection and acceptance are
   both tested.
6. **P2 malformed declarations** — `events` is required, so `model_validate({})` fails
   while explicit `{"events": []}` remains legal. Dangling revoke targets are rejected
   at load time. The former acceptance test now expects `ConfigError`.
7. **P2 documentation/evidence** — inverted-range claims removed (validation rejects
   them), MTGT/industrial fixtures removed from the deliverable list, `denied` replaced
   with `revoked`, test counts and verification status corrected, and the smoke output
   extended with revision-bound hashes plus query inputs/results.

## Design Decisions

### Half-Open Effective Windows
`effective_to` is an exclusive end (`[effective_from, effective_to)`), matching the
authority resolution rule that `decision_at >= effective_to.latest` is definitely
expired. Window feasibility uses the same semantics.

### Unknown Enactment → Possibly Effective
A revoke with unknown or overlapping enactment is possibly effective, never
definitely effective. If its effective window has definitely expired or definitely
not started, it is removed before uncertainty is considered.

### Three-Valued Authority Resolution
`authority_at` returns `granted`, `revoked`, or `unknown`. Uncertainty arises from
uncertain/unknown enactment or start dates, possibly effective revokes, and possibly
expired effective ends. A definitely surviving independent grant still yields
`granted`; uncertainty is tracked per target grant.

### Calendar Declarations
Missing `events` and dangling revoke targets are load-time errors because they are
malformed declarations. An explicit empty calendar is a well-formed artifact whose
queries return `unknown` without synthesizing a default rule.

### Round-3 re-audit repairs (2026-10-18)
| ID | Finding | Repair |
|---|---|---|
| R3-1 | Effective-window feasibility ignored the lifecycle lower bound; an end before certain enactment was accepted | Feasibility now requires `max(proposal/approval/enactment/effective-start earliest) < effective_to.latest` |
| R3-2 | Smoke T5 accepted any exception and recorded no trace | T5 requires `ConfigError`, records calendar/event/decision input and the observed exception, and fails on any other exception |
| R3-3 | The in-memory fallback calendar used an inverted range and was never exercised | Effective end corrected to a half-open day boundary; `test_in_memory_fallback_calendar_is_valid` exercises it |

Round-3 verification: `tests/test_hist_regime_calendar.py` **59 passed**;
smoke **14/14** with T5 trace; ruff clean.

### Round-4 authority repair (2026-10-18)
| ID | Finding | Repair |
|---|---|---|
| R4-1 | A definite revoke disappeared when its target grant had expired, yielding `unknown` instead of `revoked` | Revoke evidence is evaluated against all declared grants before the no-active-grant fallback; definite/possible revokes preserve `revoked`/`unknown`, and an independent surviving grant still yields `granted` |

Round-4 verification: `tests/test_hist_regime_calendar.py` **63 passed**;
smoke **14/14**; ruff clean.

### Round-5 provenance/ordering repairs
| ID | Finding | Repair |
|---|---|---|
| R5-1 | Persisted smoke provenance held a stale authority hash | Smoke regenerated against the repaired implementation; `test_smoke_manifest_hashes_match_current_files` detects stale artifacts |
| R5-2 | Expired-grant revocation traces depended on event order | Definite/possible revocation IDs are sorted; permutation-invariance regression added |
| R5-3 | Plan wording contradicted wildcard revoke containment | Plan now states specific-sector revocation of a wildcard grant is permissible narrowing |

Round-5 verification: `tests/test_hist_regime_calendar.py` **65 passed**;
smoke **14/14**; ruff clean.

## Round 3 repairs (2026-10-18, independent re-audit PASS)
- `effective_to.precision="unknown"` is rejected; `None` is the only unbounded spelling.
- The synthetic-evidence guard now applies unconditionally to `source_ids` and
  `implementation_evidence_ids`, including events with no observed implementation.
- PLAN restated the lifecycle lower-bound feasibility rule.
- Tests: 67 H1B; focused H1B+observation+tiny 198. Smoke regenerated 14/14
  with current file and calendar hashes.
