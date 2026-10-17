# H2A Report — Implementation Evidence

## Phase
HIST_VNEXT H2A — observation authority, proposal validation, single clock.

## Revision
- Base HEAD: `e315b1e` (`fix(H2A): eliminate all type().__name__ in error messages`)
- Working-tree changes under review (uncommitted): `observed.py`,
  `proposal_validation.py`, `decisions.py`,
  `tests/test_hist_observation_authority.py`, `PLAN.md`, `REVIEW.md`,
  smoke runner/output.
- No commit or push was performed for this repair round.
- Untracked H2B work (`execution_adapter.py`, `test_hist_tiny_execution.py`,
  `H2B_准入阻断_PLAN.md`) was not modified and is outside this report.

## File identities (SHA-256)
```text
656ad0dffd0eba0db4bf382e919915a72cdc254f070c03180f37d1b2b1afa034  src/hsm_lab/institutions/observed.py
3d7e83d053e210eebd76322fbdb1c0e80b51d72a169a87ba9beb3a9105abe2fe  src/hsm_lab/institutions/proposal_validation.py
2fca6f66ffa75c7ae59d82ba06bff7130876b56352b7909410a243303b99c211  src/hsm_lab/institutions/decisions.py
1423531db07c194bc4fc054d7f7257af4d6d9fb5b7b55a8e0b18d38952733ed0  tests/test_hist_observation_authority.py
cb80aea13bd255dc89d0c53b8404f2111e78a988dae58f899c98f5385d68acdb  institutions/HIST_VNEXT/h1b_synthetic_calendar.json
0e526c3c6e61ec4e7ef926fd1675ad6e777c4dda12cfb3d604d82078dd26fe30  institutions/HIST_VNEXT/H2A/evidence/h2a-smoke-001/run_smoke.py
823e6ff044236da2a406d3a7d0ff525e3fad24601bcc370e7d83f0db10ea03ff  institutions/HIST_VNEXT/H2A/evidence/h2a-smoke-001/smoke_output.txt
0e8483ab0d979f199a29d870a3c97bd6861b8aab46b02ed94db59b70a627dc49  docs/phases/HIST_VNEXT/H2A/PLAN.md
```

## Commands exercised in this round (newly run)
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_hist_observation_authority.py
# → 131 passed, 0 failed

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
# → 990 passed, 172 warnings

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  institutions/HIST_VNEXT/H2A/evidence/h2a-smoke-001/run_smoke.py
# → 11 passed, 0 failed (S5 is session-bound admission; S10 proves the
# retrospective path is not admission-eligible)

.venv/bin/ruff check --no-cache src tests
# → All checks passed
```

Adversarial probes were additionally executed inline for every counterexample
in review rounds 13 and 14: unsupported decision, `model_copy` payload,
str-subclass role, `model_construct` metadata escape, non-exact storage key,
missing storage field, cyclic and 1,500-deep acyclic containers, quarter
conflict, duplicate measurement names, household identity mismatch,
geographic `__ne__`, decision-date `__gt__`, dict-key `__eq__`, constructor
`__float__`, stock/cash assignment, and unsupported rule observation. Every
probe returned a rejection with zero callbacks recorded.

## Defects repaired

### Round 13
| ID | Finding | Repair |
|---|---|---|
| P0-A | Unsupported decision path called `getattr(decision, "decision_id")` | Static `<unknown>` identifier; no attribute access |
| P0-B | Decision field screening used `isinstance`, metaclass `getattr`, tuple membership, `model_dump()` before exact types | Static per-class exact-type table; identity-only checks; serialization only after every field is exact |
| P0-C | Rejection diagnostics formatted untrusted `type(...).__name__` | Static messages throughout the H2A boundary |
| P0-D | Builder role lookup accepted str subclasses | Exact `str` gate before membership |
| P0-E | Pydantic iterated custom `observed_fields` | Pre-gate in `ActorObservation.__init__` before `super().__init__` |
| P0-F | Public `BoundedPlanning.evaluate` used `getattr(observation, ...)` | Exact-type dispatch; unsupported types rejected |
| P0-G | `model_construct(_fields_set=...)` smuggled `raw_truth`/`session` | Metadata/extra/private/`__dict__` custody audit |
| P0-H | Dict observations retained aliases and conflicting quarter | Canonicalisation into immutable `ActorObservation`; conflict rejected |
| P1-A | No existing-session clock binding | Trusted `session=` bridge |
| P1-B | Observation availability not bounded by decision horizon | `observation.available_at <= decision.available_at` |
| P1-C | `geographic_id` compared before type validation | Exact `str` gate at entry |
| P1-D | Household need could claim another identity | `household_id == organization_id` |
| P1-E | Proxy-only acceptance tests | Behavioural regressions added |

### Round 14
| ID | Finding | Repair |
|---|---|---|
| R14-A | Storage keys could be str subclasses carrying `raw_truth` | Exact-string storage-key iteration; return immediately; never construct a set from untrusted keys |
| R14-B | Malformed storage continued into field access (`AttributeError`) | Structural failures return immediately; missing/extra keys rejected |
| R14-C | Verifier executed descriptors on an unsupported object | Exact `ActorObservation` gate at verifier entry |
| R14-D | Verifier compared a hostile `quarter` value with `__ne__` | Type-gate the value before comparison |
| R14-E | Public rule compared decision dates from `model_copy` payloads | Exact `date` gate on decision fields before comparison |
| R14-F | Public rule looked up dict observations before key validation | Exact-string key gate before lookup |
| R14-G | Decision constructor executed `__float__` coercion | Pre-Pydantic exact-type constructor gate |
| R14-H | Household observation could present `HH-002` while bound to `HH-001` | Observed `household_id` must equal the observation organization |
| R14-I | Duplicate measurement names accepted; reads and evidence disagreed | Unique observed field names enforced in constructor and verifier |
| R14-J | Direct construction accepted a conflicting duplicate quarter | Enforced in constructor as well as verifier |
| R14-K | Deep acyclic input raised `RecursionError` | Explicit 64-level nesting limit with deterministic rejection |
| R14-L | Session clock was optional for admission | Admission requires an opened, unfinished exact `PoliticalSession` matching `completed_ticks`; calendar-only checking moved to `validate_proposal_retrospective` |

### Round 15
| ID | Finding | Repair |
|---|---|---|
| R15-A | Decision constructor called `isinstance`, executing `__class__` on hostile payloads | Identity-only exact-type gate; no reflective operation |
| R15-B | Observation constructor looked up hostile keyword keys before validating them | Exact-string keyword-key gate before any `data.get` or Pydantic processing |
| R15-C | Public rule bypassed observation storage/metadata custody and raised `AttributeError` on missing fields | Rule reuses `verify_observation_invariants`; decision storage audited via `_decision_storage_violation` |
| R15-D | Batch validation iterated arbitrary custom containers | Requires an exact plain `list` before iteration |
| R15-E | A `finished=True` session could still authorize admission | Requires `finished is False` in addition to `done is False` |
| R15-F | Verifier did not unconditionally type-check context fields | `actor_role`, `organization_id`, `sector_id`, `geographic_id`, `quarter` must all be exact `str` |
| R15-G | Retrospective results were indistinguishable from admission | `ValidationResult.mode` and `admission_eligible`; retrospective is machine-readable non-admission |
| R15-H | Docs described session binding as optional and had stale hashes/counts | Plan/report/review/manifest corrected |

### Round 16
| ID | Finding | Repair |
|---|---|---|
| R16-A | Exact enum types accepted fabricated non-members whose `_value_` coerced via `__str__` | Field-specific type map plus identity membership against declared enum members, before Pydantic |
| R16-B | Forged choice kinds passed rule evaluation and admission | Shared membership-aware storage audit used by core validator and public rule |
| R16-C | Session clock properties coerced (`int(...)`) before status/type rejection | Raw `opened`/`finished`/`state`/`spec`/`target_ticks`/`completed_ticks` read with `object.__getattribute__`; exact types checked before quarter computation |
| R16-D | Public rule dict observations bypassed prohibited-key/identity/value custody | Rule uses `_canonical_observation`, the same boundary as proposal validation |
| R16-E | Decision metadata (`__pydantic_fields_set__`/extra/private) unchecked | Decision custody audit extended to metadata, extras, private storage, and exact declared keys |
| R16-F | Plan still reported round 14 / 108 tests | Plan counts, revision, and status corrected |

### Round 17
| ID | Finding | Repair |
|---|---|---|
| R17-A | An exact `Quarter` could shadow `advance` or hold forged fields | `_quarter_storage_violation` audits metadata, exact keys, exact ints, and ranges; quarter arithmetic uses trusted integer ops only |
| R17-B | `state.completed_ticks` / `spec.start` descriptors executed before validation | Raw `__dict__` reads with exact-string key gates; descriptors are never invoked |
| R17-C | Clock regressions missing | Added method-shadowing, state/spec descriptor, and forged-quarter field tests |

### Round 18
| ID | Finding | Repair |
|---|---|---|
| R18-A | `state.__dict__` / `spec.__dict__` could be hostile properties | Admission requires exact `MaterialState` / `ScenarioSpec` before any attribute access; fixtures use the real engine types |
| R18-B | Incomplete `Quarter.__pydantic_fields_set__` accepted | Requires exactly `{"year","quarter"}` in addition to exact element checks |
| R18-C | Missing regressions for hostile `__dict__` and incomplete field sets | Added state/spec `__dict__` descriptor and empty/singleton field-set tests |

### Round 19
| ID | Finding | Repair |
|---|---|---|
| R19-A | Instance-level `session.quarter_of` could shadow the engine clock | Reject instance shadowing; require the verified class function; compare engine quarter with the audited raw-storage quarter |
| R19-B | No rollover/agreement coverage | Added rollover cases (1967Q4+2, 1966Q3+7, 1968Q2+0) and shadowed-method rejection asserting zero calls |

## Scope notes
- H2A performs no delivery, settlement, or material/financial mutation.
- The H1B synthetic calendar is labelled synthetic. No historical claim is made.
- C0/C1 benchmark manifests belong to an earlier revision and are not H2A
  acceptance evidence; they were not regenerated for this phase.
- Prerequisite phase approvals (H0A/H0B, H1B) are separate phase gates. This
  report does not substitute for them and does not claim them.

## Verdict
Implementer evidence only. Independent phase review remains the authority on
PASS/PATCH/REDESIGN.
