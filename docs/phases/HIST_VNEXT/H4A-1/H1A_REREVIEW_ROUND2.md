VERDICT: PATCH

## Observed verification

Read-only review of the current working tree, including BASELINE first, the original H1A contract, round-1 review, repair record, phase documents, implementation, tests, declarations, diff, manifests and provenance. No repository files were edited and no data approval was signed.

|Command exercised|Exit|Observed result|
|---|---:|---|
|`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py`|0|**108 passed in 0.25s**|
|`.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py`|0|All checks passed|
|`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .`|1|Structural **PASS**, historical **BLOCKED**; 4 candidates, 0 admitted, 63 blocked anchors, 5 blocked authorities, 10 candidate events|
|`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.admission --root . --verify-files`|1|Structural **PASS**, historical **UNIDENTIFIED**; 14 candidates: 0 admitted / 11 candidate / 3 blocked; 0 approved inputs|
|Read-only Python metadata, hash and mutation diagnostics|0|Results detailed below; diagnostic harnesses captured individual failures rather than failing themselves|

The two real CLI exit-1 results are expected historical blocks, not technical failures.

Additional observed evidence:

- Current H1A rows cover **63 distinct legacy artifact IDs**, with **zero mismatches** for variable, source, SHA, path, grade, evidence status and dates.
- H4’s **63 embedded `legacy_record` snapshots exactly match H1A**. Comparing H4 against HEAD, its header and every row field **outside `legacy_record` are unchanged**. Thus the snapshot synchronization did not change H4 classifications, admissions or approval decisions.
- All four candidate hashes, paths and page counts match batch-01 intake metadata. Restricted original PDFs were not opened.
- BASELINE matches HEAD and its frozen SHA256:  
  `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
- `DATA_MANIFEST_v1.json` matches its frozen SHA256:  
  `5d91e014c2b80651eb87d3515147468cb84fe77430bf336ba52e357000e58fdd`.
- Inspected existing benchmark output and H4 C0/C1 provenance. Independently hashed all **18 manifest-listed output files per arm**, with zero mismatches. The manifests declare the frozen C0/C1 digests. These were existing runs—not new simulations or independently recomputed replay identities.

## Per-finding disposition

|Round-1 finding|Disposition|Evidence|
|---|---|---|
|**1. R1: legacy bijection and metadata**|**PATCH**|Current artifacts match, ID-only validation is rejected, and the named single-field mutations fail. Geographic identity can nevertheless be permuted, and changing `source_evidence_kind` bypasses the direct-classification guard. Repair 1.|
|**2. Rights / excerpt provenance**|**PATCH**|`RightsSpec` is reused; evidence-free verified and invented statuses are rejected. Source/parent mismatch, malformed hash, out-of-range page, disallowed use and wholly disjoint window are rejected; unrelated register entries no longer block a source. Evidence-free restricted rights, partial-period authorization and unbound content hashes remain accepted. Repair 2.|
|**3. Shared roots**|**PASS for the specified cases**|Independent mutations produced: direct overlap → `False`; same work with distinct roots → `False`; unrooted record → `None`; unknown cited root → `None`; cross-work cited overlap → `False`; distinct rooted works → `True`. Eligibility of these pairs for historical coverage remains defective under finding 5.|
|**4. Structural exit 2**|**PATCH**|Malformed JSON in all seven required files and injected manifest `OSError` now return structured exit 2. Top-level/container checks work for tested declaration shapes. Deeper malformed containers still cause traceback/process exit 1. Repair 3.|
|**5. Empty historical coverage**|**PATCH**|Empty authorities, empty events, candidate events, removal of the independent pair, and a blocked anchor each correctly prevent PASS. However, false event provenance, an unverified authority status and a non-admitted second “pattern” still permit historical PASS. Repair 4.|
|**6. Date precision / schema / caveats**|**PATCH, limited remainder**|Candidate year/month precision and unknown availability are corrected. Event precision, explicit unknown enactment/effective/availability/source/page fields, and crosswalk 2011-boundary caveat are present; the unsupported autonomy-law assertion is removed. Three original-contract event dimensions remain absent. Repair 5.|

## Prioritized finite repair list

### 1. P1 — Bind anchor geography and evidence classification to authoritative legacy identity

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:739–759,802–820`  
`tests/test_hist_source_admission.py:600–690`

Two independently exercised mutations passed `validate_anchor_crosswalk(..., legacy_artifacts=...)`:

```python
# Starting with the actual current crosswalk and legacy manifest:
for field in ("anchor_id", "geographic_scope"):
    rows[0][field], rows[1][field] = rows[1][field], rows[0][field]
```

This swaps the national and Budapest anchor labels while leaving each row’s legacy artifact, path and hash untouched. The validator checks that geography agrees with the freely assigned anchor suffix, but never binds that suffix to the legacy artifact.

Separately:

```python
rows[0].update(
    classification="direct",
    source_evidence_kind="direct",
)
```

also passed, despite the unchanged authoritative **1960 observation, grade C and `literature_proxy` evidence status**. The rejection at line 739 depends on the caller retaining `source_evidence_kind="proxy"`.

**Required repair:** Bind canonical anchor/geographic identity to the covered artifact, and derive/check source evidence kind from authoritative metadata. Direct classification must independently satisfy the 1957 target-date and boundary requirements. Add both counterexamples as rejection tests.

### 2. P1 — Finish purpose-specific rights and independently bound excerpt authorization

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:480–490,526–529,542–588`  
`tests/test_hist_source_admission.py:346–470`

Using `_primary_record()` and `_excerpt()` from the test module, these independent inputs returned:

```text
rights={"license_status":"restricted"}                 → admitted
source_available_at=None,
statistical_period="1966/1988",
excerpt.allowed_window="1966"                         → admitted
pdf_pages=None, pdf_page_range="1-999",
excerpt.pdf_pages=[999]                               → admitted
excerpt.content_hash changed to another valid SHA256  → admitted
```

The first input supplies **no evidence of permission for the requested use**. `RightsSpec` permits a restricted declaration, but `_rights_reasons` treats it as sufficient admission permission without examining the restriction or supporting evidence.

The window test admits a source spanning through the reserved period on authorization covering only 1966. The code requires only overlap when availability is unknown. The page test bypasses the total-page bound when `pdf_pages` is absent.

Content hashes are checked only for hexadecimal shape. No independent administrator handoff evidence is loaded or compared, although original H1A §4 expressly requires that binding. A changed valid hash therefore remains admitted.

**Required repair:** Keep `RightsSpec`, but require evidence permitting the specific use for restricted material; require adequate page-count/range evidence; bind the authorized content period rather than accepting mere overlap; and compare source/excerpt identity against the independent handoff evidence required by the original contract. Do not obtain that evidence by opening restricted originals. Add the four counterexamples to the behavioral tests.

### 3. P1 — Return structured exit 2 for malformed nested declarations

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:119–128,231–239,297–306,426–436,837–841`

Actual subprocess CLI invocations against temporary copies produced:

| Failing input | Observed CLI result |
|---|---|
| Primary source: `"approved_excerpt_ids": [{}]` | Exit **1**, `TypeError: unhashable type: 'dict'` |
| Anchor: `"supporting_anchor_ids": 1` | Exit **1**, `TypeError: 'int' object is not iterable` |
| Authority: `"implementation_evidence_ids": 1` | Exit **1**, `TypeError: 'int' object is not iterable` |

These are structural errors, not historical-block exit-1 results. `_records` validates only the outer list and object entries; deeper operations assume valid element types.

**Required repair:** Validate nested containers and their element types before hash lookup, iteration or set construction. Route violations through the structural result. Extend subprocess-level tests to assert exit 2 and valid JSON without traceback.

### 4. P1 — Require verified evidence links and two admitted observable patterns before historical PASS

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:352–354,369–380,823–866`  
`tests/test_hist_source_admission.py:265–323,752–760`

Starting from the positive software fixture, each mutation independently yielded **CLI exit 0 / structural PASS / historical PASS**:

```python
event["source_id"] = "ABSENT"  # No such source exists.
```

```python
event.update(
    rights={"license_status": "invented"},
    date="NOT_A_DATE",
    pdf_page=999,
)
```

```python
authority["status"] = "candidate"
```

`_event_ready` checks truthiness rather than valid rights/date/provenance, and never binds the event to an admitted source or approved page. `_coverage_ok` rejects only authority status literally equal to `"blocked"`.

The existing positive fixture itself contains **one admitted primary plus one non-admitted secondary** and no specific observable-pattern descriptions. It nevertheless passes because independence is counted over **all source records**. Changing the secondary to `catalogue` also retained historical PASS. Original H1A §3 requires two independent, **admitted observable patterns**, not merely two different root labels.

A compact reproduction of the absent-source defect is:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json, runpy, tempfile
from pathlib import Path
from history.HIST_VNEXT.sources.admission import audit_h1a

h = runpy.run_path("tests/test_hist_source_admission.py")
with tempfile.TemporaryDirectory() as tmp:
    root = h["repo_root"].__wrapped__(Path(tmp))
    h["positive_repo"].__wrapped__(root)
    path = root / "history/HIST_VNEXT/event_candidates/events.json"
    data = json.loads(path.read_text())
    data["events"][0]["source_id"] = "ABSENT"
    path.write_text(json.dumps(data))
    result = audit_h1a(root)
    print(result["exit_code"], result["structural"], result["historical"])
PY
# Current result: 0 PASS PASS
```

The equivalent mutation was exercised both through `audit_h1a` and through the CLI subprocess.

**Required repair:** Bind event evidence to admitted sources and approved pages/hashes; validate dates, rights and affirmative authority readiness; count only eligible, described, independently rooted admitted patterns. Replace the positive fixture with a contract-complete software fixture and add these rejection cases. **The fixture is a software contract, not historical evidence.**

### 5. P2 — Complete the original event-schema dimensions with explicit unknowns

**Paths:**  
`history/HIST_VNEXT/event_candidates/events.json:4–51` and the remaining event records  
`tests/test_hist_source_admission.py:786–805`  
Contract: `docs/upgrade_review/HIST_VNEXT/03_HISTORICAL_INSTITUTION_EVENT_SOURCES.md:53–55`

All ten events omit:

- `effective_to`
- `observed_implementation_at`
- `information_rights`

These are semantically distinct original minimum fields; existing enactment/effective/availability fields do not represent expiry, observed implementation or information rights. The current schema test asserts only a subset.

**Required repair:** Represent these dimensions explicitly as unknown where unsupported, and test the complete required semantics. Preserve the repaired date precision and boundary caveats; do not invent dates or authority claims.

## Scope boundaries

- **H1A remains an offline, declaration-only admission/crosswalk package. No historical input or runtime connection is approved by this review.**
- Current on-disk H1A sources remain candidates and all 63 anchors remain blocked. The defects above are validator acceptance paths, not evidence that current declarations were numerically wired.
- No `src/` consumer of these crosswalk/admission declarations was found. H4 snapshot synchronization did not promote any classification, admission or input.
- This review opened metadata, code and existing technical output artifacts—not restricted PDF/OCR content, legacy mixed-year XLS contents or hold-out target values. Prior exposure remains disclosed; this review does not restore blindness.
- No new interpolation, state updates, stochastic replicates, single-good substitution or LLM-probability interpretation occurs in this repaired module. Broader accounting/material-balance correctness and stochastic independence were not re-certified.
- No full-suite run, fresh simulation, new benchmark run, source acquisition or historical approval was performed.
