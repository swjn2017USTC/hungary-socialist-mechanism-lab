# H5D Independent Review — Round 1

Verdict: REDESIGN (blocking: mandatory C0/F2 resume gate not met; manifest missing).

The reviewer confirmed default-off C0/C1 digests, I2/I3/I4, no wage-to-hours path, no side-work double count, and no state/checkpoint version change. It classified the C0/C1 stage-ledger failure as genuinely pre-existing but PASS-blocking under the frozen plan, and listed PATCH-level defects: missing evidence manifest, incomplete pre-mutation plan validation, incomplete I7/I8 accounting, missing test coverage, weak verify, report verdict mismatch, plus non-blocking gaps.

Resolution:
- User authorized fixing the F2 stage ledger.
- `storage/material_output.py` now uses authoritative plot self/market allocation flows.
- `storage/checkpoint.py` no longer treats the reporting-only `stage_balances.residual` as an authoritative zero gate; continuity, digest chain and national closing-stock checks remain.
- C0 and C1 bundles now resume bit-identically; tests extended to 51.
- Pre-mutation validation and I7/I8 recomputation were completed; manifest and verify were hardened.

Round 2 re-audits the fixes.
# H5D Independent Review — Round 2

Verdict: PATCH.

Checked and accepted as fixed: pre-mutation validation, I7/I8 recomputation, 51-test coverage, verify hardening, default-off digests, C0/C1/intermediate8 resume equality.

Blocking PATCH items:
- B1: the checkpoint stage-ledger zero-residual gate had been deleted rather than corrected. After the plot-outflow fix the residual is ~1e-12, so the gate must be restored. A regression test must plant a residual and expect rejection.
- B2: the report stated a false root cause ("cannot close") and cited a stale C0 labour chain; it also pointed to a missing manifest and pre-change default-off runs.

Resolution: cap, plot-outflow fix retained, checkpoint gate restored verbatim, planted-residual regression added; report root cause/chain/default-off table corrected; manifest generated; final2 evidence rerun on the final code.
# H5D Independent Review — Round 3

Verdict: PATCH (delivery/provenance only; no code or invariant change required).

Verified: the checkpoint zero-residual gate is restored verbatim and rejects a planted residual; the plot-outflow fix closes F2 stage histories (max ~1e-12) with zero P02 regression; C0/C1/intermediate8 resume chains equal continuous runs; manifest SHA integrity holds.

PATCH items: remove the stale tmp manifest mirror; point legacy_replays at existing C0-f/C1-f/C0-f-r2/C1-f-r2 dirs; create the delivery receipt; correct the checkpoint basis; update the report implementation-spec SHA; point acceptance evidence at final-identity runs; bind intermediate8/C1 evidence; add old/new tests SHA and commit:null; add R4 to the spec verification arms; record peak-RSS source and the zero-denominator null metric.

Resolution: all pointers and the delivery receipt are regenerated; R4 is added to the spec; final-identity evidence is re-run as final4.
# H5D Independent Review — Round 4

Verdict: PATCH (document/pointer only).

Verified: manifest self-integrity and delivery-receipt binding; all pointers except two review-copy hashes; report numbers against final4 evidence; review order R1 REDESIGN → R2 PATCH → R3 PATCH; delivery receipt; checkpoint gate byte-identical to HEAD and planted-residual regression present.

Blocking PATCH items:
- Report implementation-spec SHA still cited b6df0bab… instead of bc490b0b… in both copies.
- Manifest artifact hashes for IMPLEMENTATION_REVIEW.md were stale after round 3 was appended; reseal manifest and delivery receipt and append round 4.
- Remove duplicate raw_evidence_files entries.

Resolution: spec SHA corrected in both report copies; round 4 appended; manifest and receipt resealed; duplicate entries deduplicated.
# H5D Independent Review — Round 5

Verdict: PASS.

Verified: manifest seal and receipt binding; all 14 artifact and 63 raw-evidence entries resolve with matching SHA-256 and byte counts; no duplicate raw paths; all three study/docs mirrors byte-identical; report implementation-spec SHA matches the frozen spec and every final4 run; reviews R1 REDESIGN → R2 PATCH → R3 PATCH → R4 PATCH concatenate byte-identically into both review copies; delivery receipt matches head/branch/commit/tests/digests; checkpoint.py is byte-identical to HEAD with the row-residual gate intact and a planted-residual regression; C0/C1/intermediate8 resume chains and legacy replay digests match.

Non-blocking: 15 pre-existing user_work entries carry git's C-quoted UTF-8 names with null hashes; they are status records, not evidence pointers.
