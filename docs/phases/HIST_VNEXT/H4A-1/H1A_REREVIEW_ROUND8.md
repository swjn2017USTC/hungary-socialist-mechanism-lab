VERDICT: PATCH

## Observed verification

Read-only audit. BASELINE was read first, followed by the complete H1A review chain through round 7, repair record, original H1A contract, phase plans/reports/review, current implementation, tests, declarations, git diff, manifests, benchmark outputs and provenance. No repository files were edited and no data approval was signed.

| Command exercised | Exit | Observed result |
|---|---:|---|
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py` | 0 | **153 passed in 2.50s** |
| `.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py` | 0 | All checks passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .` | 1 | Structural **PASS**, historical **BLOCKED**; 4 candidates, 0 admitted, 63 blocked anchors, 5 blocked authorities, 10 candidate events |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.admission --root . --verify-files` | 1 | Structural **PASS**, historical **UNIDENTIFIED**; 14 candidates: 0 admitted / 11 candidate / 3 blocked; **0 approved inputs** |
| Five read-only Python diagnostic invocations | 0 each | **56 CLI subprocess invocations**, public-API mutations, metadata comparisons, injected manifest-read error and existing-output hashing |
| Git status/log, scoped diffs and HEAD artifact reads | 0 | Existing changes inspected; preservation results below |

The two real-package exit-1 results are expected historical blocks, not technical crashes.

## Round-7 repair disposition

| Requirement | Independently observed disposition |
|---|---|
| Source identifiers structurally strings/null | **Closed for exercised types.** List, object and boolean values in **either** `document_number` or `archival_reference` returned CLI **exit 2**, valid JSON and empty stderr, including when the other identifier remained valid. |
| Three originally reported subprocess cases | **Closed.** List-valued document number, object-valued archive and boolean document number, each with the alternative null, returned structured **exit 2**, without traceback. |
| At least one usable string identifier | **Partially closed.** Null/null and empty-string/empty-string block. Whitespace-only strings still admit the source and clear the fixture’s historical gate: repair 2. |
| Public evaluator fails closed for malformed identifiers | **Not closed.** The original three cases block when no valid alternative remains, but malformed identifiers are accepted when the other field is valid: repair 1. |
| Valid single-identifier positives | **Retained.** Document-only and archive-only sources each returned API `admitted` and software-fixture CLI **exit 0**. |

**The positive fixture is a software contract, not historical evidence.** Its successful result establishes neither a historical observation nor an actual approval.

## Finite prioritized repair list

### 1. P1 — Make the public evaluator reject every supplied malformed identifier

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:98–103`  
`tests/test_hist_source_admission.py:1222–1241`

The CLI’s structural validator rejects malformed identifier fields, but the public evaluator checks only whether **either** field is a usable string. It therefore ignores a malformed field whenever the alternative remains valid.

Independently observed for **both fields**, substituting each of a list, object and boolean while retaining the fixture’s valid alternative:

```text
evaluate_source(...) → {"status": "admitted", "reasons": []}
CLI                  → exit 2 / structural BLOCKED
```

Minimal reproduction:

```python
import runpy
from history.HIST_VNEXT.sources.admission import evaluate_source

h = runpy.run_path("tests/test_hist_source_admission.py")
record = h["_primary_record"]()
record["document_number"] = ["41/1966"]
# archival_reference remains a valid string.

print(evaluate_source(record, approved_excerpts=[h["_excerpt"]()]))
# Observed: {'status': 'admitted', 'reasons': []}
```

This directly fails the round-7 requirement that the **public evaluator also fails closed for malformed identifiers**. The new subprocess regression exercises the structural path, not this API boundary.

**Required repair:** Independently reject each supplied identifier that is neither a string nor null before applying the document-number-or-archive alternative. Add direct public-API regressions for both fields with a valid alternative, covering list/object/boolean inputs. Preserve valid single-identifier admission.

### 2. P1 — Do not treat whitespace as usable source or event identification

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:100–103,1272–1273`  
`tests/test_hist_source_admission.py`

The source evaluator uses `bool(value)` rather than checking for non-whitespace content. Event identification likewise uses truthiness.

Each source mutation below independently returned API `admitted` and subprocess **exit 0 / structural PASS / historical PASS**:

```python
{"document_number": " \t\n", "archival_reference": None}
{"document_number": None, "archival_reference": " \t\n"}
```

Separately, this event mutation returned subprocess **exit 0 / historical PASS**:

```python
events["events"][0].update(
    document_number=" \t",
    archival_reference=None,
)
```

These records contain no usable document number or archival reference. This is an identifier-evidence defect, not a formatting preference.

**Required repair:** Require at least one string with non-whitespace content for source and verified-event identification. Keep blank strings as missing evidence rather than inventing identifiers. Add isolated API and CLI negatives for both source identifier alternatives and the corresponding event gate.

### Subprocess reproduction

Run with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python`. Writes are confined to a temporary software fixture:

```python
import json
import runpy
import tempfile
from pathlib import Path

h = runpy.run_path("tests/test_hist_source_admission.py")

with tempfile.TemporaryDirectory() as tmp:
    root = h["repo_root"].__wrapped__(Path(tmp))
    h["positive_repo"].__wrapped__(root)

    path = root / "history/HIST_VNEXT/sources/batch01_candidates.json"
    data = json.loads(path.read_text())
    data["records"][0].update(
        document_number=" \t\n",
        archival_reference=None,
    )
    path.write_text(json.dumps(data))

    completed = h["_run_cli"](root)
    print(completed.returncode, completed.stdout, completed.stderr)
    # Observed: exit 0, structural PASS, historical PASS, empty stderr.
```

## Earlier finding rechecks

| Finding | Observed disposition |
|---|---|
| **Anchor bijection/geography/evidence kind** | Current rows cover **63 distinct legacy artifacts**, with zero mismatches across variable, source, SHA, path, grade, evidence status and dates. Swapped geography, forged direct evidence, changed SHA, duplicate coverage and omitted coverage were rejected. |
| **Classification sufficiency** | Actual unresolved rows relabelled only `proxy` or `synthetic` were rejected. All real rows remain blocked, with false runtime flags. |
| **Rights/excerpt handoff/pages/full period** | Evidence-free restricted rights, stale handoff hash, wrong parent hash, page 99 and missing page count blocked. Known availability did not bypass authorization of content declared through 1988. |
| **Forcing/actor rejection** | Both purpose mutations blocked. |
| **Shared roots** | Distinct rooted works returned `True`; same work, direct overlap and cited overlap returned `False`; unknown cited roots and unrooted records returned `None`. |
| **Duplicate IDs** | Duplicate source, event and excerpt IDs each returned structured exit 2. |
| **Nested structural errors** | Exercised malformed source type/purpose/work-ID/excerpt-ID, excerpt use, anchor variable/support, authority evidence and manifest evidence-status containers returned structured exit 2. Null authority implementation evidence returned a structured historical block. |
| **Required-file errors** | Malformed JSON in all seven required files returned structured exit 2. An injected manifest-read `OSError` also returned structured exit 2. |
| **Date precision** | Year-only date claiming day precision blocked; current declarations preserve supported precision and explicit unknowns. |
| **Event document-or-archive** | Both valid single-identifier alternatives passed; neither identifier blocked. Whitespace remains defective as described above. |
| **Authority evidence disjointness** | Partial primary/implementation overlap blocked. Missing issuer and unapproved event page also blocked. |
| **Same-excerpt page/window tuple** | Split page-3/1966–67 and page-4/1966–1988 authorization could not support page-3/1988, including a spanning observation range. An unselected late excerpt did not authorize it. A selected matching page-4/1988 tuple passed the software fixture. |
| **Two admitted patterns** | Catalogue substitution, missing pattern and shared-root mutations prevented historical PASS. Empty authority coverage blocked. |
| **H4A-0 preservation** | All 63 embedded legacy snapshots match H1A. H4’s header and every row field outside `legacy_record` are unchanged from HEAD; all three approval sets remain empty. |

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
