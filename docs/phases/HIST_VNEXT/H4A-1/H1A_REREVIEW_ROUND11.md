VERDICT: PATCH

## Observed verification

Read-only audit. BASELINE was read first, followed by the H1A review chain through round 10, H1A and H4A-1 phase documents, original source contract, implementation, tests, declarations, git diff, manifests, benchmark outputs and provenance. No repository files were edited and no data approval was signed.

| Command exercised | Exit | Observed result |
|---|---:|---|
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py` | 0 | **176 passed in 3.65s** |
| `.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py` | 0 | All checks passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .` | 1 | Structural **PASS**, historical **BLOCKED**; 4 candidates, 0 admitted, 63 blocked anchors, 5 blocked authorities, 10 candidate events |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.admission --root . --verify-files` | 1 | Structural **PASS**, historical **UNIDENTIFIED**; 14 candidates: 0 admitted / 11 candidate / 3 blocked; **0 approved inputs** |
| Corrected public-API/whitespace diagnostic using `.venv/bin/python -c …` | 0 | 24 direct evaluator negatives; 85 audit-API/subprocess cases |
| Earlier-invariant diagnostic using `.venv/bin/python -c …` | 0 | 44 CLI subprocess cases, seven actual-crosswalk rejection mutations, six shared-root cases and injected manifest-read error |
| Metadata/output-hash diagnostic using `.venv/bin/python -c …` | 0 | Preservation results below |
| Isolated authority-coverage reproduction using `.venv/bin/python -c …` | 0 | Six inputs falsely returned API/subprocess **exit 0 / historical PASS** |

Both real-package exit-1 results are expected historical blocks, not crashes. An initial custom diagnostic exited 1 because its harness targeted `id` instead of `excerpt_id`; that harness error was corrected and is not evidence of a repository defect.

## Round-10 repair dispositions

| Requirement | Independently observed disposition |
|---|---|
| **Blank source/work IDs rejected by public evaluator** | **Closed.** Empty strings, ASCII whitespace and Unicode whitespace returned `blocked`, including matching blank source IDs in source and excerpt. Corresponding audit/subprocess inputs returned structured exit 2. |
| **Blank selected excerpt IDs rejected** | **Closed.** Matching blank selection and excerpt identities returned evaluator `blocked` and structured audit/subprocess exit 2. |
| **Blank excerpt IDs/source IDs rejected** | **Closed.** Independently blanking either field prevented admission. |
| **Blank excerpt/handoff approval identities rejected, even when equal** | **Closed.** Blanking either side individually, or both together, prevented admission. |
| **Valid positives retained** | **Retained.** The unmodified positive package returned audit/subprocess exit 0. Valid document-only and archive-only alternatives remained admitted, including direct evaluator checks. |
| **Broad whitespace rejection in source/event/excerpt/handoff/anchor/manifest gates** | **Closed for exercised fields.** Blank rights evidence, observable claims, hashes, page ranges, dates, institutional fields, authorization fields, anchor provenance/boundary/transformation fields and initial-state manifest scalars did not pass. **The adjacent authority-coverage gate still accepts blank institutional identity and period; repair below.** |

**The positive fixture is a software contract, not historical evidence.** Its successful exit establishes neither a real source nor an actual approval.

## Remaining defect and finite prioritized repair

### 1. P1 — An unnamed or undated authority declaration still clears historical coverage

**Paths:**

- `history/HIST_VNEXT/sources/admission.py:624–634` — `_validate_authority_records` validates evidence-ID containers and status, but not `authority` or `period`.
- `history/HIST_VNEXT/sources/admission.py:1250–1278` — `_coverage_ok` uses the authority name only as a diagnostic label and does not check its period.
- Regression coverage: `tests/test_hist_source_admission.py:327–339,1032–1050,1140–1150`.

Starting independently from the positive software fixture, either mutation returns:

```python
data["authorities"][0]["authority"] = " \t\n"
```

```python
data["authorities"][0]["period"] = " \t\n"
```

**Observed for each:** audit API **exit_code 0 / structural PASS / historical PASS**; subprocess CLI **exit 0 / structural PASS / historical PASS**, empty stderr. Empty strings and Unicode whitespace also passed—six isolated reproductions in total.

This is not a formatting concern. The gate asserts verified institutional coverage without identifying **what authority** is covered or **which institutional period** the claim concerns. Original H1A §3, `HIST_VNEXT_H1A_PLAN.md:75–77`, expressly requires authority-by-authority, period-specific coverage. Valid event references do not supply a missing coverage declaration.

**Required bounded repair:**

1. Reject blank `authority` and `period` values before a coverage row can satisfy historical readiness. Explicit unknowns may remain in blocked candidate declarations, but must not become covered merely because event references are valid.
2. Add isolated audit-API and subprocess regressions for both fields, covering empty, ASCII-whitespace and Unicode-whitespace values. Assert a structured nonzero result and no traceback; preserve the meaningful positive fixture.
3. Record the repair and exercised evidence in `docs/phases/HIST_VNEXT/H4A-1/H1A_REPAIR.md`, preserving prior independent reviews.

No runtime change, source acquisition or data approval is required.

## Earlier finding rechecks

| Finding | Observed disposition |
|---|---|
| **Anchor bijection/classification/geography/evidence kind** | All 63 real rows match authoritative legacy metadata. Swapped geography, forged direct evidence, changed hash, duplicate/omitted coverage and unresolved proxy/synthetic relabelling were rejected. |
| **Rights/excerpt handoff/pages/full period** | Evidence-free restricted rights, stale handoff content hash, wrong parent hash, page 99 and missing page count blocked. Known availability did not bypass checking content through 1988. |
| **Shared roots** | Distinct rooted works returned `True`; same work, direct overlap and cited overlap returned `False`; unknown citations and unrooted records returned `None`. |
| **Duplicate IDs/nested structural errors** | Duplicate source/event/excerpt IDs and exercised malformed nested containers returned structured exit 2. Null authority implementation evidence returned a structured historical block. |
| **Required-file errors** | Malformed JSON in all seven required files returned structured subprocess exit 2. Injected manifest-read `OSError` returned audit API exit 2. |
| **Date precision/event document-or-archive** | Year-only date claiming day precision blocked. Either legitimate event identifier alone passed; neither identifier blocked. |
| **Authority evidence disjointness** | Partial primary/implementation overlap blocked. Evidence-set separation remains enforced; the distinct blank coverage-description defect is above. |
| **Same-excerpt page/window tuple** | Split page-3/1966–67 and page-4/1966–1988 permissions did not authorize page-3/1988. An unselected late excerpt did not authorize it. A selected matching page-4/1988 tuple passed. |
| **Two admitted patterns/role discipline** | Catalogue substitution, missing pattern, shared root and empty authority coverage prevented historical PASS. Forcing and actor purposes blocked. |
| **H4A-0 preservation** | All 63 embedded snapshots match H1A. H4’s header and every row field outside `legacy_record` match HEAD; all three approval sets remain empty. |

## Preservation and scope boundaries

- BASELINE matches HEAD and frozen SHA256 `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
- `DATA_MANIFEST_v1.json` matches HEAD and frozen SHA256 `5d91e014c2b80651eb87d3515147468cb84fe77430bf336ba52e357000e58fdd`. Manifest v2 also matches HEAD.
- All four batch-01 candidate paths, hashes and page counts match intake metadata. This is metadata consistency, not historical authentication.
- All **18 manifest-listed outputs per arm** in existing `C0_review4` and `C1_review4` were independently hashed with zero mismatches. Their manifests declare 16 commodities, 116 completed ticks and the frozen digests. No new simulation or replay-identity recomputation was performed.
- Existing benchmark repeats were inspected as performance/replay evidence, **not independent stochastic historical replicates**.

**H1A remains offline and declaration-only: no runtime wiring, no historical-input admission or approval, and no production initialization or measurement authorization.** Actual H1A declarations remain four candidates, zero admitted sources, zero approved excerpts and 63 blocked anchors.

No matching production consumer was found in `src/`. The reviewed module introduces no observed target injection, state update, quarterly interpolation, single-good substitution or LLM-probability interpretation. Broader accounting/material-balance correctness and stochastic independence were not re-certified.

Restricted PDF/OCR text, mixed-year XLS contents and historical target values were not displayed. Prior exposure remains disclosed; blindness is not restored. No full-suite run, fresh benchmark, source acquisition or strict full-file-byte-gate closure was performed.
