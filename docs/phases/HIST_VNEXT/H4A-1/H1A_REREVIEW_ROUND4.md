VERDICT: PATCH

## Observed verification

Read-only audit. No repository files were edited and no data approval was signed. BASELINE was read first, followed by the H1A review chain, repair record, original contract, phase documents, implementation, tests, declarations, scoped diff, manifests and provenance.

|Command exercised|Exit|Observed result|
|---|---:|---|
|`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py`|0|**136 passed in 1.20s**|
|`.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py`|0|All checks passed|
|`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .`|1|Structural **PASS**, historical **BLOCKED**; 4 candidates, 0 admitted, 63 blocked anchors, 5 blocked authorities, 10 candidate events|
|`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.admission --root . --verify-files`|1|Structural **PASS**, historical **UNIDENTIFIED**; 14 candidates: 0 admitted / 11 candidate / 3 blocked; **0 approved inputs**|
|Independent Python falsification harness, using 26 CLI subprocess invocations against fresh temporary fixtures|0|Individual CLI results below; repository files untouched|
|Independent Python metadata/hash/provenance diagnostic|0|Legacy identity, H4 preservation, intake consistency and existing output hashes checked|
|Git status/log and scoped diff inspection|0|Existing changes inspected; BASELINE has no diff|

The two real-package CLI exit-1 results are expected historical blocks, not crashes.

## Round-3 finding dispositions

|Finding|Disposition and independently observed evidence|
|---|---|
|**1. Event evidence and institutional coverage**|**Partially closed.** An in-PDF but unapproved page (`pdf_page=4`, approved page only 3) and a wrong source SHA each returned structured exit **1 / historical BLOCKED**. Separately removing issuer, legal force, reviewer, granted authority, implementation link or observed implementation date also blocked. Self-referencing and unknown implementation links blocked. Authority evidence containing only the primary event blocked. **Partial overlap between primary and implementation evidence still passes:** repair 1.|
|**2. Availability and statistical period checked independently**|**Closed for the specified counterexample.** With availability `1966-07-01`, statistical period `1966/1988` and excerpt authorization only `1966`, the CLI returned **1 / historical BLOCKED**; the affected source was not admitted.|
|**3. Duplicate source IDs before counting patterns**|**Closed for the specified false-independence declaration.** Copying the first source over the second while changing only work/root labels returned structured **exit 2**, with an empty summary—no admission counting. Other declaration identities remain unchecked: repair 2.|
|**4. Three malformed nested declarations**|**Closed for all three named inputs.** Authority `implementation_evidence_ids=null` returned structured **1 / structural PASS / historical BLOCKED**. Excerpt `allowed_use=["narrow_citation"]` and source `work_id=["x"]` each returned structured **exit 2**. None produced a traceback. Other source-field containers still crash: repair 3.|
|**5. Date representation versus precision**|**Closed for the specified counterexample.** `date="1966", date_precision="day"` returned structured **1 / historical BLOCKED**. All ten current event declarations preserve their represented precision or explicit unknown dates.|
|**6. Document-number OR archival-reference identification**|**Closed.** Both single-identifier paths independently returned **exit 0** in the software fixture; removing both returned **1 / historical BLOCKED**.|

The unmodified positive fixture returned **exit 0**, two admitted patterns and one independent pair. **That fixture is a software contract, not historical evidence.**

## Finite prioritized repair list

### 1. P1 — Require distinct primary and implementation evidence throughout an authority declaration

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:1131–1147`  
`tests/test_hist_source_admission.py:1063–1073`

The current check at line 1140 requires only **some** implementation event outside the primary set. It permits an event to serve simultaneously as primary authority and implementation evidence.

Independently exercised mutation of the positive fixture:

```python
data["authorities"][0]["implementation_evidence_ids"] = ["E01", "E02"]
# required_primary_ids remains ["E01"]
```

Observed CLI result:

```text
exit 0
structural PASS
historical PASS
```

This does not satisfy the review contract that required authority and implementation evidence must be distinct events. Adding one distinct event should not legitimize an overlapping evidence designation.

**Required repair:** Reject overlapping primary/implementation event sets, while retaining the non-empty and verified-reference requirements. Add the partial-overlap regression alongside the existing same-event-only test. Expected result: structured historical block.

### 2. P1 — Reject duplicate event and excerpt IDs before constructing lookup dictionaries

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:541–569,583–624`  
Last-wins lookups: `:120–124,369–373,1122–1126,1163–1167`  
Tests: `tests/test_hist_source_admission.py`

Duplicate source IDs are now rejected, but event and excerpt identities are not. Original H1A §2 requires duplicate-ID structural rejection; round 3 also requested validating declaration identities before last-wins lookups.

Two independently exercised mutations each retained **CLI exit 0 / structural PASS / historical PASS**:

```python
# events.json
data["events"].append(
    dict(
        copy.deepcopy(data["events"][0]),
        issuer="contradictory issuer",
        document_number="CONFLICTING/1966",
    )
)
```

This creates two contradictory records with `event_id="E01"`.

```python
# access_register.json
data["approved_excerpts"].insert(
    0,
    dict(
        copy.deepcopy(data["approved_excerpts"][0]),
        allowed_use="none",
        pdf_pages=[4],
    ),
)
```

This creates conflicting authorization declarations under the same excerpt ID. The later valid record silently replaces the earlier declaration in the lookup, so its disallowed use and different page do not prevent PASS.

**Required repair:** Enforce unique `event_id` and `excerpt_id` values during structural validation, before lookup construction or admission counting. Add subprocess regressions for both conflicting duplicate inputs. Expected result: structured **exit 2**, not order-dependent selection.

### 3. P1 — Validate source type and purpose containers before semantic evaluation

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:515–538`  
Crashing operations: `:91` and `:720`  
Tests: `tests/test_hist_source_admission.py`

The three specifically requested nested cases are fixed, but the original structured-error contract remains incomplete.

Actual subprocess results against fresh positive fixtures:

| Failing source declaration | Observed CLI result |
|---|---|
| `"source_type": ["primary_institutional"]` | Process **exit 1**, empty stdout, traceback ending at line 91: `TypeError: unhashable type: 'list'` |
| `"purpose": ["institutional_context"]` | Process **exit 1**, empty stdout, traceback ending at line 720: `TypeError: unhashable type: 'list'` |

These are malformed declarations, not legitimate historical-block exit-1 results.

**Required repair:** Validate these fields’ scalar types before set membership or dictionary lookup, routing violations through `_StructuralError`. Add subprocess tests requiring valid JSON, **exit 2**, and no traceback. Do not replace structural validation with a broad exception catch.

### Reproduction setup

All fixture mutations above were exercised independently using this setup, with writes confined to a temporary directory:

```python
import copy
import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

h = runpy.run_path("tests/test_hist_source_admission.py")

with tempfile.TemporaryDirectory() as tmp:
    root = h["repo_root"].__wrapped__(Path(tmp))
    h["positive_repo"].__wrapped__(root)

    path = root / "history/HIST_VNEXT/sources/authority_coverage.json"
    data = json.loads(path.read_text())
    data["authorities"][0]["implementation_evidence_ids"] = ["E01", "E02"]
    path.write_text(json.dumps(data))

    completed = subprocess.run(
        [sys.executable, "-m", "history.HIST_VNEXT.sources.admission",
         "--root", str(root)],
        capture_output=True,
        text=True,
    )
    print(completed.returncode, completed.stdout, completed.stderr)
```

Use `.venv/bin/python` with `PYTHONDONTWRITEBYTECODE=1`. Substitute the file and mutation specified above to reproduce the other findings.

## Preservation and provenance evidence

Independently observed:

- **63 distinct legacy artifacts**, covered exactly once, with zero mismatches across variable, source, SHA, path, grade, evidence status and dates. All 63 current H1A anchors remain blocked; all runtime flags remain false.
- All **63 H4 `legacy_record` snapshots match H1A**. H4’s header and every row field outside `legacy_record` are unchanged from HEAD. Classifications and admissions were not promoted.
- All four batch-01 candidate paths match exactly one intake entry; declared hashes and page counts agree with intake metadata. This is metadata consistency, not fresh restricted-PDF verification.
- All ten events contain the previously missing `effective_to`, `observed_implementation_at` and `information_rights` dimensions.
- BASELINE matches HEAD and frozen SHA256  
  `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
- `DATA_MANIFEST_v1.json` matches HEAD and frozen SHA256  
  `5d91e014c2b80651eb87d3515147468cb84fe77430bf336ba52e357000e58fdd`.
- Existing benchmark summary/metadata were inspected, not rerun. All **18 manifest-listed outputs per arm** in H4 `C0_review4` and `C1_review4` were hashed with zero mismatches. Their manifests declare 16 commodities, 116 completed ticks and the frozen replay digests. This does not independently recompute replay identity or close the strict full-file-byte gate.

## Scope boundaries

- **H1A remains declaration-only, offline, with no runtime wiring and no historical-input approval.**
- Real H1A declarations remain four candidates, zero admitted sources, zero approved excerpts and 63 blocked anchors. H4A-0 remains structural PASS / historical UNIDENTIFIED with zero approved inputs.
- No matching `src/` consumer of the reviewed admission/crosswalk declarations was found. The repair introduces no observed state update, target injection, quarterly interpolation, stochastic experiment, single-good substitution or LLM-probability interpretation.
- Broader runtime accounting/material balance and replicate independence were not re-certified. No full-suite run, new simulation, fresh benchmark or source acquisition was performed.
- Restricted PDF/OCR content, mixed-year XLS contents and historical target values were not opened. Prior exposure remains disclosed; this review does not restore hold-out blindness.
- Passing software fixtures and targeted tests do not establish historical truth, approve data, authorize production initialization/measurement, or close the remaining H4A-1 gates.
