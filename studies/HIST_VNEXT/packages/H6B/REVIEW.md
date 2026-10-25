# HIST_VNEXT H6B — independent review record

Reviewer: `phase-reviewer` via `@review`
(`minimax-code-cn/MiniMax-M3:high`), independent read-only session.  The
reviewer edited no repository file; all probes ran on clones under `/tmp` or
on the isolated cold checkout.  Full review texts are saved verbatim in
`reviews/round-1.md`, `reviews/round-2.md` and `reviews/round-3.md`.

## Round 1 — PATCH

The first review reproduced both exports, the cold git-archive export, the
tamper/restricted/symlink cases, C0/C1 bundles and the test suite, then found
P1–P7:

- P1 symlink escape through the restricted-path guard.
- P2 several real-card checks were asserted rather than derived.
- P3 the user-work snapshot stored git-octal paths as literals.
- P4 the isolated checkout index still pointed at main-repo outputs.
- P5 unsupported report line anchors.
- P6 a dead duplicate check key.
- P7 missing absolute repo/interpreter traceability and missing `REVIEW.md`.

All were repaired inside the H6B whitelist; the three complete cards and eight
blocked cards did not change classification.

## Round 2 — PATCH

The second review independently verified P1–P7 and found three bounded gates:

- P8 `load_evidence_manifest` was CWD-bound rather than `--root`-bound.
- P9 M01/M02/M04 sensitivity and counterevidence were still asserted.
- P10 residual non-supporting anchors on M02/M03/M06/M07.

Repairs: root-bound manifest (`root / "studies" / "manifest.json"`), permanent
CWD-foreign-manifest test; artifact-derived sensitivity and counterevidence for
M01/M02/M04 with permanent helper tests; JSON-pointer/report anchors that
support their claims.

## Round 3 — PASS

Final verdict: **PASS**.

The third review independently proved:

- P8 is non-vacuous: a foreign/invalid CWD manifest is ignored, while a
  corrupted root manifest exits 2.
- Six single-check P9 mutations each block the named check and flip the card to
  `complete=false`; the unmutated classification remains 3 complete
  (M01/M02/M04) and 8 blocked.
- P10 anchors resolve to supporting JSON/report content.
- Both exports rebuild byte-for-byte from the main checkout, a foreign CWD and a
  cold `git archive` checkout; `verify` exits 0.
- No restricted file is opened in git-only or local-data mode; no absolute
  path, OCR/translation/original excerpt or historical `SUPPORTED` claim is
  exported.
- 29/29 user snapshot paths and 20/20 protected hashes match; only the three
  H6B whitelist paths were added.
- Full suite: 1902 passed, 180 warnings.

## Residuals recorded by the PASS review

- R1 M09's sensitivity/counterevidence and some structural verdict literals
  remain asserted; M09 is permanently blocked by `negative_control`, and
  validator-covered contradictions abort the build.
- R2 M01's sensitivity check does not require all nine seed×cut ablation rows;
  editing only the existing root blocks `reproduction_bundle`.
- R3 a stale "17 passed" sentence in `failed_seeds.json` was corrected after the
  review to 25 contract tests / 1902 full-suite tests.  Documentation only.

These residuals do not change a scientific claim, the 3/8 classification or any
export byte.  Final independent PASS authorises only this evidence-only local
commit; it is not a historical SUPPORTED claim and does not authorise a push.
