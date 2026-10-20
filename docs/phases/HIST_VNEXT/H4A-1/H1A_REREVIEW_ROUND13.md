VERDICT: PATCH

## Observed verification

Read-only audit. BASELINE was read first, followed by the H1A review chain, repair record, original contract, phase documents, current implementation, tests, declarations, git diff, manifests, benchmark output and provenance. Round 11’s Markdown artifact is absent; its review was read from `history://H1AReReviewRound11`.

No repository files were edited and no data approval was signed.

| Command exercised | Exit | Observed result |
|---|---:|---|
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py` | 0 | **189 passed in 4.88s** |
| `.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py` | 0 | All checks passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .` | 1 | Structural **PASS**, historical **BLOCKED**; 4 candidates, 0 admitted sources, 63 blocked anchors |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.admission --root . --verify-files` | 1 | Structural **PASS**, historical **UNIDENTIFIED**; 14 candidates, 0 admitted, **0 approved inputs** |
| Three independent diagnostics using `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c …` | 0 each | **97 paired audit-API/subprocess cases**, direct evaluator/parser checks, seven anchor rejection mutations, six shared-root cases, injected manifest-read error, and preservation/output hashing |
| Git status, scoped diff, log and HEAD comparisons | 0 | Existing changes inspected; preservation results below |

Both real-package exit-1 results are expected historical blocks, not crashes.

## Round-12 repair disposition

| Requirement | Observed disposition |
|---|---|
| Reject three slash-separated endpoints | **Closed for the named inputs.** `1966/1967/1968` and `1966/1967/1988` parse as invalid and produce structured historical blocks. Malformed excerpt windows prevent source admission. |
| Reject reversed date endpoints | **Closed for the named input.** `1967-12-31/1966-01-01` is rejected through parser, evaluator, audit API and subprocess CLI. |
| Preserve legitimate precision and ordered intervals | **Retained.** Year/month/day parsing and source-admission positives remain; ordered year, month and day intervals pass. Standalone ordered hyphenated year ranges remain supported. Event observations outside a narrower valid window still block historically. |
| Accept exactly one supported representation or two non-interval endpoints | **Not closed.** A slash endpoint may itself contain a hyphenated year interval. The resulting composite can discard a declared endpoint or expand authorization; finding 1 below. |
| Positive software package | **Retained.** Unmodified fixture returns API/subprocess exit 0, with two admitted patterns and one independent pair. |

**The positive fixture is a software contract, not historical evidence.** Its successful result establishes neither a real source nor an actual approval.

## Remaining defect and finite prioritized repair

### 1. P1 — A slash endpoint can itself be an interval, bypassing the two-endpoint grammar and full-period check

**Paths:**

- `history/HIST_VNEXT/sources/admission.py:909–925` — `_single_date_bounds` accepts a complete `YYYY-YYYY` interval.
- `history/HIST_VNEXT/sources/admission.py:946–964` — `_date_bounds` uses that same interval-capable parser for both slash endpoints, then returns only `left[0]` and `right[1]`.
- Downstream consumers: `:833–852` and `:1278–1283`.
- Regression coverage: `tests/test_hist_source_admission.py:1174–1201`.

The new slash-count check rejects the four round-12 examples, but does not enforce the required **non-interval endpoint** grammar.

Independently observed parser results:

```text
_date_bounds("1966-1988/1967")
    → (1966-01-01, 1967-12-31)

_date_bounds("1966/1967-1988")
    → (1966-01-01, 1988-12-31)

_date_bounds("1966-1988/1967-1968")
    → (1966-01-01, 1968-12-31)
```

These composite declarations contain more than two temporal endpoints. The first and third silently discard the left interval’s 1988 endpoint.

Starting independently from a fresh positive fixture:

| Single-field mutation | Evaluator | Audit API / subprocess CLI |
|---|---|---|
| `authority.period="1966-1988/1967"` | Not applicable | **0 / historical PASS** |
| `excerpt.allowed_window="1966-1988/1967"` | **admitted** | **0 / historical PASS** |
| `source.statistical_period="1966-1988/1967"` | **admitted** | **0 / historical PASS** |

All three subprocesses emitted structured JSON with empty stderr.

The statistical-period case demonstrates the substantive consequence: the default excerpt authorizes only **1966–1967**, but a malformed declaration containing a content interval through **1988** is truncated to 1967 and admitted. This is a validator acceptance defect—not evidence that actual historical hold-out values entered runtime.

### Reproduction

Run with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python`. Writes are confined to temporary software fixtures:

```python
import json
import runpy
import tempfile
from pathlib import Path

from history.HIST_VNEXT.sources.admission import (
    _date_bounds,
    audit_h1a,
    evaluate_source,
)

h = runpy.run_path("tests/test_hist_source_admission.py")
bad = "1966-1988/1967"

print(_date_bounds(bad))
record = h["_primary_record"]()
record["statistical_period"] = bad
print(evaluate_source(record, approved_excerpts=[h["_excerpt"]()]))

cases = [
    (
        "history/HIST_VNEXT/sources/authority_coverage.json",
        "authorities", "period",
    ),
    (
        "history/HIST_VNEXT/exposure/access_register.json",
        "approved_excerpts", "allowed_window",
    ),
    (
        "history/HIST_VNEXT/sources/batch01_candidates.json",
        "records", "statistical_period",
    ),
]

for relative, key, field in cases:
    with tempfile.TemporaryDirectory() as tmp:
        root = h["repo_root"].__wrapped__(Path(tmp))
        h["positive_repo"].__wrapped__(root)

        path = root / relative
        data = json.loads(path.read_text())
        data[key][0][field] = bad
        path.write_text(json.dumps(data))

        result = audit_h1a(root)
        completed = h["_run_cli"](root)
        print(field, result["exit_code"], result["historical"])
        print(completed.returncode, completed.stdout, completed.stderr)
```

**Required bounded repair:**

1. Separate atomic year/month/day endpoint parsing from standalone year-range parsing. Preserve legitimate standalone `1968-1985`, but reject a year interval embedded on either side of `/`.
2. Add isolated parser, evaluator, audit-API and subprocess regressions for the three composite forms above. Exercise authority periods, excerpt windows and source statistical periods; malformed declarations must not authorize admission or historical PASS.
3. Record the repair and exercised evidence in `docs/phases/HIST_VNEXT/H4A-1/H1A_REPAIR.md`. Preserve the valid precision/interval positives and prior review records.

No runtime change, source acquisition or data approval is needed.

## Earlier finding rechecks

| Finding | Observed disposition |
|---|---|
| **Anchor bijection/classification/geography/evidence kind** | All 63 real rows match authoritative legacy metadata. Swapped geography, forged direct evidence, changed hash, duplicate/omitted coverage and unresolved proxy/synthetic relabelling were rejected. |
| **Rights/excerpt handoff/pages/full period** | Evidence-free restricted rights, stale handoff hash, wrong parent hash, page 99 and missing page count blocked. Ordinary `statistical_period="1966/1988"` remained blocked despite known 1966 availability. **Composite interval bypass remains as described above.** |
| **Shared roots** | Distinct rooted works returned `True`; same work, direct overlap and cited overlap returned `False`; unknown citations and unrooted records returned `None`. |
| **Duplicate IDs/nested structural errors** | Duplicate source/event/excerpt IDs and exercised malformed nested containers returned structured exit 2. Null implementation evidence returned a structured historical block. |
| **Required-file errors** | Malformed JSON in all seven required files returned structured API/subprocess exit 2. Injected manifest-read `OSError` returned API exit 2. |
| **Date precision/event document-or-archive** | Year-only event date claiming day precision blocked. Either valid event identifier alone passed; neither identifier blocked. |
| **Authority identity/period/disjointness** | Unicode-whitespace identity and period blocked. Partial primary/implementation overlap blocked. Period grammar remains incomplete under finding 1. |
| **Same-excerpt page/window tuple** | Split page-3/1966–67 and page-4/1966–1988 permissions did not authorize page-3/1988. An unselected late excerpt did not authorize it; a selected matching page-4/1988 tuple passed. |
| **Two admitted patterns/role discipline** | Catalogue substitution, blank observable pattern and empty authority/event coverage prevented historical PASS. Forcing and actor purposes blocked. |
| **Public approval identity** | Matching Unicode-whitespace excerpt/handoff approver identities prevented admission. |
| **H4A-0 preservation** | All 63 embedded legacy snapshots match H1A. H4’s header and every row field outside `legacy_record` match HEAD. All three approval sets remain empty. |

## Preservation and scope boundaries

- BASELINE matches HEAD and frozen SHA256  
  `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
- `DATA_MANIFEST_v1.json` matches HEAD and frozen SHA256  
  `5d91e014c2b80651eb87d3515147468cb84fe77430bf336ba52e357000e58fdd`. Manifest v2 also matches HEAD.
- All four batch-01 candidate paths, hashes and page counts match intake metadata. This is metadata consistency, not independent historical authentication.
- All **18 manifest-listed outputs per arm** in existing `C0_review4` and `C1_review4` were hashed with zero mismatches. Their manifests declare 16 commodities, 116 completed ticks and the frozen replay digests. No simulation or replay-identity recomputation was performed.
- Existing benchmark repeats were inspected as performance/replay evidence, **not independent stochastic historical replicates**.

**H1A remains offline and declaration-only: no runtime wiring, no historical-input admission or approval, and no production initialization or measurement authorization.** Actual declarations remain four candidates, zero admitted sources, zero approved excerpts and 63 blocked anchors.

No matching production consumer was found in `src/`. No target injection, state update, quarterly interpolation, single-good substitution or LLM-probability interpretation was observed in this repair. Broader accounting/material-balance correctness and stochastic independence were not re-certified.

Restricted PDF/OCR text, mixed-year XLS contents and historical target values were not displayed. Prior exposure remains disclosed; blindness is not restored. No full-suite run, fresh benchmark, source acquisition or strict full-file-byte-gate closure was performed.
