# H1A Report: 原件来源准入、暴露登记与1957锚crosswalk声明

## Delivery summary
H1A implements the offline source admission module, creates all required JSON artifacts, and
validates the 63-anchor 1957 crosswalk. All 20 new tests pass; full suite is 816 passed.
The smoke test (`admission.py --root .`) returns exit 1 (structural PASS, historical BLOCKED),
which is the expected state given no primary documents have been admitted.

## What was executed

### Step 1 — Authorization and prerequisites
- H0B confirmed PASS (independent re-review, 2026-10-16)
- H1A authorization and budget set (see PLAN.md)
- All H1A files created under approved whitelist

### Step 2 — admission.py implementation
Four public functions:
- `evaluate_source(record, approved_excerpts)` — admission status evaluation
- `find_shared_observations(records)` — shared-observation / independence detection
- `validate_anchor_crosswalk(records, legacy_anchors)` — crosswalk validation with ValueError on violation
- `audit_h1a(root)` — full audit returning exit_code 0/1/2

Tests (20 total): all 4 secondary sources → candidate (not admitted); complete primary with
document_number + archival_reference + rights + excerpt → admitted; missing any field →
candidate/blocked; purpose forcing/actor → blocked; excerpt source_id mismatch → blocked;
1960 proxy claiming 1957 direct → ValueError; 63 blocked anchors → validated; audit smoke →
exit 1 (structural PASS, historical BLOCKED).

### Step 3 — JSON artifacts
| Artifact | Records | Status |
|---|---|---|
| batch01_candidates.json | 4 sources, 3 works | all candidate |
| authority_coverage.json | 5 authorities | all blocked |
| event_candidates/events.json | 10 events (E01–E10) | all candidate |
| access_register.json | 0 approved excerpts | — |
| review_requests.json | 4 REVIEW_REQUIRED pages | — |
| anchor_crosswalk.json | 63 anchors | all blocked (1957) |

### Step 4 — Smoke test
```text
$ python history/HIST_VNEXT/sources/admission.py --root .
exit_code: 1
structural: PASS
historical: BLOCKED
total_candidates: 4, total_admitted: 0, total_blocked_anchors: 63
total_sources: 4, total_works: 3
anchor_classifications: {blocked: 63}
authority_blocked: 5, event_candidates: 10, review_requests_required: 4
```

## Test results
```
20 passed in 0.18s                           # H1A-specific tests
816 passed, 172 warnings in 82.37s          # full suite
All checks passed!                           # ruff
```

## Evidence ledger
| Step | Command | Exit | Result |
|---|---|---|---|
| H1A tests | `pytest tests/test_hist_source_admission.py` | 0 | 20 passed |
| Smoke | `admission.py --root .` | 1 | structural PASS, historical BLOCKED |
| Lint | `ruff check history/ tests/` | 0 | clean |
| Full suite | `pytest -q` | 0 | 816 passed |

## Known limitations
- No primary institutional documents admitted; all authorities remain blocked
- All 63 anchors are classified blocked for 1957; no 1960 proxy forwarded as 1957 direct
- No approved excerpts; all pages remain REVIEW_REQUIRED
- H1B/H2/H3/H4 and synthetic experiments remain out of scope
- Structural results: NOT_RUN; Historical identification: BLOCKED/UNIDENTIFIED
