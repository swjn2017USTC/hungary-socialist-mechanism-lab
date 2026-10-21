# H5B / M04 Independent Reviews

Read-only `phase-reviewer` sessions; the reviewer did not edit implementation
files.  The text below is the reviewer's output, preserved verbatim.

## Round 1 — 2026-10-21 (PATCH)

**Independent review — H5B / M04 (fresh probes: `outputs/h5b-review-20261021T162018Z/`)**

Verified, no repair required:
- **Scope/whitelist**: HEAD `a3ad69c`; `git diff --check` clean. New/changed bytes are exactly the F2 adapter, the three declared engine hooks, the new test, `studies/HIST_VNEXT/M04/*`, and `docs/phases/HIST_VNEXT/H5B/{PLAN,REPORT}.md`. The three user-dirty files and all pre-existing untracked files match `protected-initial.json`; no `network.py`, `state.py`, `accounting.py`, `finance.py`, `policy.py`, `contract/*`, scenario/config, or old test changes.
- **F2 axis/recipe**: real network tuples empty pre-attach; post-attach `(1,3)→(10,14)`; spec/adapter/study recipe hash all `f2aeef74…`; invalid/duplicate/unknown/non-finite/non-positive/empty/bad-hours/bad-capacity recipes rejected; non-F2 callers stay on legacy.
- **Time/opportunity**: independent tight case (540 endowment, 520 formal, plot 52, second 130) gives plot 5.714 + second 14.286 = 20.0; tolerance 0 → second 0; 0.5 → 11.11/8.89; formal>endowment raises `ConfigError` before mutation; endowment==formal → 0/0; time gate holds every tick.
- **Settlement**: controlled one-household case gives activity 1, inputs 0.02/0.03, funding 0.05 = seller credit, g11 0.10 retained, g15 0.25 expired; plot-only/import/treasury sources give activity 0; funding formula and bank/cash closure hold.
- **Allocator**: weights [2,3], working [1,2], sale 0.15 → receipts [0.01875,0.0375], weighted total 0.15; each substitution shelf consumed once; formal/second payments not doubled; F1 output byte-identical.
- **Experiment**: 144/144 study ticks `COMPLETED`, zero failures, exact zero arm, ordering in all three seeds; my independent `study16` is byte-identical to `study16-final/study.json`, and my `profile`/`reproduce` are byte-identical to the final artefacts.
- **Evidence**: report table numbers match `study16-final/study.json`; C0/C1 re-verified at 116 ticks/1985Q4 with frozen digests and parameter hashes; F1 before/after manifests are identical; all 11 manifest artefact hashes valid and self-excluded; independent `verify` reports no failures; final logs record full pytest 1795 passed, ruff/lock/baseline clean.

Repair list (prioritized; all observations are from fresh probes under `outputs/h5b-review-20261021T162018Z/`):

1. **Process provenance — implementation model timed out, then final files were changed by an unlogged actor.** `runs/impl/usage.json` says `status=timeout, exit=-9, wall=3600.08s`, finished `2026-10-21 23:54:34`; mtimes are later: `material.py 23:56:33`, `second_economy.py 00:07:59`, `household_allocation.py 00:02:15`, `adapter 00:12:29`, `tests 00:07:51`, `runner 00:07:59`, `spec 00:12:22`, `REPORT 00:10:49`. There is no second logged implementation run; `EVIDENCE_MANIFEST.json:79` still says `failures: []`. PLAN §1/§6 require the single explicit MiniMax-M3 process and STOP on a technical timeout. Repro: `cat outputs/hist-vnext-h5b-20261021T145305Z/runs/impl/usage.json; stat -f "%Sm %N" -t "%Y-%m-%d %H:%M:%S" src/hsm_lab/institutions/second_economy_f2_adapter.py studies/HIST_VNEXT/M04/runner.py`. Fix: rerun the implementation/repair step in a fresh logged explicit MiniMax-M3 session (or record actual authorship plus a user waiver), add a model-usage record or `NOT_MEASURED`, list the timeout in the manifest/report, then rerun the final regression.
2. **Checker trusts the trace for production/expiry instead of re-deriving it.** `src/hsm_lab/institutions/second_economy_f2_adapter.py:830-880` consumes `trace["produced"]`/`["expired"]` directly; it never checks `produced == activity ⊗ output_coefficients` and never re-checks commodity `stockable`. Repro: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python outputs/h5b-review-20261021T162018Z/probe_checker_gaps.py` → `output_coefficient_tamper: ACCEPTED (BAD)`, `stockable_g11_expiry_tamper: ACCEPTED (BAD)` (g11 is stockable). Fix: derive expected production from activity and recipe outputs, derive expiry from `commodity_spec(...).stockable`, and require non-stockable closing pool zero; add permanent tests.
3. **Per-household direct-sale receipts and journal counterparties are not checked.** `adapter.py:939-950` compares only the weighted total; `962-975` checks only account class and total amount; `per_participant_receipt_offset_tamper` and `direct_sale_debit_credit_swap` are both accepted in `probe_checker_gaps.py` (weighted total preserved). PLAN §5 row 10 requires rejection. Fix: recompute the working-share receipts per household and validate each leg's payer/payee, currency, and amount.
4. **Input-payment journal has no seller/household counterparties.** `adapter.py:620-645` writes only interbank legs (`_append_interbank_legs`); `978-981` checks only `amount > 0`. A real tick has 10 `hist_second_input_payment` legs, **0 naming an organisation**; retargeting a credit to the Treasury account is accepted (`probe_checker_gaps.py`). PLAN §3 requires deterministic payer/receiver matching. Fix: append real household-cash→organisation-cash legs and verify seller credits and counterparties in the checker.
5. **Runner discards the per-tick trace and the preregistered evidence.** `studies/HIST_VNEXT/M04/runner.py:336-337` stores the trace locally; the return dict at `341-370` omits it; `_summarise_tick` (`373-419`) exports only six F2 totals. `study.json` has no plot self/direct/formal, formal delivered/used, formal availability gap, per-household time/cash/income, or journal counterparties; `REPORT.md:8` therefore overclaims that delivery components are reported. Fix: persist the trace or a bounded per-tick record, add the missing fields, rerun study/profile, and update the manifest/report.
6. **False quantitative claim in the report.** `studies/HIST_VNEXT/M04/REPORT.md:85-87` (and the identical docs copy) says the half arm is “roughly half” and the full arm “roughly twice” the half arm. Actual means: activity 305,371.2 vs 370,737.0 (82.4%, 1.21×); g11 30,537.1 vs 37,073.7 (1.21×). Repro: `cat outputs/h5b-review-20261021T162018Z/logs/report-numbers.log`. Fix the sentence and re-hash.
7. **Preregistration mismatch.** `studies/HIST_VNEXT/M04/spec.json:121-126` declares `FIRST_STAGE_SUPPORTED / FIRST_STAGE_NULL / STRUCTURAL_UNDETERMINED / INVARIANT_VIOLATED`; `REPORT.md:112` uses `FIRST_STAGE_MONOTONE`, which is not declared. The runner hardcodes seeds/ticks/arms (`runner.py:58-59,557-568`) and `study`/`profile` do not record `spec_sha256`. Fix: emit a declared code (or amend the frozen spec before rerunning), drive the run from `spec.json`, bind study/profile to the spec SHA, and assert treatment-only arm differences plus shared initial-state hashes.
8. **Validation/evidence hygiene.** `adapter.py:163-230` accepts an output commodity that is not a household-channel parent (a recipe outputting `g04_basic_metals_materials` attaches successfully; repro `logs/probe-validation.log`); `adapter.py:1011` has unused `_compute_second_substitution_h`; `tests/test_hist_second_economy_f2.py:248,273-275` leave placeholders (`_TRIVIAL_CONTRACT`, `_seed_small_stock` raising `NotImplementedError`); `impl/red-before/capture.py:95` uses `working.sum()` rather than `(weight*working).sum()` for the “expected F2” revenue, so `case2_double_weight_legacy.json` reports weighted 2.667 instead of the implemented/tested 1.0; `impl/red-before-fix/` is empty and the reproduce substitution case is analytic, not an executed legacy run. Fix: reject non-household-channel outputs, delete the placeholders/dead code, and correct or relabel the red-before capture.

Minor: `_summarise_tick` mixes unweighted `second_income_total`/`second_hours_total` with weighted `funding_total`; `gate_residuals.money_gap` is total deposits, not a gap; per-arm network/forcing are shared rather than deep-copied (fresh-arm reruns matched, so no observed contamination). Historical status, composite-measurement disclaimers, and the no-formal-effort/no-welfare claims are honest and not defects.

PATCH

## Round 2 — 2026-10-21 (PATCH)

**Verdict: PATCH**

Round-1's three PATCH items are genuinely fixed on the evidence surface, but the round still fails on (a) a false headline number in the report, (b) an unclosed part of round‑1 item 3 (input‑payment journal + trace‑internal funding closure), and (c) two evidence/manifest accuracy gaps. No engine/accounting defect found.

### What I independently re-tested (all reproductions in `outputs/h5b-review2-20261021T164434Z/probes/`)

| Check | Result |
|---|---|
| Fix 2 – `trace["produced"]` tamper (single coeff, and cross‑region net‑zero) | **REJECTED** by `produced quantity ... activity x recipe coefficient` (`probe_round2.json`) |
| Fix 2 – g11 stockable moved to `expired` (also with pool adjusted so pool identity holds) | **REJECTED** by the stockable rule itself (`F2 trace expires ... stockable 'g11_textiles_footwear'`) — not merely shadowed by pool continuity (`probe_round2b.json`) |
| Fix 2 – g15 expiry dropped / moved across regions / retained in pool | **REJECTED** (non‑stockable rule fires independently) |
| Fix 3 – weighted‑neutral receipt offset between two participants | **REJECTED** per household |
| Fix 3 – direct‑sale debit/credit swap and leg amount shift | **REJECTED** (leg‑exact match) |
| Clean real 1000‑household tick (1188 direct‑sale legs, 10 input‑payment legs) | **PASSES** (`f2_pool_residual` 8.5e‑14) |
| `pytest tests/test_hist_second_economy_f2.py` / directed set / full suite | 40 passed / 105 passed / **1799 passed** |
| `runner.py reproduce|profile` into fresh dir | byte‑identical to `reproduce-final`, `profile4-final` |
| `runner.py verify` fresh | status PASS, `manifest_artifacts_ok`, all artefact + protected hashes still match |
| C0/C1 | 116 ticks, 1985Q4, digests `92f9ea0a…`/`c4810481…`, parameter hashes `e27ade6a…`/`632ee6a6…` reproduced |
| F1 before/after/my own run | 49/49 files byte‑identical, digest `8c2abc84…`, 4 ticks/1957Q4 |
| 144/144 study ticks, zero arm exact, monotone per seed, report table means | all reproduce exactly (max pool 1.14e‑13, max input 1.42e‑14); my 16‑tick rerun of seed 1729 gives 309006.7 / 374955.6 = study values |
| Study/profile independent of checker hardening | `study.json`/`profile.json` byte‑identical to the round‑1 reviewer's pre‑fix runs |
| Fix 1 – fix session | `runs/fix-impl/usage.json` `status=ok`, `exit=0`, `wall=580.7s`, argv `--model minimax-code-cn/MiniMax-M3`; JSONL usage recomputed exactly: 91 assistant messages, input 146 233, output 67 563, cacheRead 9 207 860, total 9 421 656, cost 0.6774171 (matches REPORT §7.1) |
| `ruff` / `uv lock --check` / `hsm baseline verify` / `git diff --check` | all clean/OK |

### Prioritized repair list

**P1 — REPORT states a false result number (both REPORT copies, lines 85‑87; `docs/phases/HIST_VNEXT/H5B/REPORT.md` and `studies/HIST_VNEXT/M04/REPORT.md`)**
Text: "*The half arm realises roughly half of the full arm's activity and material throughput, and the full arm roughly twice the half arm*". Actual: **0.824×** and **1.214×**.
Repro:
```sh
.venv/bin/python - <<'PY'
import json,statistics
s=json.load(open('outputs/hist-vnext-h5b-20261021T145305Z/study16-final/study.json'));seeds=['1729','1730','1731']
for k in ('activity_total','produced_g11','produced_g15','second_input_used_total','funding_total'):
 h=statistics.fmean(sum(t[k] for t in s['arms']['tolerance_05'][sd]['ticks']) for sd in seeds)
 f=statistics.fmean(sum(t[k] for t in s['arms']['tolerance_1'][sd]['ticks']) for sd in seeds);print(k,round(h/f,3),round(f/h,3))
PY
```
Observed: `0.824 / 1.214` for every column. The true mechanism (my 16‑tick rerun, seed 1729): reserved second hours do halve (0.501), the full arm hits the capacity ceiling 23 743 from tick 1 (`capacity` binds 268×, `labor` 52×) while the half arm stays labour‑bound (`labor` 170×, `capacity` 150×). Rewrite the sentence with the hours ratio and the capacity ceiling; keep "first stage, not historical size".

**P2 — `check_f2_second_economy` still trusts trace for funding and does not validate `hist_second_input_payment` legs (round‑1 item 3 only half‑closed)** — `src/hsm_lab/institutions/second_economy_f2_adapter.py:970-984` and `:1096-1099`
Repro:
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python outputs/h5b-review2-20261021T164434Z/probes/probe_round2.py 1000 1.0
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python outputs/h5b-review2-20261021T164434Z/probes/probe_round2b.py
```
Observed: `funding_and_seller_credit_joint_scale` → **ACCEPTED** (reported funding 1543.2654 → 2314.8981 with every gate green); `input_payment_debit_credit_swap` → **ACCEPTED**; `input_payment_household_accounts` (leg accounts replaced by household cash ids) → **ACCEPTED**. `trace["funding"]` equals `flows.household_second_input_funding` to 0.0 on a clean tick, so the anchor is free: compare per‑household funding to that flow, and validate input‑payment legs against `finance.bank_account_ids(...)` reserve/deposit‑liability kinds (reject household‑cash accounts and swapped reserve/credit roles). Add 2 permanent tamper tests. (The round‑1 probe log already recorded this as `ACCEPTED (BAD)`; it is still open.)

**P3 — provenance ledger is incomplete/mischaracterised** — `studies/HIST_VNEXT/M04/EVIDENCE_MANIFEST.json:87,97` and `docs/phases/HIST_VNEXT/H5B/REPORT.md:135-137`
The manifest `resolution` attributes the repair to `runs/fix-impl`, but the engine/runner/spec bytes were finished **before** that session: `material.py` 23:56:33, `household_allocation.py` 00:02:15, `second_economy.py`/`runner.py` 00:07:59, `spec.json` 00:12:22, while `runs/fix-impl/usage.json` `started_at=1792600198.6` = 00:29:58 (and `profile4-check*`, `reproduce-check` 23:57–00:04 show the intervening debugging loop). REPORT's "the scheduler then completed part of *the repair*" mislabels pre‑review implementation completion as repair. Also `implementation_first_session.usage = "NOT_MEASURED"` is avoidable — the killed session's JSONL carries 408 assistant usages: input 385 629, output 214 669, cacheRead 82 828 226, total 83 428 524, cost 5.3429851. State the affected files/interval in `process_failures`/`model_usage` and record the partial totals labelled "partial, session killed".

**P4 — `REVIEW.md` does not exist although the manifest claims it does** — manifest `:113-115` (`review_present: true`, `review_path: docs/phases/HIST_VNEXT/H5B/REVIEW.md`); `ls docs/phases/HIST_VNEXT/H5B/` shows only `PLAN.md`, `REPORT.md`. The round‑1 review 原文 is not preserved anywhere in the repo (PLAN §6/Verification requires `PLAN/REPORT/REVIEW` and "review 原文"). Write the round‑1 PATCH text into that path (and bind it in the manifest / add it to the verify check) before any final PASS.

**P5 — hygiene** — `src/hsm_lab/institutions/second_economy_f2_adapter.py:347-349` comment claims "Endow == formal => scale >= 1, so the joint compression leaves plot/second as-is"; the code and the `tight_time_budget_reserves_nothing` counterexample give **0**. `_compute_second_substitution_h` (`:1180-1207`) is dead (no caller in `src|tests|studies`). Fix the comment, delete the helper.

### Items still not established (independent of the repairs above)
Structural: the tolerance response is first‑stage only and saturates at the 10‑activities/worker capacity ceiling in the full arm — the study cannot separate "policy tolerance" from "capacity" above ~0.5. Historical/calibration remain `UNIDENTIFIED`/`NOT_RUN`; `household_formal_effort` still has no producer, so no formal‑effort feedback is claimed. Runner discipline nit: `ARM_IDS`/`DEFAULT_SEEDS` are hardcoded (`runner.py:51,59,563`) rather than read from `spec.json`, so a spec/runner divergence would not be rejected.

## Round 3 — 2026-10-21 (PATCH)

**Verdict: PATCH**

### Blocking finding (new regression, not caught by the frozen final run)

The round-2 funding/input-journal hardening is correct on funded ticks, but the zero-activity path is now rejected by the new shape anchor. Every declared `tolerance_0` arm fails at tick 0, so the submitted study admits **96/144** ticks, not the reported 144/144.

| Artifact | Observed |
|---|---|
| `outputs/hist-vnext-h5b-20261021T145305Z/study16-final/study.json` | seeds 1729/1730/1731 × `tolerance_0`: **PARTIAL, completed_ticks=0**, error `F2 funding trace shape (0,) does not match the flow (1000,)` |
| `outputs/hist-vnext-h5b-20261021T145305Z/profile4-final/profile.json` | `tolerance_0`: **PARTIAL, completed_ticks=0** |
| Fresh reruns (`outputs/h5b-review3-20261021T170136Z/{profile4,study16}`) | byte-identical to the final artifacts, so this is current code, not a stale output |
| Submitted regression log `runs/study16-final/usage.json` | `status=ok`, `exit_code=0`, `wall_s=5.27` despite the failure |

Root cause: `_record_zero_trace` writes `trace["funding"] = np.zeros(0)` and `trace["seller_credit"] = np.zeros(0)` while the checker unconditionally requires `trace["funding"].shape == flows.household_second_input_funding.shape`, and that flow is always `(N,)`. This also affects any other legitimate no-activity/no-input/no-cash tick, not just tolerance 0.

### What passed independently

- **Round-2 P2 anchoring**: joint funding/seller-credit scaling, input-payment debit/credit swap, and household-account substitution are rejected; clean funded tick passes.
- **Round-1 tamper surface**: produced coefficient/cross-region tamper, stockable g11 expiry, non-stockable g15 expiry/retention, per-household receipt offset, direct-sale swap and leg shift — all `REJECTED`; clean real tick passes (`1188` direct-sale legs, `10` input-payment legs).
- **Report arithmetic**: 0.501 reserved-hours ratio, 0.824 activity/throughput ratio, capacity ceiling, table means, and max residuals reproduce; `FIRST_STAGE_SUPPORTED` is the code declared in `spec.json`.
- **Tests**: F2 file 43 passed; directed set 108 passed; full suite 1802 passed; ruff/lock/baseline/`git diff --check` clean.
- **Reproducibility**: fresh `reproduce`, `profile`, `study` byte-identical to the final artifacts.
- **C0/C1/F1**: 116 ticks/1985Q4 with frozen digests and matching parameter hashes; fresh F1 run byte-identical to both `F1-before` and `F1-after`.
- **Recipe validation**: non-household outputs and unknown outputs rejected; dead helper and test placeholders gone.
- **Provenance/REVIEW**: first-session partial usage and the logged MiniMax repair session reproduce exactly; `REVIEW.md` contains rounds 1–2; manifest includes `REVIEW.md` and excludes itself/verification.
- **Manifest hashes and verify**: all artefact/protected hashes match; fresh `verify` PASS.
- **No F1 drift and no engine/accounting error on completed ticks.**

### Repair list

1. **P1 — make the zero trace axis-complete (blocks all three zero arms).** Fix `_record_zero_trace` to write full-length zeros for funding and seller credit; add a permanent integration test that a real zero-tolerance/no-participant tick passes the checker.
2. **P2 — correct the false report/manifest status claims.** After P1, regenerate study/profile and update both REPORT copies and the manifest from the regenerated JSON; do not claim the zero arm as measured unless it completes 16 ticks.
3. **P3 — enforce the declared completion rule in the runner and regression.** Return nonzero when any arm is not `COMPLETED`/has failures; add a top-level status so the regression fails automatically.
4. **P4 — remove/drive the remaining hardcoded evidence and dead constants (minor).** Derive/assert `treatment_only` from the built policies; remove the unused `ARM_IDS`/`_arm_label`; use the declared seed everywhere.
5. **P5 — disclose the analytic reproduction case (minor).** Label the legacy repair-shelf counterfactual as analytic, not executed.

### Unestablished

Historical identification remains `UNIDENTIFIED`; calibration `NOT_RUN`; the structural response is first-stage and saturates at the 10-activities/worker capacity ceiling; no formal-effort feedback exists.

**PATCH**

## Round 4 — 2026-10-21 (PATCH)

**Verdict: PATCH**

The zero-arm fix, tamper surface, arithmetic, identities and the final regression all hold on fresh probes. One required runner guard is still missing (the second half of round-3 P3), and two evidence-text items are inaccurate. No engine/accounting defect and no F1 drift was found.

### What I re-established independently

| Check | Result |
|---|---|
| Zero-arm fix: fresh `profile`, `study`, `reproduce` | exit 0; `profile4/profile.json` all 3 arms `COMPLETED`/4 ticks; `study16/study.json` **144/144 ticks COMPLETED, 0 failures**; both **byte-identical** to `profile4-final` / `study16-final` |
| Zero arm is a true no-activity trace | all seeds: activity/produced g11+g15/input/funding/second-hours = **0.0**; end pool 1.14e‑15; max pool residual 1.01e‑13; no bypass |
| Round-1/2 tamper surface (real 1000-household tick, 1188 direct-sale legs, 10 input-payment legs) | **14/14 REJECTED**; clean tick and genuine zero tick pass |
| Manifest/report arithmetic | 12 artefact + 5 protected hashes recomputed, **0 mismatches**; spec SHA bound; 144 admitted, 0 failed, max residuals 1.14e‑13/1.42e‑14; table means reproduce; `FIRST_STAGE_SUPPORTED` declared; no 144/96 claim |
| Identities | fresh `verify`: **PASS**, 0 failures, 218 evidence artefacts; C0/C1 116 ticks/1985Q4 with frozen digests/parameter hashes; F1 4 ticks/1957Q4, 49/49 output hashes identical |
| Regression | all 12 logs exit 0; F2 44 passed, directed 109 passed, full 1803 passed, ruff/lock/baseline/`git diff --check` clean |
| Recipe/hygiene | non-household/unknown/etc. rejected; dead constants/helper/placeholders gone; analytic counterfactual labelled; treatment-only/shared opening enforced; seeds/arms read from spec |

### Repair list

1. **P1 — runner does not fail fast on a non-`COMPLETED` arm; there is no top-level status.** `runner.py:648-652`/`:712-718` raise only on `run["failures"]`; `run["status"]` and `completed_ticks == ticks` are never enforced, and profile/study payloads carry no `status`. `study --ticks 15` exits 0 with 135 ticks. Fix: reject any run whose status is not `COMPLETED` or whose `completed_ticks` differs from the declared count, require the mode tick count to equal `spec.run.ticks_profile`/`ticks_study`, emit a top-level `status`, and have the regression assert it.
2. **P2 — manifest overstates the report’s provenance disclosure.** Manifest says round-2/3/4 repairs are disclosed in REPORT §7.1, but the report did not describe the round-3 zero-trace/fail-fast repair or the superseded 96/144 regression. Make the two texts agree.

### Unestablished

Historical identification `UNIDENTIFIED`; calibration `NOT_RUN`; first-stage structural response saturates at the 10-activities/worker ceiling; no formal-effort feedback.

**PATCH**

## Round 5 — 2026-10-21 (PASS)

**Verdict: PASS**

Fresh independent probes are under `outputs/h5b-review5-20261021T172752Z/` (repo files untouched; `git status` still shows only the six pre-existing tracked modifications).

### Executed checks and observed evidence

**1. Completion guards**
- `study --ticks 15` → exit 1, `ConfigError: study ticks 15 != declared ticks_study 16`; empty output dir.
- `profile --ticks 3` → exit 1, `profile ticks 3 != declared ticks_profile 4`; empty dir.
- Declared `profile`/`study` → exit 0; top-level `status=COMPLETED`; `profile` 3 arms × 4 ticks; `study` 9 × 16 = 144/144, 0 failures; byte-identical to `profile4-final`/`study16-final`. `reproduce` byte-identical.

**2. Runner cannot silently accept a bad arm**
A monkeypatched failure-free `PARTIAL` arm with `completed_ticks=16` → rejected; an induced real tick failure → rejected (`AccountingError`); no `study.json` written. Wrong tick count is rejected before any tick executes.

**3. Zero trace and tamper surface**
Real 1000-household seed-1730 tick: clean tick passes (`f2_checked=1.0`, 1186 direct-sale legs, 10 input-payment legs, funding-vs-flow max abs 0.0). Rejected: produced-coefficient tamper (with/without coherent pool edit), stockable g11 expiry, non-stockable g15 retention, per-household receipt offset, direct-sale debit/credit swap, funding+seller-credit joint scale, input-payment debit/credit swap, zero-trace funding/activity tamper. Genuine zero tick: activity/produced/funding/seller-credit/pool zero, funding shape `(1000,)`, seller-credit `(400,)`, checker PASS (`pool_residual 3.4e-15`).

**4. Report / manifest / REVIEW agreement**
- All 12 artefact + 5 protected hashes recomputed: match. Report copies are byte-identical.
- Table means reproduce: activity 305 371 / 370 737; g11 30 537 / 37 074; g15 76 343 / 92 684; input 15 268.56 / 18 536.85; funding 24 429.69 / 29 658.96; end g11 19 732.48 / 25 752.21. Hours ratio 0.5005; activity/throughput 0.8237; max residuals 1.14e-13 / 1.42e-14; monotone in every seed.
- REPORT §7.1 and manifest resolution disclose the round-3 zero-trace/fail-fast repair and the **superseded** 96/144 regression; no current 96/144 claim.
- Provenance numbers recomputed exactly: first session 408 usages, input 385 629, output 214 669, cacheRead 82 828 226, total 83 428 524, cost 5.3429851; repair session 91 turns, input 146 233, output 67 563, cacheRead 9 207 860, total 9 421 656, cost 0.6774171.

**5. Identities / regression**
Fresh `verify`: PASS, 0 failures, 222 artefacts. C0/C1: 116 ticks, 1985Q4, digests `92f9ea0a…`/`c4810481…`, parameter hashes `e27ade6a…`/`632ee6a6…`. F1: 4 ticks/1957Q4, digest `8c2abc84…`, before/after output hashes identical; no drift. Independent reruns: F2 44 passed; full suite 1803 passed; ruff clean; lock/baseline OK. Submitted 12-command regression logs all exit 0.

### Non-blocking observations
- Report table cell `15 268` is floor-rounded (`15 268.55795`); display-only.
- `trace["seller_credit"]` is anchored by total closure and recomputed bank legs, not per-organisation re-derivation; a trace-only same-bank redistribution is accepted and changes no reported metric or settlement state; a tampered `organization_sales_receipts` flow is rejected by `check_material_invariants`.
- Appending this verdict changes `REVIEW.md` bytes, so the manifest hash and round-5 field must be updated and `verify` re-run before commit; production/test/spec/runner bytes must not change after the PASS binding.

### Remains unestablished
Historical identification **UNIDENTIFIED**; calibration **NOT_RUN**; the structural response is first-stage and saturates the 10-activities/person capacity ceiling (full arm binds all 20 regions at tick 1 and most regions thereafter); no formal-effort feedback (`household_formal_effort` has no producer). No full M4 net-stabilisation composite, welfare or political-support claim is made.
