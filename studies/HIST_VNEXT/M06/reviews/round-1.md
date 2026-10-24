# H5G-G1 Blocker Sealing — Independent Phase Review (Round 1)

**Verdict: PATCH**

Scope note: this PASS/PATCH covers only whether the blocker judgment and the sealed evidence are accurate and evidence-only. It is **not** H5G engineering/structural/historical acceptance, and **not** contract-original admission. I edited nothing; all my scratch files went to `/tmp/h5g_rev/`.

---

## A. What I independently reproduced and confirmed

**A1 — Admission audit reproduced (byte-exact).**
```
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root .
→ exit 1; stdout 4107 B sha256 b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419
  stderr 0 B sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```
`cmp` byte-identical to `logs/preflight_admission.attempt-{1,2,3}.stdout.json`. Validator untouched, exit 1 not suppressed. Parsed summary matches the certificate field-for-field: `total_candidates 4, total_sources 4, total_works 3, total_admitted 0, total_blocked_sources 0, total_blocked_anchors 63, anchor_classifications.blocked 63, authority_blocked 5, event_candidates 10, review_requests_required 4, independent_pairs 0, non_independent_pairs 1`; stdout `details` contains every reason the report quotes, including `authority 'Domestic/external trade financing and receivables' … unverified / no implementation_evidence_ids / event 'E09' is not verified` and `63 anchor(s) remain blocked for 1957`.

**A2 — All 32 M06 files hashed; every cited hash/byte matches actual bytes.** `studies/HIST_VNEXT/M06/PLAN.md` is byte-identical to `HIST_VNEXT_H5G_G1_HIST_VNEXT_H5G_PLAN.md` (`7bd46908…5577`, 17660 B).

**A3 — All six `required_contract` quotes are verbatim** (script-checked line-by-line against the source bytes, incl. the 4-space-indent strip for `phase-contracts.json`): 05:246/248–253, 06:17/19/21, 01:30–33/43–46, 06:27/29/31, `phase-contracts.json`:194/195/197/198, `M06/PLAN.md`:4 — all quoted strings identical, all six source-file sha256/bytes correct. The REPORT §2 table reproduces the certificate's quote arrays (its only diff is markdown `\|` escaping, see D6).

**A4 — Prior-review scope statements hold at the cited lines.** H3F-D0:15–30 (“not historical validation… UNIDENTIFIED”, no contract/source rights); H3F-D1:58–60; H3F-D2:7–9 (“full-file C0/C1 byte criterion remains unmet”); H3F-D3:9–11 & 75–79 (strict full-file byte gate unmet); H4B-ID `REVIEW.md:55–98` (fresh runs byte-identical, `diff -rq` exit 0) with `:102` “byte identity still **not claimed**” for resume; H4B-EXEC `REPORT.md:80–82` (`historical_inputs_admitted=0`, `historical_comparison=NOT_RUN`) and `:96–105` (`CLEARED for fresh runs`, self-attributed to the previous H4B-ID step, legacy C0/C1 checked only by digest pins). H4C `ORIGINAL_COVERAGE.md:35–36` = D03/D04/D05/D16 **missing**, D06/D07/D17 **MISSING/UNVERIFIED**, excerpts `null`; `:39–47` HOLD/empty-excerpt policy. `MEASUREMENT_MANIFEST.json:14–26` = `rollover: NOT_IMPLEMENTED`, `usd_new_draw: … g01..g16 match none, so the probe draws 0`. The package preserves D3’s unmet record *and* H4B’s later fresh-run clearance without merging them. ✓

**A5 — F2 technical finding is exact and not overgeneralized.** `src/hsm_lab/engine/material.py:1842–1851` uses `COMMODITY_INDEX.get(network.commodity_ids[g])` with `continue`; `COMMODITY_INDEX` has 8 P02 keys, F2 `config/ontology/f2_v1.json` ids `g01…g16` → **0 matches** → `desired_usd_outlay = 0` → `trade.py:194–199` `draw = min(limit, max(0, 0 − reserve)) = 0`. `trade.py:154–236` genuinely implements USD reserve/principal/interest/draw. `tests/test_hist_pilot_b.py:261–284` is the non-F2 positive case (draw = 5, import payment = 5), and the report correctly marks it as **not run this round**. ✓

**A6 — Frozen hashes all match exactly:** BASELINE.md `1f5b233f…d61b6f` (64445 B), `config/research_contract.json` `6f54522a…752c82` (2908), `uv.lock` `9fd79b62…8882b9` (157941), `config/p06/cards/M6.json` `047db0a8…de5e6c6` (815), `config/p06/cards/M10.json` `c23d545b…129b880` (806).

**A7 — User work fully protected.** All 22 untracked user files + 3 modified files still hash to `user_work_snapshot.json` (0 mismatches); all 22 `protected_hashes.preflight.json` entries match (0 mismatches). `git diff --cached` empty; `git diff -- src tests config history BASELINE.md` empty; only new path is `studies/HIST_VNEXT/M06/`; **0 `.py` files**, no runner/scenario/output/test added; no new run directory (the only `outputs/` dir today is `hist-vnext-h5f-f1-20261024T021255Z`, from 02:12Z, pre-dating this step); HEAD still `f88eb43…`, no commit.

**A8 — Usage/cost records are truthful.** Recomputed from the JSONL `message_end.usage` records: 78/13/20/9/29/12 assistant records for attempts 1–6; token sums `120401/35857/5782064/0/5938322`, `64368/33993/463819/0/562180`, `77009/48468/684327/0/809804`, `29041/2905/125007/0/156953`, `89334/49040/1546413/0/1684787`, `30844/7982/253435/0/292261`; per-session `cost.total` sums `0.42607254 / 0.08793114 / 0.12232392 / 0.01969872 / 0.17843298 / 0.0340377`; totals `410997/178245/8855065/0/9444307`, `cost 0.868497` — **exact match to `model_usage.json`**. Every session record carries `provider=minimax-code-cn, model=MiniMax-M3, api=anthropic-messages`; no reasoning-token field exists (report’s wording is right). `NOT_MEASURED` used where unmeasured, never faked as 0; timeouts/aborts preserved; attempt-2 admission exit explicitly `NOT_RECORDED_BY_SUPERVISOR`.

**A9 — Blocker judgment independently corroborated (by me, not by the package).** `docs/upgrade_review/HIST_VNEXT/07_MANUAL_HISTORICAL_DATA_DOWNLOAD_CHECKLIST.md:42` — D17 (per-currency external-debt stock, draw, interest, principal, rollover/maturity, subsidies, import use) is required **before H5G-G1/G2 historical research**, “不用国内企业credit_fraction代表外债；缺期限/用途不能宣称消费平滑机制已识别”; `:129` — H5G-G1/G2 requires **D06/D07/D17**, prohibited substitutes “国内企业借款、外贸总指数或通用CMEA公式”. `09_BATCH02_YEARBOOKS_D08_D10_INTAKE.md:41,57` — statistical conversion ≠ contract payment/financing system; D03–D07 originals remain deferred. `docs/phases/HIST_VNEXT/H4B/ORIGINAL_AUTHORITY_MATRIX.md:6–7,24–34` — `approved_excerpt_id = null` everywhere. No admitted external-debt contract original exists anywhere in the repo. **The BLOCKED judgment and `MISSING_EXTERNAL_DEBT_CONTRACT_ADMISSION` code are correct.**

**A10 — No fabricated claims.** dimensions `technical=BLOCKED_PREREQUISITE / structural=NOT_RUN / historical=BLOCKED`; `blocking_code` as claimed; `seeds.seed_status=NOT_RUN, failed_seeds=null`; `failed_seeds.json = {status NOT_RUN, seeds []}`; `delivery.commit=null, pushed=false, phase_completion_claimed=false, research_package_complete=false, simulation_manifests=[]`; `review.status=NOT_RUN`; `implementation/experiments=NOT_RUN`; `frozen_digests_not_run` explicitly not run; no “first-stage activated”, no run digest, no self-signed PASS. BASELINE.md unmodified.

---

## B. Defects — finite prioritized repair list (all inside `studies/HIST_VNEXT/M06/`)

**D1 (blocking, truthfulness of a sealed failure record).** `studies/HIST_VNEXT/M06/commands.json` → CMD-9 `result`:
> “The shell command substitution inside the launcher prompt was evaluated by bash before omp received it (h-fields in the prompt replaced by command-not-found errors), so the model received a corrupted prompt.”

Repeated in `BLOCKER_CERTIFICATE.json` → `executor.patch_sessions[attempt-4].outcome` and `REPORT.md:161` (§10 执行会话 row). **The sealed artifact contradicts this.**
Reproduction:
```
grep -c "command not found\|h-fields\|corrupt\|bad substitution" studies/HIST_VNEXT/M06/logs/implementation_session.attempt-4.jsonl   → 0
```
The session received exactly **one** user message (2655 chars, complete and coherent, **0 backticks, 0 `$`**), made **21 `read` calls and 0 writes**, and its last record is a `message_end` mid-thinking with **no `agent_end`** and 8 `turn_end` for 9 `turn_start` — i.e. it was killed mid-work, not blocked by a corrupted prompt. Repair: rewrite the CMD-9 `result`, the certificate `patch_sessions[attempt-4].outcome`, and `REPORT.md:161` to the artifact-supported description (“session aborted at ~30 s while still in the read phase; 21 read calls, no write; no `agent_end` record; the intended edits were applied in attempt-5”), or produce the artifact that proves corruption. The “no file change” conclusion stays valid either way.

**D2 (blocking, provenance completeness of the certificate).** The last session that wrote `REPORT.md` and `BLOCKER_CERTIFICATE.json` — **attempt-6** (session start `2026-10-24T13:05:31.509Z`, exit 0, 12 usage records, cost 0.0340377; `logs/implementation_session.attempt-6.{jsonl,exit.txt,stderr.txt}`; `commands.json` CMD-11 “Normalized REPORT §12 and certificate delivery/executor”; `model_usage.json` / `resource_usage.json` entry present; 5 `edit` calls confirmed in its JSONL) — **appears nowhere** in the two evidence documents:
- `BLOCKER_CERTIFICATE.json` `executor.patch_sessions` lists attempt-3/4/5 only;
- `BLOCKER_CERTIFICATE.json` `amended_utc` = `2026-10-24T13:00:30Z` and `amendment_note` describe **only the attempt-5 patch**;
- `REPORT.md:8` 修订 line likewise says only “attempt-5 patch … 13:00:30Z”.

So the certificate does not record the session that produced it, and its amendment metadata is stale. Repair: add attempt-6 to `executor.patch_sessions` (selector, exit 0, usage/cost from `model_usage.json`, log path), set `amended_utc` to the attempt-6 completion time with an `amendment_note` that states “attempt-6 normalized REPORT §12 and certificate `delivery`/`executor` (self-referential supervisor-file hashes removed); BLOCKED/three-dimension verdicts/nulls/commit unchanged”, and mirror it in `REPORT.md:8` and `REPORT.md:161`.

**D3 (blocking, dangling artifact reference).** `commands.json` CMD-9 → `"exit_record": "studies/HIST_VNEXT/M06/logs/implementation_session.attempt-4.exit.txt"` — **this file does not exist**:
```
ls studies/HIST_VNEXT/M06/logs/ | grep exit→ attempt-1.exit.txt, attempt-2.exit.txt, attempt-3.exit.txt, attempt-5.exit.txt, attempt-6.exit.txt   (no attempt-4)
```
The plan requires the manifest to list only real files and to report a missing reference as missing rather than silently. Repair: either write the real attempt-4 exit record (if one exists outside the log) or replace `exit_record` with the actual artifact path plus an explicit “no exit record file; session terminated without `agent_end` (see D1)” note. Verify with `test -f` before `EVIDENCE_MANIFEST.json` generation.

**D4 (minor, metadata).** `resource_usage.json` `measured_at_utc` = `2026-10-24T12:46:10Z`, but the file contains attempt-5 (12:59–13:05Z) and attempt-6 (13:05–13:07Z) entries. Set it to the actual write time (≥13:07Z) or rename it to the per-entry measurement scope.

**D5 (minor, ordering statement).** `user_work_snapshot.json` `note`: “M06 evidence files are created after this snapshot”. `M06/PLAN.md` and `M06/logs/` were created by CMD-1 at `12:29:17Z`, **19 s before** the `12:29:36Z` snapshot. Substance holds (no M06 file is in the 25 user entries), but reword to “M06 evidence files are excluded from this user-work snapshot (the directory itself was created at 12:29:17Z by CMD-1)”. Also note `untracked_count: 22` is the count of **user** untracked files; the raw `git status` untracked count at that moment was 23 (22 user + `studies/HIST_VNEXT/M06/`) — worth stating explicitly so the later “exactly 25 pre-existing user entries” check is not misread.

**D6 (minor, evidence-chain completeness — recommended).** The package grounds the missing-originals list and the M6-vs-domestic-credit object difference in `H4C/ORIGINAL_COVERAGE.md` and in `PLAN.md:32/13`, but does **not** cite the contract’s own dependency rows, which are the strongest available ground: `07_MANUAL_HISTORICAL_DATA_DOWNLOAD_CHECKLIST.md:42` and `:129` (D06/D07/D17 required before H5G-G1/G2; domestic enterprise borrowing / foreign-trade indices / generic CMEA formulas are prohibited substitutes) and `09_BATCH02_YEARBOOKS_D08_D10_INTAKE.md:41,57`. Adding these two files to `required_contract` (with line ranges and sha256) and to `prerequisite_reviews`/`stop_reason` makes the blocker directly traceable to the contract instead of only to a phase artifact. (I verified both files and their lines myself.)

**D7 (cosmetic).** `REPORT.md` §2 labels the quote cells “verbatim”, but the raw bytes escape pipes as `\|` for the `01_BASELINE_AND_VERSION_AUDIT.md` rows (markdown table escaping; renders identically). Either state “verbatim with markdown pipe escaping” in the cell header or keep the byte-exact strings only in the certificate.

---

## C. Procedure notes for the supervisor (not defects of the candidate)

- `REVIEW.md`, `reviews/round-1.md`, `EVIDENCE_MANIFEST.json` are legitimately absent at round 1 per the plan; the certificate’s `files_not_yet_written` and `review.status=NOT_RUN` correctly record that.
- When generating `EVIDENCE_MANIFEST.json` (`schema_version="hist_vnext_h5g_g1_evidence_v1"`, self-excluded, commit receipt excluded), the plan’s in-memory integrity smoke test still must be run: I confirmed SHA-256 detects a single flipped byte (`b167c110…` → `33418785…` on byte 0) and that `os.path.exists` correctly reports a missing reference; the D3 dangling path must be resolved before the manifest is written.
- After fixing D1–D5, per PLAN §3 the same explicitly-designated MiniMax executor repairs only inside the evidence directory, all rounds are preserved, and the candidate is re-reviewed independently. Do not start G1/G2, do not create `experiments/hist_external.py` / `tests/test_hist_external_mechanisms.py` / `studies/HIST_VNEXT/M10/`, and do not commit before a final independent PASS.

---

## D. Limits of this review

- I did not run `pytest`, `ruff`, `uv lock --check`, `hsm baseline verify`, or any C0/C1 replay; the package correctly declares all of them `NOT_RUN`, and none is required for an evidence-only sealing. I therefore did **not** re-verify the frozen C0/C1 digests as executed results (only as quoted strings, which match `01_BASELINE_AND_VERSION_AUDIT.md:43–46` exactly).
- `EVIDENCE_MANIFEST.json` did not exist, so I verified the underlying bytes/hashes rather than the manifest itself.
- Reviewer-session usage/cost is `PENDING_REVIEW` in `model_usage.json`; I did not and cannot attest to the future review session’s cost record.
- My verification of supervisor-side process facts is limited to the captured JSONL, the exit files, `commands.json`, and the three `model_usage`/`resource_usage` files; I had no access to the supervisor’s shell history, so the D1 repair must be chosen as “rewrite the record to match the artifact” unless the supervisor can produce the corrupting artifact.
- I verified the repository state at review time only; any concurrent user edit after this review is outside my evidence.
- I confirmed I created no repository side effects: `git status` outside `studies/HIST_VNEXT/M06/` is unchanged, no new `.pyc`/bytecode was written, and all scratch output went to `/tmp/h5g_rev/`.