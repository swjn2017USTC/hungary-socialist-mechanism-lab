# H5D M03 — independent review record

**Phase:** HIST_VNEXT H5D · **Mechanism:** M3 · **Study:** M03
**Final verdict:** **PASS** (round 6).
**Blocking code:** `MISSING_LABOR_INSTITUTION_UNIT_SPEC_PASS`
**Scope of this PASS:** the blocker package only — that the H5D prerequisite
labour institution/unit spec is genuinely absent, that the block is correctly
recorded, and that nothing is claimed as implemented. It is **not** a PASS on
H5D implementation, which does not exist.

## Reviewer and roles

- Reviewer: repository `phase-reviewer` subagent, read-only (`read`, `grep`,
  `glob`, `bash`), model `minimax-code-cn/MiniMax-M3`, thinking level `high`,
  per `.omp/agents/phase-reviewer.md` and the project `@review` role.
- Selector is taken from each round's transcript `model_change` record, not
  from the reviewer's self-report. `resolvedModelIsFallback: false` in every
  round; no model switch, no paid fallback.
- The implementer session (`deepseek/deepseek-flash`) never signed a review.
- Per-message token/cache/cost is not persisted by this harness version; the
  only retrievable figures are `model_usage` completion probes, listed per
  round below. No estimate is substituted.

## Rounds at a glance

| round | verdict | started (UTC) | ended (UTC) | errors | probe rows / input / output / cacheRead / cost USD |
| --- | --- | --- | --- | --- | --- |
| 1 | PATCH | 2026-10-22T07:47:03.144Z | 2026-10-22T08:05:00.635Z | 0 | 2 / 6335 / 102 / 90624 / 0.00746034 |
| 2 | PATCH | 2026-10-22T07:59:52.684Z | 2026-10-22T09:36:28.205Z | 0 | 4 / 17504 / 269 / 503040 / 0.03575640 |
| 3 | PATCH | 2026-10-22T09:31:08.686Z | 2026-10-22T09:49:29.596Z | 0 | 2 / 1132 / 134 / 132419 / 0.00844554 |
| 4 | PATCH | 2026-10-22T09:43:51.485Z | 2026-10-22T10:00:18.549Z | 0 | 2 / 1366 / 133 / 115035 / 0.00747150 |
| 5 | PATCH | 2026-10-22T09:53:51.884Z | 2026-10-22T10:13:49.262Z | 0 | 2 / 1571 / 134 / 104738 / 0.00691638 |
| 6 | PASS | 2026-10-22T10:07:04.811Z | 2026-10-22T10:15:27.609Z | 0 | 2 / 2641 / 115 / 102251 / 0.00706536 |

Probe totals over 14 rows: input 30549, output 887,
cacheRead 1048107, cost 0.07311552 USD. Round 6 is this
sealing verdict.

Every round found only bookkeeping, citation or gate-strength defects; no round
found a research-content defect and no round found any implementation, test,
replay, digest or `SUPPORTED` claim.

## What was verified every round

1. The prerequisite is genuinely absent. Independent filename and bilingual
   keyword searches (including ignored files and `git log --all`) over
   `docs/`, `institutions/`, `studies/`, `config/`, `src/`, `history/` and
   `outputs/` found only the requirement text, the legacy blocked declarations
   and this delivery's own files. `studies/HIST_VNEXT/` holds five `spec.json`
   files (M01, M02, M04, pilot_A, pilot_B); none is a labour spec. All 25
   `REVIEW.md` files were scanned; none carries a labour institution/unit PASS.
2. The H3 spine passes are engine-side technical closures only: H3A r2,
   H3B r4, H3C final, H3D r7, H3F-D0 r3, D1 r2, D2 r7, D3 r3; H3E is optional
   per `05:137` and states "No PASS is claimed"; H3G has no `REVIEW.md` and is
   not in the `05:99-152` spine. None covers employment/hire/release rules,
   establishment vs headcount, or nominal-labor to persons/hours conversion.
3. Every hash and byte count in `BLOCKER_CERTIFICATE.json` and
   `EVIDENCE_MANIFEST.json` recomputes from disk; the three `PLAN.md` copies and
   the two `REPORT.md` copies are byte-identical.
4. Protected files are unchanged and the pre-existing user work is untouched;
   `git status` shows only the pre-existing entries plus this delivery's paths.
5. No over-claim: `implementation.status=NOT_RUN`, `files_created=[]`,
   `new_permanent_tests=[]`, `simulation_manifests=[]`,
   `seed_status=NOT_RUN` with `failed_seeds=null`, C0/C1 `actual_digest=null`,
   `research_package_complete=false`, `outputs_committed=false`,
   `pushed=false`.

## Repairs between rounds

- Round 1 (7 defects): missing plan-mandated `delivery.json`; unbound raw
  evidence; H3 scope table limited to A/B/C; frozen-PLAN count; plan-file
  provenance; citation ranges; stale probe description.
- Round 2 (7 defects): plan-file authorship reclassified as this task's own
  `@plan` output; erratum rewritten so both counts are correct at their own
  instants; manifest review rounds; plan-schema `commit_hash`/`commit_status`;
  remaining `165..170` citation; usage disclosure; H3F-D0 scope and D1-D3
  rounds.
- Round 3 (6 defects): review usage and spans grown to all recorded rounds and
  derived from transcripts; dangling post-commit reference; evidence-scope
  label; `state.py` field citation (`:365` is `organization_cash`); plan
  provenance timestamps split into first-write / last-edit / proposed.
- Round 4 (3 defects): certificate review block was stale relative to manifest
  and receipt; the gate could not detect that divergence; the rebuild had to
  touch all three artefacts.
- Round 5 (3 defects): the receipt's final verdict was hand-typed, so the seal
  sequence would have aborted; the gate accepted a PASS whose last round was
  not PASS and whose round records were not all bound; both scripts needed a
  rebuild.
- Round 6: PASS. The seal sequence was simulated end to end in a scratch copy
  (build exit 0, verify exit 0, six rounds, all three artefacts agreeing,
  `REVIEW.md` bound), and both negative mutations — deleting the final round
  record and flipping it to PATCH — now exit 1.

## Residual limits of the gate (disclosed, not exploited)

- Verdict and round-record content are attested lexically: the gate checks that
  the bound record's last verdict token is `PASS`, not that its argument is
  sound. The transcript is the root of trust and is recorded per round.
- `REVIEW.md` content is bound by hash but not cross-checked line by line
  against the round records.
- Package-level status fields (`status`, `blocked`, `research_package_complete`)
  are not gated; they are honest in this package and were verified directly.
- `outputs/` is gitignored, so the round transcripts and log substrate are not
  in the commit; the committed package binds their SHA-256 values instead.

## Sealing note

This file was written after the round 6 verdict. Writing it and
copying round 6's record changes bound bytes, so
`build_manifest.py` was re-run: it derives all three artefacts' review blocks
from the transcripts plus the presence of this file, binds `REVIEW.md`, and
records round 6 as `PASS`. `verify_manifest.py` was then re-run and
exits 0. The only post-verdict changes are this file, the round record copy and
the review/resource/hash fields they affect; the blocker reasoning, the
certificate evidence and the report text were not altered.

## Round records (verbatim)

### Round 1 — PATCH

````text
# H5D Blocker Package — Independent Phase Review

## Audit question 1 — Is the prerequisite genuinely absent?

**Yes. Independently confirmed.** Searches I ran myself (not the package's):

| Probe | Command | Result |
|---|---|---|
| Filenames | `find . -path ./.git -prune -o -path ./.venv -prune -o \( -iname '*labor*' -o -iname '*labour*' -o -iname '*h5d*' \) -print` | Exactly2 hits, both created by this step: `./docs/phases/HIST_VNEXT/H5D`, `./outputs/hist-vnext-h5d-20261022T074508Z` |
| Requirement wording | `grep -rin -E '劳动制度\|单位spec\|labor_spec\|labor institution\|labour institution' docs institutions studies config src history` | Hits only at `05…:221`, `06…:366`, `phase-contracts.json:167`, and the package's own files. No spec artefact, no PASS record |
| Approved spec + PASS | package pattern `(labor\|labour)[ _-]?(spec\|institution).{0,80}(PASS\|approved\|accepted)\|组织劳动\|囤工独立` — I re-ran the **broader** variant below, which the package did **not** run | No approval artefact |
| My own broader probe | `grep -rn -iE '编制\|在岗\|缺勤\|有效工时\|headcount\|labour_hours\|labor_hours\|workforce\|employment_rule\|establishment'` over `docs institutions studies config src history` | Only requirement text (`05:223`, `06:369`, `phase-contracts.json:169`) and "must be added first" statements (`studies/M03/study_decl.json:8`, `studies/manifest.json:32`, `overlay.json:186`). **No labor institution/unit spec anywhere.** |

`config/p06/cards/M3.json` is a mechanism card with `calibrated_parameter_dependencies: []` — not a unit/employment spec. `institutions/HIST_VNEXT/` contains only H1B/H2A/calendar/lead-time files. **The "唯一未满足前置" conclusion is substantively correct; the blocking code `MISSING_LABOR_INSTITUTION_UNIT_SPEC_PASS` is warranted.**

## Audit question 2 — H3A/H3B/H3C PASS scopes

Correctly characterised. Verified in the source files:
- `H3A/REVIEW.md:17-19` — `**PASS** — no reproducible blocking defect remains in the repaired observation layer` (round 2).
- `H3B/REVIEW.md:32-34` — `**PASS** … in the repaired H3B implementation and evidence` (round 4).
- `H3C/REVIEW.md:10-16` — `**PASS** … Acceptance is limited to the revised synthetic, full-information technical routing/shortfall contract. It is **not** historical validation…`

All three are engine-side technical closure; none mentions employment rules, establishment-vs-headcount, or nominal-labor→persons/hours. `H5B/REVIEW.md:167-201` (Round 5 PASS) ends at line 201 with `no formal-effort feedback (household_formal_effort has no producer)` — cited correctly. **No scope overreach found** — but the closure basis is incomplete (Defect 3 below).

## Audit question 3 — Do REPORT claims match the cited files?

Verified line-by-line. **Accurate:** `study_decl.json` (`status: blocked`, `research_package_complete: false`); `overlay.json:159-197` = the `H0B-M03` record (`blocked: 3`, `structural_result NOT_RUN/HYPOTHESIS`, `historical_support UNIDENTIFIED/NOT_RUN`, `no admitted labour-hours or absence series`); `state.py:360-366` contains exactly the five cited labour fields (all at 361-366) with no headcount/attendance/hours; `H5B/REVIEW.md:167-201`; `01_…AUDIT.md:43-46` carries the four C0/C1 digest rows; `05:221-224` and `06:366-369` quotes are verbatim. Line-range errors: Defects 4/6 below.

## Audit question 4 — Blocker certificate schema-completeness

Schema fields all present. I recomputed **every** bound hash: 3/3 `required_contract`, 4/4 `protected`, 21/21 `user_work`, 4/5 `found_evidence` — **all match**. `labor_spec_path/sha256/review_sha256` are `null` with explicit `null_semantics: "NOT_OBTAINED — not zero, not an empty file, not an approval"`. `missing_artifacts` MISSING-1..6 match REPORT §4. `stop_reason` is accurate. Defects: 2 (5th `found_evidence` row lacks `sha256`; computed value is `e46979b7dbe235c09f4caf793164a2b9e7c675fd1679f6fbbd731a704e7f4059`), 3, 5.

## Audit question 5 — Manifest bindings

`.venv/bin/python outputs/hist-vnext-h5d-20261022T074508Z/verify_manifest.py` → `{"ok": true, "failures": [], "review_status": "PENDING"}`, exit 0. I independently recomputed all 5 `artifacts` + 4 `protected` rows (SHA **and** byte counts) — all match. `bytes_written: 67150` = 15776+11357+12884+15776+11357 ✓. Self-excluded ✓. `simulation_status=NOT_RUN`, `simulation_manifests=[]` ✓. C0/C1 `expected_digest`/`expected_parameter_hash` kept separate from `actual_digest=null` ✓. No `PASS`/`SUPPORTED` claim for H5D anywhere (only the negative assertion at `PLAN.md:53`) ✓. PLAN/REPORT pairs byte-identical ✓. `REVIEW.md` absent and declared in `pending_artifacts` ✓. **Gap: the raw search evidence, the command logs and the verify script itself are not hash-bound at all** (Defect 2).

## Audit question 6 — Three-dimensional separation

Correct. `technical=BLOCKED/VERIFIED_BY_CODE`, `structural=NOT_RUN/HYPOTHESIS`, `historical=UNIDENTIFIED/NOT_RUN`; `failed_seeds=null`, `seed_status="NOT_RUN"` with the explicit note that null is *not* evidence of absence of failure. No empty-list "no failed seeds" claim.

## Audit question 7 — Protected files and pre-existing user work

`git status --porcelain=v1 -uall` → 3 `M`, 24 `??` = the 18 pre-existing untracked + the 6 new M03/H5D paths. All 21 `user_work` rows recompute identical; all 4 protected SHAs identical to `01_BASELINE_AND_VERSION_AUDIT.md:33-36` and `config/research_contract.json:expected_baseline_sha256`. `outputs/` is gitignored (`.gitignore:10`). No tracked file changed beyond the three pre-existing user modifications; mtimes of every other repo file predate the step's first command. Defects 4 and 5 apply to the *accounting* of this, not to file integrity.

## Audit question 8 — Overreach

None found. No adapter, no `tests/test_hist_labor_identity.py`, no engine/state/storage edit, no simulation, no C0/C1 replay, no invented conversion coefficient, no invented historical series, no `TODO`/`placeholder`. All 14 `not_executed` entries and `implementation.files_created=[]` are consistent with the filesystem I inspected.

## Defects requiring repair

1. **Plan-mandated delivery receipt missing; REPORT cites a non-existent file.** `PLAN.md:46` mandates `outputs/.../delivery.json` with `commit_hash=null`, `commit_status="NOT_RUN_BLOCKED"`, `pushed=false`, `stop=true`. It does not exist. `REPORT.md:105` (`commit / push | 见 REVIEW/delivery.json`) and `REPORT.md:134` (`@commit 模型调用 | 见 delivery.json`) both point at it. `EVIDENCE_MANIFEST.json` `resource.wall_s` is still `null` / `"filled at delivery"`.
2. **Negative-search evidence is not tamper-evident.** `EVIDENCE_MANIFEST.json` `raw_evidence_files` is a list of bare strings (no `sha256`/`bytes`); `logs/00–03` and `verify_manifest.py` are absent from the manifest; `verify_manifest.py` checks neither. Also `logs/03_protected_sha.txt:2` is an empty-hash row for a non-existent path (`docs/upgrade_review/HIST_VNEXT/research_contract.json`), only corrected at line 5.
3. **`h3_closure` basis does not support the exclusivity claim.** `BLOCKER_CERTIFICATE.json` `h3_closure.passes` lists only H3A/H3B/H3C; `REPORT.md:11` asserts `唯一未满足前置`. The H3 spine in `05:99-152` also contains H3D (`:126`, PASS) and H3F (`:144`, PASS, D0–D3 all PASS) — never examined — and H3E (`:135`, optional) whose `REVIEW.md` ends `Final status — BLOCKED … No PASS is claimed`. The conclusion survives (H3E is `可选` per `:137`), but the exclusivity claim is not evidenced.
4. **Frozen PLAN carries a wrong `VERIFIED_BY_RUN` count.** `PLAN.md:9` states `untracked=17`; the step's own `logs/00_baseline.txt:9-26` (18 `??` rows) and `logs/02_initial_untracked_sizes.txt` (18 rows) at the same HEAD show 18, and `BLOCKER_CERTIFICATE.json` `user_work.counts.untracked` = 18.
5. **Provenance misattribution in `user_work`.** `M3劳动纪律与囤工_PLAN.md` is listed as pre-existing protected user work, but its mtime is `2026-10-22 15:44:18` (≈`07:44:18Z`), ~50 s before the step's first recorded command (`logs/00_baseline.txt:28`, `date -u 2026-10-22T07:45:08Z`); every other root `*_PLAN.md` is from Oct 20 – Oct 22 13:12 or earlier. It is this task's own frozen plan, not user work.
6. **Line-citation defects.** `PLAN.md:13` cites `studies/M03/study_decl.json:1–11` (file has 12 lines). The H5D object in `phase-contracts.json` is cited three ways: `BLOCKER_CERTIFICATE.json` `164-172` (correct), `REPORT.md:27` `165-171`, `raw/21_…txt` `165..170` (drops `stop` at `:171`).
7. **Stale probe description.** `REPORT.md:68` states the filename probe's "唯一命中是本步自建 outputs 目录"; a re-run now returns two hits. The raw file records `ABSENT docs/phases/HIST_VNEXT/H5D`, so the probe itself is honest — the REPORT just omits the timing caveat.

## Prioritised repair list

- **P1** `studies/HIST_VNEXT/M03/REPORT.md:105,134` + `EVIDENCE_MANIFEST.json:resource.wall_s` — write `outputs/hist-vnext-h5d-20261022T074508Z/delivery.json` per `PLAN.md:46` and fill `wall_s`, or delete both dangling references. Repro: `ls outputs/hist-vnext-h5d-20261022T074508Z/` (no `delivery.json`).
- **P2** `studies/HIST_VNEXT/M03/EVIDENCE_MANIFEST.json:raw_evidence_files` — convert to rows with `sha256`/`bytes`, add `logs/00-03` and `verify_manifest.py`, and extend `verify_manifest.py` to check them. Repro: `.venv/bin/python -c "import json;print(json.load(open('studies/HIST_VNEXT/M03/EVIDENCE_MANIFEST.json'))['raw_evidence_files'][0])"` → plain `str`.
- **P3** `studies/HIST_VNEXT/M03/BLOCKER_CERTIFICATE.json:h3_closure` + `REPORT.md:11` — add H3D/H3F verdicts and an explicit H3E-optional/BLOCKED note, or weaken `唯一未满足前置` to what the evidence supports.
- **P4** `studies/HIST_VNEXT/M03/PLAN.md:9` and `docs/phases/HIST_VNEXT/H5D/PLAN.md:9` (byte-identical pair) — correct `untracked=17` → `18` or add an erratum; reconcile with `logs/00_baseline.txt`.
- **P5** `BLOCKER_CERTIFICATE.json:user_work.untracked` — move `M3劳动纪律与囤工_PLAN.md` into a separate `produced_by_this_step` list.
- **P6** `BLOCKER_CERTIFICATE.json:found_evidence[5]` — add `sha256` `e46979b7…`; fix `PLAN.md:13` (`1–11`→`1–12`) and unify the `phase-contracts.json` range to `164-172`.
- **P7** `REPORT.md:68` — add the probe-time caveat (`ABSENT docs/phases/HIST_VNEXT/H5D` at probe time).

**Model selector that answered:** `minimax-code-cn/MiniMax-M3` (project context). **Effort:** NOT_SET.

PASS

PATCH
````

### Round 2 — PATCH

````text
## Verification performed

**1. `verify_manifest.py` — exact output, exit code**

```
$ .venv/bin/python outputs/hist-vnext-h5d-20261022T074508Z/verify_manifest.py
{
  "ok": true,
  "failures": [],
  "review_status": "PENDING"
}
EXIT_CODE=0
```

**2. Row-by-row SHA-256 + byte recomputation (independent, from disk)**

| Row set | Rows | Matched | Mismatch |
|---|---|---|---|
| `EVIDENCE_MANIFEST.artifacts` | 5 | 5 | 0 |
| `EVIDENCE_MANIFEST.protected` | 4 | 4 | 0 |
| `EVIDENCE_MANIFEST.raw_evidence_files` | 16 | 16 | 0 |
| `BLOCKER_CERTIFICATE.found_evidence` | 6 | 6 (SHA; rows carry no `bytes` field) | 0 |
| `BLOCKER_CERTIFICATE.required_contract` | 3 | 3 | 0 |
| `BLOCKER_CERTIFICATE.protected` | 4 | 4 | 0 |
| `BLOCKER_CERTIFICATE.user_work.modified` | 3 | 3 | 0 |
| `BLOCKER_CERTIFICATE.user_work.untracked` | 18 | 18 | 0 |
| 3 × PLAN copies (root + 2 frozen) | 3 | 3 byte-identical (`004757e8…`, 15776 B) | 0 |

**62 row/file checks, 0 mismatches.** `cmp` confirms the two REPORT.md copies are byte-identical (`64de00b3…`, 14117 B). No duplicate JSON keys in any of the three JSON files. No file in the repo was modified after the manifest build (`find -newermt '15:59:38.858'` → empty). `git status -uall` = 3 `M` + 24 `??` = the 18 pre-existing untracked + the 6 new M03/H5D files — no extra paths. Protected files unchanged; `src/`, `config/`, `tests/` untouched (`git diff HEAD` empty).

**3. H3 table — every row re-checked against the actual `REVIEW.md` files**

H3A round 2 ✔ (`H3A/REVIEW.md:15`), H3B round 4 ✔ (`:30`), H3C final ✔ (title "Final PASS"), H3D round 7 ✔ (`:88`), H3F-D0 round 3 ✔, H3F-D1 round 2 ✔ ("second independent review"), H3F-D2 round 7 ✔ ("seventh"), H3F-D3 round 3 ✔ ("third"), H3E `BLOCKED_NO_PASS` ✔ (ends "No PASS is claimed"), H3G `NO_REVIEW_MD` ✔ (no REVIEW.md in `docs/phases/HIST_VNEXT/H3G/`). The 05 anchor claims also check out: `05:221` is the prerequisite line, `05:137` is H3E's "不作为纯规则实验的强制前置", `05:99-152` is the H3 spine (H3G does not appear in 05 at all), `phase-contracts.json:164-172` covers the H5D object incl. `stop` at :171. **All rounds/scopes in the certificate are correct except the H3F-D0 scope label (item P7 below).**

**4. Independent negative search (re-run from scratch, incl. ignored files)**

Filenames, case-insensitive, whole repo excluding `.git`/`.venv` (so ignored dirs included): `*labor* *labour* *h5d* *H5D* *workforce* *headcount* *attendance* *discipline* *hoarding*` → only `./docs/phases/HIST_VNEXT/H5D` and `./outputs/hist-vnext-h5d-20261022T074508Z` (both this delivery's own).
Keywords, case-insensitive: `labor[ _-]?(institution|spec|rule|discipline)`, `labour[ _-]?(institution|spec|rule|discipline)`, `labor_spec`, `labour_spec`, `劳动制度`, `劳动规制`, `单位spec`, `单位转换`, `编制`, `在岗`, `缺勤`, `有效工时`, `工时`, `囤工`, `劳动密集`, `labor hoarding`, `labour hoarding`, `headcount`, `attendance`, `establishment`, `person-hour(s)`, `labor hour`, `labour hour` → hits only in requirement text (05/06/phase-contracts/02 gap matrix), the "must be added first" statements in `studies/M03/study_decl.json:8`, `studies/manifest.json:32`, `research_status_overlay.json:186`, the H5B/M04 household-hour-budget plans, and `config/p06/cards/M3.json` (a mechanism card, `calibrated_parameter_dependencies: []`). Also checked `git ls-files` and `git log --all --diff-filter=A` for labor/labour/h5d/headcount/discipline/hoarding/attendance/establishment/workforce → **no tracked file, ever**. `studies/**/spec.json` = M01, M02, M04, pilot_A, pilot_B — **no M03 spec**. `institutions/HIST_VNEXT/` = H1B/H2A/calendar/lead-time only. **No approved labour institution/unit spec exists.** The blocking conclusion is substantively correct.

**5. No over-claiming** — grep of the whole package for `SUPPORTED`, "H5D 完成/已实现", "测试通过", "replay(ed) success", digest assertions: only the PLAN's own prohibition sentences and other phases' H3 scopes. `failed_seeds: null` / `seed_status: "NOT_RUN"` in manifest, certificate and delivery; `actual_digest: null` for C0/C1; `implementation.status: NOT_RUN`; `simulation_manifests: []`. No `tests/test_hist_labor_identity.py`, no labour adapter, no engine/state/storage change, no sim output. `REVIEW.md` correctly absent and listed in `pending_artifacts`.

---

## Defects

**P1 — P5 not repaired; provenance is affirmatively mislabelled (material).**
`M3劳动纪律与囤工_PLAN.md` (sha `004757e8…`, 15776 B) is byte-identical to this task's **own @plan-phase artifact**: `~/.omp/agent/sessions/-OMP-…/2026-10-22T07-07-34-040Z_01a1626f-c318-7466-be7d-aa689f651149/local/hist-vnext-h5d-plan.md`, written by `openai-codex/gpt-6.1-sol` via a `write` tool call at 07:08:40Z (final mtime 07:28:52Z). Same pattern for prior phases: `HIST_VNEXT_H5B_PLAN.md` == `…/hist-vnext-h5b-plan.md`; `H5C_参照历史棘轮实验_PLAN.md` == `…/hist-vnext-h5c-plan.md`. The root copy appeared at 07:44:18Z, and the user's message at 07:44:38Z is "按照M3劳动纪律与囤工_PLAN.md执行" — i.e. the user is pointing at this task's own plan output. It is **not pre-existing user work**. Yet `BLOCKER_CERTIFICATE.json:255-260` asserts `"provenance": "… user-provided frozen contract"`, `REPORT.md:135` says "它是用户提供的输入", `raw/20:39` says "untracked user work", and `user_work.untracked[17]` carries `preexisting: true`. Round-1 P5's inference was correct; the repair reasserted the opposite with more specificity. No file was harmed (it was neither edited nor staged), but the audit trail now carries a false authorship claim for the contract this delivery implements.

**P2 — P4's erratum misdiagnoses the cause (material).**
`untracked=17` at 07:08:00Z was **correct**: the plan-phase's own `git status` (session `01a1626f…`, line 20) lists exactly 17 `??` rows and **does not contain** the M3 plan file — it was not yet in the tree. `untracked=18` at 07:45:08Z was also **correct** (`logs/00_baseline.txt`, `logs/02…` = 18 rows each, verified). The delta is the plan file's own materialization into the repo root at 07:44:18Z, **not** a counting slip. `BLOCKER_CERTIFICATE.json:476` and `REPORT.md:148` nonetheless declare "17 is a planning-stage counting slip", converting a true contemporaneous VERIFIED_BY_RUN statement into a documented error. The **freeze decision itself is correct and must stand** (editing PLAN bytes would break the byte-identity the plan demands, and all three copies must stay identical) — the byte-identity requirement should not lose. Only the erratum's *wording* must change, to: both counts are correct at their own instants; the difference is the plan artifact's own materialization at 07:44:18Z.

**P3 — manifest `review` contradicts delivery.json (minor).** `EVIDENCE_MANIFEST.json:review` = `{status: "PENDING", review_sha256: null, rounds: []}` while `delivery.json:review.rounds` = `[{round: 1, verdict: "PATCH", evidence: …/reviews/round-1.txt}]`, and the manifest itself hash-binds `reviews/round-1.txt` (`b1c0c507…`). Cause: `build_manifest.py:review_state()` returns `rounds: []` whenever `REVIEW.md` is absent, discarding round 1. A manifest-only reader concludes no review round occurred. `verify_manifest.py`'s required-row set also omits `reviews/round-1.txt` and `logs/03b_protected_sha_correction.txt`.

**P4 — delivery receipt deviates from the plan-mandated schema without an erratum (minor).** `PLAN.md:46` mandates `commit_hash=null` and `commit_status="NOT_RUN_BLOCKED"`; `delivery.json` has **no** `commit_hash` key (renamed `commit.implementation_commit`/`blocker_package_commit`, both null) and `commit_status: "PENDING_FINAL_REVIEW"`. `EVIDENCE_MANIFEST.json:excluded_after_commit` forward-references a `post_commit_receipt.json` that exists nowhere. `resource.bytes_written` (76848) counts the 5 artifacts only and omits the 50262 evidence bytes; `delivery.json` points `outputs_bytes` at `:bytes_written` without saying so.

**P5 — P6 only 2/3 repaired (minor).** `raw/21_search_approved_spec_negative.txt:25` still reads `165..170 (H5D contract row, requirement only)` — the exact third variant round-1 P6 flagged, still dropping `stop` at `phase-contracts.json:171`, and contradicting the unified `164-172` used in `BLOCKER_CERTIFICATE.json` (required_contract and found_evidence) and `REPORT.md` §2. `raw/21` is a hand-written summary (it contains prose "RESULT:"/"NEGATIVE-SEARCH SCOPE LIMIT"), not verbatim tool output, so it is not protected from correction.

**P6 — review token/cache/cost recorded NOT_MEASURED although retrievable (minor).** `PLAN.md:36` requires preserving token/cache/cost for the review; `delivery.json` and `BLOCKER_CERTIFICATE.json` record `usage: "NOT_MEASURED"` with the note "no token/cache/cost metadata returned to this session". The reviewer's own transcript `…/H5DBlockerReview.jsonl` contains exact per-message usage: 40 assistant messages, input 82,159 / output 23,533 / cacheRead 1,801,067, cost **0.160951 USD**, provider `minimax-code-cn` / model `MiniMax-M3` (effort NOT_SET is accurate; the round-1 file's "selector … (project context)" is a guess the transcript confirms). The implementer transcript `…/2026-10-22T07-44-18-516Z_….jsonl` likewise shows 45 assistant messages, cost 0.099415 USD, model `deepseek/deepseek-flash` (matches `delivery.json:implementer_model`).

**P7 — H3F-D0 scope label overstates coverage (minor).** `BLOCKER_CERTIFICATE.json:82` scopes H3F-D0 as "independent foreign-trade financing institution baseline"; D0's own `REVIEW.md` scopes it to the versioned `legacy_treasury_prepay` reference plus read-only double-book observation and states "H3F-D1 … D2 … D3 remain NOT_IMPLEMENTED_IN_D0". `REPORT.md:48` compounds it ("H3F-D0..D3 … 外贸融资") and omits D1/D2/D3's rounds (2/7/3) that the certificate records. The `covers_labor_unit_spec: false` conclusion is unaffected.

---

## Verdict

**PATCH**

Not REDESIGN: the blocking conclusion is independently verified correct, the H3 spine table is now accurate, the manifest binds every artefact, and the package makes no implementation/test/replay/digest/SUPPORTED/PASS claim — there is no simulation, no target leakage, no interpolation, and no multi-commodity shortcut to find. The defects are finite, textual and confined to provenance bookkeeping and citations.

**Prioritised repair list**

1. `studies/HIST_VNEXT/M03/BLOCKER_CERTIFICATE.json:255-260` + `REPORT.md:132-137` + `raw/20:39` — reclassify `M3劳动纪律与囤工_PLAN.md`: remove `preexisting: true` / "user-provided"; state it is this task's own @plan-phase output (sha `004757e8…`, byte-identical to `…/2026-10-22T07-07-34-040Z_01a1626f-…/local/hist-vnext-h5d-plan.md`, written by `openai-codex/gpt-6.1-sol` at 07:08:40Z) materialized into the repo root at 07:44:18Z; keep `modified_by_this_step: false`.
2. `studies/HIST_VNEXT/M03/BLOCKER_CERTIFICATE.json:469-476` + `REPORT.md:140-148` — keep the PLAN bytes frozen (byte-identity requirement stands) but replace the "counting slip" narrative: 17 was correct at 07:08:00Z (plan-phase git status lists 17 `??` without the plan file), 18 correct at 07:45:08Z; the delta is the plan artifact's own materialization at 07:44:18Z.
3. `outputs/hist-vnext-h5d-20261022T074508Z/build_manifest.py:review_state()` + `studies/HIST_VNEXT/M03/EVIDENCE_MANIFEST.json` — record `reviews/round-1.txt` in `review.rounds` even while `REVIEW.md` is pending, so the manifest agrees with `delivery.json` and with its own bound evidence; add `reviews/round-1.txt` and `logs/03b_protected_sha_correction.txt` to `verify_manifest.py`'s required-row set; rebuild the manifest.
4. `outputs/hist-vnext-h5d-20261022T074508Z/delivery.json` — add the plan-mandated `commit_hash: null`; either use `commit_status: "NOT_RUN_BLOCKED"` or record an erratum justifying `PENDING_FINAL_REVIEW`; drop the unbacked `post_commit_receipt.json` forward reference in the manifest and label `bytes_written` as artifacts-only (76848) versus `output_evidence_bytes` (50262).
5. `outputs/hist-vnext-h5d-20261022T074508Z/raw/21_search_approved_spec_negative.txt:25` — change `165..170` to `164-172`; rebuild the manifest afterwards (the file is a curated summary, not protected tool output).
6. `outputs/hist-vnext-h5d-20261022T074508Z/delivery.json` + `BLOCKER_CERTIFICATE.json` `review`/`model_resources` — populate review token/cache/cost and the confirmed selector from `…/H5DBlockerReview.jsonl` (input 82,159 / output 23,533 / cacheRead 1,801,067 / cost 0.160951 USD; `minimax-code-cn/MiniMax-M3`), per `PLAN.md:36`.
7. `studies/HIST_VNEXT/M03/BLOCKER_CERTIFICATE.json:82` + `REPORT.md:48` — restate H3F-D0's scope as the legacy `legacy_treasury_prepay` versioned reference + read-only double-book observation (D1/D2/D3 remain `NOT_IMPLEMENTED_IN_D0`) and add D1/D2/D3 rounds 2/7/3 to the REPORT §3 table.

**Model selector that answered:** `minimax-code-cn/MiniMax-M3` — project `@review` role (`minimax-code-cn/MiniMax-M3:high`); confirmed in this session's transcript (provider `minimax-code-cn`, model `MiniMax-M3`).
````

### Round 3 — PATCH

````text
## Round-3 verification — HIST_VNEXT H5D blocker package

**1. `verify_manifest.py` (exact output, exit code)**

```
$ .venv/bin/python outputs/hist-vnext-h5d-20261022T074508Z/verify_manifest.py
{
  "ok": true,
  "failures": [],
  "review_status": "PENDING"
}
EXIT_CODE=0
```

**2. Independent recomputation from disk (SHA-256 + bytes), 0 mismatches**

| Row set | Rows | Mismatch |
|---|---|---|
| `EVIDENCE_MANIFEST.artifacts` | 5 | 0 |
| `EVIDENCE_MANIFEST.protected` | 4 | 0 |
| `EVIDENCE_MANIFEST.raw_evidence_files` | 17 | 0 |
| `BLOCKER_CERTIFICATE.found_evidence` | 6 | 0 |
| `.required_contract` | 3 | 0 |
| `.protected` | 4 | 0 |
| `.user_work.modified` | 3 | 0 |
| `.user_work.untracked` | 18 | 0 |
| 3 × PLAN copies | 3 | 0 (`cmp` identical, `004757e8…`, 15776 B) |
| 2 × REPORT copies | 2 | 0 (`cmp` identical, `5914d83c…`, 15961 B) |

**65 row/file checks, 0 mismatches.** Arithmetic checks out: `bytes_written` 84100 = 15776×2 + 15961×2 + 20626; `output_evidence_bytes` 65054 = Σ17 evidence rows.

**3. Independent negative search (re-run from scratch, `--no-ignore --hidden`, `.git`/`.venv` excluded). No approved labour institution/unit spec exists.**
- Filenames: `*labor* *labour* *H5D* *h5d* *劳动* *工时*` → 1 hit only: `./M3劳动纪律与囤工_PLAN.md` (this task's plan).
- Keywords: `(labor|labour)[ _-]?(institution|unit|spec)|labor_spec|劳动制度|单位spec|组织劳动|囤积|hoarding|headcount|缺勤|有效工时|编制` (23 hits outside the package/plan) → only requirement text (05:221-224, 06:366-369, phase-contracts.json:164-172), the "must be added first" statements (`studies/M03/study_decl.json:8`, `studies/manifest.json:32`, overlay:186), `config/p06/cards/M3.json` (mechanism card, `calibrated_parameter_dependencies: []`), and **material-inventory** `hoarding_quarters` (P05/MATERIAL/TEST) — a different mechanism, not labour hoarding. Blocking code `MISSING_LABOR_INSTITUTION_UNIT_SPEC_PASS` is substantively correct.

**4. No over-claim.** No adapter/spec/test/replay/simulation; `implementation.status=NOT_RUN`, `simulation_manifests=[]`, `failed_seeds=null` + `seed_status=NOT_RUN`, C0/C1 `actual_digest=null`, `research_package_complete=false`, `outputs_committed=false`, `pushed=false`; no SUPPORTED/H5D-complete/digest-unchanged claim anywhere in the four delivery files. `REVIEW.md` absent from both roots and listed in `pending_artifacts`; `review.status=PENDING`. H3 table re-checked against the actual `REVIEW.md` files (H3A r2, H3B r4, H3C final, H3D r7, H3E 10×REDESIGN/no PASS, H3F-D0 r3, D1 r2, D2 r7, D3 r3, H3G no REVIEW.md) — all correct, H3F-D0 scope now accurate.

**5. Files intact.** `git status --porcelain=v1 -uall` = 3 `M` + 24 `??` = 18 pre-existing untracked + 6 delivery paths; `git diff HEAD --stat` = only the three pre-existing user files (`.omp/config.yml`, `05_…`, `06_…`); BASELINE.md/uv.lock/`config/research_contract.json`/`config/p06/cards/M3.json` unmodified; nothing in the repo modified after the manifest build (09:30:58Z).

**6. Round-2 repairs confirmed:** P1 ✓ (`cmp` exit 0 against `…/local/hist-vnext-h5d-plan.md`; no "user-provided" wording left; transcript shows `write` to `local://hist-vnext-h5d-plan.md` at 07:08:40.157Z by `openai-codex/gpt-6.1-sol`, `model_change`→`deepseek/deepseek-flash`+mode exit at 07:44:18.5Z, first user message 07:44:38.504Z). P2 ✓ — plan-phase `git status` at 07:08:00.521Z lists exactly **17** `??` rows without the M3 plan; 07:45:08Z lists **18**; both narrative and erratum match, no text calls 17 an error. P3 ✓, P4 ✓ (`commit_hash:null`, `commit_status:"NOT_RUN_BLOCKED"`, no `excluded_after_commit`), P5 ✓ (`raw/21:28` now `164-172 … stop clause at :171`), P6 partially (see P1 below), P7 ✓. Regression: 3 JSON files parse, zero duplicate keys; only "missing" paths are the deliberately-labelled wrong-path note and the pending `REVIEW.md`.

---

## PATCH

Not REDESIGN: the block is substantively correct, every bound row recomputes, and the package makes no implementation/test/replay/digest/SUPPORTED/PASS claim — there is no simulation, no target leakage, no interpolation, no single-commodity shortcut to find. The residual defects are finite, textual, and confined to evidence bookkeeping.

**Prioritised repair list**

1. **Review usage is still under-disclosed and mislabelled as exhaustive (minor, same class as round-2 P6).** `delivery.json:review.usage` and `BLOCKER_CERTIFICATE.json:review.usage` list **2** probe rows with the basis "only model_usage probe rows exist in the review transcript"; `REPORT.md:154` says "仅 2 条". Round2's transcript holds **4 more**: `~/.omp/…/2026-10-22T07-44-18-516Z_01a16291-…/H5DBlockerReview2.jsonl` →08:01:54.823Z 454/63/42368/0.00275388; 08:06:56.929Z 4968/55/78208/0.00624888; 08:17:00.056Z 1458/89/141824/0.00905364; 08:47:02.955Z 10624/62/240640/0.0177 — all four predate `built_utc` 09:30:58Z, and that transcript produced the manifest-bound `reviews/round-2.txt`. All six rows: input 23,839 / output 371 / cacheRead 593,664 / cost 0.04321674 USD. Fix: enumerate all six (or scope the claim to round 1) in `delivery.json`, `BLOCKER_CERTIFICATE.json:review.usage` and `REPORT.md` §9. Repro: the transcript scan above.
   *Pushback accepted on the substance*: I confirm no per-message ledger exists — `type:"message"` rows carry only `[type,id,parentId,timestamp,runtime,message]`, the implementer session jsonl has **0** `model_usage` rows, `~/.omp/stats.db` `messages` max(timestamp)=1787847420578 (2026-08-27 16:17:00Z) with 0 rows for `01a16291`. Round-2's figures (82,159/23,533/1,801,067/0.160951) are **not reproducible**; `NOT_RECORDED` is the honest label.

2. **`PLAN.md:37` ("开始/结束/退出与错误") is still unrecorded.** No review start/end/exit/error field exists in `delivery.json`, the certificate or the manifest. Values are retrievable: round 1 `H5DBlockerReview.jsonl`07:47:03.144Z→08:05:00.635Z (session `01a16293-e968-…`), round 2 `H5DBlockerReview2.jsonl` 07:59:52.684Z→09:36:28.205Z (session `01a1629f-a76c-…`), zero error/abort records in either. Add per-round `started_utc`/`ended_utc`/`exit`/`errors` (and the round-3 transcript's own span) to the receipt.

3. **Dangling reference survives in a hash-bound evidence file.** `outputs/…/build_manifest.py:9` docstring still says the manifest excludes "post_commit_receipt.json (written after the commit it records)" — no such file exists anywhere; round-2 P4 removed only the `excluded_after_commit` manifest key. Delete the docstring clause (then rebuild the manifest, since `build_manifest.py` is a bound row).

4. **`resource.output_evidence_scope` under-describes its own sum.** 65054 includes `delivery.json` (3896 B); the scope string names only "raw search/log/review files plus the build and verify scripts". Add delivery.json to the label (`build_manifest.py:196-199`).

5. **Citation imprecision, same class as the `1–11`→`1–12` repair.** `REPORT.md:101` and `BLOCKER_CERTIFICATE.json:found_evidence[2]` cite `src/hsm_lab/engine/state.py:361-366` as "恰为五个" labour fields, but 361-366 is six lines and **365 is `organization_cash`** (visible in the package's own `raw/23…txt`); the five labour fields are at 361, 362, 363, 364, 366. Restate as `361-366 (five labour fields at 361-364,366; :365 is organization_cash)` or narrow the range.

6. **Provenance timestamp labelling (cosmetic).** `source_of_plan.authored_utc = 07:08:40Z` is the first `write`; the frozen bytes are from the last `edit` at **07:28:52.189Z** and `xd://propose` at **07:29:05.007Z**. `REPORT.md:139` ("于 07:08:40Z 写出") reads as completion. Record first-write / last-edit / propose separately.

**Model selector that answered:** `minimax-code-cn/MiniMax-M3`, thinkingLevel `high` — from this session's `model_change` record (`H5DBlockerReview3.jsonl`, 09:31:08.724Z), matching the `@review` role recorded in the manifest.
````

### Round 4 — PATCH

````text
**1. `verify_manifest.py` (exact output, exit code)**

```
$ .venv/bin/python outputs/hist-vnext-h5d-20261022T074508Z/verify_manifest.py
{
  "ok": true,
  "failures": [],
  "review_status": "PENDING"
}
EXIT_CODE=0
```
Read-only; no repo file written (see §6).

**2. Hash recomputation from disk (SHA-256 + bytes): 62 bound rows, 0 mismatches**

| Row set | Rows | Mismatch |
|---|---|---|
| `EVIDENCE_MANIFEST.artifacts` | 5 | 0 |
| `.protected` | 4 | 0 |
| `.raw_evidence_files` | 18 | 0 |
| `BLOCKER_CERTIFICATE.found_evidence` / `.required_contract` / `.protected` | 6 / 3 / 4 | 0 |
| `.user_work.modified` / `.untracked` / `source_of_plan` | 3 / 18 / 1 | 0 |
| 3 × PLAN copies (`studies/…`, `docs/phases/…`, repo root) | 3 | 0 — `004757e8…`, 15776 B |
| 2 × REPORT copies | 2 | 0 — `9b78b7d0…`, 16231 B |

Arithmetic recomputed: `bytes_written` 84676 = 15776×2 + 16231×2 + 20662; `output_evidence_bytes` 79296 = Σ18 evidence rows. `REVIEW.md` absent in both roots, listed in `pending_artifacts`, `review.status="PENDING"`.

**3. Transcript-derived usage/spans, recomputed independently** (filter `rec.type=="model_usage"`, min/max timestamp over all records; 4 transcripts now exist)

| transcript | started | ended | errors | probe rows | input | output | cacheRead | cost |
|---|---|---|---|---|---|---|---|---|
| `H5DBlockerReview.jsonl` | 07:47:03.144Z | 08:05:00.635Z | 0 | 2 | 6335 | 102 | 90624 | 0.00746034 |
| `…2.jsonl` | 07:59:52.684Z | 09:36:28.205Z | 0 | 4 | 17504 | 269 | 503040 | 0.0357564 |
| `…3.jsonl` | 09:31:08.686Z | 09:42:29.579Z | 0 | 2 | 1132 | 134 | 132419 | 0.00844554 |
| `…4.jsonl` (this round) | 09:43:51.485Z | (open) | 0 | 0 | 0 | 0 | 0 | 0 |
| **total** | | | 0 | **8** | **24971** | **505** | **726083** | **0.05166228** |

Matches `EVIDENCE_MANIFEST.review.rounds[0..2]` and `delivery.json:review.rounds[0..2]` exactly (per-round values, `exit:"completed"`, `errors:0`, totals 8/24971/505/726083/0.05166228). Round count 3 is correct **as of `built_utc` 09:43:43.455Z** — round 4's transcript opened 09:43:51Z, after the build. **But see defect D1: the certificate's own review block still records only 2 rounds.**

**4. Dangling-reference grep — result: no dangling reference.** Scanned all 24 package files for path-like tokens; 22 hits, every one accounted for: `outputs/.../delivery.json` (elision placeholder in frozen `PLAN.md:46` and in review files), `tests/test_hist_labor_identity.py` (repeatedly declared `NOT_CREATED` in `not_executed`/`not_executed_acceptance`), `docs/upgrade_review/HIST_VNEXT/research_contract.json` (explicitly labelled wrong-path probe in REPORT §5 erratum and `probe_notes.logs_03_row_2`), and the two `REVIEW.md` paths in `pending_artifacts`. `post_commit_receipt` occurs only inside `reviews/round-2.txt:54` and `reviews/round-3.txt:55` as quoted history of the repaired defect — no live reference remains (round-3 defect 3 ✓). Stale-claim sweep (`仅 2 条`, `165-171`, `165..170`, `untracked=17 是笔误`, `user-provided`, `authored_utc`) → only hits are in the three historical review transcripts; `PLAN.md:13/75`'s `1–11` is the frozen plan body (12-line file, cited as `1–12` in REPORT §5 / certificate) and the `untracked=17` erratum. `post_commit_receipt` in `build_manifest.py:9` docstring is gone; docstring now reads only "EVIDENCE_MANIFEST.json itself is deliberately not hashed". No implementation/test/replay/digest/SUPPORTED/PASS claim: `implementation.status=NOT_RUN`, `files_created=[]`, `new_permanent_tests=[]`, `simulation_manifests=[]`, `seed_status=NOT_RUN`+`failed_seeds=null`, C0/C1 `actual_digest=null`, `research_package_complete=false`, `outputs_committed=false`, `pushed=false`.

**5. Independent negative search — no approved labour spec exists.** Patterns: filenames `*labor* *labour* *h5d* *劳动* *工时* *编制* *在岗* labor_spec` (find, no-ignore, hidden, `.git`/`.venv` excluded) → 3 hits, all this delivery's own artefacts (`M3劳动纪律与囤工_PLAN.md`, `docs/phases/HIST_VNEXT/H5D`, `outputs/hist-vnext-h5d-20261022T074508Z`). Keywords `(labor|labour)[ _-]?(institution|unit|spec)|labor_spec|劳动制度|单位spec|组织劳动|囤工|有效工时|编制|在岗|headcount|attendance|absence` repo-wide → only requirement text (`05:219-225`, `06:362-373`, `phase-contracts.json:164-172`), blocked-reason strings (`studies/manifest.json:32`, `overlay:186/192`, `studies/M03/study_decl.json:8`), and download checklists (`07_…:36/125`, `09_…:35`). `grep -l 'labor_spec|劳动制度|单位spec|labour institution' **/REVIEW.md` → **zero files** (26 REVIEW.md scanned); `institutions/HIST_VNEXT` contains only H1B/H2A evidence and two json fixtures. Blocking code `MISSING_LABOR_INSTITUTION_UNIT_SPEC_PASS` is substantively correct. Citations re-verified: `state.py:361-364,366` labour fields / `:365 organization_cash` ✓; `phase-contracts.json:164-172` incl. `stop` at `:171` ✓; `01_…AUDIT.md:41-46` C0/C1 digests ✓; `H5B/REVIEW.md:167-201` = Round-5 **PASS** heading → final "no formal-effort feedback" ✓; H3 spine verdicts (H3A r2, H3B r4, H3C final, H3D r7, H3E 10×REDESIGN/no PASS, H3F-D0 r3, D1 r2, D2 r7, D3 r3, H3G no REVIEW.md) ✓; provenance `first_write 07:08:40.157Z` (write→`local://hist-vnext-h5d-plan.md`), `last_edit 07:28:52.189Z` (edit; file mtime 07:28:52), `proposed_utc 07:29:05.003Z` (write→`xd://propose`), `plan_mode_set 07:29:05.046Z` (mode_change) ✓; plan-phase `1.bash-original.log` holds exactly 17 `??` rows without the M3 plan, so the 17-vs-18 erratum is factual ✓. No target leakage, no fake interpolation, no fake replicates, no hold-out leakage, no LLM-probability-as-history, no single-commodity shortcut — nothing was implemented.

**6. Files intact.** `git status --porcelain=v1 -uall` = 3 `M` + 24 `??` = 18 pre-existing untracked + 6 delivery paths (4 under `studies/HIST_VNEXT/M03/`, 2 under `docs/phases/HIST_VNEXT/H5D/`). `git diff HEAD --stat` touches only `.omp/config.yml`, `05_REVISED_IMPLEMENTATION_PLAN.md`, `06_OMP_MINIMAX_HANDOFF.md`. All 3 modified + 18 untracked user files byte-identical to `logs/01`/`logs/02` (21 rows, 0 drift). 4 protected files recompute. `find -newermt '17:43:44'` → **empty**: nothing in the repo changed after the 09:43:43Z build. `outputs/` is `.gitignore`d (line 10). `REVIEW.md` absent, pending.

**7. Regression.** 3 JSON files parse, zero duplicate keys, trailing newline present. `delivery.json` vs `EVIDENCE_MANIFEST.json`: round count 3 = 3 (`round_count_matches_delivery:true`, `delivery_round_count:3`), verdicts PATCH×3, totals 24971/505/726083/0.05166228 both sides, `commit.commit_hash:null` / `commit_status:"NOT_RUN_BLOCKED"`, `final_verdict:null` both sides. One cross-artefact field is **not** consistent — D1 below.

---

**PATCH**

Not REDESIGN: the block is substantively correct and independently reproducible from disk and transcripts; every hash recomputes; no implementation, test, replay, seed, digest or PASS claim exists; no research-integrity defect (no leakage, no interpolation, no fake replicates, no single-good shortcut, BASELINE.md untouched, protected files intact). One bound artefact carries a stale review record — the same defect class round 2 flagged as P3 and that round 3's repair pass propagated to the manifest and delivery but not to the certificate.

**Prioritised repair list**

1. **`studies/HIST_VNEXT/M03/BLOCKER_CERTIFICATE.json:505-528` — `review.rounds` omits round 3 (2 entries vs 3 in its sibling artefacts), and `review.status` uses a hand-typed string outside the generator's vocabulary.** Evidence: `delivery.json:review.rounds` has 3 entries (r1/r2/r3 = PATCH) and `EVIDENCE_MANIFEST.json:review.rounds` has 3 with `delivery_round_count: 3`; `EVIDENCE_MANIFEST.raw_evidence_files` hash-binds `outputs/…/reviews/round-3.txt` (`5b2ddf8d724eaeb87a78f56858dc2530b6f79463fb339ffe7d5db4fa41f07e40`, 7968 B) whose last verdict token is `## PATCH` (round-3.txt:44); `H5DBlockerReview3.jsonl`'s last record is 2026-10-22T09:42:29.579Z, i.e. **46 s before** the certificate's mtime 17:43:15 local = 09:43:15Z, so this is not a pre-round-3 snapshot. Repro: `.venv/bin/python -c "import json;print([r['round'] for r in json.load(open('studies/HIST_VNEXT/M03/BLOCKER_CERTIFICATE.json'))['review']['rounds']])"` → `[1, 2]`; same expression on `EVIDENCE_MANIFEST.json`/`delivery.json` → `[1, 2, 3]`. Fix: append `{"round": 3, "verdict": "PATCH", "findings": 6, "evidence": "outputs/hist-vnext-h5d-20261022T074508Z/reviews/round-3.txt"}`; set `"status": "PENDING"` (matching `build_manifest.py:review_state()`, which only ever emits `PENDING`/`PASS`) instead of `"PENDING_FINAL_ROUND"`; add `"final_verdict": null` (delivery and manifest both carry it); then rebuild the manifest, since the certificate is a bound row (`db5453271361a9ba6b115e4d4fa4f939641399288d58fea7bccece3f612a1673`).
2. **`outputs/hist-vnext-h5d-20261022T074508Z/verify_manifest.py:85-88,97-110` — the gate cannot detect D1.** Its `required` set hardcodes `reviews/round-1.txt`, `round-2.txt` and no cross-artefact comparison of review rounds, so it exits 0 on a package whose three JSON artefacts disagree on how many review rounds occurred. Fix: require any `reviews/round-*.txt` row, and assert `len(BLOCKER_CERTIFICATE.review.rounds) == len(manifest.review.rounds) == len(delivery.review.rounds)` (and equal verdict per round). Both scripts are bound rows (`0c2ed980…`, `f654593d…`) → rebuild the manifest after editing.
3. **Round-4 rebuild must touch all three artefacts, not two.** The planned post-verdict rebuild regenerates `EVIDENCE_MANIFEST.json` + `delivery.json` from the transcripts; if `BLOCKER_CERTIFICATE.json:review` is not updated to 4 rounds at the same time, defect 1 reappears one round later. Update the certificate's `review.rounds` in the same pass and re-run `verify_manifest.py`.

Everything else checked out: no stale claims, no dangling paths, no over-claim, no untracked/pre-existing file touched, no post-build modification.

**Model selector that answered:** `minimax-code-cn/MiniMax-M3`, `thinkingLevel: high` (`resolvedModelIsFallback: false`) — from this session's `model_change`/`thinking_level_change` records at 2026-10-22T09:43:51.521Z in `~/.omp/agent/sessions/-OMP-hungary-socialist-mechanism-lab/2026-10-22T07-44-18-516Z_01a16291-6654-765a-8195-d0bf71504e67/H5DBlockerReview4.jsonl`, matching the `@review` role recorded in the manifest.
````

### Round 5 — PATCH

````text
**Model selector that answered:** `minimax-code-cn/MiniMax-M3`, `thinkingLevel: high`, `resolvedModelIsFallback: false` — from this session's `model_change` / `thinking_level_change` records at `2026-10-22T09:53:51.917Z` in `~/.omp/agent/sessions/-OMP-hungary-socialist-mechanism-lab/2026-10-22T07-44-18-516Z_01a16291-6654-765a-8195-d0bf71504e67/H5DBlockerReview5.jsonl`, matching the `@review` role recorded in all three artefacts. (Rounds 1–4 carry the same selector, verified from their own transcripts — the manifest's `selector_basis` claim is true.)

# 1. `verify_manifest.py` — output and exit code

```
$ .venv/bin/python outputs/hist-vnext-h5d-20261022T074508Z/verify_manifest.py
{
  "ok": true,
  "failures": [],
  "review_status": "PENDING",
  "review_rounds": 4
}
EXIT_CODE=0
```

# 2. Cross-artefact round agreement (independent recomputation)

| round | verdict (manifest = cert = delivery) | started_utc | ended_utc | errors | probe rows / input / output / cacheRead / cost |
|---|---|---|---|---|---|
| 1 | PATCH | 07:47:03.144Z | 08:05:00.635Z | 0 | 2 / 6335 / 102 / 90624 / 0.00746034 |
| 2 | PATCH | 07:59:52.684Z | 09:36:28.205Z | 0 | 4 / 17504 / 269 / 503040 / 0.0357564 |
| 3 | PATCH | 09:31:08.686Z | 09:49:29.596Z | 0 | 2 / 1132 / 134 / 132419 / 0.00844554 |
| 4 | PATCH | 09:43:51.485Z | 09:53:18.534Z | 0 | 2 / 1366 / 133 / 115035 / 0.0074715 |

`len` = 4/4/4; tuples, spans, per-round usage and totals identical across `EVIDENCE_MANIFEST.json`, `BLOCKER_CERTIFICATE.json` and `delivery.json`. Summed totals 10 probes / 26337 / 638 / 841118 / 0.05913378 equal `delivery.review.usage.probe_totals` exactly. `status` PENDING/PENDING, `final_verdict` null/null/null. `manifest.review.round_count_matches_delivery: true`, `delivery_round_count: 4`.

Transcript count: `H5DBlockerReview*.jsonl` = **5 files exist now**; the 5th is this session (`model_change` 09:53:51.917Z), created 6.9 s **after** `built_utc = 09:53:45.048598Z`. At build time exactly 4 existed, and all four recorded transcript paths still exist on disk. `verdict_of()` re-parses each `reviews/round-N.txt` to PATCH (round-1 has a PASS token at line 71 inside a quoted earlier verdict and PATCH at line 73 — last-token parsing is correct). All four `round-N.txt` are byte-identical to the session-local `H5DBlockerReview*.md` copies.

**Round-4 repairs: D1, D2, D3 all verified fixed, no regression.** Mutation replays against the gate in a scratch copy outside the repo (`/tmp/h5d_gate_r5`, since removed):

| mutation | gate result |
|---|---|
| cert `review.rounds` truncated to 2 (D1 replay) | **exit 1** — `review rounds differ: manifest [(1,'PATCH'),(2,'PATCH'),(3,'PATCH'),(4,'PATCH')] vs cert [(1,'PATCH'),(2,'PATCH')]` |
| cert round-4 verdict flipped to PASS | **exit 1** — cross-artefact tuple mismatch |
| `delivery.json` rounds truncated to 3 | **exit 1** — `... vs delivery [(1,'PATCH'),(2,'PATCH'),(3,'PATCH')]` |

# 3. Hash recomputation from disk

**41+21 = 62 bound rows recomputed, 0 mismatches.** `artifacts` 5, `protected` 4, `raw_evidence_files` 19, `certificate.protected` 4, `certificate.required_contract` 3, `certificate.found_evidence` 6, `certificate.user_work.modified+untracked` 21. Three PLAN copies (`studies/…`, `docs/phases/…`, repo root `M3劳动纪律与囤工_PLAN.md`) all `004757e8…`, 15776 B; two REPORT copies `9b78b7d0…`, 16231 B, byte-identical pairs `true`. Arithmetic: `bytes_written` 86049 = 15776×2 + 16231×2 + 22035; `output_evidence_bytes` 93523 = Σ19 evidence rows.

# 4. What the new gate still cannot detect — and materiality

Cannot detect: (a) anything about `~/.omp/agent/sessions/**` — a deleted/renamed transcript, or a session directory that `rglob` misses, silently shrinks the round list on all three artefacts and the agreement test still passes (`rounds: []` would be self-consistent); (b) it never re-derives a verdict from the round record, so any record text is accepted verbatim; (c) it does not require the **final** round's verdict to be `PASS` when `status == "PASS"`, nor that every listed round has a hash-bound `reviews/round-N.txt`; (d) non-`review` fields of `delivery.json` (`commit.*`, `prerequisite.*`) are only hashed, never cross-checked against another artefact; (e) `sorted(rglob(...))` orders `H5DBlockerReview10.jsonl` before `…2.jsonl` at ≥10 rounds.

(a), (b), (d), (e) are **not material to the current package** (4 recorded transcripts all present; verdicts re-parsed and correct; those fields are honest today). **(c) is material at seal time** — demonstrated in §5 below: a package with `review_status: PASS`, `final_verdict: PASS` and `rounds[4].verdict: "PENDING"` (no round-5 record) returns `ok: true`, exit 0.

# 5. The disclosed sealing sequence does re-introduce a defect

Reproduced end-to-end in the scratch copy (repo untouched, scratch deleted afterwards), simulating steps (a)–(c) with `REVIEW.md` present:

```
BUILD_EXIT=0     review_status: "PASS", review_rounds: 5, pending: []
VERIFY → {"ok": false, "failures": ["final_verdict differs between manifest and delivery"], ...}
VERIFY_EXIT=1
manifest: PASS PASS   rounds1-4 PATCH, 5 PENDING
cert    : PASS PASS   rounds 1-4 PATCH, 5 PENDING
delivery: final_verdict None
```

Cause: `sync_delivery()` assigns only `review.rounds` and `review.usage`; `sync_certificate()` and `review_state()` both derive `final_verdict` from `REVIEW.md` presence. So the moment `REVIEW.md` exists, manifest and certificate say `PASS` while `delivery.json` still carries the hand-written `null`, and the (correctly strengthened) verifier aborts. **Step (c) of the sequence cannot pass as written.** With that one line repaired and `reviews/round-5.txt` present, the same simulation returns `ok: true`, exit 0, all three artefacts on 5 rounds with round 5 = PASS, 7 artifacts, 20 evidence rows, `review_sha256` bound.

Two further seal-time notes, not defects: after the commit, `delivery.commit.blocker_package_commit: null` and the manifest's `head` = the pre-commit commit stay as-is (the receipt self-scopes: *"at receipt-writing time nothing was staged or committed"*; `outputs_committed: false` remains literally true because `outputs/` is `.gitignore`d line 10). `reviews/round-5.txt` must end with a token that strips to `PASS` and `REVIEW.md` must contain the literal `**PASS**`, or `verify_manifest.py` records `PENDING`/`fails` respectively.

# 6. Negative search for an approved labour institution/unit spec (independent)

Filename probe (`find`, no-ignore, hidden, `.git`/`.venv` pruned, case-insensitive) over `labou?r|h5d|劳动|工时|编制|在岗|出勤|缺勤|雇佣|用工|劳动力|headcount|attendance|absence` → **27 hits, all this delivery's own artefacts** (`M3劳动纪律与囤工_PLAN.md`, `docs/phases/HIST_VNEXT/H5D/{PLAN,REPORT}.md`, `outputs/hist-vnext-h5d-20261022T074508Z/**`). **No approved spec, no spec file, no unit-conversion basis.**

Keyword sweep (`gitignore: false`, so ignored paths included) over `劳动制度|单位\s*spec|labor_spec|labour_spec|labor institution|labour institution|组织劳动|囤工独立|有效工时|编制|在岗|headcount|attendance rate|absence rate|employment rule|hire/release|用工制度|雇佣规则|释放规则|招聘规则` → hits only in: requirement wording (`05:219-226`, `06:362-373`, `evidence/phase-contracts.json:164-172`), legacy audit/gap-matrix blocked-reason strings (`01_TEST_AND_REPRO_AUDIT.md:70`, `02_MECHANISM_GAP_MATRIX.md:15`, `03_DEPENDENCIES_AND_SOURCES.md:77`, `04:91,93`), the audit baseline `HSM_LAB_VNEXT_CODEX_AUDIT_BASELINE_2026-10-11.md:156,178` (design intent, not an approval), download checklists `07:36,125` / `09:35` (D11 marked *"H5D历史解释/识别前"*), `data/private/hist_vnext_sources/batch02_20261020/` D08/D09/D10 locator + limitation notes (no target values; reviewer read-only sweep, no HOLD/target file opened), and this package's own PLAN/REPORT. **No REDESIGN trigger.** This matches the recorded `raw/21_search_approved_spec_negative.txt` and `certificate.searched`.

# 7. No over-claim; repo state

No implementation (`tests/test_hist_labor_identity.py`, `studies/HIST_VNEXT/M03/runner.py`, `src/hsm_lab/engine/labor.py` all absent), no tests/replays/commits (`implementation.status NOT_RUN`, `files_created []`, `new_permanent_tests []`, `simulation_manifests []`, C0/C1 `status NOT_RUN` + `actual_digest null`, `seeds.failed_seeds null`, `research_package_complete false`, `blocked true`, `stop true`, `outputs_committed false`, `pushed false`, `model_usage NOT_RECORDED`, no `SUPPORTED` anywhere). `REVIEW.md` absent in both roots and listed in `pending_artifacts`; `review.status PENDING`, `final_verdict null` — pending and consistent. All four protected files recompute and show **no** `git diff` against HEAD (BASELINE.md untouched: `1f5b233f…`). All 21 declared user-work files byte-identical; `git status --porcelain -uall` = 3 `M` (exactly the declared set) + 24 `??` = 18 declared pre-existing + 6 delivery paths, nothing else; nothing staged. `find -newermt '2026-10-22 17:53:59'` → empty: no repo file touched since the build. Recorded probe totals in `REPORT.md` §9 cover rounds 1–3 only (8 probes / 24971 / 505 / 726083 / 0.05166228, arithmetically exact for the three rounds it names) and defer per-round detail to the manifest; stale-by-one but self-scoped, not a false claim — no repair required.

# 8. Prioritised repair list (finite)

1. **`outputs/hist-vnext-h5d-20261022T074508Z/build_manifest.py`, `sync_delivery()`** — derive the receipt's final verdict instead of leaving it hand-typed, mirroring `sync_certificate()`:
   `delivery["review"]["final_verdict"] = "PASS" if (STUDY / "REVIEW.md").is_file() else None`
   *Evidence:* without it the disclosed seal step (c) exits 1 with `"final_verdict differs between manifest and delivery"` (reproduced above). This is the same hand-typed-review-block class as round-4 D1.
2. **`outputs/hist-vnext-h5d-20261022T074508Z/verify_manifest.py`, inside the `if review_status == "PASS":` branch** — add two assertions: the last round's `verdict` must be `"PASS"`, and every round in `manifest["review"]["rounds"]` must have a hash-bound `…/reviews/round-<n>.txt` evidence row.
   *Evidence:* scratch seal simulation with that one line from item 1 applied and `reviews/round-5.txt` absent → `{"ok": true, "failures": [], "review_status": "PASS", "review_rounds": 5}`, exit 0, while `rounds[4].verdict == "PENDING"` — a false "independent PASS" would ride through the gate.
3. **After editing either script, re-run `build_manifest.py` in the repo and then `verify_manifest.py`.** Both scripts are hash-bound evidence rows (`verify_manifest.py` `b3949cfa…`, `build_manifest.py` `38c87036…`); editing them without a rebuild makes the gate fail on `evidence: sha mismatch`.

No research-content repair is required: the blocker reasoning, the H3-spine scoping, the missing-spec definition, the negative search and the NOT_RUN accounting are substantively correct and independently reproducible from disk and transcripts.

**Verdict: PATCH**

PATCH
````

### Round 6 — PASS

````text
**Model selector that answered:** `minimax-code-cn/MiniMax-M3`, `thinkingLevel: high` — from this session's `model_change` / `thinking_level_change` records in `~/.omp/agent/sessions/-OMP-hungary-socialist-mechanism-lab/2026-10-22T07-44-18-516Z_01a16291-6654-765a-8195-d0bf71504e67/H5DBlockerReview6.jsonl`, matching `@review` in `.omp/config.yml`.

---

## 1. `verify_manifest.py` — real repo

```
$ .venv/bin/python outputs/hist-vnext-h5d-20261022T074508Z/verify_manifest.py
{
  "ok": true,
  "failures": [],
  "review_status": "PENDING",
  "review_rounds": 5
}
EXIT=0
```

## 2. Round-5 repairs — verified in code and by reproduction

| # | Repair | Located | Status |
|---|---|---|---|
| 1 | `sync_delivery()` derives the receipt's `final_verdict` | `build_manifest.py:211-213` | present |
| 2 | Gate rejects empty rounds / non-PASS last round / unbound round record | `verify_manifest.py:146-158` | present, both new branches fire (below) |
| 3 | Both scripts are hash-bound evidence rows | `build_manifest.py:38 EVIDENCE_EXTRA`, rows `9dc17ecc…` / `c41f19bf…` | present, live bytes MATCH |

## 3. Sealing simulation (`/tmp` scratch copy, repo untouched)

Sequence (a) REVIEW.md byte-identical in both locations with literal `**PASS**`, (b) `reviews/round-6.txt` present ending in a `PASS` token, (c) build, (d) verify.

```
BUILD_EXIT=0  {"artifacts":7,"evidence_rows":21,"pending":[],"review_status":"PASS","review_rounds":6}
VERIFY {"ok":true,"failures":[],"review_status":"PASS","review_rounds":6}   VERIFY_EXIT=0
```
Round tuples and status, all three artefacts, agreeing:
`[(1,PATCH),(2,PATCH),(3,PATCH),(4,PATCH),(5,PATCH),(6,PASS)]`; manifest/cert/delivery `status=PASS`, `final_verdict=PASS`, `pending_artifacts=[]`, `round_count_matches_delivery=True`.
REVIEW.md bound: `review_sha256 fc5e4f13…` equals the live `shasum` of `studies/HIST_VNEXT/M03/REVIEW.md`; both copies also bound as artifact rows (7 artifacts).
Totals: artifacts 7, evidence 21, protected 4, `bytes_written` 88691, `output_evidence_bytes` 117306, delivery probe totals 14 rows / input 30549 / output 887 / cacheRead 1048107 / cost 0.07311552 USD.

One operational note for the scheduler, not a defect: the gate requires the literal string `**PASS**` in REVIEW.md. My first simulation draft used a bare `PASS` line and correctly failed (`"review PASS declared but REVIEW.md carries no PASS verdict"`, exit 1); the disclosed seal text already mandates `**PASS**`.

Negative mutations:

- **(i) `reviews/round-6.txt` removed, status PASS kept.** Without rebuild: `{"ok":false,"failures":["evidence: missing …/reviews/round-6.txt"]}`, **EXIT=1**. With rebuild (round 6 falls to `PENDING`): `{"ok":false,"failures":["final round verdict is 'PENDING', not PASS","round 6 record is not hash-bound"]}`, **EXIT=1**.
- **(ii) `round-6.txt` ending in `PATCH`.** With rebuild: `{"ok":false,"failures":["final round verdict is 'PATCH', not PASS"]}`, **EXIT=1**. Without rebuild: `["evidence: sha mismatch …","evidence: size mismatch …"]`, **EXIT=1**.

Both round-5 gate repairs are load-bearing and were demonstrated to fire.

## 4. Hash recomputation (my own, independent of the verifier)

| Set | Rows | Mismatches |
|---|---|---|
| `manifest.artifacts` | 5 |0 |
| `manifest.protected` | 4 | 0 |
| `manifest.raw_evidence_files` | 20 | 0 |
| `cert.found_evidence` | 6 | 0 |
| `cert.required_contract` | 3 | 0 |
| `cert.protected` | 4 | 0 |
| `cert.user_work` (modified 3 + untracked 18) | 21 | 0 |

PLAN study≡phase: identical. REPORT study≡phase: identical. PLAN study≡root `M3劳动纪律与囤工_PLAN.md`: identical. **No mismatches.** Live protected SHAs equal the manifest's and equal the values recorded at step start (`1f5b233f…`, `6f54522a…`, `9fd79b62…`, `06adefbd…`), and `git diff HEAD` over `src tests config studies/M03 studies/manifest.json studies/HIST_VNEXT/declarations BASELINE.md uv.lock` is empty.

## 5. Remaining gate blind spots (materiality judged)

1. **Verdict provenance is lexical, not semantic.** `verdict_of()` scans for the last bare `PASS|PATCH|REDESIGN` token. My mutation (ii) used exactly that property; conversely a record whose *argument* is "this round should have been PATCH" but whose last token line reads `PASS` would pass. Mitigation: the transcript is the root of trust and each round record is bound to it by construction, so this is not exploitable without tampering the transcript, which the manifest's `transcript` path records. **Not material** — but it means the gate attests "the transcript round-N file ends in PASS", nothing more.
2. **REVIEW.md content is not cross-checked against the round records.** A REVIEW.md containing only `**PASS**` passes (reproduced: `ok:true`, exit 0). The gate does not verify that REVIEW.md lists all rounds verbatim as the seal step promises. **Not material to this package** — the verifier's job is binding, and the reviewer's own transcript is the evidence — but it is the sharpest residual gap and it is exactly what step (a)'s "listing all rounds verbatim" requirement is not machine-enforced against.
3. **`round-N.txt` content is unconstrained.** Replacing it with the single line `PASS` still yields `ok:true`, exit 0. **Not material** — same reason as (1): the round files are hash-bound copies, and the transcript is the primary record.
4. **Package status fields are not gated.** Setting `status=COMPLETE`, `blocked=false`, `research_package_complete=true`, `pushed=true` in the manifest and rebuilding passes (reproduced: `ok:true`, exit 0). The gate asserts only `implementation.status == NOT_RUN`, `simulation_manifests == []`, `failed_seeds is None`, C0/C1 `NOT_RUN`/`actual_digest null`. **Material as a class, immaterial here**: the current real values are `status=BLOCKED`, `blocked=true`, `research_package_complete=false`, `outputs_committed=false`, `pushed=false`, verified directly above. A future package could launder a completion claim through the manifest; for this blocker package nothing is being laundered.
5. **Text tampering inside a bound artefact is undetectable by the gate** — appending "H5D implementation complete, tests passed" to REPORT.md and rebuilding passes (reproduced). **Not material**: the gate binds bytes, it does not police prose; prose policing is this review's function, and the current REPORT/PLAN text makes no such claim (scan for `SUPPORTED|已完成|implementation complete|tests passed` returns only the PLAN's own negative gate statement at `:53`).
6. **`outputs/` is gitignored**, so nothing in the round records or transcripts is committed. Combined with (1)–(3), the sealed commit carries the verdict but not the machine-checkable substrate. **Not material** to the blocker decision (which rests on files that *are* committed: PLAN/REPORT/CERT/MANIFEST and the protected hashes), but it does bound what a future auditor can re-derive from the repository alone.

## 6. Package hygiene confirmed

No `tests/test_hist_labor_identity.py`; no `src`/`state.py`/storage edits; no replay; no actual digest (both `null`); no `SUPPORTED`; no PASS claim in the current package. `studies/HIST_VNEXT/M03/REVIEW.md` and `docs/phases/HIST_VNEXT/H5D/REVIEW.md` are absent; `pending_artifacts` lists both; status PENDING. `git status --porcelain=v1` = 23 entries: the 3 pre-existing tracked modifications (`.omp/config.yml`, `05_REVISED_IMPLEMENTATION_PLAN.md`, `06_OMP_MINIMAX_HANDOFF.md`), the 18 pre-existing untracked plan files, plus the two delivery directories `docs/phases/HIST_VNEXT/H5D/` and `studies/HIST_VNEXT/M03/`. Staged = 0. HEAD unchanged at `3ec08983f0ca2f77dc1a5e446e4f39e7fab7be98`.

## 7. Independent negative search for an approved labour institution/unit spec

Patterns run (whole repo, gitignore respected, `.git`/`.venv` excluded, untracked files included):
- filenames: `*labor*`, `*labour*`, `*h5d*`, `*workhour*`, `*headcount*`, `*discipline*`, `*hours*`, `*establish*`, `*workforce*`, `*spec*` under `studies/ docs/phases/ institutions/ config/`
- content: `劳动制度|单位spec|labor_spec|劳动单位|工时制|劳动纪律|囤工|hoarding`; `(labor|labour)[ _-]?(spec|institution|unit|discipline|hours)[^|]{0,120}(PASS|approved|accepted|admitted|已批准|通过)`; `labor_(unit|discipline|institution)|labour_(unit|institution)|workforce_spec|employment_rule`

Result: **no approved labour institution/unit spec and no PASS record binding one.** Only hits are the requirement text itself (`05:221`, `06:366`, `evidence/phase-contracts.json:164-172`), the legacy blocked declaration (`studies/M03/study_decl.json:3,8,11`, `studies/manifest.json:32`, `research_status_overlay.json:163`), the H5B boundary line "no formal-effort feedback" (`H5B/REVIEW.md:199-201`, confirmed), and this step's own blocker package. `studies/HIST_VNEXT/` contains exactly five `spec.json` files (M01, M02, M04, pilot_A, pilot_B) — none labour. All 25 `REVIEW.md` files enumerated; `H5D` has none.

H3 spine cross-check from disk: H3A round 2, H3B round 4, H3C final, H3D round 7, H3F-D0 round 3, H3F-D1 round 2, H3F-D2 round 7, H3F-D3 round 3 all carry `**PASS**`; H3E exists but its text states "No PASS is claimed" (`H3E/REVIEW.md:322`) and matches `05:137` marking it optional; H3G has PLAN.md+REPORT.md and no REVIEW.md. Every one is engine-side technical closure and none covers employment/headcount/unit conversion, so the block stands independently of H3 status. C0/C1 expected digests in the manifest match `01_BASELINE_AND_VERSION_AUDIT.md:43,45` exactly and remain `actual_digest=null` (constant reference, not a replay) — correctly disclosed.

No blocking defect remains. The three round-5 repairs are real, the seal sequence closes cleanly at exit 0, and both negative mutations exit 1. The residual blind spots are gate-scope limits that this package does not exploit.

PASS
````

