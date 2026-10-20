VERDICT: PATCH

## Observed verification

Read-only review. No repository files were edited and no data approval was signed.

|Command exercised|Exit|Observed result|
|---|---:|---|
|`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py`|0|**124 passed in 0.44s**|
|`.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py`|0|All checks passed|
|`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .`|1|Structural **PASS**, historical **BLOCKED**; 4 candidates, 0 admitted, 63 blocked anchors, 5 blocked authorities, 10 candidate events|
|`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.admission --root . --verify-files`|1|Structural **PASS**, historical **UNIDENTIFIED**; 14 candidates: 0 admitted / 11 candidate / 3 blocked; 0 approved inputs|
|Five read-only Python diagnostic invocations covering mutations, subprocess CLIs, metadata comparison and output hashing|0 each|Individual subprocess failures and false admissions are reported below|
|Git status/log and scoped diff inspection|0|Reviewed current changes; BASELINE has no diff|

The real-package CLI exit-1 results are expected historical blocks, not technical crashes.

Additional independently observed evidence:

- **63 distinct legacy artifacts**, with zero mismatches across variable, source, SHA, path, grade, evidence status and dates.
- H4’s **63 `legacy_record` snapshots exactly match H1A**. H4’s header and every row field outside `legacy_record` are unchanged from HEAD.
- All four batch-01 candidate paths resolve to matching intake-manifest entries; hashes and page counts match.
- All ten events explicitly contain `effective_to`, `observed_implementation_at` and `information_rights`, currently null.
- BASELINE matches HEAD and frozen SHA256  
  `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
- `DATA_MANIFEST_v1.json` matches HEAD and frozen SHA256  
  `5d91e014c2b80651eb87d3515147468cb84fe77430bf336ba52e357000e58fdd`.
- Existing benchmark outputs and H4 C0/C1 provenance were inspected. All **18 manifest-listed output files per arm** were independently hashed, with zero mismatches. The manifests declare the frozen replay digests. This was not a new simulation or recomputation of replay identity.

## Round-2 finding dispositions

| Finding | Disposition |
|---|---|
| **Anchor identity and direct classification** | **Closed for specified counterexamples.** Swapped anchor/geography and forged `source_evidence_kind="direct"` are rejected. Separate mutations withholding either 1957 date or direct evidence status are rejected. |
| **Rights and excerpt authorization** | **Partially closed.** Both restricted and verified rights reject removal of each required evidence field or download permission. Invalid page counts and changed source/content hashes with stale handoffs are blocked. Full-period authorization still has an availability-date bypass: repair 2. |
| **Three named nested structural errors** | **Closed for those inputs.** `approved_excerpt_ids=[{}]`, `supporting_anchor_ids=1` and `implementation_evidence_ids=1` each returned structured CLI exit **2**, without traceback. Other malformed nested declarations still crash: repair 4. |
| **Historical PASS gate** | **Partially closed.** The positive fixture now has two admitted pattern records and an independent admitted pair. Absent event source, wrong source SHA, invalid rights, invalid date, page 999, candidate authority, non-admitted second pattern, missing pattern and shared roots each prevent PASS. Unapproved event pages, missing institutional evidence and duplicate source identity still permit PASS: repairs 1 and 3. |
| **Event-schema remainder** | **Closed in current declarations.** All three requested dimensions are explicit on all ten events. Precision validation remains incomplete: repair 5. |
| **Shared-root logic retained from earlier repair** | **Specified cases pass.** Direct/cited overlap and same-work pairs return false; unrooted or unknown-citation pairs return null; distinct rooted works return true. Duplicate declarations can still manufacture the counted pair: repair 3. |
| **H4A-0 preservation** | **Preserved within its original scope.** Structural PASS / historical UNIDENTIFIED, zero approved inputs, unchanged classifications/admissions outside synchronized snapshots. |

Malformed JSON in each of the seven required files returned structured CLI exit 2 without traceback. An injected manifest-read `OSError` also returned structured exit 2.

## Finite prioritized repair list

### 1. P1 — Bind verified events to approved excerpt evidence and substantive institutional coverage

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:1015–1049,1065–1097`  
`tests/test_hist_source_admission.py:267–344,929–945`

Two independently exercised mutations of the positive software fixture produced **CLI exit 0 / structural PASS / historical PASS**:

```python
event["pdf_page"] = 4
```

The source declares pages 1–12, but its only approved excerpt covers **page 3**. `_event_ready` checks the PDF’s broad bounds, not the approved evidence pages. Admission of one excerpt therefore authorizes event claims from another, unapproved page.

Separately:

```python
event.update(
    issuer=None,
    legal_force=None,
    reviewer=None,
    authority_granted=[],
    implementation_evidence_id=None,
    observed_implementation_at=None,
)
```

also retained historical PASS. The positive fixture already omits these substantive evidence dimensions. Its authority row names the same event as both primary and implementation evidence, while neither validator establishes an institutional authority or observed implementation chain.

The original H1A contract requires issuer/legal force, authority provisions and execution evidence; a verified status label is not a substitute.

**Required repair:** Bind event claims to selected, validated approved excerpts, including source SHA and approved page. Require purpose-appropriate institutional and implementation evidence before historical PASS; missing evidence must remain unresolved. Complete the software fixture accordingly. Test an in-PDF but unapproved page and the missing-evidence case separately.

### 2. P1 — Check the full declared content period even when availability is known

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:676–694`  
`tests/test_hist_source_admission.py:495–506`

Observed reproduction:

```python
record = h["_primary_record"]()
record["statistical_period"] = "1966/1988"
result = evaluate_source(
    record,
    approved_excerpts=[h["_excerpt"](allowed_window="1966")],
)
# Observed: {"status": "admitted", "reasons": []}
```

Here `h` is the test module loaded using `runpy.run_path`.

The existing test sets `source_available_at=None`; that case is correctly blocked. Keeping the fixture’s known availability date instead selects the `if available_at` branch and skips the statistical-period check entirely.

This leaves the round-2 full-period repair incomplete and permits authorization covering only 1966 to admit declared content through 1988.

**Required repair:** Validate every applicable declared period independently. Availability must not override content/exposure coverage. Add the same negative case with both fields populated.

### 3. P1 — Reject duplicate source identity before counting independent admitted patterns

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:350–375,490–505`  
`tests/test_hist_source_admission.py:267–344,869–878`

Observed mutation:

```python
records[1] = copy.deepcopy(records[0])
records[1].update(
    work_id="different_label",
    observation_ids=["invented_root"],
    cited_observation_ids=["invented_root"],
)
```

Both declarations now have the **same source ID, source SHA and approved excerpt**. Only their work/root labels differ.

Actual CLI result:

```text
exit 0
structural PASS
historical PASS
total_admitted 2
independent_pairs 1
```

`_validate_candidate_records` does not reject duplicate source IDs. The audit increments its admitted count twice and appends both declarations, while `admitted_by_id` silently overwrites the first entry. Thus one source identity can satisfy the two-source gate through contradictory labels.

**Required repair:** Reject duplicate source IDs as a structural error before admission/counting, consistent with the original duplicate-ID contract. Validate other declaration identities before constructing last-wins lookup dictionaries. Add this exact false-independence regression.

### 4. P1 — Finish nested structural validation; do not allow tracebacks after the structural gate

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:363,490–516,641,1041–1043`  
`tests/test_hist_source_admission.py:881–913`

Although the three specifically requested malformed inputs now work correctly, these independent mutations still produced **actual CLI process exit 1, empty stdout and a traceback**, rather than structured JSON:

| Declaration mutation | Observed exception |
|---|---|
| Authority: `"implementation_evidence_ids": null` | `TypeError: 'NoneType' object is not iterable`, line 1043 |
| Approved excerpt: `"allowed_use": ["narrow_citation"]` | `TypeError: unhashable type: 'list'`, line 641 |
| Source: `"work_id": ["x"]` | `TypeError: unhashable type: 'list'`, line 363 |

The authority validator explicitly skips null, but coverage subsequently calls `set(implementation)`.

**Required repair:** Validate nested scalar/container types before iteration, hashing or set membership. Handle absent implementation evidence without crashing, according to its declared schema. Add subprocess tests asserting structured results and no traceback for all three inputs; do not merely suppress exceptions with a broad catch.

### 5. P2 — Enforce date precision against the date representation

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:1068–1071`  
`tests/test_hist_source_admission.py:987–1020`

Observed mutation:

```python
event.update(date="1966", date_precision="day")
```

Actual CLI result: **exit 0 / structural PASS / historical PASS**.

The validator independently accepts a precision enum and any parsable date representation, allowing a year-only observation to claim day precision. Current on-disk event dates preserve precision correctly; this is an acceptance-path defect.

**Required repair:** Check consistency between date representation and declared precision, preserving explicit interval semantics where supported. Add a mismatched-precision negative test without combining it with unrelated invalid rights or pages.

### 6. P2 — Preserve the original document-number-or-archive identification alternative

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:95–98,1072–1080`  
`tests/test_hist_source_admission.py:374–383`

The source evaluator correctly permits a verifiable published document number without an archival reference. `_event_ready` contradicts that rule by requiring both.

Independently observed fixture mutations:

```python
event["archival_reference"] = None  # Published document number remains.
```

and:

```python
event["document_number"] = None    # Archival reference remains.
```

Each returned **CLI exit 1 / structural PASS / historical BLOCKED**.

**Required repair:** Apply the same context-appropriate document-number-or-archival-reference rule to events. Keep rejection when neither usable identifier exists. Add positive event-level tests for both legitimate identification paths.

### Reproduction setup

The fixture-based CLI mutations above were exercised using this setup, with each mutation applied independently in a fresh temporary directory:

```python
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

    path = root / "history/HIST_VNEXT/event_candidates/events.json"
    data = json.loads(path.read_text())
    data["events"][0]["pdf_page"] = 4  # Repair-1 counterexample.
    path.write_text(json.dumps(data))

    completed = subprocess.run(
        [sys.executable, "-m", "history.HIST_VNEXT.sources.admission",
         "--root", str(root)],
        capture_output=True,
        text=True,
    )
    print(completed.returncode, completed.stdout, completed.stderr)
```

Use `.venv/bin/python` with `PYTHONDONTWRITEBYTECODE=1`. This changes temporary fixture declarations only, not repository files.

## Scope boundaries

- **H1A remains declaration-only and offline: no runtime wiring and no historical input approval.**
- The positive fixture is a **software contract, not historical evidence**. Its exit 0 does not establish any real decree, authority, observation or approval.
- Current real H1A declarations remain four candidates, zero admitted sources, zero approved excerpts and 63 blocked anchors.
- H4A-0 retains zero approved inputs and its original candidate/gap-only scope. This review does not authorize H4A-1 production initialization or measurement.
- No matching `src/` runtime consumer of the reviewed admission/crosswalk declarations was found. No new state updates, quarterly interpolation, material-balance implementation, stochastic experiment or LLM-probability interpretation occurs in this repair.
- Restricted PDF/OCR content, mixed-year XLS contents and historical target values were not opened. Previously disclosed exposure remains disclosed; blindness is not restored.
- No full-suite run, new simulation, new benchmark execution, accounting/material-balance recertification or strict full-file-byte-gate closure was performed.
