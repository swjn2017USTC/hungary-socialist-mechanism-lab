# H1A prerequisite repair record

Authorization: user message 2026-10-20 explicitly limited this repair to the six H1A findings:
R1 legacy-artifact bijection, `RightsSpec`/excerpt provenance, shared-root independence,
structural exit-2 propagation, empty-coverage fail-closed, and date-precision/schema.
No H4A-1 experiment domain, production initialization, or measurement wiring was started.

## Files changed

| Path | Change |
|---|---|
| `history/HIST_VNEXT/sources/admission.py` | Rebuilt admission, shared-root, crosswalk, and audit gates |
| `tests/test_hist_source_admission.py` | Replaced implementation-pinning tests with behavioral boundary/error tests; added software-only positive fixture |
| `history/HIST_VNEXT/sources/batch01_candidates.json` | `RightsSpec` field shape; publication precision and explicit unknown availability |
| `history/HIST_VNEXT/event_candidates/events.json` | Explicit date precision, enactment/effective/availability fields, source/page/authority unknowns |
| `config/initial_state/hist_vnext_v1/anchor_crosswalk.json` | Added `legacy_artifact_id`; corrected 2011 fixed-boundary caveat; removed unsupported autonomy-law basis |
| `config/initial_state/hist_vnext_h4_v1/anchor_crosswalk.json` | Synced the embedded `legacy_record` snapshots to the repaired H1A rows; classifications/admissions unchanged |
| `docs/phases/HIST_VNEXT/H1A/PLAN.md` | Removed stale test-count expectations |

The old `H1A/REPORT.md` and `H1A/REVIEW.md` are preserved as historical records. This file is the
repair record; the independent verdicts are in `H1A_REREVIEW.md`,
`H1A_REREVIEW_ROUND2.md`, `H1A_REREVIEW_ROUND3.md`, `H1A_REREVIEW_ROUND4.md`, `H1A_REREVIEW_ROUND5.md`,
`H1A_REREVIEW_ROUND6.md`, `H1A_REREVIEW_ROUND7.md`, `H1A_REREVIEW_ROUND8.md`,
`H1A_REREVIEW_ROUND9.md`, `H1A_REREVIEW_ROUND10.md`, `H1A_REREVIEW_ROUND11.md`,
`H1A_REREVIEW_ROUND12.md`, `H1A_REREVIEW_ROUND13.md`, and `H1A_REREVIEW_ROUND14.md` (PASS).

## Findings and repair

1. **R1 legacy identity.** `validate_anchor_crosswalk` requires full `legacy_artifacts` metadata
   and a unique `legacy_artifact_id` per row. It checks all 63 artifacts are covered exactly once,
   matches variable, source, path, SHA, dates, grade, and evidence status, derives the canonical
   anchor/geography from the artifact identity, and derives `source_evidence_kind` from the
   authoritative `evidence_status`. A direct classification must also have 1957 observation and
   initial dates and a direct evidence status. Non-blocked classifications must match the
   authoritative evidence kind; proxy/synthetic rows need a transformation, no unresolved
   missing evidence, and a stated 1957 limitation. Actual unresolved legacy rows cannot be
   relabelled proxy or synthetic. `legacy_artifact_ids` alone is rejected.
2. **Rights/excerpt provenance.** `RightsSpec` validates rights; non-unknown statuses need a named
   licence, terms locator, quoted evidence, check date, and `download_allowed=true`. Excerpts bind
   source ID, parent SHA, content SHA, approved-by/at, allowed use, full period coverage, pages,
   and an independent `handoff` block whose content/source hashes and approval fields must match.
   A missing `pdf_pages` cannot bypass the page bound. The global register is filtered by the
   record's `approved_excerpt_ids`.
3. **Shared roots.** Direct root overlap, cited/root overlap, and same-work pairs are
   non-independent. A record without its own traceable root, or an unknown cited root, yields
   `None`, not `True`.
4. **Structural exit 2.** JSON/OS errors raise a structural error; top-level and nested container
   types are validated, including duplicate source/event/excerpt IDs, ID lists, page fields,
   excerpt `allowed_use`, `work_id`, `source_type`, `purpose`, and source
   `document_number`/`archival_reference` (a list, object, or boolean is not an identifier;
   the public evaluator rejects malformed identifiers even when the other alternative is valid).
   Source and event identifiers must contain non-whitespace text, so blank strings remain
   missing evidence. The public evaluator also rejects blank source/work IDs, blank selected
   excerpt IDs, and blank excerpt/handoff approval identities, not only the file-audit path.
   The `observable_pattern` description has the same non-whitespace requirement in both the
   evaluator and the historical pattern gate. A malformed legacy manifest,
   candidate list, excerpt register, authority list, or anchor supporting list is exit 2, never
   structural PASS or a traceback.
5. **Coverage and patterns.** Historical PASS requires two admitted sources with declared
   `observable_pattern` values and an independent admitted pair, verified authority coverage,
   and verified events bound to an admitted source hash and an approved excerpt page. Events need
   issuer, legal force, reviewer, granted authority, an observed implementation date, and a
   distinct implementation-evidence link; the authority's primary and implementation evidence
   sets must be disjoint. Each coverage row must name an institution/authority and a parseable
   institutional period; blank or unnamed coverage is not historical readiness.
   `observed_implementation_at` and the cited page must be covered by the
   same selected excerpt, so a page-3/1988 claim cannot combine a page-3 1966–67 excerpt with a
   page-4 1966–1988 excerpt. Empty authorities/events,
   candidate events, unverified authority
   statuses, overlapping evidence sets, absent sources, unapproved pages, invalid
   dates/rights/pages, duplicate identities, and non-admitted second patterns fail closed.
6. **Date/schema precision.** Candidate publication dates keep year/month precision and unknown
   availability. Slash intervals require exactly two ordered atomic year/month/day endpoints;
   extra endpoints, composite ranges embedded in an endpoint, and reversed ranges are rejected
   rather than normalized. Standalone ordered year ranges remain accepted. Excerpt windows must cover every declared
   availability and statistical period, not just one of them. Events carry explicit precision and unknown enactment,
   effective-from/to, availability, observed implementation, information rights, source/page,
   and authority fields; a year-only date cannot claim day precision. Crosswalk boundary text
   keeps the 2011 fixed-boundary qualification and no longer asserts an unsupported 1957
   autonomy-law jurisdiction.

## Evidence observed

```
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_hist_source_admission.py
# 135 passed

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py
# 198 passed

.venv/bin/ruff check --no-cache \
  history/HIST_VNEXT/sources/admission.py tests/test_hist_source_admission.py
# All checks passed

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .
# exit 1, structural PASS, historical BLOCKED (4 candidates, 0 admitted, 63 blocked anchors)

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.admission \
  --root . --verify-files
# exit 1, structural PASS, historical UNIDENTIFIED (14 candidates, 0 admitted, 0 approved)

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
# 1652 passed, 180 warnings in 107.32s

.venv/bin/hsm baseline verify --json
# exit 0

uv lock --check --offline
# exit 0, resolved 101 packages
```

The first three round-14 attempts returned `usage_limit_reached` under the old
`openai-codex/gpt-6.1-sol:high` selector; the failure record is
`H1A_REREVIEW_ROUND14_ATTEMPTS.md`. After the review model was changed to
`minimax-code-cn/MiniMax-M3:high`, the independent round 14 returned **PASS**; see
`H1A_REREVIEW_ROUND14.md`. That PASS is the prerequisite bound by the experiment review.

The positive audit fixture is a software contract (`positive_software_fixture_reaches_exit_0`);
it is not a historical source, value, or approval.

## Boundary

H1A remains an offline admission/crosswalk declaration. No historical input was admitted, no
1960 value was forwarded to 1957, and no runtime connection was created.
