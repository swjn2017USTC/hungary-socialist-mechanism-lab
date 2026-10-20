# H4B Pilot A — evidence/hypothesis freeze and technical blocker package

Status: **BLOCKED (technical)**. This plan authorizes no pilot execution and no engine change.
Phase: HIST_VNEXT H4B, per `H4B_PILOT_A_阻断包_PLAN.md`.
Execution date: 2026-10-20 (UTC 2026-10-20T18:11Z output root).

## 1. Frozen start state and execution identity

| Item | Observed value |
|---|---|
| Repository | `/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab` |
| HEAD | `92d727f8762e6493db0ac5ac2634cdbb13f3597b` |
| Branch | `codex/audit-hsm-vnext-2026-10-11` |
| Tracked dirty | `.omp/config.yml` (`2e90b9c6…`), `docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md` (`bc45bc84…`), `docs/upgrade_review/HIST_VNEXT/06_OMP_MINIMAX_HANDOFF.md` (`5fcb75b4…`) |
| Untracked user files | `docs/upgrade_review/HIST_VNEXT/09_BATCH02_YEARBOOKS_D08_D10_INTAKE.md` plus 12 untracked root `*_PLAN.md` documents (11 pre-existing + this step's plan) |
| H4 policy hashes | 05 = `bc45bc8498ad2c43e80b638b82280765c90dac6e49dfa33a5313fca37bbdd1a1`; 06 = `5fcb75b444dfaa6bacaf17b4e1b68d9ccd7ad8c45ab4f089cb4f6bcfd4ace393` — both match the plan's frozen values |
| Frozen files | `BASELINE.md` = `1f5b233f…`; `config/research_contract.json` = `6f54522a…`; `uv.lock` = `9fd79b62…` — all match the plan's pins |

No user file was reset, overwritten, staged, or normalized. The H4A-1 REVIEW line 62 requirement
(stage the earlier H1A repair files together with H4A-1) is not applicable here because this step
commits only the nine H4B files; the H1A repair files are already part of the committed history at
HEAD and are not dirty in this working tree.

### Roles actually used

| Role | Configured | Actual |
|---|---|---|
| Plan | `openai-codex/gpt-6.1-sol:high` | not invoked as a separate agent; the frozen plan is the user-supplied `H4B_PILOT_A_阻断包_PLAN.md` |
| Default implementation | `minimax-code-cn/MiniMax-M2.7-highspeed:medium` | runtime selector `deepseek/deepseek-flash` (session model; recorded as a deviation, not silently claimed as MiniMax) |
| Review | `minimax-code-cn/MiniMax-M3:high` | `phase-reviewer` subagent; selector recorded in this step's report |
| Commit | `deepseek/deepseek-flash` | used only after independent PASS |

Tokens/cache/paid cost are not exposed by the runtime → `NOT_MEASURED` (never recorded as 0).

## 2. Deliverable scope (whitelist)

Only these files may be created or edited, all under `docs/phases/HIST_VNEXT/H4B/`:

1. `PLAN.md`
2. `ASSUMPTION_LEDGER.md`
3. `ORIGINAL_AUTHORITY_MATRIX.md`
4. `SOURCE_MANIFEST.json`
5. `INPUT_MANIFEST.json`
6. `MEASUREMENT_MANIFEST.json`
7. `BLOCKER_CERTIFICATE.json`
8. `REPORT.md`
9. `REVIEW.md` (written only by the independent reviewer)

Not created: `studies/HIST_VNEXT/pilot_A/` spec/runner, `tests/test_hist_pilot_a.py`, any engine,
history, config, BASELINE, lock, research-contract, source-package, target, or user-file change.
Run logs and machine output live in `outputs/hist-vnext-h4b-20261020T181104Z/`, which is gitignored
and is not committed.

## 3. Evidence method

1. Read only metadata entry points: batch01/batch02 README, manifests, page indexes, QA, deferred
   archives, exposure/access records; H1A/H1B/H2A/H2B/H3A–H3G final technical records; H4A-0/H4A-1
   declarations, manifests and reviews.
2. No original PDF, full OCR text, HOLD page, sealed target, or private value payload was opened in
   this step. Approved excerpt sets in both source packages are empty; no new excerpt was invented.
3. The planning-phase `EvidenceIntake` subagent deviation is inherited and disclosed in
   `SOURCE_MANIFEST.json` and `REPORT.md`: it self-reports having opened candidate native text for
   D01 pp. 10–18, D02 ch02 pp. 1–2, 1968 yearbook pp. 105/106/144/272/350/351 and 1975 p. 120. Those
   reads are treated as unapproved exposure: no proposition, value, parameter, or selection
   derives from them, and this step did not re-read the pages to repair the deviation.
4. Authority statements are limited to what the read metadata itself states. Page tags are
   "candidate locating, not read, no direct basis" unless an approved, admitted excerpt exists.

## 4. Design freeze (no execution)

Two competing institutional settings are frozen in `ASSUMPTION_LEDGER.md`:
`A_delegated_choice` (permits transmitted through actual procurement/price-proposal/investment
approval) and `B_binding_bottlenecks` (permits nominally changed but money, inventory, transport, and
central approval remain binding). Sensitivity axes: procurement `granted/revoked/unknown`; price
`fixed/authorized-adjustment`; investment `central-approval/delegated-approval`. Paired design uses
one initial state, one external forcing, RNG seed 1729, each single mechanism and the full
combination, plus a no-permission-change control and a procurement-revocation arm. No numerical
price/approval magnitude is identified → `UNIDENTIFIED`, not fabricated.

Every pilot arm is `NOT_RUN`, because the technical gates below fail *before* any arm can be
executed. Missing historical originals (D03/D04/D05/D06/D07/D16) are **not** used as a blocker.

## 5. Technical blockers

| Blocker | Status | Source |
|---|---|---|
| `H4A_RUNTIME_MEASUREMENT_NOT_CONNECTED` | BLOCKED | H4A-0 approved sets empty; H4A-1 `runtime_connected=false`, `consumed_by_model=[]`; H4A-1 REVIEW 60 |
| `PRICE_INVESTMENT_EXECUTION_MAPPING_ABSENT` | BLOCKED | `execution_adapter.py:363–371`; H2B REVIEW "Known limits"; global policy scalars in `engine/policy.py:79–105` |
| `STRICT_FULL_FILE_BYTE_GATE_UNMET` | UNMET | H3F-D3 REVIEW 8–11, 75–80; H4A-1 REPORT 177–195 |
| `H3G_STRUCTURAL_NULL_AND_MISSING_STANDALONE_REVIEW` | cited, unresolved | `H3G/REPORT.md`; no `H3G/REVIEW.md` |
| `F2_CLOSURE_COLLAPSED_SNAPSHOT` | retained snapshot | `config/calibration/p06_clearance.json:22–29,48–58` |

## 6. Verification executed

- Both source-package integrity verifiers.
- H4A-1 experiment-admission CLI with the current approval.
- Six targeted test modules, then the full suite, Ruff, `hsm baseline verify --json`,
  `uv lock --check --offline`.
- New-directory C0/C1 replays at seed 1729 plus `verify_run_identity` against the frozen digests.
- `REPORT.md` tabulates exit codes and observed results. The uncommitted
  `outputs/hist-vnext-h4b-20261020T181104Z/COMMANDS.md` records exact command lines and which
  wall/RSS values were actually measured (unmeasured fields are `NOT_MEASURED`). Raw logs are in
  the same directory; they do not all carry their own command line or timing.

## 7. STOP contract

If the independent review returns PATCH, only whitelisted documents are repaired and re-reviewed.
REDESIGN, an out-of-whitelist requirement, a real regression, or a model failure stops the step with
a preserved failure record and no commit. On PASS: stage exactly the nine files, verify staged paths
contain no original/full text, numeric tables, outputs, user files, or config, commit locally with
`docs(hist-vnext): freeze H4B assumptions and technical blockers`, do not push, and stop.
