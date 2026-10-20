**VERDICT: PASS**

## Observed evidence

Read-only audit. BASELINE read first; round-13 review read second; H4A-1 PLAN/REPORT and original H1A contract inspected. No repository file was edited and no data approval was signed.

| Command exercised | Exit | Observed result |
|---|---:|---|
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py` | 0 | **198 passed in 5.61s** |
| `.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py` | 0 | All checks passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .` | 1 | structural **PASS**, historical **BLOCKED**; 4 candidates, 0 admitted, 63 blocked anchors, 5 blocked authorities, 10 candidate events, 4 review requests |
| `PYTHONDONDWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.admission --root . --verify-files` | 1 | structural **PASS**, historical **UNIDENTIFIED**, 0 approved inputs |
| `shasum -a 256 BASELINE.md data/manifests/DATA_MANIFEST_v1.json` | 0 | matches frozen hashes `1f5b233f…` / `5d91e014…` |
| 12 read-only Python falsification mutations (parser, evaluator, audit API, subprocess CLI) over the round-13 inputs and several extended composite variants | 0 each | result inline below |
| `git status` / `git diff -- BASELINE.md docs/phases/HIST_VNEXT/H1A/REPORT.md docs/phases/HIST_VNEXT/H1A/REVIEW.md data/manifests/DATA_MANIFEST_v1.json` | 0 | all five files identical to HEAD; only `docs/phases/HIST_VNEXT/H1A/PLAN.md` shows the 5-line stale-test-count cleanup already accepted in `H1A_REPAIR.md` |

## Round-13 PATCH verification

Round 13 required: slash intervals accept exactly two ordered atomic year/month/day endpoints; composite year-range endpoints on either side of `/` are rejected; standalone ordered year ranges remain accepted; malformed authority periods, excerpt windows and source statistical periods must not authorize admission or historical PASS; legitimate precision/ordered interval positives remain.

`_date_bounds` was re-read at `history/HIST_VNEXT/sources/admission.py:954–973`. Slash endpoints go through `_atomic_date_bounds` (line 909), which only accepts `YYYY`, `YYYY-MM`, `YYYY-MM-DD`; the standalone `_standalone_date_bounds` (line 934) is invoked only for single-token values, where its year-range branch still admits `1968-1985`. The order check `left[0] > right[0]` rejects reversed pairs.

| Input | `_date_bounds(...)` | Evaluator | audit_h1a API | Subprocess CLI | Verdict |
|---|---|---|---|---|---|
| `1966-1988/1967` | `None` | source blocked: `allowed_window is not a date range` | historical BLOCKED | rc=1 / historical BLOCKED | Rejected (composite LHS) |
| `1966/1967-1988` | `None` | source blocked | historical BLOCKED | rc=1 / historical BLOCKED | Rejected (composite RHS) |
| `1966-1988/1967-1968` | `None` | source blocked | historical BLOCKED | rc=1 / historical BLOCKED | Rejected (composite both sides) |
| `1968/1968-1985`, `1968-01/1968-1985`, `1966-05/1966-1988`, `1966-12-31/1966-1988`, `1966-1988/1966-12-31` | `None` (extended falsification) | — | — | — | Rejected (extended composite forms) |
| `1966/1967`, `1966`, `1966-05`, `1966-05-15`, `1968-1985`, `1968/1985`, `1966/1966-05` | respective bounds | admitted with matching window | rc=0 / historical PASS for atomic-only fixture | rc=0 / PASS in positive fixture | Retained positives |
| `1967-12-31/1966-01-01`, `1966/1967/1968`, `1968/1967`, `1966/1967/1988`, `not-a-period`, `""`, `"1966/"`, `"/1966"`, `"1966//1967"`, `"1966-13"`, `"1966-04-31"`, `"abc"` | `None` | blocked | historical BLOCKED | rc=1 / historical BLOCKED | Malformed negatives rejected |

Substantive authority-period mutation with the round-13 input `1966-1988/1967`: real `audit_h1a` API and the subprocess CLI both return historical `BLOCKED`; with both records' `statistical_period` set to the same composite form, `total_admitted=0`, `total_blocked_sources=2`, and the details line `[decree_1966_41] invalid excerpt 'excerpt_001': allowed_window does not cover statistical_period='1966-1988/1967'` confirms a source-level block, not just a downstream gate.

A standalone `allowed_window="1968-1985"` with `statistical_period="1968/1985"` is admitted by the evaluator (`status="admitted"`, `reasons=[]`), confirming positive retention of the standalone year range. Matching `period="1968-1985"` is also admitted.

Malformed authority period `1966-1988/1967`, malformed excerpt window `1966-1988/1967`, malformed source statistical period `1966-1988/1967` were each tested through `audit_h1a(positive_repo)` with the positive software fixture in place. Each returns `exit_code=1`, `historical=BLOCKED`. No malformed declaration authorizes admission or historical PASS.

## Earlier finding rechecks

| Finding | Reproduction command summary | Disposition |
|---|---|---|
| Anchor bijection/classification/geography/evidence kind (R1/R2) | `shutil.copy` real crosswalk; forge `classification=direct` on proxy artifact, swap in `FAKE_NOT_A_VARIABLE`, replace `anchor_id` with `FAKE_invented_anchor`, drop `legacy_artifact_id`, set `source_evidence_kind=synthetic` on proxy artifact, tamper `path` | Each is rejected at `validate_anchor_crosswalk`, exit 2 / structural BLOCKED with a per-field reason (e.g., `direct rows cannot retain missing_evidence`, `unknown variable_id`, `does not match legacy artifact identity`, `missing legacy_artifact_id`, `does not match legacy artifact evidence_status`, `does not match legacy artifact value`). Legacy-artifact bijection contract restored and verified. |
| Rights/excerpt handoff/pages/full period (F2/F3) | `evaluate_source` with `rights={"license_status":"verified"}` only; with `excerpt` minus `pdf_pages` | RightsSpec is reused; bare "verified" raises `ValueError` listing required fields; missing `pdf_pages` rejected. |
| Forcing/actor purposes (F4) | `purpose=forcing` / `purpose=actor` | Both blocked with explicit reason `historical target as forcing/actor not admitted`. |
| Malformed JSON (F5) | Replace each of seven required files with `"{"` | All seven exit `rc=2` / structural BLOCKED. Missing required files also exit 2. |
| Fabricated SHA (F6) | Overwrite first record `source_sha256` with `deadbeefdead…` | Structural PASS, historical BLOCKED (downstream gate). |
| Shared roots (R4/F1) | `find_shared_observations` over four hand-built record pairs | Same work → False; shared root distinct works → False (or None if unknown cited); disjoint distinct works → True; one unrooted → None. |
| Required-file errors | OSError injected on manifest load | Returns structured `AttributeError`-free structural BLOCKED via the structural-error path. |
| Date precision / event document-or-archive | Set event `date=1966` with `date_precision=day`; null both `document_number` and `archival_reference`; null each one alone | Day-precision mismatch blocked; both nulls blocked; one null passes. |
| Authority identity/period/disjointness | Set `authority=" \t"` and `period=" \t"`; primary/implementation ids overlap | Whitespace identifiers blocked; primary-implementation overlap blocked. |
| Same-excerpt page/window tuple | Add an unselected late `page=4, window=1966-01-01/1988-12-31` excerpt and set the event's `observed_implementation_at` to 1988-02-01 | Blocked because page-3 1966/1967 excerpt does not cover `1988-02-01`; same-page/window tuple in the matching excerpt passes. |
| Two admitted patterns / role discipline (R3) | Replace `observable_pattern=" \t\n"` or `None`; force second record to `secondary_analysis` | Whitespace/missing observable pattern → BLOCKED; demoted secondary record → BLOCKED. |
| Public approval identity | Whitespace-only `approved_by` for an excerpt or `handoff.approved_by` mismatching | BLOCKED. |
| H4A-0 preservation (R5/historical-id) | Real `history/HIST_VNEXT.h4_sources.admission --root . --verify-files`; targeted `tests/test_hist_h4_source_crosswalk.py` | Exit 1 / structural PASS / historical UNIDENTIFIED, 0 approved; 63 H4A-0 tests pass; 0 unrelated regressions. |

## Per-finding disposition (summary)

Round-13 finding (composite-interval bypass): **closed**. All three explicit composite forms rejected at parser, evaluator, audit API, and subprocess CLI; extended composite falsifications (`1968/1968-1985`, `1968-01/1968-1985`, `1966-05/1966-1988`, `1966-12-31/1966-1988`, `1966-1988/1966-12-31`) similarly rejected. Legitimate `1966/1967`, `1966/1966-05`, `1966-05-15/1966-08-30`, and standalone `1968-1985` retained.

R1 legacy-artifact identity contract: **closed** (R1 bijection restored, classification/evidence-kind enforced, missing `legacy_artifact_id` rejected, tampered identity and metadata rejected).

F2 rights/excerpt handling: **closed** (RightsSpec reused, restrictive license needs licence+terms+evidence+check+download).

F3 evidence gates: **closed** (excerpt binds `pdf_pages`, parent hash, content hash, handoff hash, allowed use, full-period coverage; observed implementation must be covered by an excerpt that covers the page).

F4 forcing/actor purposes: **closed**.

F5 required-file structural propagation: **closed** (all seven malformed files yield structural exit 2; missing files exit 2; no traceback leakage).

F6 fabricated SHA: **closed** at intake and crosswalk levels.

R2 shared-root independence: **closed** (direct overlap, cited overlap, same-work, unrooted records all return the expected `False`/`None`).

R3 regression coverage: **closed** at named behavioral level; the new tests assert invariants on parsed grammar and structural exit codes rather than implementation.

R4 OS error handling: **closed** (no traceback; structured `BLOCKED`).

R6 schema/date precision: **closed** (events keep explicit unknown fields, year-only events cannot claim day precision, intake metadata retains publication-year precision and unknown availability).

## Preservation and scope boundaries

- BASELINE.md hash unchanged: `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
- `DATA_MANIFEST_v1.json` hash unchanged: `5d91e014c2b80651eb87d3515147468cb84fe77430bf336ba52e357000e58fdd`. Manifest v2 also unchanged.
- `docs/phases/HIST_VNEXT/H1A/REPORT.md` and `docs/phases/HIST_VNEXT/H1A/REVIEW.md` unchanged from HEAD.
- The only unstaged file in the H1A area is `docs/phases/HIST_VNEXT/H1A/PLAN.md`, whose diff is a 5-line text-only deferral of stale test-count expectations to the H4A-1 evidence, already disclosed in `H1A_REPAIR.md`.

**H1A is an offline admission/crosswalk declaration only.** No runtime wiring, no source acquisition, no historical-input approval, no production initialization or measurement authorization. Real H1A CLI result remains 4 candidates, 0 admitted sources, 0 approved excerpts, 63 blocked anchors. Real H4A-0 CLI result remains 0 approved inputs. The positive software fixture is a contract for the parser/gate, not a historical source.

## Remaining concrete defect

None observed. The round-13 PATCH is closed; the prior closed findings remain closed; no new defect was introduced by the round-13 parser rework. The H1A boundary remains intact and explicitly declared-only/no-runtime/no-historical-input.
