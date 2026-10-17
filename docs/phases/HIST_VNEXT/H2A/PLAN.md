# HIST_VNEXT H2A — Implementation Plan

## Phase Goal
Implement H2A: actor observation authority, proposal validation, and single-clock constraints for the Hungarian socialist mechanism lab. H2A operates **without** actual goods/cash settlement — it only validates whether decisions are legally authorized and bounded by the calendar.

## Scope

### In Scope (H2A)
- **Observation authority**: actors see only whitelisted fields; no `raw_truth`, `session`, `callback`, `closure`, `target`, `truth`, `calibration_target` at any nesting level
- **Deep immutability**: all observed values converted to immutable primitives, tuples, frozensets
- **`available_at <= decision_at` enforcement**: temporal ordering of observations
- **Proposal validation**: decisions are legal choices, not stock/cash patches
- **Authority check**: H1B calendar maps actor role → permission (granted / revoked / unknown)
- **Three decision rules**: `HistoricalRuleBased`, `BoundedPlanning`, `FullInformationUpperBound`
- **Single clock**: no second `PoliticalSession`; quarter derived from `decision_at` year/month
- **Type-exact validation**: no subclasses of `str`, `date`, `int`, `float`; no coercion via `__float__`/`__int__`/`__index__`
- **No callback execution**: all type checks before any method calls on untrusted input

### Out of Scope (H2B and later)
- Actual goods delivery, transport, financial settlement
- Material flow or financial account mutations
- Execution runner hooks
- Historical F2 replay

---

## Key Files

| File | Role |
|---|---|
| `src/hsm_lab/institutions/observed.py` | `ActorObservation`, `ObservationBuilder`, immutable conversion |
| `src/hsm_lab/institutions/proposal_validation.py` | `validate_proposal`, authority check, rule evaluation |
| `src/hsm_lab/institutions/calendar.py` | `RegimeCalendar` (H1B synthetic calendar) |
| `src/hsm_lab/institutions/decisions.py` | Decision dataclasses per role |
| `tests/test_hist_observation_authority.py` | 131 tests covering all H2A acceptance criteria |

---

## API Surface

### Observation Building
```python
builder = ObservationBuilder(actor_role: str)
obs = builder.build(
    organization_id=str,
    sector_id=str,
    geographic_id=str,
    quarter=str,          # e.g. "1968Q2"
    decision_at=date,
    available_at=date,
    raw_data=dict,        # role-specific fields only, no prohibited keys
) -> ActorObservation   # deep-immutable, whitelist-filtered
```

### Proposal Validation
```python
result = validate_proposal(
    decision: Decision,     # ProcurementDecision | HouseholdNeedDecision | InvestmentDecision | PriceProposalDecision
    calendar: RegimeCalendar,
    observation=None | ActorObservation | dict,
) -> ValidationResult  # is_legal: bool, authority_status: str, reason: str
```

### Calendar Authority Query
```python
from hsm_lab.institutions.authority import authority_at

result = authority_at(
    calendar,
    organization_id=str,
    sector_id=str,
    geographic_id=str,   # e.g. "national"
    permission=str,      # e.g. "procurement" — maps to H1B authority event kind
    decision_at=date,    # query date; only sources available by then are used
) -> AuthorityResult   # result.status ∈ {"granted", "revoked", "unknown"}
```

### Admission requires the existing session clock
```python
result = validate_proposal(
    decision, calendar, observation=None, session=political_session,
)
# session is the engine-owned PoliticalSession; actors never receive it.
# Admission requires session.opened is True, session.finished is False,
# session.done is False, and decision.quarter must equal
# session.quarter_of(session.completed_ticks) — the existing single clock.

# Calendar-only diagnosis for an already-recorded decision (NOT admission):
diagnosis = validate_proposal_retrospective(
    decision, calendar, observation=None,
)
# diagnosis.mode == "retrospective"; diagnosis.admission_eligible is False.
```

---

## Acceptance Criteria

| ID | Criterion | Test(s) |
|---|---|---|
| AC-1 | Actor sees only whitelisted fields | `TestObservationWhitelist` |
| AC-2 | `available_at <= decision_at` enforced | `TestAvailableAtConstraint` |
| AC-3 | No prohibited keys (`raw_truth`, `session`, etc.) at any nesting | `TestObservationBoundaryEnforcement` |
| AC-4 | Deep immutability: no mutable aliases | `TestDeepImmutability` |
| AC-5 | Stock/cash assignments in decisions rejected | `TestProposalLegality` |
| AC-6 | Authority from H1B calendar: granted/revoked/unknown | `TestAuthorityValidation` |
| AC-7 | Bounded planning rejects future info | `TestBoundedPlanningRule` |
| AC-8 | Single clock: `quarter` derived from `decision_at`, not caller-supplied | `TestSingleClock` + `test_expired_tick_rejected` + `test_future_tick_rejected` |
| AC-9 | Same observation dict, different roles → different outcomes | `test_same_observation_dict_different_roles_different_outcomes` |
| AC-10 | No callback execution on any rejected input | All `TestObservationBoundaryEnforcement` and `TestAuthorityBindingEnforcement` regression tests |
| AC-11 | Three roles validated at same tick without conflict | `test_three_roles_same_decision_at_same_quarter_rejected_together` |

---

## Resource Envelope

- **No LLM calls** during H2A validation
- **No execution of actual trades or settlements**
- **No second clock or session created**
- All tests deterministic, isolated, full-suite-safe

---

## Dependencies

- **H1B** (`RegimeCalendar`, synthetic authority events) — loaded from `institutions/HIST_VNEXT/h1b_synthetic_calendar.json`
- **H0A/H0B** — schema definitions in `decisions.py`

## Current revision
Base HEAD `e315b1e` plus the round-19 repair diff recorded in `REPORT.md`
(uncommitted). File hashes and commands are in `REPORT.md`.

## Status After Round-19 Repairs
- Callback-safe field-specific boundary (constructors, builders, verifiers,
  rules, batch admission): **Fixed**
- Declared enum membership enforced by identity (fabricated non-members
  rejected before Pydantic coercion): **Fixed**
- Observation and decision storage custody (`__dict__`, metadata, extras,
  private storage, keys, aliases): **Fixed**
- Session-clock binding requires exact engine-owned `MaterialState` /
  `ScenarioSpec` containers, rejects instance shadowing of `quarter_of`, and
  reads raw lifecycle/clock values before coercion; `Quarter` storage and
  metadata are audited directly (no descriptor dispatch or unverified
  instance methods); the engine quarter must agree with the audited clock;
  stale/future/unopened/finished/exhausted/omitted cases rejected: **Fixed**
- Calendar-only checking is the explicitly separate, machine-readable
  `validate_proposal_retrospective` (never admission-eligible).
- **Independent PASS**: pending independent review. C0/C1 benchmark replay is
  not H2A acceptance evidence and is not required by this phase plan.
