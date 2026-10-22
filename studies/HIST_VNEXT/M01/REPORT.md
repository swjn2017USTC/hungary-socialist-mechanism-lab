# H5C M01 — matched reference-history ratchet experiment

**Phase:** HIST_VNEXT H5C · **Mechanism:** M1 · **Study:** M01
**Verdict:** technical **PASS**; structural **CONDITIONAL / UNIDENTIFIED** by
lever; historical **UNIDENTIFIED**.
**No next ID was started and nothing was pushed.**

## 1. Question and design

The legacy M1 card compares a one-shot welfare cut at **1961Q1** with the same
cut at **1967Q1**. Those are different calendar points, so quarter, cash,
physical supply, external history and the remaining policy vector are not held
fixed. H5C replaces that comparison with a **same-quarter controlled
transplant**: three synthetic reference histories are installed at one boundary
(1958Q1, tick 4) and the same one-quarter absolute policy SET is applied to all
arms.

- Base: `config/scenarios/p04_replay.json` (F1/Intermediate-8 synthetic
  structure: 20 regions, 8 commodities, 1,000 households, 100 organizations).
- Typed in-memory copy only: `scenario_id=hist_vnext_h5c_m01_synthetic`,
  `ticks=8`, `seed ∈ {1729, 1730, 1731}`. The modified spec is revalidated with
  `ScenarioSpec.model_validate` and `validate_for_run`.
- 4Q identical warm-up; treatment at tick 4; 4Q post-treatment window.
- 19 policy coordinates are set **absolutely, every quarter, one declaration
  per coordinate per quarter** (152 `InterventionSpec` records per arm). Only
  the declared cut coordinate differs at 1958Q1; it returns to the default at
  1958Q2.
- Levers: `income_cut` (`wage_factor` 1.0→0.9), `welfare_cut`
  (`welfare_provision` 0.5→0.4), `import_cut`
  (`consumer_import_factor` 1.0→0.8). `welfare_cut` is an entitlement cut, not
  a cash transfer.
- Budget-only controls: native memory, 8Q, no transplant; `no_cut` and the same
  `income_cut`.

The carried histories end in 1957Q4 and are formed **only** through the
existing `update_household_expectations` updater on an isolated donor copy:

| history | sequence | final expectation (real consumption) | streak | threshold |
| --- | --- | ---: | ---: | --- |
| `one_jump` | 0.5, 0.5, 0.5, 0.9 | 0.600000 | 1 | no |
| `two_steps` | 0.5, 0.5, 0.7, 0.9 | 0.637500 | 2 | no |
| `four_steps` | 0.6, 0.7, 0.8, 0.9 | 0.704922 | 4 | **yes** |

At ratchet strength 0.0 the `four_steps` expectation is 0.694922; `one_jump`
and `two_steps` are exactly unchanged. This is the reference first stage.

Only three state fields are transplanted:
`household_expectation[:, real_consumption]`,
`household_improvement_streak[:, real_consumption]`, and the full
`household_consumption_reference`. Grievance, compliance, entitlement, cash,
inventory, durables, housing and all political state stay at the matched
warm-up values.

## 2. Counterexamples (recorded before implementation)

`reproduce-final3/counterexamples.json` contains real measurements:

1. **Card mismatch:** the card names 1961Q1 and 1967Q1; the two quarters are
   different years, so a matched pair is impossible.
2. **Empty C0 political tables:** the fresh 116-tick C0 output has
   `political_quarters=0`, `opposition_regions=0`,
   `information_quarters=0` rows. This is a **missing measurement**, not a
   measured zero political response.
3. **Forced-saving-only input:** `forced_saving` is one of five declared
   metrics; it cannot substitute for grievance, consumption, policy or
   expectations.
4. **Welfare is not cash:** two real 1-tick sessions with
   `welfare_provision` 0.5 vs 0.4 keep household cash open/close, organization
   cash and Treasury identical (20,742.46 / 20,742.46; 863,414;
   360,586), while the welfare entitlement component moves 0.5→0.4 and mean
   grievance moves 0.02716→0.02916.
5. **Planning probe construction errors** (recorded from the frozen PLAN, not
   re-run here): a missing `ExternalWorldSlice.origins/evidence_status` and a
   nonexistent `treasury_cash` diagnostic field. These were probe errors, not
   model accounting failures.

## 3. Evidence

### 3.1 Matching

- Every arm completed 4Q warm-up and was measured before and after the
  transplant.
- For each seed, all 26 arms share one pre-transplant
  `MaterialState`/`PoliticalState`/RNG matching digest and one warm-up
  intervention digest. This includes quarter, completed ticks, household and
  organization cash, bank deposits/reserves, Treasury, USD, physical stock,
  capacity, the 19-coordinate policy vector, scenario/parameter/forcing/external
  pack hashes.
- After the transplant the non-memory digest and every explicit key are
  unchanged, and the only changed material fields are the three whitelisted
  memory fields. Native budget-only arms have `pre == post` and
  `transplant = none`.
- Memory evidence is stored per quarter (`memory/pre-transplant-1957Q4.json`,
  `memory/opening-1957Q4.json`, `memory/post-1958Q1..Q4.json`) with household /
  entitlement / channel axes, units, full arrays and per-array SHA-256.
- Cross-check: the state-weighted national grievance equals the table-produced
  `opposition_regions.weighted_grievance` aggregate at every post-treatment
  quarter; the committed policy equals `political_quarters.policy_*`.

### 3.2 First stage and binding

| lever | applied/effective | recovered after one quarter | binding flow |
| --- | --- | --- | --- |
| `income_cut` | yes | yes | `pre_purchase_wages` 102,000 → 91,800 (Δ −10,200) |
| `welfare_cut` | yes | yes | `household_entitlement[:,welfare]` 0.5 → 0.4 |
| `import_cut` | yes | yes | `convertible_imports` moves: consumer_goods −21.27, durable_goods −5.32, food −10.63, energy −53.17; capital_goods/raw_materials +36.74 each (endogenous reallocation) |

No lever was non-binding. Each lever is checked per seed, not only for the last
seed.

### 3.3 Technical gates

Across all 78 arms:

| gate | maximum |
| --- | ---: |
| material abs residual | 1.46e-11 |
| material tolerance ratio | 9.53e-4 |
| finance abs residual | 4.19e-9 |
| finance tolerance ratio | 2.70e-5 |

All ratios are below 1. Table row counts are exactly 8 political quarters,
160 opposition rows, 80 information rows (10 features × 8 ticks), 160 budget
rows and 64 national-account rows per arm. 1958Q1 is present in every arm.

## 4. Results

`R = Y_cut − Y_no_cut` for each history. The main contrast is
`D = R(four_steps) − R(one_jump)`; `N = D(strength 0.1) − D(strength 0.0)`.
Values are per seed; the three seeds are an engineering bank, not a power
calculation.

### 4.1 Income cut (`wage_factor` 0.9)

| seed | D grievance (cumulative) | D spending (cumulative) | N grievance | N spending |
| ---: | ---: | ---: | ---: | ---: |
| 1729 | +4.782e-4 | −16.541 | +1.435e-5 | −2.300 |
| 1730 | +5.488e-4 | −17.994 | +1.317e-5 | −2.247 |
| 1731 | +2.928e-4 | −20.454 | +1.285e-5 | −2.270 |

Carried history changes the response: the long history has higher grievance and
a larger spending fall under the same wage cut. The formation-period threshold
ratchet contributes a small but consistently signed part of that contrast
(`N ≠ 0`). Per-commodity cumulative differences are mixed in sign, so no
aggregate "consumption" total is formed.

### 4.2 Import cut (`consumer_import_factor` 0.8)

| seed | D grievance | D spending | N grievance | N spending |
| ---: | ---: | ---: | ---: | ---: |
| 1729 | +2.899e-6 | −2.3002 | +1.163e-7 | −0.21384 |
| 1730 | +2.980e-6 | −2.3002 | +1.494e-7 | −0.21386 |
| 1731 | +3.018e-6 | −2.3006 | +1.489e-7 | −0.21386 |

Same sign structure and a detectable ablation, at a much smaller magnitude than
the cash lever.

### 4.3 Welfare cut (`welfare_provision` 0.4)

The entitlement cut binds, but the history contrast at the main formation
strength (0.1) is mixed across seeds (D grievance −1.614e-6, +3.03e-7, ~0;
D spending −0.2424, −0.1662, 0.0) and the ablation is numerically zero. Result: **UNIDENTIFIED**, not "no political
cost". The early exposure/voice channel can be structurally non-binding; this
study does not claim protest, alliance or policy-feedback effects.

### 4.4 Budget-only control

The native `no_cut` and `income_cut` arms keep identical opening memory and
differ only through the one-quarter wage SET. They are the negative control for
"a budget change without a carried-reference treatment".

## 5. Verdicts

| dimension | verdict |
| --- | --- |
| Technical | **PASS** — 78/78 arms completed; matching, gates, tables, policy and cross-checks pass |
| Reference first stage | **PASS** — every seed; threshold crossing and ablation exactly as preregistered |
| Cut first stage | **PASS** — applied/effective/binding/recovery for every seed |
| Political measurability | **PASS** — non-empty real political tables including 1958Q1 |
| Structural, income lever | **CONDITIONAL_CARRIED_REFERENCE_EFFECT** |
| Structural, import lever | **CONDITIONAL_CARRIED_REFERENCE_EFFECT** |
| Structural, welfare lever | **UNIDENTIFIED** (binding, mixed/zero history contrast) |
| Historical | **UNIDENTIFIED** — no admitted D14 source identifies expectations, equal cuts and same-period local responses |
| Economic minimum margin | **UNIDENTIFIED** — no p-values or arbitrary percentage thresholds |

## 6. What this does and does not show

- The experiment identifies a **conditional structural effect of a synthetic
  carried reference** under one frozen F1 state. It does not identify a
  naturally reachable macro history, a pure streak-duration curvature, or a
  Hungarian historical magnitude.
- The synthetic experienced-acquisition samples (`reference × e/(1−e)`) are
  inputs to the existing consumption-reference EMA. They were not produced by
  the economic ledger and were not installed into forcing, actor observation or
  any data registry. The donor trace records each sample quarter, input vector,
  units, opening entitlement/expectation/streak and closing memory.
- The consumption reference scale is a declared experimental input; it affects
  welfare via coverage/reference. It is not an observed consumption series.
- `welfare_cut` moves an entitlement component, never a cash transfer.
- Import effects include endogenous reallocation to capital goods/raw
  materials; the household-channel reduction is the first stage.
- No p-value, percentage threshold or seed count is treated as historical
  evidence. The old priors' "identified" status is not restored.

## 7. Files, models and reproduction

New production/test files:

- `studies/HIST_VNEXT/M01/expectations_adapter.py`
- `studies/HIST_VNEXT/M01/runner.py`
- `studies/HIST_VNEXT/M01/spec.json`
- `tests/test_hist_ratchet_matched.py`

No engine/state/storage/policy/CLI/contract file was modified. The only
mechanism is the existing
`src/hsm_lab/engine/household_welfare.py:update_household_expectations`.

Model and effort record:

| role | actual |
| --- | --- |
| Implementer | current project session model `deepseek/deepseek-flash`; per-call token/cost fields NOT_MEASURED |
| Planned reviewer | `minimax-code-cn/MiniMax-M3:high` — HTTP 429 Token Plan cap (request_id `0728d2aea086f40af5bc9a15c1143962`) |
| Fallback reviewer, round 1 | `openai-codex/gpt-6.1-sol:high`, independent session; usage input 783, output 2,136, cache read 78,720, reasoning 516, cost 0.030798 USD, wall 334 s |
| Fallback reviewer, round 2 | same model, independent session; usage input 198, output 1,519, cache read 93,312, reasoning 356, cost 0.024917 USD, wall 258 s |
| Fallback reviewer, round 3 | same model, independent session; usage input 1,105, output 2,311, cache read 88,320, reasoning 970, cost 0.034352 USD, wall 295 s |
| Fallback reviewer, round 4 | same model, independent session; usage input 1,240, output 1,041, cache read 65,408, cost 0.019431 USD, wall 167 s |
| Commit message | current `@commit` selector (session role); generation only, scheduler executes the commit |

The reviewer fallback is an explicit, recorded substitution, not a silent
global-role change. It is not treated as a PASS reason.

Commands (repository root, existing `.venv`, `PYTHONDONTWRITEBYTECODE=1`):

```sh
.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner reproduce --output-dir <out>/reproduce --c0-dir <out>/C0
.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner profile --output-dir <out>/profile
.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner study --output-dir <out>/study
.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir <out>/study
```

Final evidence (excluded from the commit) lives in
`outputs/hist-vnext-h5c-20261022T051501Z/`:
`reproduce-final3/`, `profile-final3/`, `study5/`, `F1-before/`, `C0/`, `C1/`,
`runs/*` (commands, exit codes, wall time, sampled peak RSS), and `tamper*`
negative copies. `study5` is the final matrix; `verify` re-hashed **2,185**
files and recomputed all 78 arms, matching, first stages, D/N statistics and
the verdict. `profile-final3` has 729 verified files.

## 8. Verification log

- Focused H5C tests: 9 passed.
- Directed suite (`test_hist_ratchet_matched`, `test_households`,
  `test_political_run`, `test_hist_tiny_execution`,
  `test_hist_semantic_registry`): 136 passed.
- Full suite: 1,812 passed, 180 warnings, 198.8 s (199.5 s wall), exit 0.
- `ruff check --no-cache src tests studies/HIST_VNEXT/M01`: clean.
- `uv lock --check --offline`: ok.
- `hsm baseline verify --json`: ok, SHA `1f5b233…`.
- Fresh C0/C1 (116 ticks, seed 1729):
  - C0 `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`
  - C1 `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`
  - `verify_run_identity` recomputed scenario/parameter/recipe/lock/input and
    output hashes; manifest ticks = completed ticks = summary = 116.
- Protected SHA unchanged: `BASELINE.md 1f5b233…`, `research_contract.json
  6f54522…`, `uv.lock 9fd79b6…`, `config/p06/cards/M1.json 7a3beaa…`.
- `verify` tamper probes (all rejected):
  - changed seed in `result.json`;
  - changed a recorded table metric (including `contract_gap_truth`);
  - changed `matching.post.explicit.treasury_deposit`;
  - changed a memory array without updating its digest;
  - changed a study-level D statistic with a re-signed manifest;
  - deleted `political_quarters.parquet`;
  - changed only an arm directory name;
  - changed both pre/opening illegal memory columns and re-signed array/result
    hashes (`tamper11`);
  - forged a memory summary and the matching result metric (`tamper12`);
  - forged only a post summary (including weighted compliance) with a re-signed
    memory file, leaving result metrics unchanged (`tamper13`).
  A status-only edit cannot pass because every file hash, arm identity, table
  value, matching digest, memory array, first stage, statistic and verdict is
  recomputed.
- Review round 1 (fallback reviewer) returned **PATCH** with five findings
  (verify coverage, per-seed first stage, axis memory evidence, tamper-test
  directory names, missing deliverables).
- Review round 2 returned **PATCH** with three findings: (a) the transplant
  whitelist was still declared, not recomputed from arrays and not bound to the
  matching field digests; (b) the verdict mixed formation strengths 0.1 and 0.0
  in a seed-keyed dict, so strength 0.0 overwrote the main arm; (c) the numeric
  comparator accepted NaN. Repairs: recompute the actual delta from
  pre/opening arrays with a code-fixed whitelist, bind array digests to
  `matching.pre/post.material`, select strength 0.1 explicitly for the main D
  and keep 0.0 separately, and reject non-finite values. Regenerated profile
  and study evidence; the final independent re-review is recorded in
  `REVIEW.md`.

- Review round 3 returned **PATCH** with two findings: (a) the memory
  `matching_field_sha256` was still payload-declared, not recomputed from the
  actual arrays (both pre/opening illegal columns could be forged together);
  (b) memory summaries were trusted rather than recomputed from the arrays.
  Repairs: `_memory_field_digest` now recomputes the canonical-dtype digest from
  the actual pre/opening arrays and compares it to
  `matching.pre/post.material`; `_recompute_memory_summary` recomputes every
  summary value from the arrays with the verified household weights and the
  saved summary must match. Regressions cover both-array forgery, forged
  summary, NaN, and illegal columns.
- Review round 4 returned **PATCH** with one finding: saved summaries were
  checked for pre/opening but not for the four post-treatment payloads, so a
  forged post summary with a re-signed memory file could pass. Repair: every
  one of the six memory payloads now has its saved summary compared to the
  array-recomputed summary; a summary-only forgery that leaves result metrics
  unchanged is rejected (`tamper13`). Regression added for expectation and
  weighted compliance.


## 9. Independent review

Reviewer verdict and full text are in `REVIEW.md` and
`docs/phases/HIST_VNEXT/H5C/REVIEW.md`. This report does not sign its own
review. Round 1 is preserved verbatim; only the final verdict is a promotion
gate.
