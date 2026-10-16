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
- `precision="unknown"`: both earliest and latest may be None
- `precision="day"`: requires earliest == latest (single day)
- `precision="range"`: allows inverted bounds (earliest > latest) to represent exclusive upper bounds (e.g., `effective_to = [1975-01-01, 1974-12-31]` means "active until just before 1975-01-01")
- `precision="month"/"quarter"/"year"`: requires earliest <= latest; no natural-period-boundary enforcement

### Authority Resolution
- Grants with unknown enactment → uncertain (contribute to "unknown" result)
- Grants with effective_from in future → not yet active
- Grants with effective_to expired at decision date → not active
- Revokes with unknown enactment → possibly effective (not definitely)
- Revokes with effective_from range precision: within range → possibly effective
- Revokes with effective_to range precision (normal): before range → not expired; within range → possibly expired
- Revokes with effective_to range precision (inverted, earliest > latest): active while decision_date < earliest; at/after earliest → expired
- plan §4: nonexistent revoke targets → silently ignored (unknown at query time), NOT error at load

### Sector/Org/Geography Scope Containment
- Revoke scope must be contained within grant scope
- Effective sector set = sector_ids − excluded_sector_ids
- Wildcard (empty sector_ids) covers all sectors
- Expanding scope (revoke has specific sectors but grant has wildcard) is rejected

## Deliverables
1. `src/hsm_lab/institutions/schemas.py`: DateInterval, AuthorityScope, InstitutionEvent, RegimeCalendar, AuthorityResult
2. `src/hsm_lab/institutions/calendar.py`: load_calendar(), event_as_of()
3. `src/hsm_lab/institutions/authority.py`: authority_at()
4. `institutions/HIST_VNEXT/h1b_synthetic_calendar.json`: 6 synthetic events
5. `tests/test_hist_regime_calendar.py`: 33 tests across 8 verification categories
6. `institutions/HIST_VNEXT/H1B/evidence/h1b-smoke-001/run_smoke.py`: 14 smoke checks

## Verification
- 33 H1B tests: PASS
- Full suite 849: PASS
- Ruff: clean
- Smoke 14/14: PASS

## File Hashes (Final)
```
institutions/HIST_VNEXT/h1b_synthetic_calendar.json  cb80aea13bd255dc89d0c53b8404f2111e78a988dae58f899c98f5385d68acdb
src/hsm_lab/institutions/schemas.py               acd07357b9d7dd85050f49f060917aa7a0d250d23884fc7a8d63231762fbf0ea
src/hsm_lab/institutions/calendar.py               a9cb6cca74d5898dfbcd11536f9ba6c78b56ebd0c577e05fd9464525d8030e44
src/hsm_lab/institutions/authority.py              17ad1f521aa262e1f531c882b72c5e124ebe002f9215d193123099287039d8c9
tests/test_hist_regime_calendar.py                  498270fa54c54761f3cfcd0c48a757c672c4eeadc65ba10e023c13a506d47163
institutions/HIST_VNEXT/H1B/evidence/h1b-smoke-001/run_smoke.py  8492e7cb0c5f71780c6fed5b661fb6aa05ec0019c545fd8e3faa41ed41301af3
```

## Open Issues (Known Limitations)
1. `InstitutionEvent.is_granted_at()` may return False for grants that `authority_at()` returns granted — this helper is not used by the authority API
2. Proposal/approval/enactment lifecycle ordering uses latest-vs-latest comparison; overlapping intervals (proposal range ending after approval date) are rejected even if a valid chronology exists within the ranges
3. Natural-period boundary enforcement for month/quarter/year precision is not implemented
4. No path authorization: PLAN.md, REPORT.md, REVIEW.md not yet written
