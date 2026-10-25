## VERDICT: **PATCH**

---

# H6B Independent Phase Review — findings

Repo: `/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab` · HEAD `bd05100525f9c31bc5fedb03218b520503edada9` · date 2026-10-25
Reviewer role: read-only. **I edited nothing inside the repo.** All my artifacts live in `/tmp/h6b-review/`. Final `git status --porcelain` = 32 lines = the 29 snapshot lines + exactly the 3 new H6B paths (`src/hsm_lab/evidence/package_export.py`, `studies/HIST_VNEXT/packages/`, `tests/test_hist_package_contract.py`); nothing staged.

---

## 1. What I independently reproduced (positive checks)

| Check | Command / method | Result |
|---|---|---|
| Local-data export rebuild | `package_export build --root . --mode local-data --output-dir /tmp/h6b-review/export-local` | exit 0; `complete=3 blocked=8`; **`diff -r` vs delivered `exports/local-data/` = IDENTICAL** |
| Git-only export rebuild | same, `--mode git-only` | exit 0; `complete=0`; byte-identical to delivered `exports/git-only/` |
| Cold git-archive rebuild | `git archive HEAD` → `/tmp/h6b-review/cold-git` (no `.git`, no ignored outputs, isolated `PYTHONPATH`), `PYTHONPATH=<iso>/src` + original venv python | exit 0; byte-identical to delivered `exports/git-only/` |
| Git-only reads no local outputs | `sys.addaudithook` open-event probe over `audit_package(mode="git-only")` | 490 open events, **0 under `outputs/`**, 0 matching private/target/holdout/reserved |
| Local-data reads only index roots | same probe, `mode="local-data"` | 258 files under `outputs/`, confined to the 5 index roots (4 existing + h6b cold-local fresh/repeat) |
| Tamper rejection | append 1 byte to `cards/M01.json`; overwrite `package.json`; add `unlisted.json` | **exit 2** for all three (`export file changed` / `file set mismatch`) |
| Restricted path rejected pre-access | index root `data/private/leak.txt` | **exit 2**, `restricted path rejected before open/hash`, nothing opened |
| Nonexistent root in git-only | index root `outputs/does-not-exist-anywhere` | exit 0, ignored (contract allows "ignored or rejected") |
| `research_package_complete` == all-11-PASS | recomputed from exported `checks` for all 11 cards | consistent in both exports (M01/M02/M04 = true; all others false) |
| 11 checks present | `set(card['checks'])` per card | exactly the 11 required names in both exports |
| Legacy metric preservation | `register_legacy_cards()` | `{'cards':11,'metrics':41,'mapped':14,'blocked':27}` — matches the report |
| C0/C1 identity | `verify_run_identity(...)` on the fresh runs | both digests = frozen 01 values, 116 ticks, parameter hashes `e27ade6a…` / `632ee6a6…` |
| C0/C1 reproducibility bundle | `verify_reproducibility_bundle(root=cold-local, bundle_dir=…, replay_dir=/tmp/…/replay-c0)` | `status=verified, digest_matches=true, parameter_hash_matches=true` (C0 and C1) |
| Tests | `pytest --collect-only` → **1894 collected**; `pytest tests/test_hist_package_contract.py` → **17 passed** | claims hold |
| Prior-commit identity | `git show <hash>:<path>` for all 11 cards, sha256 vs export | **11/11 blob sha256 match** — no `manifest.head` shortcut, no fabricated commits |
| Frozen plan | `shasum` `HIST_VNEXT_H6B_PLAN.md` vs `packages/H6B/PLAN.md` | identical (`af13a50b…`) — plan not rewritten |

**Scientific re-verification from raw artifacts (not via the module)** — M01: 78 arm files, 3 seeds × 26 arms, exactly one `opening.matching_digest` per seed, coverage == full registered matrix (0 missing / 0 extra), 8 ticks/arm, all `max_*_tolerance_ratio ≤ 1`, `failures == []`. M02: `status=COMPLETED`, 156 ticks, 39 arm-seeds, one opening state per seed, placebo bit-equal on all four digests × 3 seeds, all three first-stage legs populated. M04: 3 seeds × 3 arms × 16 ticks, max pool/input residual `1.1e-13 / 1.4e-14`, monotone `tolerance_0(0) < 0.5 < 1` per seed, zero arm is a real executed control. M09: 48 distinct `(seed,arm,target)` cells, `changed_sets=24`, ledger 48/48, `historical_status=NOT_RUN`, `registration_status_changed=false`.
**Fresh ≡ repeat ≡ existing** scientific payloads confirmed independently for all four studies; the only M02 file diff is `resources.wall_seconds` / `max_rss_bytes`.

**Negative checks I ran myself** — missing-evidence ⇒ `complete=false` and tamper ⇒ exit 2 (above); plus the targeted gate-robustness mutations in §2.

**Are the three complete cards justified?** **Yes, on the actual artifacts.** Every substantive invariant the frozen gate names for M01/M02/M04 is real and reproducible (matrix completeness, single opening state per seed, ≤1 tolerance ratios, 156/156 conservation, per-tick F2 closure ≤1e-9, monotone first stage, real zero-arm control, two independent fresh/repeat replays matching the existing digest). Historical status is `UNIDENTIFIED` (M01–M08) / `NOT_RUN` (M09) everywhere — **no false historical SUPPORTED claim**. The other eight classifications are also correct: M09 genuinely has no preregistered negative control (its spec contains no negative-control arm), M03 is an opt-in implementation without a paired matrix, M06/M07 are blocker-only with the right b…

**The defects below are gate robustness and ledger fidelity — not a misclassification of the current data.** That is why this is PATCH, not REDESIGN: the architecture (separate package layer, strict index, deterministic export, recomputing verifier) is sound and I reproduced its outputs byte-for-byte.

---

## 2. PATCH list (all inside the H6B whitelist)

### P1 — HIGH · restricted-path guard is bypassable by symlink (restricted-file access)
`src/hsm_lab/evidence/package_export.py:402` applies `_FORBIDDEN_COMPONENTS` to the **raw** path parts, then `:404` calls `.resolve()` and `:407` tests `target.is_symlink()` on the **already-resolved** path (always `False`). A symlink whose *raw* name is innocuous but whose *resolved* location is a forbidden directory is therefore opened.

Reproduced (read-only fixture, `/tmp/h6b-review/cold-neg4`):
```
ln -s ../../../../data/private studies/HIST_VNEXT/packages/H6B/privlink
# index M01.existing_root = studies/HIST_VNEXT/packages/H6B/privlink
→ audit hook log: PRIVATE FILES OPENED: ['/private/tmp/h6b-review/cold-neg4/data/private/study.json']
```
The frozen plan requires rejection *"在任何open/hash之前…（包括符号链接解析后的路径）"*. **Fix:** re-check `_FORBIDDEN_COMPONENTS` against the **resolved** path relative to root (and reject any resolved path whose components hit the forbidden set) before any `open`/`sha256_file`; reject symlinked ancestors *before* resolution.

### P2 — HIGH · several real-card checks are asserted, not derived (self-reported PASS)
The fixture adapter verifies all eleven checks against artifacts, but the five **real**-card adapters hardcode PASS plus a reason string. Verified by mutation in `/tmp/h6b-review/neg-metrics` (exit 0, cards stay `complete`):

| Mutation | Expected | Observed |
|---|---|---|
| M02 `shortage_expectation_mean = None` (`outputs/m02/results.json`) | `metrics_generated` BLOCKED (`package_export.py:1230`) | **PASS**, reason still *"required shortage, credit, investment and axis-scoped gap metrics have finite per-seed values"*; M02 `complete=True` |
| M04 tick metric `formal_unmet_total = None` | `metrics_generated` BLOCKED (`:1573`) | **PASS**, M04 `complete=True` |
| M01 `verdict.levers.import_cut.D_four_minus_one_grievance_by_seed = None` | `metrics_generated` BLOCKED (`:1005`) | **PASS**, M01 `complete=True` |
| M01 `cut_first_stage.by_seed.1731.import_cut → binding=false, effective=false`, `cut_first_stage.status="DEGRADED"` | `first_stage_checked` BLOCKED (`:986`) | **PASS**, reason *"reference and cut first stages PASS for every seed"* — now false; M01 `complete=True` |
| M02 all 24 budget/investment first-stage rows → `status="NONBINDING"` | `first_stage_checked` BLOCKED (`:1204`) | **PASS**; M02 `complete=True` — but M02's own spec (`falsification_rule.conditions_for_reading`) says a budget contrast is readable **only when the budget first stage is binding** |
| M01 artifact `historical_status="SUPPORTED"` | flag contradiction | export still reports `verdicts.historical="UNIDENTIFIED"`, *"no SUPPORTED claim"* (`:1077` hardcodes `"UNIDENTIFIED"`) — fails safe but misreports the artifact |

The plan's checks #4/#7/#9 require artifact-derived verdicts and explicitly forbid null/empty metrics passing; the new test file only exercises the fixture path, so **the tests assert implementation, not the research invariant, for the real cards**. **Fix:** derive `metrics_generated` from the artifacts' required-metric inventories (reject null/empty/missing component, per plan), verify applied→effective→binding→flow against each spec's first-stage rule (M01 `cut_first_stage`/`reference_first_stage`, M02 leg statuses + the spec's binding condition), and cross-check the declared historical grade against the artifact instead of hardcoding it.

### P3 — MEDIUM · `user_work_snapshot.json` misreports 18 existing user files
`studies/HIST_VNEXT/packages/H6B/user_work_snapshot.json` records `{"path": "\"CMEA_\\346…\"", "exists": false}` for **18** CJK-named untracked files that **do exist**. The snapshot script used git's octal-quoted path as a literal filesystem path, so it never hashed them (11 ASCII-path entries hash-match; 18 have no `sha256`).
The files are in fact untouched (mtimes 2026-10-18 … 2026-10-24, all before the H6B start `2026-10-25T06:44:07Z`; `git status` still lists all 26 untracked paths) — but the delivered ledger asserts `exists:false` for them. **Fix:** unquote (`\NNN` bytes → UTF-8) before hashing; record `sha256`/`bytes` for all 29 entries.

### P4 — MEDIUM · the isolated checkout's index copy was never updated
`outputs/hist-vnext-h6b-20261025T065107Z/cold-local/studies/HIST_VNEXT/packages/H6B/evidence_index.json` still points M01/M02/M03/M04/M09 at the **main repo's** `outputs/hist-vnext-h5*` roots and has `fresh_root = repeat_root = null`. A local-data audit inside the isolated checkout therefore dies:
```
build --root . --mode local-data (cwd=cold-local)
→ exit 2: "outputs/hist-vnext-h5c-20261022T051501Z/study5/study.json"
```
The plan requires the isolated index copy to use isolated-root-relative `outputs/<study-run>` roots. **Fix:** write `outputs/m01-fresh` etc. into the cold-local index copy (and/or make the audit treat a missing *existing* root as that card's explicit `BLOCKED` rather than a whole-audit hard failure).

### P5 — LOW · evidence_refs line anchors do not support the stated reason
`AuditContext.ref` (`:455`-ish) only bounds-checks the line number. Examples: M01 `counterevidence` cites `studies/HIST_VNEXT/M01/REPORT.md:113` (= *"Across all 78 arms:"*) and `:45` (= *"…This is the reference first stage."*) for the welfare-`UNIDENTIFIED` / empty-political-tables claim, which actually lives at `:4-5` and `:60-63`; M09 `negative_control` and `counterevidence` both cite `REPORT.md:99` (= *"The residual is a real `realized − prediction`…"*) while the saturation / valid-null statements are at `:106-107` and `:205`. **Fix:** re-anchor to the supporting lines (or attach the JSON pointer instead).

### P6 — LOW · dead duplicate check key
`package_export.py:1339` builds `"pair_control"` duplicating `"paired_control"` in `_m03_checks`. It is dropped by the `CHECK_NAMES` projection (exports carry exactly 11 checks — verified), but it is misleading dead code inside a gate module. **Fix:** delete it.

### P7 — LOW · ledger/report traceability
`REPORT.md` §1 states *"verdict in `REVIEW.md`"*, but `studies/HIST_VNEXT/packages/H6B/REVIEW.md` does not exist yet (expected pre-review; `model_usage.json` still records independent-review as `PENDING`). `commands.json` records no absolute REPO / interpreter path (the plan's Verification section asked for RUNROOT/REPO/PY in `commands.json`), which weakens traceability of the "original venv interpreter + isolated `PYTHONPATH`" claim — although the run artifacts themselves corroborate it (`cold-local/outputs/m01-fresh/arms/*/result.json` records `output_dir` inside the isolated tree, and both `cold-*` checkouts have no `.git`). **Fix:** add `repo`/`python` absolute paths to `commands.json` and write `REVIEW.md` after this review returns.

---

## 3. Clean bills of health (evidence)

- No target leakage, no fake quarterly interpolation, no fake replicates, no hold-out leakage, no LLM-probability-as-history, no single-commodity shortcut: H6B adds **no** simulation and **no** new time series; it only reads existing artifacts. M09's `historical_status=NOT_RUN` and `registration_status_changed=false` are enforced in code.
- No historical `SUPPORTED` claim anywhere in either export; `source_rights` = 15 reference-only records, `admitted_historical_series=[]`, `redistribution_allowed_any=false`.
- Export safety: zero occurrences of `/Users/`, `/home/`, `/private/`, `/tmp/`, `/var/`, `original_excerpt`, `ocr_text`, `translation`, `local_path`, `secret`, or any timestamp field across both exports.
- `BASELINE.md` sha256 `1f5b233f…` unchanged; all 20 protected hashes in `protected_hashes.json` re-verified **0 mismatches**; `.omp/config.yml` `2e90b9c6…` unchanged; `studies/manifest.json`, `uv.lock`, `config/p06/cards/M1–M11.json`, both scenario specs unchanged.
- Implementation-role deviation is disclosed honestly in `model_usage.json` and `REPORT.md` (supervisor `deepseek/deepseek-flash` instead of a separate MiniMax task; usage `NOT_MEASURED`, never zero); `resource_usage.json` records `max_rss_bytes: null` as `NOT_MEASURED`.

**Recommendation:** apply P1–P4 (mandatory), P5–P7 (cheap cleanups), re-run the H6B test file, rebuild both exports, and re-submit for a second independent review before committing. The three complete cards (M01/M02/M04) and the eight blocked cards may stand as they are scientifically; the *gate* that certifies them must be made to actually test what it claims.

[You have received this identical output 3 times. Re-reading 'agent://H6BReview' will not change it — use a narrower selector (path:A-B), or proceed with the edit.]

[Some lines truncated to 768 chars. Use agent://H6BReview:raw:38-38 to read line 38 whole]