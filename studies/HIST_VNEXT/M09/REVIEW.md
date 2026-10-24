# H5F-F1 / M09 — independent review record

This file records the independent `phase-reviewer` reviews. The reviewer never
edited implementation files; it reconstructed the forecast matrix, chronology,
state chain, first stage, profile/repeat identity and C0/C1 identities from the
artifacts.

## Round 1 — verdict PATCH

Task `H5F1Review1` (configured @review `minimax-code-cn/MiniMax-M3:high`).

Confirmed independently: 48 issued/realized/residual pairs, exact MAE matrix
(108.750292 / 14.734604 / 170.492740 / 71.181518), first-stage delay change,
strict issue → kernel → realization chronology, single clock, `activity_realized
@ network.B` realized provenance, profile/repeat byte identity, gate
residuals, and the mechanical economic null (all requests capped at 100).

Repair list and resolution:

| Repair | Resolution | Evidence |
|---|---|---|
| P1 complete final evidence / acceptance | Full pytest, ruff, uv lock, baseline, C0/C1, acceptance executed and logged | run-root `commands.json`, `regression.json`, `logs/`, `ACCEPTANCE.json` |
| P2 mislabeled report digest | Canonical science digests separated from `sha256(science.json)` | REPORT §7 |
| P3 adapter accepted pre-close publication | `available_at >= quarter_end(measurement_quarter)` enforced in the write path; test added | adapter `_report_violation`; test suite |
| P4 post-loop failure had no certificate | Aggregation wrapped; `FAILED_SEEDS.json` + `BLOCKER_CERTIFICATE.json` written on failure; preserved failure artifact sealed and disclosed | runner failure path; `FAILED_SEEDS.json` |
| P5 report overclaims | 16 unique cells × 3 seed-identical replicates disclosed; continuity diagnostic explained; model-usage deviation disclosed; source hash labeled composite | REPORT §1/§5/§8 |
| P6 not independently sealed | Regenerated packages bound to final source/spec SHA | manifests |

## Round 2 — verdict PATCH

Task `H5F1ReviewFinal` (configured @review `minimax-code-cn/MiniMax-M3:high`).

Confirmed all P1–P6 substantively closed, acceptance PASS read-only, C0/C1 real
(`92f9ea0a…`/`e27ade6a…`, `c4810481…`/`632ee6a6…`, 116 ticks, 1957Q1–1985Q4),
full regression 1877 passed / 0 skipped / 0 failed, final-source binding, and
no target leakage or request echo.

Residual repair list and resolution:

| Repair | Resolution | Evidence |
|---|---|---|
| R1 missing `EVIDENCE_MANIFEST.json`, `REVIEW.md`, phase `REVIEW.md` | This file, `docs/phases/HIST_VNEXT/H5F-F1/REVIEW.md`, `EVIDENCE_MANIFEST.json` created; REPORT §8 lists only existing files | `ls studies/HIST_VNEXT/M09/`; manifest |
| R2 `verify` did not re-derive publication/delay schedule | `_verify_package` now re-derives the two expected measurement quarters from the arm delay and the exact publication date; `_issued_violation` also rejects pre-close availability; schedule-tamper and read-path tests added | runner verify block; test suite |
| R3 hand-edited preserved failure certificate | `FAILED_SEEDS.json` now states the certificate was added retroactively and that the runner auto-seals the path | study `FAILED_SEEDS.json` |

## Round 3 — verdict PATCH

Task `H5F1ReviewFinal3` (configured @review `minimax-code-cn/MiniMax-M3:high`).

Confirmed R1 and R3 closed, final-source binding, profile/repeat identity,
acceptance PASS, C0/C1 real, all report numbers reproduced.  Residual findings:

| Repair | Resolution | Evidence |
|---|---|---|
| P1 tamper helper dropped mutated rows, so cases passed for an empty-set reason | `_update_sidecar` now keeps every row; each case asserts its specific rejection message; schedule, prediction and timing cases added | test suite |
| P2 verify did not re-derive the prediction from the two report values, so a perfect-foresight forgery could pass | `_issued_violation` and `_verify_package` recompute raw/prediction/clipping; `older_value/newer_value` must equal the report values | adapter; runner verify |
| P3 verify did not bind issued availability to the report publication dates | `_verify_package` requires `older_available_at/newer_available_at/available_at` to equal the reports' published dates and the day-15 issue date | runner verify |
| P4 REVIEW/REPORT overstated the test evidence | This record and REPORT §7/§8 restated the exact verify re-derivations and tamper coverage | this file; REPORT |

All four packages were regenerated after the source change; final source
composite SHA is `eeb024efef5a37e621980940f4fb1a6f883d9f7e268189b913468286809bf128`
and test SHA is `afd383eeb9969c4838adb4d5304edf6c31ea470ccdcde79aa81dc4155eaa35c2`.
Full regression: 1877 passed / 0 skipped / 0 failed in 242.92 s; ruff, uv lock
and baseline verify exit 0; acceptance `acceptance-final3` PASS with no
failures.

## Round 4 — final independent verdict: PASS

Task `H5F1ReviewFinal4` (configured @review `minimax-code-cn/MiniMax-M3:high`).

The reviewer independently rebuilt a fresh smoke package, replayed every tamper
case, and observed one distinct, field-specific rejection reason per mutation
(unit, residual, realized date, witness, science hash, publication schedule,
perfect-foresight prediction, information timing, deleted cell). It also
confirmed the extra guards: schedule swap, `newer_available_at`, `available_at`,
report-value tamper and a self-consistent perfect-foresight forgery.

Confirmed: all Round-3 P1–P3 closed; final source/test/spec SHAs match the
regenerated packages; profile ≡ repeat (`98d99f5a…`); study digest
`d42db5c3…`; smoke digest `1b9b1b2e…`; acceptance PASS with no failures; C0/C1
real (`92f9ea0a…`/`e27ade6a…`, `c4810481…`/`632ee6a6…`, 116 ticks); full
regression 1877 passed / 0 skipped / 0 failed; EVIDENCE_MANIFEST 225/225 files
matched; no target leakage, no fake interpolation, no fabricated/missing/
out-of-whitelist artifact, no historical or registration change.

Non-blocking observations retained for future hardening (not defects in this
phase): verify does not cross-check report values/witnesses against the
package's own tick rows (reviewer closed that gap externally, 96/96); the
pre-close verify branch is redundant after the schedule check; early
`resource_usage` rows carry honest `null` RSS; the package regeneration round is
named `final4` while regression/acceptance is `final3` (cosmetic); the commit is
made only after this PASS.

**Final verdict: PASS.**

