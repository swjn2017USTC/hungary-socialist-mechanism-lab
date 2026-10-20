VERDICT: PATCH

## Observed evidence

This is a read-only technical re-review of H1A as currently implemented. The implementer’s resolution note is not treated as an independent verdict.

| Command exercised | Exit | Observed result |
|---|---:|---|
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py` | 0 | **20 passed in 0.23s** |
| `.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py` | 0 | All checks passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .` | 1 | Structural **PASS**, historical **BLOCKED**; 4 candidates, 3 works, 0 admitted sources, 63 blocked anchors, 5 blocked authorities, 10 candidate events, 4 review requests |
| `shasum -a 256 BASELINE.md data/manifests/DATA_MANIFEST_v1.json` | 0 | Both match the frozen hashes recorded in the H1A plan |

Additional read-only Python diagnostics exited 0 and established:

- All **63 current crosswalk rows** have distinct `(variable_id, path)` bindings matching the 63 legacy initial-state artifacts. Compared source IDs, hashes, grades, evidence statuses and dates had **zero mismatches**. Each variable family has 21 rows; all classifications are `blocked` and all per-row `runtime_connected` values are false.
- All **four candidate source hashes, paths and page counts** match the batch-01 intake manifest. This is metadata consistency, not independent PDF-byte verification.
- In-memory mutations and mocked file reads reproduced the defects below without changing repository files.

Read material included BASELINE first; both H1A plans, REPORT and REVIEW; the implementation, tests and requested artifacts; legacy manifest/artifact/unit declarations; intake provenance and exposure disclosure; the H4A-0 review’s H1A boundary statements; git status/diff and the H1A commit. Existing C0/C1 manifests and benchmark/provenance artifacts were inspected, not rerun. Their inspected manifests identify **2026-10-15 runs**, not fresh H1A verification. No full-suite, replay, accounting or benchmark execution was performed in this review.

## F1–F6 / R1–R5 disposition

| Finding | Current disposition |
|---|---|
| **F1 — cross-work shared roots** | **Specific repair works:** different works citing the same known root returned `independent=False`. Broader independence defects remain; see repair 3. |
| **F2 — rights handling** | **Partially repaired, not closed.** `license_status` is recognized, but `RightsSpec` is not reused and its evidence/enumeration validation is bypassed. |
| **F3 — admission evidence gates** | **Partially repaired, not closed.** Hash/page/period presence checks and excerpt-source matching exist. Provenance, page bounds, approval identity, permitted use and window are not substantively checked. |
| **F4 — forcing/actor purposes** | **Repaired for the named declarations.** Both `purpose="forcing"` and `"actor"` returned blocked; regression tests are present. |
| **F5 — malformed JSON** | **Partially repaired, not closed.** Six declaration files returned structured exit 2 for malformed JSON. A malformed legacy manifest still returned exit 1 / structural PASS. |
| **F6 — fabricated candidate SHA placeholders** | **Repaired in current artifacts against intake metadata.** All four hashes match the intake manifest. Arbitrary hashes can nevertheless pass the admission API; that is a separate validator defect under F3. |
| **R1 — legacy-anchor identity** | **Not resolved.** The argument remains in the function signature but is unused. Deleting the identity check without replacement leaves an independently reproduced contract hole. |
| **R2 — crosswalk fields/semantic IDs** | **Current artifact repair is present:** semantic variable IDs, source IDs, paths and false runtime flags match legacy metadata. Validation remains insufficient: arbitrary paths/variables and true runtime flags pass. |
| **R3 — regression coverage** | **Named additions present:** forcing, actor and excerpt-source mismatch tests pass. They do not establish the broader admission/crosswalk research invariants. |
| **R4 — unknown shared root** | **Named case repaired:** two records citing the same unknown root returned `independent=None`. Other unrooted records can still be reported independent. |
| **R5 — OS errors** | **Partially repaired, not closed.** `_load_json` catches `OSError`, but its failure when loading the legacy manifest is ignored and structural PASS survives. |

## Prioritized finite repair list

### 1. P1 — Restore a real legacy-artifact identity contract and enforce crosswalk semantics

**Paths:**  
`history/HIST_VNEXT/sources/admission.py:174–255,444–469`  
`tests/test_hist_source_admission.py:700–812`  
`docs/phases/HIST_VNEXT/H1A/REVIEW.md:67`

Original H1A §5 explicitly requires complete, duplicate-free coverage of the **63 legacy artifact IDs**, preserving their metadata. It does not merely require 63 unique, freely chosen anchor labels.

The following reproduces the central R1 hole using the current files:

```python
import json
from pathlib import Path
from history.HIST_VNEXT.sources.admission import validate_anchor_crosswalk

rows = json.loads(Path(
    "config/initial_state/hist_vnext_v1/anchor_crosswalk.json"
).read_text())["records"]
manifest = json.loads(Path("data/manifests/DATA_MANIFEST_v1.json").read_text())
ids = {a["artifact_id"] for a in manifest["artifacts"]
       if a["role"] == "initial_state"}

rows[0]["variable_id"] = "NOT_A_REGISTERED_VARIABLE"
validate_anchor_crosswalk(rows, legacy_artifact_ids=ids)  # returns normally
```

Observed separately, each of these first-row changes also passed validation:

- `anchor_id="invented_1957_orszagos_00"`
- `classification="invented"`
- `path="data/raw/does-not-exist.xls"`
- `runtime_connected=True`
- `classification="reconstructed"` with no transformation or supporting anchors
- `classification="direct"` together with rewriting both legacy/observation dates to `1957-01-01`

Through `audit_h1a`, mocked crosswalk inputs with an unknown variable, unknown anchor, true runtime flag, invented classification or all-zero source hash each retained **exit 1 / structural PASS**.

**Required repair:** Establish an unambiguous bijection to the legacy artifacts and validate the associated variable, source, path, hash, dates, grade and evidence status. Do **not** restore the mistaken equation `variable_id == artifact_id`; these are different identifiers. Enforce the classification enum and evidence requirements, false declaration-only runtime flags, valid supporting references and fixed top-level declaration contract. Add mutation tests against the real metadata relationship.

### 2. P1 — Validate rights and approved-excerpt provenance, rather than truthiness

**Paths:** `history/HIST_VNEXT/sources/admission.py:43–94,362,534–555`  
`tests/test_hist_source_admission.py:483–605`

A primary record with the required presence fields and this excerpt was admitted:

```python
record = {
    "source_id": "S", "source_type": "primary_institutional",
    "purpose": "institutional_context",
    "document_number": "D", "archival_reference": "A",
    "rights": {"license_status": "verified"},
    "source_sha256": "a" * 64,
    "pdf_pages": 1, "pdf_page_range": "1-1",
    "statistical_period": "1966",
    "source_available_at": "1966-07-01",
    "approved_excerpt_ids": ["X"],
}
excerpt = {
    "excerpt_id": "X", "source_id": "S",
    "content_hash": "b" * 64,
    "approved_by": "admin", "approved_at": "2026-10-16",
    "allowed_window": "1966-01-01/1966-12-31",
}
```

Observed one-at-a-time mutations still returned `{"status":"admitted","reasons":[]}`:

- `rights={"license_status":"invented"}`
- source and excerpt hashes changed to `"NOT_A_SHA256"`
- excerpt parent `source_sha256` changed to a different hash
- excerpt `pdf_pages=[999]`
- excerpt ID changed to `"NOT_APPROVED"`
- excerpt `allowed_window="1986-01-01/1988-12-31"` and `allowed_use="none"`

By contrast, independently invoking `RightsSpec.model_validate` rejected both the evidence-free `"verified"` declaration and the invented status.

There is also a multi-source defect: `audit_h1a` supplies the entire global excerpt register to every source. Adding a second source’s excerpt caused the otherwise admitted first source to be blocked for source-ID mismatch.

**Required repair:** Reuse `RightsSpec`; apply purpose-specific rights/evidence requirements; bind selected approved excerpt IDs to the source, parent hash, independently approved excerpt hash, valid pages, allowed use and permitted window. Preserve the external-review boundary without opening restricted originals. Filter the global register correctly per source. Test these mutations and a valid two-source package. The existing mandatory-archive test must also respect the original contract allowing a verifiable published document number without an archival reference.

### 3. P1 — Do not report shared or unrooted evidence as independent

**Path:** `history/HIST_VNEXT/sources/admission.py:123–158`

Observed inputs and outputs:

| Input pair | Current result |
|---|---|
| Different works, both `observation_ids=["root"]`, no cited IDs | `independent=True`, shared IDs empty |
| Same work, disjoint known observations | `independent=True` |
| One record without observations or citations; another with a known root | `independent=True` |

The shared-set calculation omits `obs_ids & other_obs`; work identity does not affect the independence decision; a global known-root set can conceal an individual record’s missing provenance.

**Required repair:** Include direct root overlap, preserve same-work non-independence, and require each record’s own traceable root before declaring independence. Add all three counterexamples alongside the repaired cross-work-citation and unknown-shared-root tests.

### 4. P1 — Propagate every required-file failure to structural exit 2

**Paths:** `history/HIST_VNEXT/sources/admission.py:314–336,444–453`

Using mocked `open` calls and the actual CLI entry point:

- Returning `"{"` for each of the six declaration JSON files produced **exit 2 / structural BLOCKED**.
- Returning `"{"` for `data/manifests/DATA_MANIFEST_v1.json` produced **exit 1 / structural PASS**, despite a logged JSON parse error.
- Raising `OSError` for that manifest likewise produced **exit 1 / structural PASS**.
- Returning valid JSON `[]` for `batch01_candidates.json` caused an uncaught `AttributeError: 'list' object has no attribute 'get'`.

**Required repair:** Return structural exit 2 immediately when the required manifest cannot load; validate container/record types before accessing them; exercise these cases through the CLI. A logged error must not coexist with structural PASS.

### 5. P1 — Prevent empty coverage from producing historical PASS

**Path:** `history/HIST_VNEXT/sources/admission.py:495–503`

An in-memory package containing:

- one primary source admitted by the current evaluator;
- its single excerpt;
- `authorities=[]`;
- `events=[]`;
- no independent observable patterns;

returned **exit 0 / structural PASS / historical PASS**. It still reported **63 blocked anchors and four REVIEW_REQUIRED requests**.

The gate checks only one admitted source, zero entries literally marked `"blocked"`, and no events literally marked `"candidate"`. Empty collections satisfy the latter conditions; independent patterns and coverage references are not verified.

**Required repair:** Validate required coverage and its evidence links, event readiness and the original independent-pattern requirement before claiming historical PASS. Empty, missing or unresolved coverage must fail closed. This concerns truthfulness of the existing CLI result, not a demand to acquire unavailable historical documents.

### 6. P2 — Restore metadata precision and the declared candidate schema

**Paths:**  
`history/HIST_VNEXT/sources/batch01_candidates.json:11–22,46–57,82–93,118–129`  
`history/HIST_VNEXT/event_candidates/events.json:50–81`  
`config/initial_state/hist_vnext_v1/anchor_crosswalk.json:18–19`  
`docs/phases/HIST_VNEXT/H1A/PLAN.md:67–76`

- Intake metadata supplies publication years, and September 1990 for Kenen; candidate records promote these to exact first-of-month/year dates and reuse them as exact availability dates without supporting evidence.
- E04’s month becomes `1972-11-01`; E05/E06’s years become January 1 dates. The original event contract explicitly forbids filling unknown dates this way.
- Events omit the declared minimum fields, including date precision, distinct enactment/effective/availability dates, source/page provenance and authority fields. Unknown values should remain explicit unknowns.
- The crosswalk’s generic `"1960 census proxy"` boundary description loses the documented **2011 fixed-boundary/definition** qualification; `"1957 autonomy law jurisdiction"` is unsupported in the inspected provenance.
- PLAN still expects 16 targeted tests while REPORT and the exercised suite contain 20.

**Required repair:** Preserve supported date precision and unknown availability; supply the declared candidate fields with explicit unknowns; retain the 2011-boundary caveat and label unresolved desired-boundary assumptions. Align phase documentation with actual checks and add invariant tests for these metadata constraints.

## Scope boundaries

- **H1A is an offline admission/crosswalk declaration only—not historical evidence, causal identification, numerical initialization or runtime wiring.**
- Current on-disk artifacts remain candidates/blocked declarations. No current 1960 row is classified direct, and no actual forwarding of those values into a 1957 runtime state was observed. The validator nevertheless accepts forged relabeling and wiring declarations.
- No `src/` runtime consumer of these H1A declarations was found. Offline H4 admission code references them; H4A-0’s review expressly does not close H1A’s pending re-review.
- No new quarterly interpolation, state/account updates, stochastic experiments or LLM-probability interpretation occur in this module. This review does not certify broader runtime accounting, material balance, replicate independence or historical validity.
- The prior incidental late-period exposure remains disclosed and referenced. Its preservation does **not** restore hold-out blindness.
- BASELINE’s observed hash is unchanged. The H4-specific evidence-policy revision in the current documentation diff does not repair H1A’s validator defects or supersede its identity contract.
- No files were edited and no new approval was signed.
