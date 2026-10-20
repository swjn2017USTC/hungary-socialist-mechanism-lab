VERDICT: PATCH

## Observed verification

Read-only audit. BASELINE was read first, followed by the review chain through round 9, repair record, original H1A contract, phase plans/reports/review, implementation, tests, declarations, scoped git diff, manifests, benchmark outputs and provenance. No repository files were edited and no data approval was signed.

| Command exercised | Exit | Observed result |
|---|---:|---|
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py` | 0 | **172 passed in 3.51s** |
| `.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py` | 0 | All checks passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .` | 1 | Structural **PASS**, historical **BLOCKED**; 4 candidates, 0 admitted, 63 blocked anchors, 5 blocked authorities, 10 candidate events |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.admission --root . --verify-files` | 1 | Structural **PASS**, historical **UNIDENTIFIED**; 14 candidates: 0 admitted / 11 candidate / 3 blocked; **0 approved inputs** |
| Four read-only `.venv/bin/python -c …` diagnostic invocations | 0 each | Public-API falsification, actual CLI subprocess mutations against temporary fixtures, metadata/output hashing and isolated gate checks |
| Git status/log, scoped diff and HEAD artifact reads | 0 | Existing changes and preservation inspected |

Both real-package exit-1 results are expected historical blocks, not crashes.

## Round-9 repair dispositions

| Requirement | Independently observed disposition |
|---|---|
| **Non-whitespace `observable_pattern` in evaluator** | **Closed.** ASCII whitespace and Unicode whitespace returned `blocked`. |
| **Non-whitespace pattern in historical gate** | **Closed independently.** Either fixture source’s blank pattern produced audit API/subprocess **exit 1 / historical BLOCKED**. With the evaluator temporarily mocked to admit both records, the historical gate still blocked the blank pattern. |
| **Source/work/event identifiers** | **Audit/CLI repaired; public evaluator incomplete.** Blank source/work/event IDs returned structured exit 2. The evaluator still admits supplied blank identities in the cases below. |
| **Rights evidence** | **Closed for exercised fields.** Blank licence name, terms locator, evidence quote and check date blocked through evaluator, audit API and subprocess. |
| **Excerpt/handoff evidence** | **Audit/CLI repaired; public evaluator incomplete.** Blank excerpt and handoff scalars returned structured exit 2, but matching blank approval identities and excerpt identifiers remain admitted by the evaluator. |
| **Anchor evidence and boundary text** | **Closed for exercised audit inputs.** Blank blocked-row `missing_evidence`, proxy transformation, source-boundary text and desired-boundary text each returned structured exit 2. |
| **Event institutional evidence** | **Closed.** Blank issuer, legal force, reviewer, source and implementation identifiers blocked historically; whitespace-only granted authority returned structured exit 2. |
| **Initial-state manifest scalars** | **Closed for exercised audit inputs.** Whitespace substitutions for artifact/variable/source ID, hash, path, grade, evidence status, observation date, initial date and role each returned structured exit 2. |

**The positive fixture is a software contract, not historical evidence.** Its successful exit does not establish an actual source, observation or approval.

## Remaining defect and finite prioritized repair

### 1. P1 — Public source admission still accepts blank identifiers and approval evidence

**Paths:**

- `history/HIST_VNEXT/sources/admission.py:60–148` — public evaluator does not apply source/work identity validation.
- `history/HIST_VNEXT/sources/admission.py:126` — selected excerpt IDs use truthiness.
- `history/HIST_VNEXT/sources/admission.py:763–784` — excerpt presence and approval identity use truthiness.
- `history/HIST_VNEXT/sources/admission.py:854–864` — handoff presence/equality permits matching whitespace.
- Regression coverage: `tests/test_hist_source_admission.py`.

Starting independently from `_primary_record()` and `_excerpt()`, all four inputs returned:

```text
evaluate_source(...) → {"status": "admitted", "reasons": []}
```

| Failing input | Change |
|---|---|
| Blank work identity | `record["work_id"] = " \t\n"` |
| Blank matching source identities | Set both `record["source_id"]` and `excerpt["source_id"]` to `" \t\n"` |
| Blank selected excerpt identity | Set `record["approved_excerpt_ids"] = [" \t\n"]` and `excerpt["excerpt_id"] = " \t\n"` |
| Blank matching approval identities | Set both `excerpt["approved_by"]` and `excerpt["handoff"]["approved_by"]` to `" \t\n"` |

The corresponding temporary packages returned **audit API exit 2 and subprocess CLI exit 2**, with empty stderr. Thus the file-audit path fails closed, but the public admission API does not. Equality between blank declarations is not evidence of an identified source, excerpt or approver.

Minimal reproduction, executed using the existing test helpers:

```python
import runpy
from history.HIST_VNEXT.sources.admission import evaluate_source

h = runpy.run_path("tests/test_hist_source_admission.py")
record = h["_primary_record"]()
excerpt = h["_excerpt"]()

excerpt["approved_by"] = " \t\n"
excerpt["handoff"]["approved_by"] = " \t\n"

print(evaluate_source(record, approved_excerpts=[excerpt]))
# Observed: {'status': 'admitted', 'reasons': []}
```

**Required repair:**

1. Apply non-whitespace identity/evidence checks at the public evaluator boundary—not only inside `audit_h1a`’s structural validators. Reject supplied blank work IDs, blank source/excerpt identities and blank excerpt/handoff approval identities.
2. Add direct evaluator regressions for all four inputs, alongside subprocess regressions preserving structured rejection. Retain meaningful positive fixtures and legitimate document-number-or-archive alternatives.
3. Append the actual repair evidence to `docs/phases/HIST_VNEXT/H4A-1/H1A_REPAIR.md`; preserve historical review records.

No runtime change, historical source acquisition or data approval is needed for this repair.

## Earlier closed findings rechecked

| Finding | Observed disposition |
|---|---|
| **Anchor bijection/classification/geography/evidence kind** | All 63 real rows match legacy metadata. Swapped geography, forged direct declaration, changed hash, duplicate/omitted coverage and unresolved proxy/synthetic relabelling were rejected. |
| **Rights/excerpt provenance/pages/full period** | Evidence-free restricted rights, stale handoff hash, wrong parent hash, page 99 and missing page count blocked. Known availability did not bypass content coverage through 1988. |
| **Shared roots** | Distinct rooted works returned `True`; same work, direct overlap and cited overlap returned `False`; unknown citations and unrooted records returned `None`. |
| **Duplicate IDs/nested errors** | Duplicate source/event/excerpt IDs and exercised malformed nested containers returned structured exit 2. Null authority implementation evidence returned a structured historical block. |
| **Required-file errors** | Malformed JSON in all seven required files returned structured subprocess exit 2. Injected manifest-read `OSError` returned audit API exit 2. |
| **Date precision/document-or-archive** | Year-only date claiming day precision blocked. Either valid event identifier alone passed the software fixture; neither identifier blocked. |
| **Authority evidence disjointness** | Partial primary/implementation overlap blocked. |
| **Same-excerpt page/window tuple** | Split page-3/1966–67 and page-4/1966–1988 authorization could not authorize page-3/1988. An unselected late excerpt did not authorize it; a selected matching page-4/1988 tuple passed. |
| **Two admitted patterns/role discipline** | Catalogue substitution, missing pattern, shared root and empty coverage prevented historical PASS. Forcing and actor purposes blocked. |
| **H4A-0 preservation** | All 63 embedded snapshots match H1A. Header and every row field outside `legacy_record` are unchanged from HEAD; all three approval sets remain empty. |

## Preservation and scope boundaries

- BASELINE matches HEAD and frozen SHA256 `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
- `DATA_MANIFEST_v1.json` matches HEAD and frozen SHA256 `5d91e014c2b80651eb87d3515147468cb84fe77430bf336ba52e357000e58fdd`. Manifest v2 also matches HEAD.
- All four batch-01 candidate paths, hashes and page counts match intake metadata. This is metadata consistency, not historical authentication.
- All **18 manifest-listed outputs per arm** in existing `C0_review4` and `C1_review4` were independently hashed with zero mismatches. Their manifests declare 16 commodities, 116 completed ticks and the frozen digests. No simulation or replay-identity recomputation was performed.
- Existing benchmark repeats were inspected as performance/replay evidence, not independent stochastic historical replicates.

**H1A remains offline and declaration-only: no runtime wiring, no historical-input admission or approval, and no production initialization or measurement authorization.** Actual H1A declarations remain four candidates, zero admitted sources, zero approved excerpts and 63 blocked anchors.

No matching production consumer was found in `src/`. No observed target injection, state update, quarterly interpolation, single-good substitution or LLM-probability interpretation is introduced by this repair. Broader accounting/material balance and stochastic independence were not re-certified.

Restricted PDF/OCR text, mixed-year XLS contents and historical target values were not displayed. Prior exposure remains disclosed; blindness is not restored. No full-suite run, fresh benchmark, source acquisition or strict full-file-byte-gate closure was performed.
