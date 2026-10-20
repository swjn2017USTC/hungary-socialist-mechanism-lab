# H4A-0 independent review record

Reviewer role: `.omp/agents/phase-reviewer.md` (`model: @review`). The reviewer is read-only and
returns PASS/PATCH/REDESIGN. Implementation repairs are listed in `REPORT.md`; they are not
presented as independent reviewer text.

## Round 1 — PATCH (2026-10-20)

Verdict: **PATCH**. The reviewer accepted the empty-input delivery as truthful but found the
admission code did not enforce several claimed research gates.

Prioritized findings:

1. Exact cell values and quoted footnotes in commit-bound `candidate_overlay.json` and
   `ANCHOR_CROSSWALK.md`.
2. Numerical admission did not require `value_ref`, verified-by/verification record, table/row/
   column, or absence of unresolved missing/block reasons; a definition-only candidate could be
   admitted.
3. HOLD approval matched only non-empty purpose, made year/use/row-column scope optional, and an
   unapproved HOLD candidate was merely `candidate`; the exposure disclosure contradicted itself.
4. Direct initial state accepted 1959/1987; regional scope could pass without an evidenced
   boundary; uses could exceed the role; an approved entry could cross roles/sets.
5. `validate_h4_crosswalk` accepted a forged legacy snapshot/hash and `--verify-files` did not
   hash the 63 anchor files or bind both artifact manifests.
6. Shared-root computation omitted direct observation-ID intersection; the static file had fewer
   pairs than the report; secondary material could be promoted to a numerical input.
7. 1968 p370 was described as a 1968 observation although its columns are 1960/1966/1967; two
   private transcripts had transcription errors.
8. Malformed approved entries raised `AttributeError` instead of a structured exit 2.

Reviewer verification at that round: both intake verifiers passed; H4 CLI `--verify-files` exit 1,
structural PASS, 14 candidates (0 admitted/11 candidate/3 blocked); targeted H4+H1A 48 passed; old
H1A exit 1/structural PASS/historical BLOCKED; ruff passed; C0/C1 identities matched. The reviewer
accepted omitting additional H3 4Q/16Q/116Q experiments and preserved the H1A, H3F-D3 and H3G
gaps and the DeepSeek-vs-MiniMax role deviation.

## Round 2 — PATCH (2026-10-20)

Verdict: **PATCH**. Repairs closed the round-1 examples but new fail-open paths remained:

1. Source identity skipped a source whose SHA was absent from the manifest; substituting
   `BASELINE.md` with its own hash could pass with `--verify-files`.
2. A verbatim Hungarian comparison-price footnote remained in commit-bound JSON.
3. HOLD authorization accepted a partial period (approval for one endpoint year only).
4. Initial state accepted `1956-01-01`, `1957-12-31`, and an annual flow with a transformation
   substring.
5. Anchor promotion ignored the linked candidate's role/admission; a blocked measurement
   candidate could promote an admitted anchor.
6. Approved entries were not bound to source/hash/page/value_ref provenance; the positive fixture
   was not a numerical source example.
7. Shared-root logic dropped work identity and treated an unrooted record as independent.
8. Malformed measurement container / malformed `value_ref` could still raise.

Reviewer verification at that round: targeted H4+H1A 70 passed; H4 `--verify-files` exit 1,
structural PASS, 14 candidates (0/11/3), 0 approved; full-suite log 1524 passed; C0/C1 identities
matched; Pécs and 1957 construction/destruction transcript corrections and 1968 p370's
1960/1966/1967 columns agreed with the page images; HOLD exposure disclosure was consistent and
no candidate used those pages.

## Round 3 — PATCH (2026-10-20)

Verdict: **PATCH**. Remaining issues:

1. Authoritative source validation still failed open when both manifests were absent, allowed a
   forged batch01 source ID, accepted non-canonical paths by suffix, and skipped page/HOLD checks
   when `page_index.csv` was missing.
2. The repair-history row in `REPORT.md` still published the corrected Pécs cell; the delivery
   test only covered candidate JSON.
3. Nested malformed `value_ref.path` (list) and `measurement.candidate_ids=null` escaped as
   `TypeError`/process exit 1.
4. The positive fixture PDF was blank, declared 10 pages, and had no authoritative fixture
   manifest/index.
5. `REVIEW.md` was absent, so the prior independent-review lineage was not persisted.

Reviewer verification at that round: targeted H4+H1A 79 passed; real H4 `--verify-files` exit 1,
structural PASS, 14 candidates (0/11/3), 63 anchors, 0 approved; 19 declared shared pairs exactly
matched 19 expected pairs; exact opening-date, annual-flow, HOLD-period, linked-candidate,
same-work and unknown-root cases were rechecked; C0_final/C1_final identities matched; full-suite
log 1533 passed. The reviewer again accepted omitting additional H3 4Q/16Q/116Q experiments and
preserved the H1A/H3F-D3/H3G gaps and model-role deviation.

## Round 4 — PASS (2026-10-20)

Verdict: **PASS**. Scope is the H4A-0 candidate/gap delivery only; it is not historical validation
or authorization for production wiring.

Reviewer evidence:

- Read BASELINE, phase plans/report, repaired implementation, declarations, crosswalks, tests,
  `REVIEW.md`, current git diff, manifests, provenance and final logs. No source files edited.
- Independently ran H4+H1A targeted tests: **83 passed**. Ruff passed. Reviewed
  `logs/pytest_full_round3.txt`: **1537 passed**; did not rerun the full suite.
- Real H4 `--verify-files`: exit **1**, structural valid, **14 candidates: 0 admitted / 11
  candidate / 3 blocked**, **63 anchors**, **9 measurement mappings**, **0 approved inputs**,
  **19 non-independent pairs**.
- Both authoritative intake verifiers passed: batch01 **112 hashed files / 4 PDFs**; batch02
  **1943 hashed files / 7 originals / 3553 page metadata rows**.

Round-3 findings verified closed:

1. Manifest/identity bypasses: absent manifests and absent page index return required metadata
   errors; unmatched sources, forged batch01 IDs and non-canonical paths are rejected.
2. Restricted delivery: the delivery test passed; an independent search found no `Pécs` followed
   by digits or `value=<digits>` in commit-bound H4 Markdown/JSON.
3. Malformed nested payloads: list-valued `value_ref.path` and null measurement `candidate_ids`
   both returned structured exit 2 / structural BLOCKED without exceptions.
4. Positive numerical fixture: independently parsed the generated PDF (one page containing the
   stated table/row/column/value); canonical manifest/index, hashes and transcript passed
   `verify_files=True`; audit returned exit 0 with one admitted candidate and one approved input.
5. Review lineage: `REVIEW.md` exists and records rounds 1–3, distinguishing repairs from
   independent review.

Research boundaries:

- No `src/` consumer of the new H4 declarations; no production state, forcing, recipe or parameter
  change.
- Later observations and household samples are not promoted into direct 1957 inputs; monetary
  trade/IO statistics are not converted into physical flows or recipes; reprints/continuation
  pages retain shared-root treatment.
- The inadvertent HOLD-text exposure remains disclosed and excluded; those pages are not
  represented as unseen.
- Independently verified `C0_review4` and `C1_review4`; digests match the frozen pins. Baseline and
  offline lock checks passed.
- The reviewer accepted omitting additional H3-specific 4Q/16Q/116Q experiments because the new
  declarations have no runtime consumer and those scans would not exercise the new admission
  gates.

This verdict does **not** resolve the DeepSeek-vs-MiniMax implementation-role deviation, H1A's
pending independent re-review, H3F-D3's historical UNIDENTIFIED/full-file-byte gap, or H3G's
same-tick household structural null and missing standalone review artifact. H4A-1 receives no
approved numerical input from this delivery.
