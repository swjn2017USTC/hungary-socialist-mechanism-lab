# H1B Report

## Phase
HIST_VNEXT H1B — synthetic regime calendar with authority queries

## What Was Done
Implemented a complete synthetic regime calendar and authority query API for the Hungary Socialist Mechanism Lab. All 5 institutional API types implemented, verified, and documented.

## Deliverables

### 1. Schema (`src/hsm_lab/institutions/schemas.py`)
- `DateInterval`: Pydantic model with precision-aware validation (day/range/month/quarter/year/unknown)
- `AuthorityScope`: sector/organization/geography permission container
- `InstitutionEvent`: full lifecycle (proposal→approval→enactment→effective_from/effective_to), synthetic_flag gating
- `RegimeCalendar`: event collection with calendar-level revocation integrity validation
- `AuthorityResult`: structured authority resolution result with status/reason/active_event_ids

### 2. Calendar Loader (`src/hsm_lab/institutions/calendar.py`)
- `load_calendar(path)`: JSON file loader with synthetic_flag enforcement
- `event_as_of(calendar, decision_at)`: event visibility at a point in time

### 3. Authority Resolution (`src/hsm_lab/institutions/authority.py`)
- `authority_at(calendar, ...)`: full permission resolution with three-valued uncertainty logic
- `_active_grants_at()`: grant activity classification (definite/uncertain/possible)
- `_effective_revokes_at()`: revoke effectiveness classification (definite/possible)
- `_resolve_authority()`: final status aggregation across grants
- `_check_revoke_scope()`: sector/organization/geography containment validation

### 4. Synthetic Calendar (`institutions/HIST_VNEXT/h1b_synthetic_calendar.json`)
Six synthetic events covering:
- CMEA PRE1975 (inverted-range effective_to for exclusive upper bound)
- CMEA POST1975 (day-precision)
- MTGT 1966-1971 (range precision)
- MTGT POST1971 (year precision)
- Industrial priority 1966-1980 (uncertain effective_from)
- Investment incentives (unknown effective_to)

### 5. Tests (`tests/test_hist_regime_calendar.py`)
33 tests across 8 verification categories:
1. Calendar loading and event visibility
2. Basic granted/denied authority
3. Uncertainty propagation
4. Effective date ranges
5. Unknown precision handling
6. Revoke scope validation
7. Empty and edge-case calendars
8. DateInterval precision validation

### 6. Smoke Tests (`institutions/HIST_VNEXT/H1B/evidence/h1b-smoke-001/run_smoke.py`)
14 smoke checks covering grant/deny/revoke chains, uncertainty propagation, scope validation, and edge cases.

## Verification Results
| Check | Result |
|---|---|
| H1B tests (33) | PASS |
| Full suite (849) | PASS |
| Ruff lint | Clean |
| Smoke (14) | PASS |

## Design Decisions

### DateInterval Inverted Ranges
The plan §2 decision to allow inverted ranges (earliest > latest) for range precision enables natural expression of exclusive upper bounds: `{"earliest": "1975-01-01", "latest": "1974-12-31", "precision": "range"}` means "active until just before 1975-01-01". This is used in the CMEA PRE1975 fixture.

### EffectiveTo Range: Normal vs Inverted
The `effective_to` range branch distinguishes:
- **Inverted** (earliest > latest): active while decision_date < earliest (exclusive upper bound)
- **Normal** (earliest <= latest): active from earliest to latest; decision within range → possibly expired

### Unknown Enactment → Possibly Effective
An event with unknown enactment date contributes to `possible` (not skipped), because the enactment is a prerequisite for effectiveness. If enacted, the other temporal constraints apply.

### Plan §4: Nonexistent Revoke Targets
`RegimeCalendar` validator silently ignores revoke targets not in the event set. At query time, this produces `unknown` (no information), not an error. This prevents schema-level coupling between events.

### Three-Valued Authority Resolution
`authority_at` returns `granted` (definite), `denied` (definite), or `unknown` (uncertain). The uncertainty stems from:
- Uncertain grant effective dates
- Unknown enactment dates
- Possibly effective revokes
- Grants at exact boundary dates

## Known Limitations
1. `is_granted_at()` helper contradicts `authority_at()` for some open-ended grants
2. Proposal/approval lifecycle ordering rejects overlapping intervals even when valid chronology exists
3. No natural-period boundary enforcement for month/quarter/year precision
4. Scope containment doesn't handle all wildcard expansion/reduction combinations
