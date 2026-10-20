VERDICT: PATCH

## Observed verification

Read-only audit. BASELINE was read first, followed by the H1A review chain through round 8, repair record, original contract, phase plans/reports/reviews, implementation, tests, declarations, scoped git diff, manifests, benchmark outputs and provenance. No repository files were edited and no data approval was signed.

| Command exercised | Exit | Observed result |
|---|---:|---|
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py` | 0 | **164 passed in 2.82s** |
| `.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py` | 0 | All checks passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .` | 1 | Structural **PASS**, historical **BLOCKED**; 4 candidates, 0 admitted, 63 blocked anchors, 5 blocked authorities, 10 candidate events |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.admission --root . --verify-files` | 1 | Structural **PASS**, historical **UNIDENTIFIED**; 14 candidates: 0 admitted / 11 candidate / 3 blocked; **0 approved inputs** |
| Four read-only Python diagnostic invocations | 0 each | **62 CLI subprocess invocations**, public-API mutations, metadata preservation comparisons, injected manifest-read error and existing-output hashing |
| Git status, log, scoped diffs and HEAD artifact reads | 0 | Existing changes and preservation inspected |

The two real-package exit-1 results are expected historical blocks, not crashes.

## Round-8 finding dispositions

| Requirement | Independently observed disposition |
|---|---|
| **Reject each supplied malformed source identifier independently** | **Closed for all six required cases.** For either `document_number` or `archival_reference`, substituting a list, object or boolean while retaining the valid alternative returned public-API **`blocked`**. Corresponding subprocess CLIs returned structured **exit 2**, without stderr. |
| **Whitespace-only source identifiers are unusable** | **Closed.** Each identifier alone containing `" \t\n"` returned evaluator **`blocked`**, audit API **exit 1**, and subprocess **exit 1 / historical BLOCKED**. Unicode whitespace was independently rejected too. |
| **Whitespace-only event identifiers are unusable** | **Closed.** Both document-only and archive-only whitespace mutations returned audit API and subprocess **exit 1 / historical BLOCKED**. |
| **Valid single-identifier alternatives remain admitted** | **Retained.** Document-only and archive-only sources returned evaluator **`admitted`**. Corresponding source and event fixture packages returned API/subprocess **exit 0**. A valid identifier accompanied by a blank alternative also remained accepted. |

**The positive fixture is a software contract, not historical evidence.** Its successful exit establishes neither a historical observation nor an actual approval.

## Remaining defect and finite prioritized repair

### 1. P1 — Whitespace can still satisfy the independently observable-pattern requirement

**Paths:**

- `history/HIST_VNEXT/sources/admission.py:120–121`
- `history/HIST_VNEXT/sources/admission.py:435–438`
- Regression coverage: `tests/test_hist_source_admission.py:1094–1103`

Both source admission and the historical pattern gate check string truthiness rather than non-whitespace content.

Starting from the positive software fixture, change only:

```python
candidates["records"][0]["observable_pattern"] = " \t\n"
```

Independently observed:

```text
evaluate_source(...) → {"status": "admitted", "reasons": []}
audit_h1a(...)       → exit_code 0 / structural PASS / historical PASS
subprocess CLI      → exit 0 / structural PASS / historical PASS
                       total_admitted 2 / independent_pairs 1
                       empty stderr
```

The mutated record supplies **no observable claim**. Root independence alone does not satisfy original H1A §3’s requirement for two independent, admitted observable patterns with specific descriptions. The existing regression covers `None`, which blocks correctly, but not an entirely blank description.

This does not require semantic interpretation of prose: rejecting whitespace-only content is a bounded missing-evidence check.

**Required repair:**

1. Require non-whitespace `observable_pattern` content in the evaluator and historical pattern predicate.
2. Add isolated public-API and subprocess regressions for whitespace-only descriptions, exercising either source record. Require source non-admission and a structured historical block; retain the meaningful positive fixture.

## Earlier finding rechecks

| Finding | Observed disposition |
|---|---|
| **Anchor bijection/geography/evidence kind** | Current rows cover 63 distinct legacy artifacts with zero mismatches. Swapped geography, forged direct evidence, changed SHA, duplicate coverage and omitted coverage were rejected. |
| **Classification sufficiency** | Actual unresolved rows relabelled only `proxy` or `synthetic` were rejected. All real rows remain blocked with false runtime flags. |
| **Rights/excerpt handoff/pages/full period** | Evidence-free restricted rights, stale handoff hash, wrong parent hash, page 99 and missing page count blocked. Known availability did not bypass content declared through 1988. |
| **Forcing/actor rejection** | Both purpose mutations blocked. |
| **Shared roots** | Distinct rooted works returned `True`; same work, direct overlap and cited overlap returned `False`; unknown cited roots and unrooted records returned `None`. |
| **Duplicate IDs** | Duplicate source, event and excerpt IDs each returned structured exit 2. |
| **Nested structural errors** | Exercised malformed source type/purpose/work-ID/excerpt-ID, excerpt use, anchor variable/support, authority evidence and manifest evidence-status containers returned structured exit 2. Null authority implementation evidence returned a structured historical block. |
| **Required-file errors** | Malformed JSON in all seven required files returned structured exit 2. An injected manifest-read `OSError` returned structured exit 2. |
| **Date precision** | Year-only date claiming day precision blocked; current declarations preserve supported precision and explicit unknowns. |
| **Event document-or-archive** | Both valid single-identifier alternatives passed; neither identifier blocked; whitespace identifiers blocked. |
| **Authority evidence disjointness** | Partial primary/implementation overlap blocked. Missing issuer and unapproved event page also blocked. |
| **Same-excerpt page/window tuple** | Split page-3/1966–67 and page-4/1966–1988 authorization could not support page-3/1988. An unselected late excerpt did not authorize it. A selected matching page-4/1988 tuple passed the software fixture. |
| **Two admitted patterns** | Catalogue substitution, missing pattern and shared-root mutations prevented historical PASS. Empty authority coverage blocked. |
| **H4A-0 preservation** | All 63 embedded legacy snapshots match H1A. Header and every row outside `legacy_record` are unchanged from HEAD; all three approval sets remain empty. |

## Preservation, provenance and scope boundaries

- BASELINE matches HEAD and frozen SHA256  
  `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
- `DATA_MANIFEST_v1.json` matches HEAD and frozen SHA256  
  `5d91e014c2b80651eb87d3515147468cb84fe77430bf336ba52e357000e58fdd`. Manifest v2 also matches HEAD.
- All four candidate paths, hashes and page counts agree with intake metadata. This is metadata consistency, not independent historical authentication.
- All **18 manifest-listed outputs per arm** in existing `C0_review4` and `C1_review4` were independently hashed with zero mismatches. Their manifests declare 16 commodities, 116 completed ticks and the frozen replay digests. No new simulation was run and replay identity was not independently recomputed.
- Existing smoke/scaling benchmark artifacts were inspected as performance/replay evidence, **not independent stochastic historical replicates**.

**H1A remains offline and declaration-only: no runtime wiring, no historical-input approval, and no production initialization or measurement authorization.** Actual declarations remain four candidates, zero admitted sources, zero approved excerpts and 63 blocked anchors.

No matching production consumer was found in `src/`. No observed state update, target injection, quarterly interpolation, single-good substitution or LLM-probability interpretation is introduced by this repair. Broader accounting/material-balance correctness and stochastic independence were not re-certified.

No restricted PDF/OCR text, mixed-year XLS contents or historical target values were displayed. The required H4 `--verify-files` audit performed its file verification. Prior exposure remains disclosed; blindness is not restored.

No full-suite run, fresh benchmark, source acquisition or strict full-file-byte-gate closure was performed.
