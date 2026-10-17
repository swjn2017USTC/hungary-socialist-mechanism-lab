# H2A Review

## Phase
HIST_VNEXT H2A — Observation authority, proposal validation, single-clock constraints

## Status
**PASS** — independent round-19 audit; no reproducible blocking defect found.

The independent reviewer exercised the full suite (990 passed), H2A smoke
(11/11), and Ruff (all checks passed), matched every SHA-256 identity in
`REPORT.md` and the smoke manifest, and ran additional adversarial probes.
All clock-dispatch shadowing, container/Quarter custody, lifecycle,
enum-membership, field-type, observation-boundary, and decision-storage
defects were rejected with zero callbacks.

Scope: this verdict covers H2A only. It does not clear the separate
H0A/H0B/H1B prerequisite gates or certify earlier C0/C1 artifacts.

## Current revision
Base HEAD `e315b1e` plus the uncommitted round-19 repair diff described in
`REPORT.md`. Commit authorization for this repair round remains separate.

---

## Code Defect Fixes (rounds 1–12)

| ID | Finding | Fix | Round |
|---|---|---|---|
| P0-1 | `_check_no_prohibited_keys`: `str(k)` before type guard | `type(k) is not str` guard + `str.lower(k)` builtin | R1 |
| P0-2 | `actor_role` compared before type check | `type(obs_role) is not str` guard before `!=` | R1 |
| P0-3 | `ObservationBuilder.build`: `{field_name!r}` + `.lower()` | `type(field_name).__name__` + `str.lower(field_name)` | R1 |
| P0-4 | `verify_observation_invariants`: unpack before tuple check | `type(obs.observed_fields) is not tuple` check + element-type guard | R1 |
| P0-5 | `ActorObservation` subclass check after `__dict__` access | Subclass check before any `__dict__` access | R2 |
| P0-6 | Date comparison before type check | `object.__getattribute__` + type check before comparison | R2 |
| P0-7 | `actor_role in _ROLE_WHITELISTS` with non-string | Early return for non-string; `object.__getattribute__` for role value | R2 |
| P0-8 | `model_dump()` triggers `__getattribute__` | Removed `model_dump()` call | R2 |
| P0-9 | Dict key type check after `.get()` | Key type check before any `.get()` | R3 |
| P0-10 | `_to_immutable`: `{k!r}` for non-string key | `type(k).__name__` only | R3 |
| P0-11 | `verify_observation_invariants`: `{actor_role_val!r}` | `type(actor_role_val).__name__` only | R3 |
| P0-12/13 | `type() in (...)` / `.isinstance()` callbacks | All replaced with `type() is` identity checks | R8 |
| P0-14 | `.__mro__` / `.__bases__` / `.__name__` callbacks | Replaced with `type() is` only; static error messages | R8-9 |
| P0-15 | Decision type whitelist `not in tuple` triggers `__eq__` | Chained `type() is` comparisons; static error messages | R10 |
| P0-16 | `_to_immutable` rejection `type().__name__` | Static rejection message | R10 |
| P0-17 | Blanket `type(value) is not int` for non-string fields | Removed; int subclass detection via `_to_immutable` | R11 |
| P0-18 | All remaining `type().__name__` in rejection paths | Static error messages throughout | R12 |

## Round 13 repairs (implementer; independent verification pending)

The independent reviewer reproduced remaining callback paths, an implicit
truth/session escape, and missing identity/clock bindings. Repairs:

| ID | Finding | Repair |
|---|---|---|
| R13-1 | Unsupported decision called `getattr(decision, "decision_id")` | Static `<unknown>`; no attribute access |
| R13-2 | Decision screening used `isinstance`/metaclass `getattr`/`model_dump()` before exact types | Static per-class exact-type table; identity-only checks; serialization only after type gate |
| R13-3 | Rejection diagnostics formatted `type(...).__name__` | Static messages throughout |
| R13-4 | Builder role lookup executed str-subclass `__hash__`/`__eq__` | Exact `str` gate before membership |
| R13-5 | Pydantic iterated custom `observed_fields` | Pre-gate in `__init__` before `super().__init__` |
| R13-6 | Public `BoundedPlanning.evaluate` used `getattr(observation, ...)` | Exact-type dispatch; unsupported types rejected |
| R13-7 | `model_construct(_fields_set=...)` smuggled `raw_truth`/`session` | Metadata, extra, private, and `__dict__` custody checks |
| R13-8 | Dict observations retained mutable aliases / duplicate quarter | Canonicalisation to immutable `ActorObservation`; quarter conflict rejected |
| R13-9 | No existing-session clock binding | Optional `session=` binding via `quarter_of(completed_ticks)` |
| R13-10 | Observation availability not bounded by decision information horizon | `observation.available_at <= decision.available_at` |
| R13-11 | `geographic_id` compared before type check | Exact `str` gate at entry |
| R13-12 | Household need could claim another identity | `household_id == organization_id` required |
| R13-13 | Proxy-only acceptance tests | Behavioural regressions added (identical information, three roles with observations, stock/cash payloads, cycles, hostile metaclasses) |
| R13-14 | Plan documented stale `authority_at` signature | Plan corrected |
| R13-15 | No report / revision-bound evidence | `REPORT.md` + `evidence/h2a-smoke-001/manifest.json` |

## Round 14 repairs (implementer; independent verification pending)

| ID | Finding | Repair |
|---|---|---|
| R14-A | Storage keys could be str subclasses carrying `raw_truth` | Exact-string storage-key iteration; immediate return; no set built from untrusted keys |
| R14-B | Malformed storage continued into field access (`AttributeError`) | Structural failures return immediately; missing/extra keys rejected |
| R14-C | Verifier executed descriptors on an unsupported object | Exact `ActorObservation` gate at verifier entry |
| R14-D | Verifier compared a hostile `quarter` value with `__ne__` | Type-gate the value before comparison |
| R14-E | Public rule compared decision dates from `model_copy` payloads | Exact `date` gate on decision fields before comparison |
| R14-F | Public rule looked up dict observations before key validation | Exact-string key gate before lookup |
| R14-G | Decision constructor executed `__float__` coercion | Pre-Pydantic exact-type constructor gate |
| R14-H | Household observation could present another household's identity | Observed `household_id` must equal the observation organization |
| R14-I | Duplicate measurement names accepted | Unique observed field names enforced in constructor and verifier |
| R14-J | Direct construction accepted a conflicting duplicate quarter | Enforced in constructor as well as verifier |
| R14-K | Deep acyclic input raised `RecursionError` | Explicit 64-level nesting limit |
| R14-L | Session clock was optional for admission | Admission requires an opened, unfinished exact `PoliticalSession`; calendar-only checking moved to `validate_proposal_retrospective` |

## Round 15 repairs (implementer; independent verification pending)

| ID | Finding | Repair |
|---|---|---|
| R15-A | Decision constructor executed `__class__` via `isinstance` | Identity-only exact-type gate |
| R15-B | Observation constructor looked up hostile keyword keys | Exact-string key gate before any lookup |
| R15-C | Public rule bypassed storage/metadata custody and raised on missing fields | Rule reuses the verifier; decision storage audited |
| R15-D | Batch validation iterated custom containers | Exact plain `list` required |
| R15-E | `finished=True` session could authorize admission | `finished is False` required in addition to `done is False` |
| R15-F | Verifier skipped unconditional context-field type checks | All context fields must be exact `str` |
| R15-G | Retrospective results indistinguishable from admission | `mode` + `admission_eligible` result fields |
| R15-H | Stale plan/report/review/manifest claims | Corrected |

## Round 16 repairs (implementer; independent verification pending)

| ID | Finding | Repair |
|---|---|---|
| R16-A | Fabricated exact enum non-members coerced via `_value_` | Field-specific type map + identity membership allowlist |
| R16-B | Forged choice kinds passed rule/admission | Shared membership-aware storage audit |
| R16-C | Session clock properties coerced before rejection | Raw lifecycle/clock reads with exact-type gates |
| R16-D | Rule dict observations bypassed custody | Rule uses `_canonical_observation` |
| R16-E | Decision metadata/extras/private unchecked | Extended decision custody audit |
| R16-F | Plan stale counts/round | Plan corrected |

## Round 17 repairs (implementer; independent verification pending)

| ID | Finding | Repair |
|---|---|---|
| R17-A | Exact `Quarter` could shadow `advance` / hold forged fields | Full quarter storage audit + trusted integer arithmetic |
| R17-B | `state.completed_ticks` / `spec.start` descriptors executed | Raw `__dict__` reads with exact-string key gates |
| R17-C | Missing clock regressions | Added shadowed-method, descriptor, and forged-field tests |

## Round 18 repairs (implementer; independent verification pending)

| ID | Finding | Repair |
|---|---|---|
| R18-A | Hostile `state.__dict__` / `spec.__dict__` properties | Exact `MaterialState` / `ScenarioSpec` gate before attribute access |
| R18-B | Incomplete `Quarter` field set accepted | Requires exactly `{"year","quarter"}` |
| R18-C | Missing clock-container regressions | Added `__dict__` descriptor and field-set tests |

## Round 19 repairs (implementer; independent verification pending)

| ID | Finding | Repair |
|---|---|---|
| R19-A | Instance `quarter_of` could shadow the engine clock | Instance shadow rejected; verified class function used; engine quarter must equal the audited clock quarter |
| R19-B | Missing rollover/agreement coverage | Added rollover cases and shadowed-method rejection |

## Acceptance Tests (round 19)

| Suite | Result |
|---|---|
| `test_hist_observation_authority.py` | **131 passed**, 0 failed |
| Full suite | **990 passed**, 0 failed |
| `ruff check --no-cache src tests` | **0 errors** |
| H2A smoke (`run_smoke.py`) | **11/11** (S5 admission; S10 retrospective distinction) |

## Verification Commands

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_hist_observation_authority.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  institutions/HIST_VNEXT/H2A/evidence/h2a-smoke-001/run_smoke.py
```

## Design-Limit Notes

| Item | Note | Severity |
|---|---|---|
| `_to_immutable` recursion | Cyclic input is rejected, and acyclic nesting deeper than 64 levels is rejected deterministically (never `RecursionError`) | Low |
| Third-party Pydantic internals | `model_construct` bypass is rejected at the validation boundary rather than prevented at construction | Low |
| Prerequisite phase gates | H0A/H0B and H1B independent approvals are separate gates; this phase does not substitute for them | Phase gate |

## Files Changed

- `src/hsm_lab/institutions/observed.py` — callback-safe boundary, metadata custody, cycles
- `src/hsm_lab/institutions/proposal_validation.py` — exact-type gate, session clock, horizon binding
- `src/hsm_lab/institutions/decisions.py` — household identity binding
- `tests/test_hist_observation_authority.py` — 131 behavioural/regression tests
- `docs/phases/HIST_VNEXT/H2A/{PLAN,REPORT}.md` — API correction and evidence

## Recommendation
Independent round-19 verdict: **PASS** for H2A. The separate H0A/H0B/H1B
prerequisite gates and any commit authorization remain outstanding.
