VERDICT: PATCH

## Observed verification

Read-only audit. BASELINE was read first, followed by the complete H1A rereview chain through round 6, repair record, original H1A contract, phase plans/reports/review, implementation, tests, declarations, git diff, manifests, benchmark outputs and provenance. No repository files were edited and no data approval was signed.

| Command exercised | Exit | Observed result |
|---|---:|---|
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py` | 0 | **150 passed in 2.08s** |
| `.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py` | 0 | All checks passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .` | 1 | Structural **PASS**, historical **BLOCKED**; 4 candidates, 0 admitted, 63 blocked anchors, 5 blocked authorities, 10 candidate events |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.admission --root . --verify-files` | 1 | Structural **PASS**, historical **UNIDENTIFIED**; 14 candidates: 0 admitted / 11 candidate / 3 blocked; **0 approved inputs** |
| Five read-only Python diagnostic invocations | 0 each | **97 H1A CLI subprocess invocations**, plus API, metadata and output-hash checks; individual results below |
| Git status/log and scoped diff inspection | 0 | Existing changes inspected; no BASELINE change |

The two real-package exit-1 results are expected historical blocks, not crashes.

## Round-6 repair dispositions

### 1. Same-excerpt page/window authorization — closed

The current implementation retains excerpt-level page/window tuples in `history/HIST_VNEXT/sources/admission.py:368–392`. The final predicate at `:1290–1296` requires **one tuple** to cover the cited page and both bounds of the observed-implementation range.

Independently exercised through CLI subprocesses:

| Software-fixture input | Exit | Result |
|---|---:|---|
| Unmodified positive fixture | 0 | Structural PASS / historical PASS |
| Only `observed_implementation_at="1988-02-01"` | 1 | Historical BLOCKED |
| Selected page-3 excerpt authorized for 1966–67, plus selected page-4 excerpt authorized through 1988; event cites **page 3 / February 1988** | 1 | Historical BLOCKED |
| Same split authorization, observed range `1967-01-01/1988-02-01`, still citing page 3 | 1 | Historical BLOCKED |
| Late excerpt exists but is **not selected** by the source | 1 | Historical BLOCKED |
| Selected page-4 excerpt covers the event’s **page 4 / February 1988** combination | 0 | Software contract accepted |

These results distinguish legitimate same-tuple authorization from the former cross-excerpt combination.

**The positive fixture is a software contract, not historical evidence.** Its successful result establishes neither a real historical observation nor an actual approval.

### 2. Manifest evidence-status container — closed

The exact mutation:

```python
manifest["artifacts"][0]["evidence_status"] = ["literature_proxy"]
```

returned **CLI exit 2**, valid JSON, empty stderr and:

```text
anchor_crosswalk validation error: legacy artifact
'p05_census2011_dwelling_00_orszagos':
evidence_status must be a string
```

The guard at `history/HIST_VNEXT/sources/admission.py:1120–1124` now precedes the dictionary lookup.

Additional independent manifest mutations replaced each of these fields with a list, object, null, boolean and integer:

```text
evidence_status, artifact_id, variable_id, source_id, sha256,
path, grade, observation_at, initial_at, role
```

All **50 cases** returned structured exit 2 without traceback. No remaining manifest-scalar crash was found in these exercised lookup/comparison paths.

## Earlier finding rechecks

| Finding | Observed disposition |
|---|---|
| **Anchor bijection, geography and evidence kind** | Current rows cover 63 distinct legacy artifacts with zero metadata mismatches. Swapped national/regional identity, forged direct evidence, changed SHA, duplicate legacy coverage and omitted coverage were rejected. |
| **Classification sufficiency** | Actual unresolved rows relabelled only `proxy` or `synthetic` were rejected. The current real rows remain blocked, with false runtime flags. |
| **Rights / excerpt handoff / pages / full period** | Evidence-free restricted rights, stale handoff content hash, parent-hash mismatch, missing page count and page 99 were blocked. Known availability did not bypass authorization of content declared through 1988. |
| **Forcing / actor rejection** | Both purpose mutations were blocked. |
| **Shared roots** | Distinct rooted works returned `True`; same work, direct overlap and cross-work cited overlap returned `False`; unknown cited roots and unrooted records returned `None`. |
| **Duplicate identities** | Duplicate source, event and excerpt IDs each returned structured exit 2. |
| **Previously named nested errors** | Malformed source type/purpose/work-ID/excerpt-ID lists, excerpt use, anchor scalar/support fields and authority evidence containers returned structured exit 2. Null implementation evidence returned a structured historical block. **Source document/archive identifier types remain insufficiently validated; repair below.** |
| **Required-file failures** | Malformed JSON in all seven required files returned structured CLI exit 2. An injected manifest-read `OSError` returned structured exit 2. |
| **Date precision** | Year-only event date claiming day precision blocked. Current declarations retain supported precision and explicit unknowns. |
| **Event document-number OR archive** | Either valid event identifier alone preserved software-fixture exit 0; removing both blocked. The corresponding **source-level scalar validation** remains defective. |
| **Authority evidence disjointness** | Partial primary/implementation overlap returned historical BLOCKED. Missing institutional fields and unapproved event pages also blocked. |
| **Two admitted observable patterns** | Catalogue substitution, missing pattern and shared-root mutations each prevented historical PASS. Empty authority coverage blocked. |
| **H4A-0 preservation** | All 63 embedded legacy snapshots match H1A. Header and every row field outside `legacy_record` are unchanged from HEAD. All three approval sets remain empty. |

## Finite prioritized repair list

### 1. P1 — Reject malformed source document/archive identifiers instead of treating truthiness as identification

**Paths:**

- `history/HIST_VNEXT/sources/admission.py:95–98`
- `history/HIST_VNEXT/sources/admission.py:523–552`
- `tests/test_hist_source_admission.py`

**Contract:** `HIST_VNEXT_H1A_PLAN.md:63` requires structural failures to return exit 2. Section 3 at `:73` requires a verifiable document number or archival reference for institutional sources.

The source evaluator checks only truthiness:

```python
if not record.get("document_number") and not record.get("archival_reference"):
```

The candidate structural validator does not validate either identifier’s scalar type. Consequently a primary source with **no usable scalar identifier** is admitted.

Starting independently from a fresh positive fixture, each mutation below returned **CLI exit 0 / structural PASS / historical PASS**, with **two admitted sources** and empty stderr:

| First source mutation | Observed exit |
|---|---:|
| `document_number=["41/1966"]`, `archival_reference=None` | 0 |
| `document_number=None`, `archival_reference={"archive":"A"}` | 0 |
| `document_number=True`, `archival_reference=None` | 0 |

This is not merely an unhelpful error message: malformed identification clears source admission and the historical gate.

**Required repair:**

1. Validate supplied source `document_number` and `archival_reference` as strings or explicit unknowns before semantic evaluation; reject list/object/boolean identifiers structurally.
2. Require at least one usable, non-empty string identifier for primary admission, preserving the legitimate document-number **or** archive alternative.
3. Make the public evaluator fail closed for these malformed identifiers as well.
4. Add subprocess regressions for the three observed inputs, requiring exit 2, valid JSON and no traceback; retain valid single-identifier positive tests.

**Reproduction:** Run with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python`; writes are confined to temporary fixtures:

```python
import json
import runpy
import tempfile
from pathlib import Path

h = runpy.run_path("tests/test_hist_source_admission.py")

for mutation in (
    {"document_number": ["41/1966"], "archival_reference": None},
    {"document_number": None, "archival_reference": {"archive": "A"}},
    {"document_number": True, "archival_reference": None},
):
    with tempfile.TemporaryDirectory() as tmp:
        root = h["repo_root"].__wrapped__(Path(tmp))
        h["positive_repo"].__wrapped__(root)

        path = root / "history/HIST_VNEXT/sources/batch01_candidates.json"
        data = json.loads(path.read_text())
        data["records"][0].update(mutation)
        path.write_text(json.dumps(data))

        completed = h["_run_cli"](root)
        result = json.loads(completed.stdout)
        print(
            mutation,
            completed.returncode,
            result["structural"],
            result["historical"],
            result["summary"].get("total_admitted"),
            repr(completed.stderr),
        )
```

## Preservation, provenance and scope boundaries

Independently observed:

- BASELINE matches HEAD and frozen SHA256  
  `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
- `DATA_MANIFEST_v1.json` matches HEAD and frozen SHA256  
  `5d91e014c2b80651eb87d3515147468cb84fe77430bf336ba52e357000e58fdd`. Manifest v2 also matches HEAD.
- All four batch-01 candidate paths, hashes and page counts agree with intake metadata. This is metadata consistency, not independent historical authentication.
- All **18 manifest-listed outputs per arm** in existing `C0_review4` and `C1_review4` were independently hashed with zero mismatches. Their manifests declare 16 commodities, 116 completed ticks and the frozen replay digests. No new simulation was run and replay identity was not independently recomputed.
- Existing benchmark repeats were inspected as performance/replay evidence, **not independent stochastic historical replicates**.

**H1A remains offline and declaration-only: no runtime wiring, no historical-input approval, and no production initialization or measurement authorization.** Actual declarations remain four candidates, zero admitted sources, zero approved excerpts and 63 blocked anchors.

No matching production consumer of the reviewed declarations was found in `src/`. The reviewed repair introduces no observed state update, target injection, quarterly interpolation, single-good substitution or LLM-probability interpretation. Broader accounting/material-balance correctness and stochastic independence were not re-certified.

No restricted PDF/OCR text, mixed-year XLS contents or historical target values were displayed to this reviewer. The required H4 `--verify-files` audit performed its file verification. Previously disclosed exposure remains disclosed; blindness is not restored.

No full-suite run, fresh benchmark, source acquisition or closure of the strict full-file-byte gate was performed. The remaining source-identifier acceptance defect prevents technical approval of this H1A revision.
