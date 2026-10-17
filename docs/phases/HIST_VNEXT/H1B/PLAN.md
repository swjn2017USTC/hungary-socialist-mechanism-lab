# H1B Plan

## Phase
HIST_VNEXT H1B — synthetic regime calendar with authority queries

## What This Phase Does
Implements a one-shot synthetic regime calendar and authority query API. No historical primary sources admitted (`synthetic_flag=False` events are rejected). No engine coupling.

## Scope
- `RegimeCalendar`: collection of `InstitutionEvent`s, calendar-level revocation integrity validation
- `authority_at()`: permission/authority resolution against a calendar at a decision date
- `load_calendar()`: JSON loader
- `event_as_of()`: event visibility at a point in time

## Synthetic Events
All events in `institutions/HIST_VNEXT/h1b_synthetic_calendar.json` have `synthetic_flag=True`. The calendar rejects any event with `synthetic_flag=False`.

## Key Design Decisions

### DateInterval
- `precision="unknown"`: both earliest and latest are None
- `precision="day"`: requires earliest == latest (single day)
- `precision="month"/"quarter"/"year"`: these name a natural calendar period. Bounds must be exactly the first/last day of one month, quarter, or year; the check lives in `DateInterval` so it applies to every interval field.
- `precision="range"`: any bounded interval with `earliest <= latest`. Use `range` for uncertainty that does not coincide with a named natural period. Inverted ranges (`earliest > latest`) are rejected.
- Bounded `effective_to` uses half-open `[effective_from, effective_to)` semantics. A window is accepted iff at least one feasible chronology exists: the latest of the earliest possible proposal/approval/enactment/effective-start dates is strictly before `effective_to.latest`; overlapping uncertainty remains legal, zero-length/impossible windows are rejected. `effective_to=None` is the only spelling of an unbounded window; `precision="unknown"` ends are rejected.

### Authority Resolution
- Definite nonactivity is applied before residual uncertainty: a grant or revoke whose `effective_to` has definitely expired, or whose `effective_from`/enactment is definitely in the future, does not affect the result even if another date is unknown.
- A decision date inside an enactment or effective-start interval is *uncertain*, not treated as future: it may already have elapsed. Such grants make the result unknown; such revokes are possibly effective.
- Grants with unknown enactment → uncertain (contribute to "unknown" result)
- Grants with effective_from in future → not yet active
- Grants with effective_to expired at decision date → not active
- Revokes with unknown enactment → possibly effective (not definitely)
- Revokes with effective_from range precision: within range → possibly effective
- Revokes with effective_to range precision: before range → not expired; within range → possibly expired; at/after latest → definitely expired
- Revoke targets must exist in the same calendar. A dangling `revokes_event_id` is a malformed declaration rejected at load time.

### Actual-Implementation Evidence
- A non-unknown `observed_implementation_at` is an evidence claim and requires non-empty `implementation_evidence_ids`.
- Because all admitted events are synthetic, those evidence ids must be explicitly `synthetic:`-prefixed. Otherwise the observation must be marked unknown (`precision="unknown"` or `None`).

### Sector/Org/Geography Scope Containment
- Revoke scope must be contained within grant scope
- Effective sector set = sector_ids − excluded_sector_ids
- Wildcard (empty sector_ids) covers all sectors
- A specific-sector revoke of a wildcard grant is permissible narrowing; only a revoke that expands beyond the grant's effective coverage (including exclusions) is rejected

### Calendar Declarations
- `events` is a required declaration. `RegimeCalendar.model_validate({})` is rejected; an explicit `{"events": []}` is a legal empty calendar and every query against it is unknown.

## Deliverables
1. `src/hsm_lab/institutions/schemas.py`: DateInterval, AuthorityScope, InstitutionEvent, RegimeCalendar, AuthorityResult
2. `src/hsm_lab/institutions/calendar.py`: load_calendar(), event_as_of()
3. `src/hsm_lab/institutions/authority.py`: authority_at()
4. `institutions/HIST_VNEXT/h1b_synthetic_calendar.json`: 6 synthetic events
5. `tests/test_hist_regime_calendar.py`: 67 tests
6. `institutions/HIST_VNEXT/H1B/evidence/h1b-smoke-001/run_smoke.py`: 14 smoke checks plus revision-bound manifest and per-query inputs/results

## Verification (round 2 repair)
- H1B tests: 67 PASS
- Downstream institution tests (`test_hist_observation_authority.py` + `test_hist_tiny_execution.py`): 151 PASS
- Ruff: clean on changed files
- Smoke: 14/14 PASS
- Full repository suite: NOT_RUN this round
- C0/C1 replay: NOT_RUN; no replay result is claimed

## File Hashes
Static hashes are intentionally not duplicated here because they go stale. The smoke
manifest (`institutions/HIST_VNEXT/H1B/evidence/h1b-smoke-001/smoke_output.json`)
records the git revision plus SHA-256 hashes of the calendar, schemas, calendar
loader, authority module, and smoke script for the run that produced it.

## Open Issues (Known Limitations)
1. Proposal/approval/enactment lifecycle ordering checks adjacent interval feasibility (earliest vs latest) but does not solve a joint chronology across all five lifecycle intervals.
2. `authority_at()` resolves per (org, sector, geo, permission); it does not aggregate across permissions or infer a default rule when no grant matches.
