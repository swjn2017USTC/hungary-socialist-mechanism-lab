VERDICT: PASS

# H4B Pilot A technical-blocker package — independent review

Reviewer: repository `phase-reviewer` subagent, read-only. No implementation or H4B document was
edited by the reviewer. The reviewer declares `model: "@review"`; actual selector/effort/tokens/cost
were not exposed to this transcription (`NOT_MEASURED`, not estimated). The reviewer independently
re-ran the integrity verifiers, the admission CLI, the targeted test modules, Ruff, baseline
verification, lock check, and `verify_run_identity` for C0/C1.

**Final verdict: PASS for the H4B blocker package.** This does **not** sign a Pilot execution PASS;
Pilot execution remains **BLOCKED**.

## Round 1 — PATCH

**Audit scope:** read-only; no implementation or H4B document edits. Eight of the nine whitelisted
files are present (`REVIEW.md` absent pending the independent reviewer; expected, not a package
defect). No Pilot execution PASS is signed; Pilot remains BLOCKED.

**Verified (acceptance criteria 1–11 pass on substance):**

- **C1** No H4B `run_id`, trace, paired delta, first stage, seed outcome, or pilot resource profile
  exists. `INPUT_MANIFEST.json` has `status=NOT_RUN`, `run_id=null`, `consumed_by_model=[]`, 9 arms
  all `NOT_RUN`; `blocked_by` lists only technical blockers. D03/D04/D05/D06/D07/D16 appear only as
  evidence gaps, never as the blocker (`BLOCKER_CERTIFICATE.json#not_blockers`, `scope_statement`).
- **C2** Missing originals are not used as the STOP reason; `ASSUMPTION_LEDGER.md` §5 and
  `REPORT.md` §12 say a technical, not archival, gate blocks execution.
- **C3** `docs/phases/HIST_VNEXT/H4A-1/ACTUAL_INPUT_MANIFEST.json` still has `consumed_by_model=[]`,
  `runtime_connected=false`, three `approved_but_unconsumed` records. Re-ran the admission CLI:
  exit 0, `structural=PASS`, `admission=EXPERIMENT_ONLY`, 3 approved,
  `historical_inputs_admitted=0`, `runtime_connected=false`, `errors=[]`.
- **C4** `src/hsm_lab/institutions/execution_adapter.py:363-371` still accepts only an exact
  `ProcurementDecision`; `engine/policy.py:89-94/100-102` are described only as global scalars,
  never as per-category/per-project authority; `engine/finance.py:1611-1615` and `engine/material.py`
  match the described cash/capacity-hunger logic. H2B `REVIEW.md:39-44` confirms the
  procurement-only bridge.
- **C5** `H3F-D3/REVIEW.md:8-11,75-80` still records strict full-file bytes UNMET;
  `H4A-1/REPORT.md:177-195` and `H4A-1/PLAN.md:75,150` are correctly cited; no normalization,
  re-pin, or P06 waiver; `REPORT.md` §8 explicitly says digest equality is not byte identity.
- **C6** Logs match `REPORT.md`: A1 `112/4/89/83/0`, A2 `1943/7/3553/368/70/0`, A3 JSON
  `3/0/false/[]`, B1 `319 passed`, B2 `1688 passed, 180 warnings, 195.97 s`, B3 clean, B4
  `1f5b233f…`, B5 `101 packages`. Independently re-ran targeted modules (319 passed), ruff,
  baseline, lock, A1/A2, A3, and `verify_run_identity` for C0/C1: both VERIFIED with the pinned
  digests/parameter hashes. C0/C1 `run.json`/`manifest.json` contain the same ids/digests, 116
  ticks, and matching time/RSS.
- **C7** `SOURCE_MANIFEST.json#access_deviations` (`H4B-ACCESS-001`) lists every path/page (D01
  pp.10–18; D02-ch02 pp.1–2; 1968 pp.105/106/144/272/350/351; 1975 p.120), marks it
  inherited/self-reported/not independently verified, and states no proposition/value/parameter
  derives from it and blindness is not restored. `REPORT.md` §2 repeats this. No authority row uses
  its content.
- **C8** Authority rows stay at “metadata only / no proposition”; page tags match
  `batch01/page_index.csv`; D02 ch02/ch05 are one `work_id`; 1956/1957 reprints and 1973 pp.94–97
  are marked non-independent in `SOURCE_MANIFEST.json#shared_source_relations`.
- **C9** Ledger freezes A/B settings, the three categorical axes, failure criteria, local 4Q window,
  no 1957→1968 rename; price/approval ranges are `UNIDENTIFIED`.
- **C10** All 33 declared SHA-256 values (SOURCE/INPUT/MEASUREMENT/BLOCKER evidence) and all 11
  source-PDF hashes match. `05=bc45bc84…`, `06=5fcb75b4…`, `BASELINE=1f5b233f…`,
  `research_contract=6f54522a…`, `uv.lock=9fd79b62…`. No staged files; only the 8 H4B files exist;
  no original text, numeric source table, secret, or `.omp/config.yml` content (only path +
  truncated hash).
- **C11** `REPORT.md` verdict table keeps evidence/technical/structural/historical separate; Pilot =
  BLOCKED. `H3G/REVIEW.md` is absent and the report’s self-claimed PASS is recorded only as an
  evidence gap.

**Finite repairs required (round 1):**

1. **P1 — Start-state untracked count is wrong (must fix).** `PLAN.md:15` and `REPORT.md:23` said
   “11 root `*_PLAN.md` documents (including this step’s plan…).” Actual: **12** untracked root
   plans, plus `09_BATCH02…` = 13 untracked user documents. Evidence:
   `git ls-files --others --exclude-standard -- '*_PLAN.md' | wc -l` → `12`; `ls -1 *_PLAN.md |
   wc -l` → `25` (13 tracked + 12 untracked); all 12 untracked plans predate the 02:11 execution
   start (latest is `H4B_PILOT_A_阻断包_PLAN.md`, 02:09:58). Fix both rows to “12 root `*_PLAN.md`
   (11 pre-existing + this step’s plan) and `09_BATCH02…`”.
2. **P2 — Log-content claim overstates the evidence (should fix).** `PLAN.md:100` said “Exact
   commands/exit codes/wall time/max RSS are recorded in `REPORT.md` and the uncommitted logs.” The
   run directory had 14 top-level files: no command transcript; B1–B5 logs have no command line,
   wall time, or max RSS; C0/C1 have wall/RSS but no byte-count. Evidence: `find
   outputs/hist-vnext-h4b-20261020T181104Z -maxdepth 1 -type f`; `cat` of the B logs. Fixed by
   adding an uncommitted `outputs/.../COMMANDS.md` with exact command lines, exit, wall/RSS, and
   byte deltas, and by correcting the sentence.
3. **P3 — Code-anchor range is imprecise (optional precision).** `REPORT.md:123`,
   `BLOCKER_CERTIFICATE.json:51,58`, and `ORIGINAL_AUTHORITY_MATRIX.md` cited
   `engine/material.py:1589–1600` as where `new_request` is formed; the assignment is at 1601–1605
   and the hunger input at 1594–1599. Evidence: `grep -n "new_request = np.where"
   src/hsm_lab/engine/material.py` → `1601`. Changed to `1594–1605`.
4. **P4 — A3 invocation transcription (optional).** `REPORT.md:173` recorded `python -m history…`,
   while the plan specifies `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history…`. Aligned the
   row with the actual invocation; the result itself is verified and unchanged.

No other factual mismatch was found. After P1/P2 were corrected, an independent `REVIEW.md` could
be issued as PASS with Pilot BLOCKED; the package must not be committed as a Pilot execution PASS.

## Round 2 — PASS

Repairs confirmed (read-only):

1. **Untracked-count repair — correct.** `PLAN.md:15` and `REPORT.md:23` now say “12 untracked root
   `*_PLAN.md` documents (11 pre-existing + this step’s plan)” plus `09_BATCH02…`. Evidence:
   `git ls-files --others --exclude-standard -- '*_PLAN.md' | wc -l` → `12`; all 12 untracked plans
   predate the 02:11 start (latest `H4B_PILOT_A_阻断包_PLAN.md`, 02:09:58). No stale “11 root” claim
   remains.
2. **`COMMANDS.md` repair — correct.** `outputs/hist-vnext-h4b-20261020T181104Z/COMMANDS.md` exists
   and verifies exactly: top-level log sizes match (`A1` 142 B, `A2` 173 B, `A3` 6,590 B, `B1`
   427 B, `B2` 3,377 B, `B3` 26 B, `B4` 325 B, `B5` 37 B, `C0_run`/`C1_run` 845 B,
   `C0_time`/`C1_time` 777 B, `C_identity_verify` 1,157 B); `C0` = 20,111,465 B / 19 files; `C1` =
   19,518,596 B / 19 files; total = 39,645,559 B for the 14 machine logs + 2 run dirs (excluding
   `COMMANDS.md` itself), recomputed exactly; A1/A2/C0/C1 wall and RSS match the raw logs;
   unmeasured fields are `NOT_MEASURED`, not 0. `PLAN.md:100–103` and `REPORT.md:167` correctly point
   to `COMMANDS.md` and correctly state that raw logs do not all carry their own command line or
   timing.

**`SOURCE_MANIFEST.json` check:** content is correct — 1956/1957 roles are
`initial_state_candidate`/`definition_review`; the 1960↔1968 relation is
`independent: NOT_ESTABLISHED` with the “distinct volumes do not establish independence” basis; no
shared source is counted as independent.

**No new factual overclaim introduced.** Residual non-blocking nits at this round: the `COMMANDS.md`
C-verify row is a `<<PY … PY` template rather than a literal paste-ready command, and `REPORT.md`’s
A3 row abbreviates `.venv/bin/python` as `python`. Neither affects any result.

**Unchanged facts rechecked:** frozen hashes still match (`BASELINE 1f5b233f…`,
`research_contract 6f54522a…`, `uv.lock 9fd79b62…`, `05 bc45bc84…`, `06 5fcb75b4…`); no staged
files; `H3G/REVIEW.md` still absent; H4A-1 still `consumed_by_model=[]`, `runtime_connected=false`;
`execution_adapter.py:363–371` still rejects non-`ProcurementDecision`; eight H4B files present,
`REVIEW.md` pending as the independent artifact.

**Final verdict: PASS for the H4B blocker package.** This does not sign a Pilot execution PASS;
Pilot execution remains BLOCKED.

## Round 3 — final confirmation after optional precision edits

Optional P3/P4 edits verified read-only:

- Material anchor: `REPORT.md:123`, `BLOCKER_CERTIFICATE.json:51/58`, and
  `ORIGINAL_AUTHORITY_MATRIX.md` row 3 now cite 1594–1605. Actual code: `hunger = (` at 1594;
  `new_request = np.where` at 1601–1605. No stale 1589 reference remains
  (`grep -rn 1589 docs/phases/HIST_VNEXT/H4B/` → none).
- A3 row: `REPORT.md:175` now `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m
  history.HIST_VNEXT.h4_sources.experiment_admission … --approval …`, matching `COMMANDS.md`'s exact
  invocation modulo the shown `…` argument ellipsis. Exit/observed text unchanged.
- All four JSON files parse (SOURCE/INPUT/MEASUREMENT/BLOCKER). Only REPORT/BLOCKER/MATRIX mtimes
  changed after the prior PLAN/REPORT repair; SOURCE/INPUT/MEASUREMENT/LEDGER unchanged. No staged
  files; `COMMANDS.md` remains uncommitted/gitignored. No results, verdicts, or numeric claims
  changed.

No remaining defect; the `…` abbreviations are honest and backed by `COMMANDS.md`.

**Final: PASS for the H4B blocker package; Pilot execution remains BLOCKED; this is not a Pilot
execution PASS.**

## Scope boundaries of this PASS

1. PASS covers only the evidence/hypothesis freeze and the technical-blocker package. It does not
   authorize production initialization, measurement wiring, price/investment execution, any pilot
   arm, or any historical claim.
2. Still unmet and correctly disclosed: H4A runtime/measurement is not connected; price and
   investment have no execution mapping; the strict full-file C0/C1 byte gate is UNMET; H3G has a
   structural null without a standalone review; the P06 collapsed snapshot is retained.
3. No H4B run id, trace, paired delta, first stage, seed outcome, or resource profile exists. The
   C0/C1 results are frozen regression replays, not pilot arms.
4. Only the nine whitelisted files may be committed; `outputs/`, `.omp/config.yml`, user dirty files,
   and untracked user plans/documents must be excluded. No push.
