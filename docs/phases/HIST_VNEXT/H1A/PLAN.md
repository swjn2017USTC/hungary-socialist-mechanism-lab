# H1A Plan: 原件来源准入、暴露登记与1957锚crosswalk声明

## Phase identity
- **ID**: H1A
- **Objective**: source admission evaluation, exposure registration, and 1957 anchor crosswalk declaration
- **Dependencies**: H0B PASS (`docs/phases/HIST_VNEXT/H0B/REVIEW.md` = PASS, 2026-10-16)
- **Plan date**: 2026-10-16
- **Status**: IMPLEMENTED

## Authorization (this phase)
| Parameter | Value |
|---|---|
| max_wall_s | 600 |
| max_rss_bytes | 512 MB |
| max_new_output_bytes | 100 MB |
| max_run_count | 1 |
| model_input_tokens | 128000 |
| model_output_tokens | 16384 |
| paid_cost_cap | 10.00 USD |
| MiniMax reasoning_effort | medium |
| Implementer | `minimax-code-cn/MiniMax-M3` (single-task override) |
| Reviewer | `@review` (`.omp/config.yml`) |
| Commit | `@commit` (`.omp/config.yml`) |

## File whitelist (executed scope)
- `history/HIST_VNEXT/sources/admission.py` — offline admission/validation module
- `history/__init__.py`, `history/HIST_VNEXT/__init__.py`, `history/HIST_VNEXT/sources/__init__.py` — package inits
- `tests/test_hist_source_admission.py` — behavioral contracts and negative examples
- `history/HIST_VNEXT/sources/batch01_candidates.json` — 4 secondary sources, 3 works
- `history/HIST_VNEXT/sources/authority_coverage.json` — 5 authority entries, all blocked
- `history/HIST_VNEXT/event_candidates/events.json` — 10 event candidates (E01–E10)
- `history/HIST_VNEXT/exposure/access_register.json` — 0 approved excerpts, 1 prior exposure reference
- `history/HIST_VNEXT/exposure/review_requests.json` — 4 REVIEW_REQUIRED page requests
- `config/initial_state/hist_vnext_v1/anchor_crosswalk.json` — 63 anchors, all classified as blocked
- `docs/phases/HIST_VNEXT/H1A/{PLAN,REPORT,REVIEW}.md` — phase delivery artifacts

## What was implemented

### H1A §2 — offline admission evaluation
`evaluate_source(record, approved_excerpts)` returns `status ∈ {candidate, admitted, blocked}` with
field-level evidence-gap reasons. Secondary sources (secondary_analysis) are always `candidate`.
Primary institutional/observation sources require: document_number, archival_reference, rights
(non-unknown), and at least one approved excerpt with valid hash/approval metadata.

### H1A §3 — shared observation detection
`find_shared_observations(records)` detects shared root observations across records. Two records
with the same work_id sharing a root observation are `independent=False`. A cited observation
ID absent from any record's observation_ids is treated as unknown root → `independent=None`.

### H1A §4 — exposure registration
`access_register.json` records prior exposure from `evidence/EXPOSURE_DISCLOSURE.md` as metadata-only.
No approved excerpts exist. `review_requests.json` holds 4 REVIEW_REQUIRED page requests for the
batch-01 candidates (Balassa 10–18, IMF ch02 1–2, IMF 1990 p.7, IMF ch05 1–4).

### H1A §5 — 63-anchor 1957 crosswalk
`anchor_crosswalk.json` declares all 63 initial-state anchors (21 each: dwelling/household/population)
from `data/manifests/DATA_MANIFEST_v1.json` filtered by `role=initial_state`. All are 1960 proxies,
so all are classified `blocked` for the 1957 target. No 1960 proxy is misclassified as direct.
No 1960 value is forwarded as a 1957 initial value.

### H1A §6 — audit_h1a CLI
`python history/HIST_VNEXT/sources/admission.py --root .` exits:
- **0**: all structural AND historical gates pass (not expected in this phase; requires primary docs + authority coverage)
- **1**: structural PASS, historical BLOCKED (current state: 4 candidates, 0 admitted, 5 blocked authorities, 10 event candidates)
- **2**: structural BLOCKED (file missing, JSON parse error, or crosswalk validation failure)

## Verification gate
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py
# expected: 16 passed
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python history/HIST_VNEXT/sources/admission.py --root .
# expected: exit 1 (structural PASS, historical BLOCKED)
.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py
# expected: All checks passed
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
# expected: 812 passed, 172 warnings
```
