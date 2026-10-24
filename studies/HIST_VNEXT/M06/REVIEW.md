# H5G-G1 M6 外债研究前置阻断 — 独立审查

- reviewer: `phase-reviewer`（仓库 `.omp/agents/phase-reviewer.md`）
- selector: `minimax-code-cn/MiniMax-M3`（由 `@review=...:high` 解析）
- thinking: `high`
- tasks: `H5GBlockerReviewR1`–`R4`
- rounds:
  | round | verdict | duration | verbatim file |
  |---|---|---:|---|
  | 1 | **PATCH** (D1–D7) | 7m27s | `reviews/round-1.md` |
  | 2 | **PATCH** (B1–B5) | 44m24s | `reviews/round-2.md` |
  | 3 | **PATCH** (P1–P2; B1–B5 confirmed) | 52m27s | `reviews/round-3.md` |
  | 4 | **PASS** | 3m38s | `reviews/round-4.md` |
- reviewer usage/cost: `NOT_MEASURED` (the task runner did not return per-session accounting; not zero)
- scope: this PASS covers **blocker judgment + sealed evidence accuracy + evidence-only scope only**. It is **not** H5G engineering/structural/historical acceptance and **not** contract-original admission. H5G remains `BLOCKED`.
- implementer: `minimax-code-cn/MiniMax-M3` (attempts 2, 5–8); supervisor completed logs/usage/manifest. The implementer did not self-sign PASS.

The four independent reviewer returns are reproduced verbatim below. Their internal scratch paths (`/tmp/...`) and references to the then-absent `REVIEW.md`/`EVIDENCE_MANIFEST.json` are preserved as returned.

---

## Round 1 — PATCH

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

---

## Round 2 — PATCH

## Verdict: **PATCH**

I re-verified the round-1 D1–D7 repairs independently, reproduced every core invariant, and read the attempt-4/6/7 session logs directly. D1–D7 are repaired at the locations round-1 named, but the repair round introduced two new evidence-accuracy defects (one dangling hash citation, one residual false failure record), plus a moderate staleness item and two cosmetic items.

---

### A. What I independently reproduced and confirmed

**A1 — Admission audit reproduced byte-exactly (exit 1, `b167c110…`).**
```
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root .
→ exit 1; stdout 4107 B sha256 b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419
  stderr 0 B sha256 e3b0c442…b7852b855
cmp → byte-identical to logs/preflight_admission.attempt-{1,3}.stdout.json
```
Certificate `admission_audit.summary` matches stdout field-for-field (4/4/3/0/0/63, blocked 63, authority_blocked 5, event_candidates 10, review_requests_required 4, independent_pairs 0, non_independent_pairs 1).

**A2 — attempt-4 log (I read it myself).** `logs/implementation_session.attempt-4.jsonl`: 1673 records, all parse; **21** `tool_execution_start`, **all** `toolName=read`,0 writes/edits, 0 tool errors;9 `turn_start` / 8 `turn_end`; **no `agent_end`**; exactly one user message, **2655 chars, 0 backticks, 0 `$`**; `grep -c` for `command not found|corrupt|bad substitution|agent_end` → **0 / 0 / 0 / 0**. No `attempt-4.exit.txt` exists. The delivered prompt has two double-space gaps exactly where the hash literals belong, while attempt-5's file-delivered prompt carries `sha256 b167c110…` / `sha256 e3b0c442…` — consistent with the repaired "substitution evaluated backtick hash literals, body remained coherent" wording. **D1 repaired at REPORT.md:163, certificate `executor.patch_sessions[attempt-4]`, and commands.json CMD-9** (exit `NOT_RECORDED`, `exit_record: null` + note). **D3 PASS** (no dangling `implementation_session.attempt-4.exit.txt` anywhere outside the preserved round-1 review text and the attempt-7 transcript).

**A3 — attempt-6/7 provenance (D2).** Certificate `patch_sessions[attempt-6]`: exit 0, wall 81.87, start `2026-10-24T13:05:31.509Z` (= JSONL `session` timestamp), last message `13:06:48.063Z` (= recomputed max assistant timestamp), tokens 30844/7982/253435/0/292261, cost 0.0340377 — **all exact**. `amended_utc=2026-10-24T13:06:53Z` (= 13:05:31.509 + 81.87) and `amendment_note` describe attempt-5/6; REPORT.md:8 mirrors it. attempt-7 pointer present in `executor.note` + REPORT §10 and supported by commands.json CMD-12 (exit 0, wall 147.18), model_usage.json attempt-7, and `logs/implementation_session.attempt-7.{jsonl,exit.txt}` (EXIT=0).

**A4 — Usage/cost records truthful.** Recomputed from all 7 JSONLs (`message_end.usage`): 78/13/20/9/29/12/21 assistant usage records; sums 473138/195963/9471467/0/10140568; per-session cost 0.42607254/0.08793114/0.12232392/0.01969872/0.17843298/0.0340377/0.07688802 → **exact match** to `model_usage.json` and totals 0.94538502.

**A5 — All quoted contract bytes verbatim.** All 7 `required_contract` entries: file sha256/bytes correct; every quoted line byte-identical to the source (incl. the 4-space-indent strip for `phase-contracts.json`). The new D6 entry `07_MANUAL_HISTORICAL_DATA_DOWNLOAD_CHECKLIST.md:42,129` = sha256 `6db6bd11…b34929`, 21432 B, both lines verbatim. `stop_reason` cites it explicitly. **D6 PASS**; `09_BATCH02…` appears only as a path+hash row in the user-work snapshot and as a citation in the preserved review — **not embedded as user-document content**.

**A6 — F2 finding exact and correctly scoped.** `COMMODITY_INDEX` = 8 P02 keys; F2 `g01…g16`; **overlap = 0** → `desired_usd_outlay = 0` → `draw = min(limit, max(0, 0−reserve)) = 0` (`material.py:1842-1860`, `trade.py:154-236`). Cited file hashes/bytes all match; `rollover` limitation preserved; the non-F2 positive test is marked **not run**.

**A7 — Core invariants re-run.** All 7 M06 JSON files parse; frozen hashes exact (BASELINE.md `1f5b233f…`, research_contract `6f54522a…`, uv.lock `9fd79b62…`, M6/M10 cards); BASELINE.md unmodified (`git diff` empty); 25/25 user-work entries and 22/22 protected entries hash-match current bytes; `git status` unchanged outside `studies/HIST_VNEXT/M06/` (3 M + 22 ?? user files + 1 ?? M06 dir), HEAD still `f88eb43`, nothing staged, **0 `.py` files** in M06, no new `outputs/`; `status=BLOCKED`, technical=BLOCKED_PREREQUISITE / structural=NOT_RUN / historical=BLOCKED, seeds NOT_RUN, `failed_seeds=null`, all 8 missing-contract rows null, `commit=null`, `pushed=false`, `phase_completion_claimed=false`, `review.status=NOT_RUN`, reviewer usage `PENDING_REVIEW`, no first-stage/run-digest/PASS claim.

---

### B. Defects — finite prioritized repair list (all inside `studies/HIST_VNEXT/M06/`)

**B1 (blocking — dangling hash citation; new, introduced by the D5 repair).**
`REPORT.md:153` and `BLOCKER_CERTIFICATE.json:554-555` still cite `user_work_snapshot.json` as sha256 `03a4e46488b17d47ad41d24a5087592bdd89e5e00e758cdc9c4e73f9e95aa33f`,5042 bytes. The file was rewritten during the D5 fix (mtime 13:15:36Z, note now correct) and is now **sha256 `5f4005bd4ff4a4eb66546ee5515d1ae18fc76924f3a8bcb5b4d1efa2f6b5dbf6`, 5225 bytes**. Repo-wide search: **no file has hash `03a4e464…`** → the certificate's `user_work` block binds a non-existent artifact state.
```
python3 -c "import hashlib;b=open('studies/HIST_VNEXT/M06/user_work_snapshot.json','rb').read();print(hashlib.sha256(b).hexdigest(),len(b))"
→ 5f4005bd4ff4a4eb66546ee5515d1ae18fc76924f3a8bcb5b4d1efa2f6b5dbf6 5225
```
Repair: recompute and write the actual sha256/bytes into REPORT.md §9 and `certificate.user_work.{snapshot_sha256,snapshot_bytes}`; re-verify no other cited M06-internal hash is stale.

**B2 (blocking — residual false failure record; D1 relocation).** The artifact-supported wording was applied to the three sites round-1 named, but the contradicted claim survives elsewhere in the same sealed package and now contradicts its own file:
- `commands.json:6` (`note`): "attempt-4's launcher prompt was **corrupted before reaching the model**" — contradicted by attempt-4's JSONL (one complete 2655-char user message; 21 reads executed) and by CMD-9's own repaired result in the same file.
- `model_usage.json:105` attempt-4 `outcome`: "launcher prompt corrupted by shell command substitution **before the model received it**"; and `model_usage.json` attempt-4 `"exit_code": 1` — **no `attempt-4.exit.txt` exists**; CMD-9 and the certificate both record `NOT_RECORDED`.
- `resource_usage.json:94` attempt-4 `note`: "aborted **after launcher-prompt corruption**" — the artifact shows a supervisor cancellation at ~30 s during reads, with no corruption-caused abort.

Repair: replace all three strings with the CMD-9/certificate wording (21 read / 0 write, 9 turn_start / 8 turn_end, no `agent_end`, aborted by supervisor cancellation, no exit file, `exit_code: NOT_RECORDED`).

**B3 (moderate — stale amendment metadata).** `BLOCKER_CERTIFICATE.json` `amended_utc`/`amendment_note` and `REPORT.md:8` still describe a **two-level** (attempt-5 + attempt-6) history ending `13:06:53Z`, but the delivered bytes were last written by attempt-7 (certificate mtime 13:16:52Z, REPORT mtime 13:18:31Z) and contain attempt-7's D1/D3/D6/D7 edits. The attempt-7 pointer exists but the amendment metadata contradicts the artifact's own history. Repair: state three levels (attempt-5/6/7) with attempt-7's D1–D7 scope and a post-13:18Z timestamp, mirrored in REPORT.md:8 (keep the no-self-hash rule — timestamps and narrative only).

**B4 (cosmetic — §2 table no longer renders as a table).** The D7 header `quote（verbatim；表格内 `|` 以 `\|` 转义…）` contains a **raw `|` inside a code span**; GFM splits table cells on unescaped pipes even inside code spans, so the header row has 8 cells vs7 in the delimiter row and the table is not recognized. Evidence: markdown-it GFM renders REPORT.md with **7** `<table>` for 8 candidate tables, and §2 renders as a literal paragraph (`<p>| 合同 / 前置 | …`); escaping that one pipe restores 8. Repair: write the pipe as `\|` (or the word "竖线") in the header and re-render to confirm 8 tables.

**B5 (cosmetic — review block predates the package's own review file).** `certificate.review` = `{status: NOT_RUN, rounds: [], reviewer: phase-reviewer (pending)}` and `delivery.files_not_yet_written` lists `studies/HIST_VNEXT/M06/reviews/round-N.md`, while `reviews/round-1.md` (15514 B, verdict PATCH) is in the same package; REPORT.md:9 ("独立审查: 尚未进行") and §11 ("独立 phase-reviewer 尚未运行") are likewise stale. Cosmetic for the sealed candidate, but must be corrected before the final manifest so the certificate does not assert that no review has occurred.

---

### C. Notes (not defects)

- `EVIDENCE_MANIFEST.json` and `REVIEW.md` are intentionally absent; not counted against the candidate.
- `D5`'s substance is correct: the note now states M06 was created at 12:29:17Z (19 s before the snapshot), excludes M06 from the 25 user entries, and clarifies 22 user-untracked + M06 = 23 raw untracked. Its side effect is B1.
- `D7`'s substance is correct (verbatim + pipe escaping is now stated); its side effect is B4.
- I created no repository side effects: all scratch output went to `/tmp/h5g_rev2/`, and `git status`/HEAD are unchanged; no bytecode written (I ran the admission audit with `PYTHONDONTWRITEBYTECODE=1`).
- B1, B2 and B3 are the round-1 D-class defects recurring in relocated form — they are metadata/provenance repairs inside the evidence directory only. No research, blocker judgment, or scope change is required; REDESIGN is not warranted (blocker judgment, evidence chain, and evidence-only scope are sound and independently corroborated).

**Do not commit until B1 and B2 are corrected and B3 is resolved; B4/B5 may be fixed in the same pass.**

---

## Round 3 — PATCH

All verification is complete. Here is my independent round-3 review.

## Verdict: **PATCH**

All five round-2 defects (B1–B5) are **confirmed repaired**, and every core H5G-G1 invariant re-verifies. One new, self-contained provenance defect remains in the supervisor-owned ledger (`commands.json`), of the same class round-2 required fixed before commit.

### What I independently reproduced and confirmed

**B1 — user-work snapshot hash (PASS).** Recomputed `user_work_snapshot.json` = `5f4005bd4ff4a4eb66546ee5515d1ae18fc76924f3a8bcb5b4d1efa2f6b5dbf6`, 5225 B. REPORT §9 and `certificate.user_work.{snapshot_sha256,snapshot_bytes}` cite exactly this. Round-2's stale `03a4e464…`/5042 is gone from every sealed file. No other M06-internal citation is stale: PLAN.md `7bd46908…`/17660, protected snapshot `cd2cd907…`/3622, all 7 `required_contract` and 8 `prerequisite_reviews` file hashes/bytes match current bytes. `commands/model/resource` hashes are intentionally **not** embedded — confirmed absent everywhere. Certificate/report self-hashes absent (no-self-hash rule holds).

**B2 — attempt-4 record (PASS).** All six named sites agree and match the artifact. From `logs/implementation_session.attempt-4.jsonl` (1673 records): **21** `tool_execution_start`, all `toolName=read`, **0** writes/edits, `turn_start` 9 / `turn_end` 8, **no `agent_end`** (last record is an assistant `message_end` with `errorMessage='Request was aborted'`, `stopReason='aborted'`). No `attempt-4.exit.txt` exists; `exit_code = NOT_RECORDED` in commands.json CMD-9, `model_usage.json` and the certificate. Delivered prompt is coherent: 2655 chars, 0 backticks, 0 `$`, with two double-space gaps exactly where attempt-5's file-delivered prompt carries `sha256 b167c110…`/`sha256 e3b0c442…`. `grep -c 'command not found\|corrupt\|bad substitution'` → **0/0/0**; the only surviving "corrupt" occurrences in the sealed set are inside the quoted-absence clause, which the task permits.

**B3 — amendment metadata (PASS).** `amended_utc = "2026-10-24T14:04:00Z (attempt-8 start; …)"`; `amendment_note` walks attempt-5/6/7/8 with the round-1 (D1–D7) and round-2 (B1–B5) scopes; REPORT line 8 mirrors it. No residual `13:06:53Z` / `13:00:30Z` / "attempt-5 与 attempt-6" markers.

**B4 — §2 table header (PASS).** Header cell contains **no raw pipe**; the only pipe is escaped `\|` inside a code span, and the word 竖线 carries the description. Row analysis: §2 header 7 cells = delimiter 7 = all 9 body rows 7. Real GFM render (markdown-it + markdown-it-github) yields **8 tables**, §2 rendering as a genuine table with 7 `<th>` — the round-2 breakage is gone.

**B5 — review block (PASS).** `certificate.review` records rounds 1 and 2 with verdict PATCH and file paths `reviews/round-1.md` / `reviews/round-2.md`, defers the final verdict to REVIEW.md, and asserts no NOT_RUN. `delivery.files_not_yet_written` = exactly `{EVIDENCE_MANIFEST.json, REVIEW.md}`. REPORT lines 9 and §11 match.

**Core invariants — all PASS.** Admission audit re-run byte-exactly: exit 1, stdout 4107 B `b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419`, `cmp`-identical to attempt-1/3 stdout (all three byte-identical); certificate `summary` matches stdout field-for-field (0 mismatches). Frozen hashes exact (BASELINE.md `1f5b233f…`, research_contract `6f54522a…`, uv.lock `9fd79b62…`, M6 card `047db0a8…`, M10 card `c23d545b…`); BASELINE.md `git diff` empty. 25/25 user entries and 22/22 protected entries hash-match. No out-of-scope change: `git status` outside M06 unchanged (3 M + 22 untracked user files), HEAD still `f88eb43`, index empty, 0 `.py` in M06, no new outputs, no commit. `BLOCKED` + `MISSING_EXTERNAL_DEBT_CONTRACT_ADMISSION`; dimensions technical=`BLOCKED_PREREQUISITE` / structural=`NOT_RUN` / historical=`BLOCKED`; all 8 missing-contract rows null (path/sha256/admission_review/source_id); `failed_seeds` NOT_RUN and `seeds.failed_seeds=null`; `commit=null`, `pushed=false`, `phase_completion_claimed=false`, `simulation_manifests=[]`; no fake first-stage, no run digest, no PASS claim. `model_usage.json` totals recomputed from the JSONLs: attempt-8 = 20 records, 63893/20185/817064/0/901142, cost 0.09241374; totals **537031/216148/10288531/0/11041710**, cost **1.03779876** — exact. All 7 `required_contract` quotes re-verified byte-identical to source lines (incl. the 4-space indent strip for `phase-contracts.json`); all quoted prerequisite-review scopes verified at the cited lines. F2 finding independently corroborated: `COMMODITY_INDEX` = 8 P02 ids, F2 = `g01…g16`, intersection empty → `desired_usd_outlay=0` → `trade.py` draw `= min(limit, max(0, 0−reserve)) = 0`, while `trade.py:154–236` genuinely implements USD reserve/principal/interest/draw; `tests/test_hist_pilot_b.py:261–284` confirmed as the non-F2 positive case (draw=5, import payment=5) and correctly labelled NOT RUN. Every `stdout_path`/`stderr_path`/`exit_record`/byte-count claim in commands.json, the certificate and resource_usage.json resolves to a real file with the stated size — **zero** dangling or mismatched references.

### Defects — finite prioritized repair list

**P1 (blocking; must be corrected before the manifest). `studies/HIST_VNEXT/M06/commands.json` contains a stale finality claim contradicted by its own CMD-13.**

- `commands.json:6` (`note`): `"Patch attempts 3-7 include timeout/abort/repair rounds"` — attempt-8 is also a patch round (CMD-13, `purpose` = `"round-2 PATCH repair: B1 user-snapshot hash, B3 amendment metadata, B4 quote header, B5 review block; B2 supervisor records fixed separately"`).
- `commands.json:209` (CMD-12 `result`): `"…certificate parses as JSON. This is the final repair session and is recorded here plus model_usage.json."` — false in-file, since CMD-13 documents a later repair session in the same array.

Evidence: the file was written at **14:07:22Z**, *after* `attempt-8.exit.txt` (14:07:10Z, `EXIT=0`) and after CMD-13 was appended — i.e. this is not a contemporaneous snapshot. `certificate.executor.note` and REPORT §10 already use the correct scoped form ("The final **round-1** PATCH repair session (attempt-7) … The B1–B5 repair session (attempt-8) …"), so commands.json is the outlier and internally inconsistent with the rest of the package. This is the same defect class as round-1 D2 ("the certificate does not record the session that produced it") and round-2 B3 ("the amendment metadata contradicts the artifact's own history"), both of which the chain treated as commit-blocking.

Repair (supervisor-owned file; no implementer session needed — round-2's B2 was corrected in the same channel): change the note to enumerate attempts 3–8, and change CMD-12's result to the scoped form already used in the certificate, e.g. `"…certificate parses as JSON. This is the final round-1 PATCH repair session; the round-2 B1–B5 repair session (attempt-8) is recorded as CMD-13 and in model_usage.json."` Do not alter CMD-13, the exit codes, paths, byte counts, or any other field.

**P2 (non-blocking, same pass). `resource_usage.json:5` `measured_at_utc = "2026-10-24T14:08:00Z"`** while the file's actual final write was **14:07:22Z**; its scope note defines the field as "the final write time of this file". Round-1's D4 required this field to be ≥ the last content; it now errs *late* by ~38 s rather than stale, so it is cosmetic — but since the field is self-describing, set it to the actual write time.

### Observations (not defects; do not repair)

- `commands.json` CMD-12's "~30 s" wording and `wall_seconds: 30.0` are supervisor-measured values for a cancelled launcher; the substantive facts (21 read / 0 write / 9–8 turns / no `agent_end` / no exit file) are exact and re-verified.
- The raw `logs/implementation_session.attempt-6/7.jsonl` still contain the superseded "corrupted" wording inside assistant thinking/tool-call arguments. That is correct: those are immutable captures of what earlier sessions actually wrote (PLAN §2), and editing them would falsify the audit trail. The sealed *claims* are clean.
- `certificate.delivery.files_written_this_attempt` (attempt-2's three files) is scoped to the sealing attempt; the later rewrites are documented in `amendment_note`.
- `certificate.amended_utc`'s "final bytes sealed in EVIDENCE_MANIFEST.json" is a forward reference, consistent with `delivery.files_not_yet_written` and `package_completeness: "…EVIDENCE_MANIFEST pending"`.
- `model_usage.json.reviewer` = `PENDING_REVIEW` / `NOT_MEASURED` is the expected transitional state (both prior rounds accepted it); the supervisor finalizes it when writing REVIEW.md — it must not be filled with a self-signed figure.

### Scope / hand-off

No research, blocker, verdict, null, seed, commit or scope claim changes are required; no simulation, runner, or test was run and none is warranted. Required supervisor actions after the P1/P2 repair: save this round-3 return verbatim to `REVIEW.md` (optionally also `reviews/round-3.md`); finalize `model_usage.json.reviewer` with the real round-3 usage (or leave it `NOT_MEASURED`); then build `EVIDENCE_MANIFEST.json` over the final bytes listing every actual file including `REVIEW.md`, excluding itself and the post-commit receipt. The certificate's `files_not_yet_written` remains a seal-time snapshot and must not be retro-edited. `REVIEW.md` and `EVIDENCE_MANIFEST.json` being absent is not counted against the candidate.

I created no repository side effects: all scratch went to `/tmp` (`/tmp/mdcheck`, `/tmp/rev3_adm.*`), no bytecode was written, `git status` outside M06 and HEAD `f88eb43` are unchanged.

---

## Round 4 — PASS

## Verdict: **PASS**

Round-4 independent verification of the H5G-G1 (M6) evidence-only blocker package. Both round-3 defects are confirmed repaired at the exact locations named; the core invariants re-verify; no substantive defect remains. This PASS covers **blocker judgment + sealed evidence accuracy + evidence-only scope only** — it is **not** H5G acceptance (H5G remains `BLOCKED`).

### P1 — `commands.json` stale finality: REPAIRED
- `commands.json:6` note now reads `Patch attempts 3-8 include timeout/abort/repair rounds; attempt-4 was aborted at ~30 s while still reading (21 read calls, 0 writes, no agent_end) and wrote no files.` (was `3-7`).
- `CMD-12.result` now: `...certificate parses as JSON. This is the final round-1 PATCH repair session; the round-2 B1-B5 repair session (attempt-8) is recorded as CMD-13 and in model_usage.json.` — scoped, points to CMD-13/attempt-8.
- `CMD-13` intact: `exit_code 0`, `wall_seconds 185.02`, `timeout_seconds 900`, `stdout_path …attempt-8.jsonl` (`stdout_bytes 2686406` = actual file size), `stderr_bytes 0`, `exit_record …attempt-8.exit.txt` (`EXIT=0`), `time_utc 2026-10-24T14:04:06Z` = session timestamp `14:04:06.213Z`.
- "No other field changed" verified by artifact cross-check of all 13 entries (exit files, session timestamps, log byte sizes, `resource_usage` wall times, `model_usage` per-session wall/exit): all consistent; the only `final` string remaining in the file is the corrected CMD-12 one. `commands.json` parses.

### P2 — `resource_usage.json` late `measured_at_utc`: REPAIRED
- `measured_at_utc = 2026-10-24T15:00:12Z` vs actual final write `2026-10-24T15:00:12.576035Z` → **not later** than the write time (was 38 s late).
- attempt-8 entry present (`wall 185.02`, `stdout_bytes 2686406`, `timeout 900`) plus attempts 1–7 and admission attempts 1–3; `stdout_bytes` equal actual JSONL sizes for all 8. JSON parses.

### No stale self-reference
Recomputed: `commands.json` `358aef16fad9f9822dc0665209e957e81116afeae4b71a5fbf90330ce51420c1` / 13240 B; `resource_usage.json` `91102143ed1611ea6c532ec79dafe1534e445bab139a5718f5519957fc43598f` / 4452 B; `model_usage.json` `b3f87a85…` / 8645 B. **None** of these hashes or byte counts appears in `REPORT.md`, `BLOCKER_CERTIFICATE.json` or `PLAN.md`.

### Core invariants re-verified (independent, not inherited)
| Check | Result |
|---|---|
| M06 JSON parse | 7/7 OK |
| Admission audit re-run | exit **1**, stdout **4107 B** `b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419`, stderr 0 B `e3b0c442…`; `cmp`-identical to attempt-1/3 stdout; certificate `admission_audit.summary` matches stdout field-for-field (0 mismatches) |
| Frozen hashes | BASELINE `1f5b233f…`, research_contract `6f54522a…`, uv.lock `9fd79b62…`, M6 `047db0a8…`, M10 `c23d545b…` — all exact; `git diff -- BASELINE.md` empty |
| User / protected snapshots | **25/25** user entries and **22/22** protected entries hash-match current bytes |
| Scope | `git status` outside M06 unchanged (3 M + 22 ?? user files), HEAD `f88eb43a028b4147ca5abe0067c89a99e4ac443a`, index empty, **0** `.py` in M06, no `outputs/` |
| Verdict block | `BLOCKED` / `MISSING_EXTERNAL_DEBT_CONTRACT_ADMISSION`; technical `BLOCKED_PREREQUISITE`, structural `NOT_RUN`, historical `BLOCKED`; implementation/experiments `NOT_RUN`; commit `null`; pushed `false`; `phase_completion_claimed false` |
| Missing contracts | all 8 rows `path/sha256/admission_review/source_id = null` |
| Seeds | `failed_seeds.json` = `NOT_RUN`/`[]`; certificate `seeds.failed_seeds = null`; model_usage `failed_seeds = NOT_RUN` |
| No fake first-stage/run/PASS | certificate field is `not_a_first_stage_evidence`; every PASS token is scoped to H3F synthetic engineering PASS (explicitly not propagated), the audit's own `structural=PASS`, or quoted contract text |
| model_usage | 8 sessions; recomputed from all 8 JSONL assistant usage records → **537031 / 216148 / 10288531 / 0 / 11041710**, cost **1.03779876** — exact, per session too |
| M06-internal citations | user snapshot `5f4005bd…`/5225, protected `cd2cd907…`/3622, PLAN `7bd46908…`/17660 — all current; 7 `required_contract` + 8 `prerequisite_reviews` + 3 src citations hash/byte-exact, quotes verbatim |
| F2 finding | independently confirmed: `P02_COMMODITY_IDS` = 8 ids vs F2 `g01…g16` → overlap **0**; scoped to F2, not "no debt engine" |
| attempt-4 record | 1673 records, 21 read / 0 write, 9 turn_start / 8 turn_end, no `agent_end`, no exit file → `NOT_RECORDED` accurate |

Repo-wide scan of every 64-hex string in `REPORT.md` + certificate: the only 4 unresolved are verbatim quoted values (C0/C1 digest pairs) from `01_BASELINE_AND_VERSION_AUDIT.md` (source `e46979b7…`/10147 matches; lines 30–33, 43–46 byte-verbatim). The only stale hash anywhere (`03a4e464…`/5042) sits inside `reviews/round-2.md`, quoted as that round's defect — correct as an immutable review record.

`REVIEW.md` and `EVIDENCE_MANIFEST.json` are confirmed absent (expected pre-PASS).

### Observations (not defects; do not repair)
- `certificate.review` enumerates rounds 1–2 and `delivery.package_completeness` / REPORT line 9 / §11 / §12 say "round-3 final review pending" — these are seal-time snapshots written at 14:06:45 during attempt-8, before round-3 existed; round-3 explicitly ruled they must not be retro-edited. The full verdict history belongs in `REVIEW.md`.
- `model_usage.reviewer` = `PENDING_REVIEW` / `NOT_MEASURED` — expected transitional state; must never be self-signed.
- `commands.json`/`resource_usage.json` are supervisor-owned ledgers; they must not be edited after the manifest is built or the manifest goes stale.

### Supervisor actions authorized by this PASS
(a) Save this verdict verbatim to `REVIEW.md` and to `reviews/round-3.md` / `reviews/round-4.md` as appropriate (have `REVIEW.md` enumerate rounds 1–4 with their verdicts and defect IDs).
(b) Fill `model_usage.reviewer` with `NOT_MEASURED` or the real reviewer usage — never a self-signed figure.
(c) Then build `EVIDENCE_MANIFEST.json` over the **final** bytes: write `REVIEW.md` (and any `reviews/round-3.md`/`round-4.md`) **first**, then hash every actual file in `studies/HIST_VNEXT/M06/` (39 files currently: PLAN.md, REPORT.md, BLOCKER_CERTIFICATE.json, failed_seeds.json, commands.json, model_usage.json, resource_usage.json, protected_hashes.preflight.json, user_work_snapshot.json, 29 log files, 2 preserved reviews, plus REVIEW.md), excluding the manifest itself and the post-commit `COMMIT_RECEIPT.json`. Do not change any other evidence claim, and note that `certificate.delivery.files_not_yet_written` / `package_completeness` remain seal-time snapshots.

No files were edited by this review; scratch output went to `/tmp` (`/tmp/rev4_adm.stdout.json`, `/tmp/rev4_adm.stderr.txt`), no bytecode written (`PYTHONDONTWRITEBYTECODE=1 -B`), and `git status`/HEAD outside M06 are unchanged.
