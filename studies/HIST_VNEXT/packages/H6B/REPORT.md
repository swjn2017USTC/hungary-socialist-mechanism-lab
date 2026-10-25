# HIST_VNEXT H6B — 11-card strict package audit and reproducible export

Status: **package audit complete; 3 cards complete, 8 cards blocked.**
This is not a claim that any historical hypothesis is `SUPPORTED`.  Historical
`UNIDENTIFIED`/`NOT_RUN` survives even where a package is complete.

## 1. Execution identity and scope

| Item | Value |
|---|---|
| Start HEAD | `bd05100525f9c31bc5fedb03218b520503edada9` |
| Branch | `codex/audit-hsm-vnext-2026-10-11` |
| User work snapshot | 3 tracked modified + 26 untracked paths at start; preserved, not reset/staged/cleaned |
| Output root | `outputs/hist-vnext-h6b-20261025T065107Z/` (ignored; not committed) |
| New code | `src/hsm_lab/evidence/package_export.py` |
| New tests | `tests/test_hist_package_contract.py` |
| New delivery | `studies/HIST_VNEXT/packages/H6B/` |
| Implementation role | **DEVIATION**: executed in the supervisor session (`deepseek/deepseek-flash`) instead of a separate `minimax-code-cn/MiniMax-M3` task; see `model_usage.json` (usage `NOT_MEASURED`) |
| Independent review | `phase-reviewer` via `@review` (`minimax-code-cn/MiniMax-M3:high`); rounds 1–2 PATCH, round 3 **PASS** (`REVIEW.md`) |

No engine, state, storage, schema, loader, CLI, existing study or existing
output was modified.  `StudyDeclaration.research_package_complete` remains
`Literal[False]`; H6B computes completeness only in the new package layer.

## 2. What was delivered

* A read-only audit module with the fixed public interface
  `audit_package`, `export_package`, `verify_export`, `main`.
* A strictly validated `evidence_index.json` that only locates existing,
  fresh and repeat run roots.  It carries no booleans, selectors, commands or
  source paths.
* `exports/git-only/` and `exports/local-data/`: deterministic JSON + Markdown
  packages with eleven cards, `MANIFEST.json`, no original sources and no UI.
* Cold-start evidence: a `git archive HEAD` checkout with no `.git` and no
  ignored outputs reproduces the git-only package byte for byte; four studies
  were replayed fresh/repeat in a second isolated checkout with the original
  interpreter and isolated `PYTHONPATH`.
* Frozen `PLAN.md`, command/resource/failed-seed/blocker/model-usage ledgers,
  user-work and protected-hash snapshots, and a final evidence manifest.

## 3. Eleven-card result

`research_package_complete` is derived only as
`all(11 checks == PASS)`.  A legitimate structural `REJECTED`/`UNIDENTIFIED`
does not by itself reduce package completeness; missing paired evidence,
first-stage evidence, accounting, a negative control, required metrics or a
replay does.

| Card | Package | Technical | Structural | Historical | Blocking checks |
|---|---|---|---|---|---|
| M01 | complete | PASS | import/income = `CONDITIONAL_CARRIED_REFERENCE_EFFECT`; welfare = `UNIDENTIFIED` | UNIDENTIFIED | none |
| M02 | complete | PASS | `FALSIFICATION_MET_SYNTHETIC_WINDOW` | UNIDENTIFIED | none |
| M03 | blocked | PASS | `PASS_SYNTHETIC` | UNIDENTIFIED | paired_control, first_stage_checked, accounting_checked, sensitivity_or_reason_not_run, reproduction_bundle |
| M04 | complete | PASS | `FIRST_STAGE_SUPPORTED_WITH_CAPACITY_CEILING` | UNIDENTIFIED | none |
| M05 | blocked | NOT_RUN | NOT_RUN | UNIDENTIFIED | no dedicated experiment; 9 checks NOT_RUN |
| M06 | blocked | BLOCKED | NOT_RUN | UNIDENTIFIED | blocker-only `MISSING_EXTERNAL_DEBT_CONTRACT_ADMISSION` |
| M07 | blocked | BLOCKED | NOT_RUN | UNIDENTIFIED | blocker-only `MISSING_REGIONAL_CROSSWALK_PASS` |
| M08 | blocked | NOT_RUN | NOT_RUN | UNIDENTIFIED | no dedicated experiment; 9 checks NOT_RUN |
| M09 | blocked | PASS | `SYNTHETIC_ENGINEERING_PROFILE` | NOT_RUN | negative_control only |
| M10 | blocked | NOT_RUN | NOT_RUN | UNIDENTIFIED | no dedicated experiment; 9 checks NOT_RUN |
| M11 | blocked | NOT_RUN | NOT_RUN | UNIDENTIFIED | no dedicated experiment; 9 checks NOT_RUN |

Summary: **11 cards; 3 complete (M01, M02, M04); 8 blocked; 41 legacy
declared metrics preserved (14 mapped, 27 blocked).**

### Why the three complete cards pass

* **M01** — 78/78 arms completed 8 ticks; one matched opening digest across
  each seed's 26 arms; reference and cut first stages PASS; all per-arm
  material/finance tolerance ratios ≤ 1; the formation-strength 0.1/0.0
  ablation ran; the welfare lever remains `UNIDENTIFIED` and is kept as
  counterevidence.  Fresh and repeat full studies reproduce the existing
  study digest.  The comparison excludes per-arm `result.json` bytes that
  contain the non-scientific `output_dir`.
* **M02** — 3 seeds × 13 arms × 4Q = 156 ticks; one shared opening state per
  seed; conservation 156/156 with 2,616,002 journal legs checked and 0 invalid;
  the placebo arm is digest-identical in all three seeds; DiD/TriD point values
  are reported without a significance claim; the card's falsification
  criterion is met (non-falling shortage axes) and `SUPPORTED` is explicitly
  unreachable.  Fresh/repeat full studies reproduce the existing scientific
  digest.
* **M04** — 3 seeds × 3 tolerance arms × 16Q = 144 arm-ticks; one shared
  opening pool per seed; tolerance 0 < 0.5 < 1 first stage in every seed with
  the declared capacity ceiling; the zero arm is a real negative control;
  per-tick F2 pool/input residuals are ≤ 1e-9; the study bytes reproduce
  exactly in fresh/repeat.

### Why the blocked cards are blocked

* **M03** is an opt-in labour implementation, not a paired experiment: the
  accepted spec has no per-seed treatment/control matrix, no per-tick ledger
  summary, no policy first stage and no preregistered sensitivity.  N1–N3 do
  pass and are preserved.  The cold-local N1–N3 and 116-tick opt-in replay
  both verified, but they do not turn implementation evidence into a paired
  research package.
* **M05/M08/M10/M11** have no dedicated directory.  Their declarations and
  H0B/H6A prerequisite gaps are recorded; they are `NOT_STARTED`, not
  placeholder-complete.
* **M06/M07** are blocker-only packages.  Their external-debt-contract and
  regional-crosswalk blockers are preserved; a blocker-seal PASS is not a
  research PASS.
* **M09** has a complete 3×4×4 paired engineering matrix, a real information
  first stage, per-tick material/finance gates and a fresh/repeat replay, but
  no dedicated preregistered negative-control arm or sealed control metric.
  The saturated-action null is recorded as counterevidence, not promoted to a
  designated negative control.

## 4. Cold-start and reproducibility

* `export-git-a` (main checkout) and `export-cold-git` (`git archive HEAD`
  checkout, no `.git`, no ignored outputs, isolated `PYTHONPATH`) are
  byte-identical; `diff -r` is empty.
* `export-local-a` and `export-local-b` from the same inputs are byte-identical;
  `verify` recomputes all file hashes, the canonical package digest and the
  eleven-card contract state (exit 0).
* The four complete/replayable studies were run in
  `outputs/hist-vnext-h6b-20261025T065107Z/cold-local` by the original venv
  interpreter with `PYTHONPATH=<isolated>/src`, never by falling back to the
  original checkout.
* M01: fresh/repeat `study.json` SHA-256
  `89b3d6619bb5d1b2eb016f75d9958bb2c9e546675fea4fc2b25545de37bde389`
  (identical to the existing H5C study).  M02: scientific digest
  `3e0562bf8d1e457ad80b27548e303497ccfc7b3b7458cb1ce01f691d185216e1`
  in existing/fresh/repeat.  M04: `study.json` SHA-256
  `92379d618ca47c0c0cde9f9cb86cc11cb6459797fbdea49ab7e105196b165930`
  in existing/fresh/repeat.  M09: `science.json` SHA-256
  `34baafa8d18bbbbbb8583345e3c481a213e3b548628bb5f9d21ac0148ba3bada`
  in existing/fresh/repeat.
* Reproduction bundles for the standard scenarios are checked separately in
  §6; an export hash verification is explicitly **not** called a cold replay.

## 5. Source rights and historical counterevidence

`source_rights` is built only from
`history/HIST_VNEXT/sources/batch01_candidates.json` and
`history/HIST_VNEXT/h4_sources/sources.json`.  It records 15 reference-only
source records, `admitted_historical_series=[]`, and
`redistribution_allowed_any=false`.  No `local_path` is copied; no original,
OCR or translation is opened or exported.  Historical status stays
`UNIDENTIFIED` (M01–M08) or `NOT_RUN` (M09).

Recorded counterevidence includes: M01 welfare `UNIDENTIFIED` and empty C0
political tables as missing measurements; M02 falsification met and F2
`NOT_RUN`; M03 institutional attribution `UNIDENTIFIED`; M04 capacity-ceiling
bound; M06/M07 missing external prerequisites; M09 saturated-action valid null
and the preserved pre-fix matrix failure.

## 6. Final commands and gates

The exact command ledgers are in `commands.json`, `resource_usage.json`,
`model_usage.json`, `failed_seeds.json` and `BLOCKERS.json`.  Final gates:

* `pytest -q -p no:cacheprovider` — **1902 passed, 180 warnings in 214.51 s** after the P8-P10 repairs (pre-PATCH 1894 passed).
* `ruff check --no-cache src tests` — **All checks passed**.
* `uv lock --check --offline` — **Resolved 101 packages** (exit 0).
* `hsm baseline verify --json` — **status=ok**, SHA-256
  `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
* Fresh C0 (`historical_f2_replay`) — 116 ticks, last quarter 1985Q4,
  digest `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`,
  parameter hash `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445`.
* Fresh C1 (`historical_f2_trade_scenario`) — 116 ticks, last quarter 1985Q4,
  digest `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`,
  parameter hash `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90`.
* `verify_run_identity` passed for both fresh runs with the frozen 01 digests.
* `assemble_reproducibility_bundle` + `verify_reproducibility_bundle` against
  the isolated cold-local checkout returned `status="verified"`,
  `digest_matches=true`, `parameter_hash_matches=true` for C0 and C1.  Bundle
  SHA-256: C0 `0404cc51cd6f3799d100f5891557828e7e56436643c8d97366fe337f856d2ddf`,
  C1 `1727523611fa42961f73c5fda6b3aa3fdc40126bb75ad99a0aa8b1d4646dc079`.
* All protected hashes in `protected_hashes.json` still match; the user
  worktree snapshot is unchanged except for the new H6B deliverables.

No HTML/UI was implemented.  No push, no release and no automatic publication
was performed.

## 7. Independent-review repairs (round 1)

The first independent review returned **PATCH**.  All findings were addressed
inside the H6B whitelist; no scientific classification changed.

* **P1 symlink escape** — `AuditContext.guard` now rejects symlinks component by
  component *before* resolving, then re-checks the resolved relative components
  against the restricted set.  A symlink named innocuously but resolving into
  `data/private` is rejected before any open/hash.  Permanent test:
  `test_restricted_symlink_is_rejected_before_resolution`.
* **P2 asserted real-card checks** — the real adapters now derive
  `first_stage_checked`, `metrics_generated` and `historical_evidence_grade`
  from artifacts.  M01 rejects null lever values, a degraded/non-binding cut
  first stage and a contradictory historical grade; M02 rejects null required
  per-arm metrics, non-binding joint/credit/investment/demand first stages and a
  non-UNIDENTIFIED historical verdict; M04 rejects null required tick metrics
  and a broken tolerance first stage.  Manual mutations of temporary copies
  (never the real outputs) all turned the target check `BLOCKED`.  Permanent
  tests exercise the M01/M02/M04 gate helpers directly.
* **P3 user snapshot** — the snapshot was regenerated from
  `git status --porcelain=v1 -z`; all 29 user paths (including 18 CJK-named
  untracked files) are decoded and hashed.
* **P4 cold-local index** — the isolated checkout index now uses
  isolated-root-relative `outputs/m01-fresh`, `outputs/m02-fresh`,
  `outputs/m04-fresh`, `outputs/m09-fresh` roots; a local-data audit inside the
  isolated checkout exits 0 instead of failing on a main-repo path.
* **P5 line anchors** — M01 counterevidence now points at REPORT:162 and :60;
  M09 negative-control/counterevidence at REPORT:106, :122 and :205.
* **P6 dead check key** — the duplicate `pair_control` key was removed.
* **P7 traceability** — `commands.json` now records absolute `repo` and
  `python` paths; this report and `REVIEW.md` record both review rounds.

The two exports were rebuilt after these repairs and re-verified.  A second
independent review is required before commit; its verdict is in `REVIEW.md`.

### Round 2 repairs (P8-P10)

* **P8 root binding** — `load_evidence_manifest` now receives
  `root / "studies" / "manifest.json"`, so the card/sidecar gate is bound to
  `--root`, not the process CWD.  Permanent test:
  `test_audit_manifest_is_root_bound_not_cwd_bound`.
* **P9 remaining asserted checks** — M01 sensitivity and counterevidence,
  M02 sensitivity and counterevidence, and M04 sensitivity and counterevidence
  are now artifact-derived:
  M01 requires the 0.1/0.0 ablation rows with finite scalars and a
  non-`SUPPORTED` welfare status; M02 requires six regime contrasts, both
  demand regimes and at least one non-falling shortage axis plus F2 `NOT_RUN`;
  M04 requires all three tolerance levels, the capacity-ceiling summary and a
  preserved process failure.  Contradictions now set the specific check
  `BLOCKED`.
* **P10 residual anchors** — M02 counterevidence points at
  `results.json#/verdicts/structural/by_regime/base` and the spec
  `falsification_rule`; M03 uses acceptance/manifest pointers; M06/M07 use the
  manifest `blocking_code` pointer instead of report line 1.

Final exports after these repairs: git-only
`2216c9f1409c65f8bd8cc6e204226b651fd874c087439b0ac125105ea1f5c85c`,
local-data `f4032201ed4f7b79e6f1c8305b1b46f1db6bc6547417fd46652bd4ef1d0b09c4`.
Both same-mode rebuilds and the cold git-archive rebuild are byte-identical;
`verify` exits 0.  A third independent review returned **PASS**; R3 (a stale test-count sentence) was corrected afterwards. See `REVIEW.md`.
