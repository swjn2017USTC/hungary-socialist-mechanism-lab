VERDICT: PATCH

## Observed verification

Read-only audit; no repository files were edited and no data approval was signed. BASELINE was read first. Review material included the H1A review chain, repair record, original contract, phase documents, implementation, tests, declarations, scoped git diff, manifests, benchmark outputs and provenance. Round 11 was read from `history://H1AReReviewRound11`; its named Markdown artifact was absent from the working tree.

| Command exercised | Exit | Observed result |
|---|---:|---|
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py` | 0 | **183 passed in 4.33s** |
| `.venv/bin/ruff check --no-cache history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py` | 0 | All checks passed |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .` | 1 | Structural **PASS**, historical **BLOCKED**; 4 candidates, 0 admitted sources, 63 blocked anchors |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.admission --root . --verify-files` | 1 | Structural **PASS**, historical **UNIDENTIFIED**; 14 candidates, 0 admitted, **0 approved inputs** |
| Three independent falsification diagnostics using `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c …` | 0 each | **82 paired audit-API/subprocess cases**, direct evaluator checks, seven anchor rejection mutations, six shared-root cases and an injected manifest-read error |
| Metadata/output-hash diagnostic using the same interpreter | 0 | Preservation results below |
| Git status/log and scoped diff inspection | 0 | Existing changes inspected; no BASELINE diff |

The real-package exit-1 results are expected historical blocks, not crashes.

## Round-11 repair dispositions

| Requirement | Disposition |
|---|---|
| **Named institution/authority** | **Closed for exercised inputs.** Missing/null, empty, ASCII-whitespace, NBSP and other Unicode-whitespace names returned structured audit/subprocess **exit 1 / historical BLOCKED**. Non-string names also blocked. |
| **Nonblank institutional period** | **Closed for exercised inputs.** The same missing/blank/Unicode-whitespace substitutions returned structured historical blocks. |
| **Parseable period** | **Partially closed.** `not-a-period`, invalid month/day and an unknown interval endpoint blocked. However, malformed multi-endpoint intervals and reversed intervals still produce historical PASS; finding 1 below. |
| **Positive software fixture retained** | **Retained.** Unmodified fixture returned audit/subprocess **exit 0**, two admitted patterns and an independent pair. |
| **Real H1A remains blocked** | **Retained.** The actual CLI returned historical BLOCKED, with zero admitted sources and 63 blocked anchors. |

**The positive fixture is a software contract, not historical evidence.** Its successful exit establishes neither a real historical observation nor an actual approval.

## Remaining defect and finite prioritized repair

### 1. P1 — Malformed temporal declarations are converted into valid authorization ranges

**Paths:**

- `history/HIST_VNEXT/sources/admission.py:909–922` — `_date_bounds`
- `history/HIST_VNEXT/sources/admission.py:833–852` — excerpt authorization
- `history/HIST_VNEXT/sources/admission.py:1253–1257` — authority-period gate
- Regression coverage: `tests/test_hist_source_admission.py:1141–1170`

The documented grammar supports a date or an `a/b` interval. The implementation recursively parses interval endpoints and takes their minimum/maximum bounds. Consequently:

1. A string containing **three endpoints** is accepted as one interval.
2. A **reversed start/end interval** is silently reordered rather than rejected.

Each mutation below was exercised independently against a fresh positive fixture:

| Failing input | Audit API | Subprocess CLI |
|---|---|---|
| `authority.period="1966/1967/1968"` | **0 / PASS / PASS** | **0**, empty stderr |
| `authority.period="1967-12-31/1966-01-01"` | **0 / PASS / PASS** | **0**, empty stderr |
| `excerpt.allowed_window="1966/1967/1988"` | **0 / PASS / PASS** | **0**, empty stderr |
| `excerpt.allowed_window="1967-12-31/1966-01-01"` | **0 / PASS / PASS** | **0**, empty stderr |

Both malformed excerpt windows also returned:

```text
evaluate_source(...) → {"status": "admitted", "reasons": []}
```

This affects the original authorization boundary, not only presentation. An invalid approval-window declaration is converted into permission covering the fixture’s source availability and implementation observations. The nested interval ending in 1988 is interpreted as a continuous authorization extending through 1988. This is a validator acceptance defect; no actual historical hold-out injection was observed.

**Required bounded repair:**

1. In `_date_bounds`, accept either one supported date representation or exactly two supported, non-interval endpoints separated by one slash. Reject additional endpoints and reversed temporal ordering rather than normalizing them into permission.
2. Add isolated evaluator, audit-API and subprocess regressions for the four inputs above. Malformed authority periods must produce a structured historical block; malformed excerpt windows must prevent source admission and historical PASS. Preserve legitimate year/month/day precision and ordered interval positives.
3. Record the repair and exercised evidence in `docs/phases/HIST_VNEXT/H4A-1/H1A_REPAIR.md`. No runtime change, source acquisition or data approval is needed.

### Reproduction

The following is equivalent to the exercised diagnostic. Run using `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python`; writes remain confined to temporary fixtures:

```python
import json
import runpy
import tempfile
from pathlib import Path

from history.HIST_VNEXT.sources.admission import audit_h1a, evaluate_source

h = runpy.run_path("tests/test_hist_source_admission.py")

cases = [
    (
        "history/HIST_VNEXT/sources/authority_coverage.json",
        "authorities", "period", "1966/1967/1968",
    ),
    (
        "history/HIST_VNEXT/exposure/access_register.json",
        "approved_excerpts", "allowed_window",
        "1967-12-31/1966-01-01",
    ),
]

for relative, key, field, value in cases:
    with tempfile.TemporaryDirectory() as tmp:
        root = h["repo_root"].__wrapped__(Path(tmp))
        h["positive_repo"].__wrapped__(root)

        path = root / relative
        data = json.loads(path.read_text())
        data[key][0][field] = value
        path.write_text(json.dumps(data))

        result = audit_h1a(root)
        completed = h["_run_cli"](root)
        print(value, result["exit_code"], result["historical"])
        print(completed.returncode, completed.stdout, completed.stderr)

        if key == "approved_excerpts":
            print(evaluate_source(
                h["_primary_record"](),
                approved_excerpts=[h["_excerpt"](allowed_window=value)],
            ))
```

## Earlier finding rechecks

| Finding | Observed disposition |
|---|---|
| **Anchor bijection/classification/geography/evidence kind** | All 63 real rows validate against authoritative legacy metadata. Swapped geography, forged direct classification, changed hash, duplicate/omitted coverage and unresolved proxy/synthetic relabelling were rejected. |
| **Rights/excerpt handoff/pages/full period** | Evidence-free restricted rights, stale handoff hash, wrong parent hash, page 99 and missing page count blocked. Known availability did not bypass content declared through 1988. **Malformed interval grammar remains defective as described above.** |
| **Shared roots** | Distinct rooted works returned `True`; same work, direct overlap and cited overlap returned `False`; unknown citations and unrooted records returned `None`. |
| **Duplicate IDs/nested structural errors** | Duplicate source/event/excerpt IDs and exercised malformed nested containers returned structured exit 2. Null implementation evidence returned a structured historical block. |
| **Required-file errors** | Malformed JSON in all seven required files returned structured audit/subprocess exit 2. Injected manifest-read `OSError` returned audit exit 2. |
| **Date precision/event document-or-archive** | Year-only event date claiming day precision blocked. Either valid event identifier alone passed; neither identifier blocked. |
| **Authority evidence disjointness** | Partial primary/implementation overlap blocked. |
| **Same-excerpt page/window tuple** | Split page-3/1966–67 and page-4/1966–1988 permissions did not authorize page-3/1988. An unselected late excerpt did not authorize it; a selected matching page-4/1988 tuple passed. |
| **Two admitted patterns/role discipline** | Catalogue substitution, blank observable pattern, shared root and empty authority/event coverage prevented historical PASS. Forcing and actor purposes blocked. |
| **Blank public-API identities/approval evidence** | Unicode-whitespace source/work IDs, selected excerpt ID and matching approval identities prevented admission. |
| **H4A-0 preservation** | All 63 embedded legacy snapshots match H1A. H4’s header and every row field outside `legacy_record` match HEAD. All three approval sets remain empty. |

## Preservation and scope boundaries

- BASELINE matches HEAD and frozen SHA256  
  `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
- `DATA_MANIFEST_v1.json` matches HEAD and frozen SHA256  
  `5d91e014c2b80651eb87d3515147468cb84fe77430bf336ba52e357000e58fdd`. Manifest v2 also matches HEAD.
- All four batch-01 candidate paths, hashes and page counts match intake metadata. This is metadata consistency, not independent historical authentication.
- All **18 manifest-listed outputs per arm** in existing `C0_review4` and `C1_review4` were independently hashed with zero mismatches. Their manifests declare 16 commodities, 116 completed ticks and the frozen replay digests. No new simulation or replay-identity recomputation was performed.
- Existing benchmark repeats were inspected as performance/replay evidence, **not independent stochastic historical replicates**.

**H1A remains offline and declaration-only: no runtime wiring, no historical-input admission or approval, and no production initialization or measurement authorization.** Actual H1A declarations remain four candidates, zero admitted sources, zero approved excerpts and 63 blocked anchors.

No matching production consumer was found in `src/`. No target injection, state update, quarterly interpolation, single-good substitution or LLM-probability interpretation was observed in this repair. Broader accounting/material-balance correctness and stochastic independence were not re-certified.

Restricted PDF/OCR text, mixed-year XLS contents and historical target values were not displayed. Prior exposure remains disclosed; blindness is not restored. No full-suite run, fresh benchmark, source acquisition or strict full-file-byte-gate closure was performed.
