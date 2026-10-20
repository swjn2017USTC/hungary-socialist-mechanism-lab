VERDICT: PATCH

## Observed verification

Read-only review. No repository files were edited and no data approval was signed. BASELINE was read first, followed by the H1A review chain, repair record, original contract, phase plans/reports/review, implementation, tests, declarations, diff, manifests and provenance.

| Command exercised | Exit | Observed result |
|---|---:|---|
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py` | 0 | **141 passed in 1.52s** |
| `.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py` | 0 | All checks passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .` | 1 | Structural **PASS**, historical **BLOCKED**; 4 candidates, 0 admitted, 63 blocked anchors, 5 blocked authorities, 10 candidate events |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.admission --root . --verify-files` | 1 | Structural **PASS**, historical **UNIDENTIFIED**; 14 candidates: 0 admitted / 11 candidate / 3 blocked; **0 approved inputs** |
| Four read-only Python diagnostic invocations covering subprocess mutations, API counterexamples, metadata preservation and output hashing | 0 each | Individual subprocess exits and defects detailed below |
| Git status/log and scoped diff inspection | 0 | Existing changes inspected; BASELINE has no diff |

The real-package exit-1 results are expected historical blocks, not crashes.

## Round-4 repair dispositions

| Finding | Independently observed disposition |
|---|---|
| **Primary/implementation evidence fully disjoint** | **Closed for the required mutation.** `required_primary_ids=["E01"]`, `implementation_evidence_ids=["E01","E02"]` returned structured **exit 1 / structural PASS / historical BLOCKED**, explicitly identifying overlapping evidence. |
| **Duplicate event IDs before lookup** | **Closed.** A contradictory `E01` with changed issuer, document number and page returned structured **exit 2**, empty summary and no traceback, whether inserted before or after the original. |
| **Duplicate excerpt IDs before lookup** | **Closed.** A conflicting excerpt with `allowed_use="none"` and `pdf_pages=[4]` returned structured **exit 2**, empty summary and no traceback, in both orders. |
| **List-valued source type and purpose** | **Closed.** `source_type=["primary_institutional"]` and `purpose=["institutional_context"]` independently returned structured **exit 2**, without traceback. |

These specific repairs work. The original structural-error and historical-evidence contracts still have the three defects below.

## Earlier finding rechecks

- **Anchor identity/geography/evidence binding:** Current declarations cover **63 distinct legacy artifacts**, with zero mismatches across variable, source, SHA, path, grade, evidence status and dates. Swapping national/regional anchor identity, forging direct evidence, or changing the source SHA was rejected. **Classification sufficiency remains incomplete: repair 1.**
- **Rights/excerpt handoff/pages/full-period coverage:** Evidence-free restricted rights, stale handoff content hash, parent-hash mismatch, page 99, and missing page count were blocked. Availability in 1966 did not bypass checking `statistical_period="1966/1988"` against authorization only for 1966. **Event claims lose that temporal authorization downstream: repair 2.**
- **Shared roots:** Distinct rooted works returned `True`; same work, direct overlap and cross-work cited overlap returned `False`; unknown cited roots and unrooted records returned `None`.
- **Nested structural errors:** Previously named malformed excerpt/source/authority/support-list inputs returned structured exit 2. Null implementation evidence returned a structured historical block. Malformed JSON in each of the seven required files returned exit 2; an injected required-file `OSError` also returned exit 2. **Other anchor containers still crash: repair 3.**
- **Date precision:** `date="1966", date_precision="day"` returned a historical block. Current candidate dates retain supported year/month/day precision and explicit unknowns.
- **Document-number OR archive:** Either event identifier alone retained software-fixture exit 0; removing both blocked.
- **Two admitted observable patterns:** The unmodified software fixture returned two admitted patterns and one independent pair. Making the second source a catalogue, removing a pattern, or sharing its root prevented historical PASS.
- **H4A-0 preservation:** All 63 embedded `legacy_record` snapshots match H1A. H4’s header and every row field outside those snapshots are unchanged from HEAD. Its admission classifications and approvals were not promoted.

**The positive fixture is a software contract, not historical evidence. Its successful exit does not establish historical validity.**

## Finite prioritized repair list

### 1. P1 — Do not clear the 1957 anchor gate by relabelling unresolved legacy records

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:968–982,434–435`  
`tests/test_hist_source_admission.py:383–389`  
Contract: `HIST_VNEXT_H1A_PLAN.md:97–99`

The validator checks special requirements for `blocked` and `reconstructed`, but does not enforce the declared requirements for `proxy` or `synthetic`. The historical gate then checks only whether any classification is literally `blocked`.

**Independently exercised input:** In a temporary positive package, replace its crosswalk and initial-state manifest metadata with the **actual current 63 H1A rows and corresponding actual legacy artifacts**, changing only:

```python
for row in crosswalk["records"]:
    row["classification"] = "proxy"
```

All actual unresolved boundary descriptions, missing-evidence statements, null transformations, empty supporting lists and 1960 dates remain unchanged.

**Observed CLI result:** **exit 0 / structural PASS / historical PASS**, zero blocked anchors.

Changing only the classification to `"synthetic"` also returned historical PASS, despite retaining null transformations and no declared synthesis rules.

This contradicts the original contract: unresolved date/space/transformation gaps remain blocked; proxies must state their 1957 limitations, and synthetic records require explicit synthesis rules and non-historical status. The positive fixture’s `"documented_proxy_identity"` label does not establish those conditions.

**Required repair:** Enforce classification-specific evidence and unresolved-gap handling before clearing the 1957 gate. Preserve these actual legacy rows as blocked absent substantive supporting declarations. Replace the fixture’s unsupported anchor promotion with a contract-complete software example, and add both relabelling counterexamples as rejection tests.

### 2. P1 — Preserve excerpt temporal authorization when verifying event implementation claims

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:368–386,1190–1233`, especially `:1212`  
`tests/test_hist_source_admission.py`

Source admission validates excerpt windows, but the downstream event evidence index retains only approved **page numbers**. `_event_ready` requires the implementation date merely to parse; it does not bind the claimed observation to temporally authorized evidence.

**Independently exercised mutation:**

```python
events["events"][0]["observed_implementation_at"] = "1988-02-01"
```

Everything else remains the positive fixture: event date in 1966, source availability in 1966, and selected excerpt authorization only for **1966-01-01 through 1967-12-31**.

**Observed CLI result:** **exit 0 / structural PASS / historical PASS**.

Thus a claimed **observed** implementation in the reserved period is accepted using evidence authorized only for 1966–67. This is an admission/evidence-boundary defect, not evidence of actual runtime hold-out injection.

**Required repair:** Carry sufficient selected-excerpt authorization into event verification and require implementation observations to have supporting evidence within its permitted content window. Do not conflate future legal effective dates with observed execution. Add this single-field negative regression; retain the repaired independent availability/statistical-period checks.

### 3. P1 — Validate anchor scalar types before dictionary/set membership

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:924–925,935–936,959–960`  
Structural propagation: `:339–345`  
`tests/test_hist_source_admission.py`

Each independent mutation below produced an actual CLI **process exit 1, empty stdout and traceback**, rather than structured exit 2:

```python
crosswalk["records"][0]["variable_id"] = ["dwelling_anchor"]
crosswalk["records"][0]["classification"] = ["proxy"]
crosswalk["records"][0]["source_evidence_kind"] = ["proxy"]
```

Observed exceptions were `TypeError: unhashable type: 'list'` at lines **925**, **936** and **960**, respectively.

**Required repair:** Check scalar types before membership operations and raise the validator’s structural/semantic error type. Add subprocess regressions requiring exit 2, valid JSON and no traceback. Do not replace validation with a broad exception catch.

## Reproduction setup

The remaining defects were exercised through the real subprocess CLI, with writes confined to fresh temporary fixtures. This setup reproduces each independently:

```python
import json
import runpy
import tempfile
from pathlib import Path

h = runpy.run_path("tests/test_hist_source_admission.py")

with tempfile.TemporaryDirectory() as tmp:
    root = h["repo_root"].__wrapped__(Path(tmp))
    h["positive_repo"].__wrapped__(root)

    # Repair 3; substitute either other field/value listed above.
    path = root / "config/initial_state/hist_vnext_v1/anchor_crosswalk.json"
    data = json.loads(path.read_text())
    data["records"][0]["variable_id"] = ["dwelling_anchor"]
    path.write_text(json.dumps(data))

    completed = h["_run_cli"](root)
    print(completed.returncode, completed.stdout, completed.stderr)
```

Run with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python`. For repair 2, mutate `history/HIST_VNEXT/event_candidates/events.json` as specified. For repair 1, load the actual repository crosswalk and `role=="initial_state"` manifest metadata into the temporary package, then change only the classifications.

## Preservation, provenance and scope boundaries

- BASELINE matches HEAD and frozen SHA256  
  `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
- `DATA_MANIFEST_v1.json` matches HEAD and frozen SHA256  
  `5d91e014c2b80651eb87d3515147468cb84fe77430bf336ba52e357000e58fdd`. Manifest v2 also matches HEAD.
- All four batch-01 candidate paths, hashes and page counts match intake metadata. This is metadata consistency, not fresh restricted-PDF verification.
- Existing benchmark output and H4 C0/C1 provenance were inspected. All **18 manifest-listed output files per arm** in `C0_review4` and `C1_review4` were independently hashed with zero mismatches. Their manifests declare 16 commodities, 116 completed ticks and the frozen replay digests. No replay identity was independently recomputed and no new simulation was run.
- **H1A remains offline and declaration-only: no runtime wiring, no historical-input approval, and no production initialization or measurement authorization.** Real declarations remain four candidates, zero admitted sources, zero approved excerpts and 63 blocked anchors.
- No matching `src/` consumer of the reviewed admission/crosswalk declarations was found. No new state update, quarterly interpolation, stochastic experiment, single-good substitution or LLM-probability interpretation occurs in this repair.
- Broader accounting/material-balance correctness, stochastic independence and the strict full-file-byte gate were not re-certified. No full-suite run or fresh benchmark was performed.
- Restricted PDF/OCR contents, mixed-year XLS contents and historical target values were not opened. Prior exposure remains disclosed; this review does not restore hold-out blindness.
