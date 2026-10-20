# HIST_VNEXT H4A-0 — source verification, statistical admission, candidate crosswalks

Run: 2026-10-20. Scope is H4A-0 only. No production initialization, no engine wiring, no H4A-1/H4B/H4C/H5.

## Contract

- Start from the live branch and record dirty user files; never stage or overwrite them.
- Read the 05/06 revisions and prior phase records; preserve the H1A PATCH gap, H3F-D3
  `UNIDENTIFIED` / strict byte-gate gap, and H3G structural null. A digest match is not a
  full-file byte proof and does not create an exception.
- The 2026-10-20 H4 policy removes archive availability as an independent execution gate.
  It does not relax the old source validator, frozen research contracts, HOLD isolation,
  technical regression, or independent review.
- Technical, structural, historical-evidence, and future-wiring verdicts are separate.
  An empty `APPROVED_INPUT_SET` is a valid candidate/gap delivery.
- Whitelist only the H4A-0 documents, `history/HIST_VNEXT/h4_sources/`,
  `config/initial_state/hist_vnext_h4_v1/`, and
  `tests/test_hist_h4_source_crosswalk.py`. Private transcripts/logs go under
  `data/private/hist_vnext_h4a0/<run-id>/` and `outputs/hist-vnext-h4a-0-<run-id>/`.
- The source packages are read-only; no PDF, image, OCR text, restricted excerpt, or
  cell value is committed.

## Steps

1. Record start revision, dirty files, existing phase evidence, and the actual model roles.
2. Read both intake packages and their metadata; run both package `verify_intake.py`
   checks. Separate metadata reads from body reads.
3. Declare 11 original PDFs in `sources.json`: four batch01 chapter files (three works;
   the two IMF 1991 chapters share `work_id`) and seven yearbooks. Keep original source
   IDs, hashes, paths, page counts, publication basis, and rights status.
4. Record local review, value reuse, upload, redistribution, and HOLD approvals separately
   in `access_register.json`. Unknown rights stay unknown; workflow authorization is not a
   licence.
5. Implement `evaluate_statistical_candidate`, `validate_h4_crosswalk`,
   `validate_shared_observations`, and `audit_h4a0` in
   `history/HIST_VNEXT/h4_sources/admission.py`, with
   `python -m history.HIST_VNEXT.h4_sources.admission --root . [--verify-files]`.
6. Create D08 candidates from non-HOLD pages: 1957-01-01 national population (1956 p20 and
   its 1957 p21 reprint), 1956 year-end national housing stock (1956 p279 and its 1957 p349
   reprint), a blocked 1960 household-definition witness, and a blocked regional-population
   candidate without a boundary crosswalk.
7. Create D09 method/observation candidates: 1959 IO method (1960 p401-402) and the 1972
   consolidated matrix (1973 p94-97 as one observation). Do not open HOLD matrix pages, do
   not build a 14x14 physical recipe.
8. Create D10 definition candidates and a definition-to-measurement crosswalk. Physical
   `household_consumption` is at most a proxy; devizaforint trade values and CPI have no
   direct physical counterpart. Do not invent a rebasing or currency conversion.
9. Audit all 63 legacy anchors one-to-one. Check file existence and SHA without opening the
   xls payloads. Preserve the legacy 1960/C/literature-proxy blocked classification.
10. Leave `APPROVED_INPUT_SET.json` empty unless a candidate actually passes the value-use
    and rights gate. Emit narrow requests for HOLD pages and missing 1957 household/regional
    housing evidence.
11. Run the package checks, H4 CLI smoke with `--verify-files`, permanent tests, old H1A
    audit, full suite, baseline verify, C0/C1 frozen regressions, and run-identity checks.
12. Invoke the independent `phase-reviewer`; repair only whitelisted defects; re-run
    affected checks and re-review until PASS; then commit only the H4A-0 files.

## Acceptance

- Structural PASS with truthful exit 1 (candidate/blocked gaps) for the real package.
- Unknown rights, HOLD without a narrow approval, sample-household substitution, later
  observations as direct 1957, target-as-forcing, publication-as-reference, forged
  admissions, duplicate/missing anchors, and runtime connections all fail closed.
- Existing H1A CLI remains exit 1 / structural PASS / historical BLOCKED.
- C0/C1 digests match the frozen pins; full suite and baseline verify pass.
- Independent review returns PASS before any commit.
