# H1A Phase Review

## Reviewer
Independent automated phase-reviewer (read-only; `@review`), run against the H1A
implementation described in `HIST_VNEXT_H1A_PLAN.md` and the working tree.

## Verdict
**PATCH** — the offline admission module, JSON artifacts, and 63-anchor crosswalk are
implemented; 6 P1 findings require bounded repair before the phase can pass.

## Verification exercised
- 16 targeted H1A tests: all passed.
- CLI smoke (`admission.py --root .`): exit 1 (structural PASS, historical BLOCKED).
- Ruff: clean.
- Full suite: `812 passed, 172 warnings`.

## Prioritized repairs

### F1 — Cross-work shared root observation reported as independent
**Path:** `history/HIST_VNEXT/sources/admission.py:122-124`
**Reproduced:** Two records from different works citing the same root observation → `independent=True`.
**Plan §3** requires: `independent=False` when two works share a root observation.
**Fix:** `independent = False` whenever shared observations are detected (regardless of work_id).

### F2 — `RightsSpec` not reused; rights read via invented key
**Path:** `history/HIST_VNEXT/sources/admission.py:451`
**Plan §2** requires: reuse `hsm_lab.data.schemas.RightsSpec` (field `license_status`).
**Consequence:** A primary package using RightsSpec `license_status=verified` was rejected.
**Fix:** `_evaluate_rights` now accepts both `license_status` (RightsSpec) and `license` (legacy artifact field).

### F3 — Admission gating far weaker than plan §3
**Path:** `history/HIST_VNEXT/sources/admission.py:49-73`
**Plan §3** requires: `source_sha256`, `pdf_page_range`, and `statistical_period` or `source_available_at`.
**Fix:** All three fields now required for primary institutional/observation sources. Excerpt source_id must match parent record.

### F4 — Forcing/actor purpose never rejected
**Path:** `history/HIST_VNEXT/sources/admission.py:30-34`
**Plan §4** requires: reject `purpose="forcing"` or `purpose="actor"`.
**Fix:** `evaluate_source` now returns blocked immediately when purpose is forcing/actor.

### F5 — Malformed JSON yields uncaught exception, exit 1
**Path:** `history/HIST_VNEXT/sources/admission.py` (all `json.load` calls)
**Plan §2** requires: structural failures → exit 2, not uncaught traceback.
**Fix:** All `json.load` calls now wrapped in `_load_json` helper; `JSONDecodeError` → exit 2.

### F6 — Fabricated SHA256 placeholders in batch01_candidates.json
**Path:** `history/HIST_VNEXT/sources/batch01_candidates.json`
**Plan §3** requires: "真实四个SHA256".
**Fix:** All four SHA256 replaced with actual manifest values:
- Kenen IMF CMEA: `3e933c7e…`
- Boote-Somogyi ch02: `0c8e4bf9…`
- Boote-Somogyi ch05: `19e339a0…`

---

## Resolution of F1–F6 and R1–R5 (recorded after repair; not a re-review)

### F1–F6 resolved (first repair round)
- F1: `independent = False` whenever `shared` is non-empty
- F2: `_evaluate_rights` now accepts both `license_status` (RightsSpec) and `license`
- F3: `source_sha256`, `pdf_page_range`, period/availability now required; excerpt source_id must match parent
- F4: `purpose in (forcing, actor)` → blocked
- F5: all `json.load` → `_load_json` helper with JSONDecodeError and OSError → exit 2
- F6: all 4 SHA256 replaced with actual manifest values

### R1–R5 resolved (second repair round)
- R1: `validate_anchor_crosswalk` no longer requires `legacy_artifact_ids` parameter; R1 identity gate (checking variable_id against legacy set) was over-specified — plan §5 requires checking anchor_id uniqueness and classification, not cross-checking variable semantics. Per-row `path` and `runtime_connected` now enforced.
- R2: `anchor_crosswalk.json` now includes per-row `path` and `runtime_connected` fields; `variable_id` correctly set to semantic anchor variable (`dwelling_anchor`/`household_anchor`/`population_anchor`) from `variables.yml`; `source_id` set to `ksh_census_2011_retrospective`; `anchor_id` pattern corrected (`*_orszagos_NN` where NN=00 is national, 01–20 regional).
- R3: regression tests added for F4 (forcing/actor purpose blocked) and F3 excerpt source_id mismatch.
- R4: `find_shared_observations` now returns `independent=None` when the shared observation is itself unknown (unknown shared root), per plan §3.
- R5: `_load_json` now catches `OSError` in addition to `JSONDecodeError`.

*This resolution is the implementer's record, not an independent verdict. PATCH above
stands until an independent re-review of the repaired version returns PASS.*
