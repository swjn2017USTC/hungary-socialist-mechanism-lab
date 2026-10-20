VERDICT: PATCH

## Observed verification

Read-only audit. No repository files were edited and no data approvals were signed. Read BASELINE first, then the five-review chain, repair record, original H1A contract, phase plans/reports/review, implementation, tests, declarations, scoped git diff, manifests and provenance artifacts.

| Command exercised | Exit | Observed result |
|---|---:|---|
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py` | 0 | **148 passed in 2.33s** |
| `.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py` | 0 | All checks passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .` | 1 | Structural **PASS**, historical **BLOCKED**; 4 candidates, 0 admitted, 63 blocked anchors, 5 blocked authorities, 10 candidate events |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.admission --root . --verify-files` | 1 | Structural **PASS**, historical **UNIDENTIFIED**; 14 candidates: 0 admitted / 11 candidate / 3 blocked; **0 approved inputs** |
| Three read-only Python diagnostic invocations: subprocess falsification; metadata/output hashing; earlier-invariant rechecks | 0 each | Captured individual subprocess results, including the false admission and traceback below |
| Git status/log and scoped diff inspection | 0 | Existing changes inspected; BASELINE has no diff |

The two real-package exit-1 results are expected historical blocks, not crashes.

## Round-5 finding dispositions

| Finding | Disposition and independently observed evidence |
|---|---|
| **1. Anchor classification sufficiency** | **Closed for the specified contract.** Non-blocked classification inconsistent with evidence kind was rejected. Actual unresolved H1A rows relabelled `proxy` or `synthetic`, using actual corresponding legacy metadata, returned structured **exit 2**. Missing transformation, retained missing evidence, and omission of the stated 1957 limitation were independently rejected. The unmodified software fixture returned **exit 0**, with two admitted patterns and an independent pair. |
| **2. Observed implementation within excerpt authorization** | **Named mutation fixed; temporal evidence binding remains incomplete.** Changing only `observed_implementation_at` to `1988-02-01` returned structured **exit 1 / structural PASS / historical BLOCKED**. Adding a selected excerpt for another page restores false historical PASS because pages and windows are aggregated separately. Repair 1 below. |
| **3. Anchor scalar-container errors** | **Closed for all requested inputs.** List-valued `variable_id`, `classification`, and `source_evidence_kind` each returned structured **exit 2**, valid JSON and no traceback. List-valued `transformation` independently returned the same result for both proxy and synthetic rows. A malformed authoritative manifest field still crashes; repair 2 below. |

**The positive fixture is a software contract, not historical evidence. Its exit 0 does not verify a historical source, observation, transformation or approval.**

## Earlier closed findings rechecked

- **Identity/geography/evidence binding:** Swapping national/regional identity, forging direct evidence kind, and changing the source SHA were rejected. Current declarations cover **63 distinct legacy artifacts**, with zero mismatches across variable, source, SHA, path, grade, evidence status and dates.
- **Rights/excerpt handoff/pages/full period:** Evidence-free restricted rights, stale handoff content hash, parent-hash mismatch, page 99 and missing page count were blocked. Known availability in 1966 did not bypass checking content declared through 1988.
- **Shared roots:** Distinct rooted works returned `True`; same work, direct overlap and cross-work cited overlap returned `False`; unknown cited roots and unrooted records returned `None`.
- **Duplicate identities:** Duplicate source, event and excerpt IDs each returned structured exit 2.
- **Nested errors:** Malformed excerpt-ID, anchor-support, authority-evidence, source-type/purpose/work-ID and excerpt-use containers returned structured exit 2. Null authority implementation evidence returned a structured historical block.
- **Required-file failures:** Malformed JSON in each of the seven required files returned structured exit 2 without traceback. An injected manifest-read `OSError` also returned exit 2.
- **Date precision:** `date="1966", date_precision="day"` returned a historical block. Current event declarations preserve supported precision and explicit unknowns.
- **Event identification:** Either document number or archival reference alone preserved fixture exit 0; removing both blocked.
- **Institutional coverage and patterns:** Partial primary/implementation evidence overlap blocked. An unapproved event page, catalogue second source, missing observable pattern, shared root and empty authority coverage each blocked historical PASS.
- **H4A-0 preservation:** All 63 embedded legacy snapshots match H1A. H4’s header and every row field outside those snapshots are unchanged from HEAD. Its three approval sets remain empty.

## Finite prioritized repair list

### 1. P1 — Keep approved page and temporal scope bound to the same excerpt

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:368–392,1275–1276,1291`  
`tests/test_hist_source_admission.py:1107–1116`

The audit constructs a union of approved pages and a separate list of approved windows per source. `_event_ready` checks the observation against **any** source window, then checks the page against **any** source page. This manufactures authorization combinations that no individual excerpt grants.

**Independently exercised input**, starting from the positive fixture:

1. Preserve `excerpt_001`: source `decree_1966_41`, **page 3**, authorized **1966–1967**.
2. Add another selected excerpt of the same source: **page 4**, authorized **1966–1988**.
3. Leave E01’s cited page at **3**, but set its observed implementation to **1988-02-01**.

**Observed subprocess result:** **exit 0 / structural PASS / historical PASS**.

Neither excerpt authorizes the claimed **page-3 / 1988** evidence combination. The later page-4 permission improperly expands page 3’s temporal authorization. This is an admission-boundary defect, not evidence of actual runtime hold-out injection.

**Required repair:** Preserve excerpt-level authorization tuples and require one selected, validated excerpt to cover both the event’s cited page and the complete observed-implementation date range. Add this two-excerpt regression alongside the existing single-excerpt 1988 rejection test.

### 2. P1 — Validate authoritative manifest evidence-status type before lookup

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:1124–1131`  
Error propagation: `history/HIST_VNEXT/sources/admission.py:339–345`  
`tests/test_hist_source_admission.py`

**Independently exercised input**, in the temporary positive package:

```python
manifest["artifacts"][0]["evidence_status"] = ["literature_proxy"]
```

**Observed subprocess result:** process **exit 1**, empty stdout, traceback ending at:

```text
admission.py:1131
    }.get(evidence_status)
TypeError: unhashable type: 'list'
```

The newly repaired row scalar checks do not protect the authoritative metadata lookup. This violates the original required-file/nested-structure contract: malformed declarations must return structured exit 2, not crash.

**Required repair:** Validate the manifest evidence-status scalar before dictionary lookup and propagate the violation through the existing structured-error path. Add a subprocess regression requiring exit 2, valid JSON and no traceback. Do not substitute a broad exception catch.

## Reproduction

The following reproduces both remaining defects independently, with writes confined to fresh temporary fixtures. Run using `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python`:

```python
import copy
import json
import runpy
import tempfile
from pathlib import Path

h = runpy.run_path("tests/test_hist_source_admission.py")

def load(root, relative):
    return json.loads((root / relative).read_text())

def save(root, relative, data):
    (root / relative).write_text(json.dumps(data))

for case in ("split_page_window", "manifest_evidence_list"):
    with tempfile.TemporaryDirectory() as tmp:
        root = h["repo_root"].__wrapped__(Path(tmp))
        h["positive_repo"].__wrapped__(root)

        if case == "split_page_window":
            candidates = "history/HIST_VNEXT/sources/batch01_candidates.json"
            access = "history/HIST_VNEXT/exposure/access_register.json"
            events = "history/HIST_VNEXT/event_candidates/events.json"

            data = load(root, candidates)
            data["records"][0]["approved_excerpt_ids"].append("late_page4")
            save(root, candidates, data)

            data = load(root, access)
            excerpt = copy.deepcopy(data["approved_excerpts"][0])
            excerpt.update(
                excerpt_id="late_page4",
                pdf_pages=[4],
                allowed_window="1966-01-01/1988-12-31",
            )
            data["approved_excerpts"].append(excerpt)
            save(root, access, data)

            data = load(root, events)
            data["events"][0]["observed_implementation_at"] = "1988-02-01"
            save(root, events, data)
        else:
            manifest = "data/manifests/DATA_MANIFEST_v1.json"
            data = load(root, manifest)
            data["artifacts"][0]["evidence_status"] = ["literature_proxy"]
            save(root, manifest, data)

        completed = h["_run_cli"](root)
        print(case, completed.returncode, completed.stdout, completed.stderr)
```

The diagnostic exercised these mutations through the actual module CLI subprocess, not merely private helper calls.

## Preservation, provenance and scope boundaries

- BASELINE matches HEAD and frozen SHA256  
  `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
- `DATA_MANIFEST_v1.json` matches HEAD and frozen SHA256  
  `5d91e014c2b80651eb87d3515147468cb84fe77430bf336ba52e357000e58fdd`. Manifest v2 also matches HEAD.
- All four batch-01 candidate paths, hashes and page counts match intake metadata. This is metadata consistency, not fresh restricted-PDF verification.
- Existing benchmark output and C0/C1 provenance were inspected. All **18 manifest-listed output files per arm** in `C0_review4` and `C1_review4` were independently hashed with zero mismatches. Their manifests declare 16 commodities, 116 completed ticks and the frozen replay digests. No replay identity was independently recomputed and no new simulation was run.
- **H1A remains offline and declaration-only: no runtime wiring, no historical-input approval, and no production initialization or measurement authorization.** Actual declarations remain four candidates, zero admitted sources, zero approved excerpts and 63 blocked anchors.
- No matching production consumer of the reviewed declarations was found in `src/`. No state update, quarterly interpolation, stochastic experiment, single-good substitution or LLM-probability interpretation is introduced by this repair.
- Broader accounting/material-balance correctness, stochastic independence and the strict full-file-byte gate were not re-certified. No full-suite run or fresh benchmark was performed.
- Restricted PDF/OCR contents, mixed-year XLS contents and historical target values were not opened. Prior exposure remains disclosed; this review does not restore hold-out blindness.
