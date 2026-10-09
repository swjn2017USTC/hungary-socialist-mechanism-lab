# P05 — Historical F2 / Calibration / Validation / Performance — Report

Scope: this report records what P05 actually executed and measured. It does not
restate the plan. Every number below is a produced artifact under `outputs/` or
a frozen registry file; nothing is projected.

- Baseline window: **1957Q1–1985Q4** (116 quarterly ticks). Reserved: 1986Q1–1988Q4 (not opened).
- Ontology: `f2_v1` (16 commodities) + `f2_regions_v1` (20 historical node ids).
- Control file: `config/calibration/p05.json` (windows, tolerances, seed banks, ABC budget, gate thresholds, registry references, parameter→target linkage).
- Commit state: committed on `main` through `feat(p05)`/`fix(material)`/`docs(p05)` commits; the data/F2 freeze artifacts are tracked, the reserved window is untouched.

## 1. Gate results (per dimension)

| # | Gate 1 dimension | Verdict | Evidence |
|---|---|---|---|
| A | F2 ontology freeze | **PASS** | `config/ontology/f2_v1.json` (16 commodities, roles/units/stages), `f2_regions_v1.json`; `catalog_id="f2_v1"` bound; `tests/test_historical_p05.py` |
| B | DATA_MANIFEST_v1 freeze | **PASS** | `data/manifests/DATA_MANIFEST_v2.json` (v1 retained as the immutable first freeze) — 144 artifacts (`exogenous_forcing 29 / initial_state 63 / latent_parameter 10 / target 42`), `missing_required=0`, `sha256=ec531d2f…`, `control_sha256` matches the control file; `p05_targets.yml` (28) / `p05_holdout.yml` (14, hash-only) / `p05_exposure.yml` (4) / `p05_parameters.yml` (10); `hsm data freeze-p05` refuses a second freeze (exit 1) |
| B′ | 1957 reconstruction | **ADMISSION-ONLY (provisional)** | `hsm data reconstruct-p05` → `ok`, `initialization_wired: false`; 21 population + 21 household + 21 dwelling anchors, **all grade C / `literature_proxy`** (see §3). No code path consumes the anchors, so the initial state is still synthetic |
| H′ | **F2 kernel closure audit** | **FAILED** | `hsm calibration audit-closure --scenario historical_f2_replay` → `status collapsed`, `output_liveness = 0.0` at both 116 and 232 diagnostic ticks, while `lambda_common = 1.0` (LP feasible). Probes excluding the obvious causes: H0 trade zeroing, investment hunger, the demand cap (`demand_limited_targets`/`cover`/`floor`), a NaN `cmea_energy_price` in the diagnostic forcing, the H0 household-parameter override, and 116 vs 232 ticks — all still collapse. The F2 *runner* (real parameters) completes 116 ticks, so this is specific to the H0 diagnostic path on the 16-commodity catalog |
| H | F2 performance benchmark | **PASS** | `outputs/p05-f2-benchmark/benchmark.json` — `overall_gate: pass`, workload `f2_historical_material_economy_kernel_storage` |
| — | Gate 1 warmup | **PASS** | `outputs/p05-f2-warmup` — `completed_ticks=16`, `last=1960Q4`, checkpoint `tick-0016`, `rng_draws=125000`, 16 commodities |
| — | run-kind clean cutover | **PASS** | `material_household_simulation` (no legacy alias); CLI summary accepts both real run kinds; end-to-end manifest/summary verified |
| — | RunManifest §195 fields | **PASS** | `ontology_id=f2_v1`, `fidelity=f2` (intermediate8 and the political run → `f1`), `retention`, `target_split_hash=86de1743…`, on both the material and political run paths; adding them left the political replay digest `0f3ac465…` unchanged; `initial_ensemble_hash`/`inference_snapshot_hash` are `null` (no ensemble/inference exists yet — reported, not fabricated) |

## 2. F2 kernel closure repair (Gate 1 §0)

The F2 benchmark initially failed inside the kernel at 1957Q4 on
`expired_services_reconciliation`. The decisive diagnostic decomposed the gate
residual exactly:

```
R_raw  = 0.000000        (cell/commodity conservation is exact)
R_clip = 327.849696      (artefact of clamping per-cell negative expected_close)
duplicate input-cell rows across tier passes = 0   (no NumPy repeated-index risk)
```

Seven defects were fixed in order; each fix exposed the next, deeper one:

1. **Same-quarter service consumption charged the consumer's input cell** while
   the same-quarter output was credited to the producer's output cell → negative
   stock (`g03_electricity_heat`, −17.02). Fixed by netting the pool draw out of
   the production credit.
2. **Continuity omitted `household_edges_out`**: `edge_out_internal` only counts
   internal edges (`dst >= 0`), while household demand targets the boundary sink
   (`dst = -1`). With the term added the un-scaled model equals the engine
   exactly; the compensating regional scaling was removed.
3. **Only one `service` role treated as ephemeral**; F2 has three non-stockable
   commodities (`g03`, `g15`, `g16`). Engine and accounting now share the full
   non-stockable set (intermediate8 stays `[services_transport]` — behaviour
   unchanged).
4. **Retail service cells over-delivered**: mirrored household sales could exceed
   the source cell's stock (per-(region, commodity) aggregate). Capped by the
   cell's stock.
5. **Per-cell pool clearing entries** exposed: `service_pool_draw_at_cell` (S_c)
   and `service_pool_credit_at_cell` (N_c); continuity uses
   `E_c* = E_c + S_c − N_c`.
6. **`production_input_availability_ceiling`** did not count the same-quarter
   pool as an available source; the ceiling now adds `S_c`.
7. **CLI profile-family bug**: `--organizations 400` hard-coded the `p02_*`
   family and silently replaced the F2 scenario's `p05_400` recipe with
   `p02_400`, breaking retail conservation at 1957Q1. The family is now derived
   from the scenario's own recipe prefix.

Result: the F2 kernel runs **116/116 ticks** (`status: completed`), and 232 ticks
is correctly refused by the core-window guard.

## 3. 1957 anchors — provisional, grade C

`hsm data reconstruct-p05` reports `ok` with 63 anchors (21 population, 21
household, 21 dwelling; national + Budapest + 19 megye).

**Honest caveat (recorded in the artifact):** the anchors are KSH
*Népszámlálás 2011* retrospective tables — official values republished on
**2011 boundaries and 2011 definitions**. They are `grade C / literature_proxy`
(fixed-space proxy), **not** 1957 historical-boundary observations. The plan
permits a boundary proxy under stated assumptions; the grade is carried per
artifact so no consumer can mistake it for an A/B observation. 1957 itself must be a
grade-S derivation from an **admitted** artifact pair (the 1949/1960 comparable
re-coded series) constrained by an official national 1957 total. No national
1957 series is registered in the frozen manifest yet, so no such number is
quoted here: the KSH STADAT 22.1.1.2 file that carries it is currently a local
download only (`data/raw/`, excluded from the repository) and must be registered
as an artifact before any 1957 constraint may be used.

Historical original volumes (Hungaricana: 1960 vol. 1, 1949 vol. 5, 1970 vols.
25/26, 1980 vols. 23/24) are the only A/B-grade route and are **not
automatically retrievable** (HTTP 202, empty body — see §7).

## 4. H0 closure certificate (intermediate8, 232 ticks)

`outputs/p05-closure/certificate.json`:

| Metric | Value | Criterion |
|---|---|---|
| `output` periodic residual | 4.63e-7 | ≤ 1e-6 ✓ |
| `cash` periodic residual | 1.87e-7 | ≤ 1e-6 ✓ |
| `stock/output` ratio residual | 0.017105 | ≤ 0.05 ✓ |
| `stock/output` annual drift | **+0.0578 /yr** | disclosed, not claimed stationary |
| `output_liveness` | 0.9875 | ≥ 0.5 ✓ |
| `debt_to_output` | 0.0082 | bounded ✓ |
| `sbc_transfer_ratio` | 0.2313 | ~historical band ✓ |
| `lambda_common` (aggregate LP) | 1.000 | ≥ 0.5 ✓ |
| certificate | `status ok`, `passed true` | — |

**The certificate is conditional on a declared control, not a historical
parameter set.** `_h0_material_parameters` sets: `hunger_base=0`,
`hunger_bailout=0`, `hunger_shortage=0`, `overorder_strength=0`,
`hoarding_quarters=0`, `domestic_credit_rate_annual=0`, `hungary_spread_annual=0`,
`distribution_margins_enabled=True`, `sbc_redistribution=True`,
`m2_neutral_credit=True`, `principal_repayment_fraction=1.0`,
`demand_limited_targets=True`, `demand_cover=1.0`, `demand_floor=1.0`, and all
CMEA/convertible trade demands and convertible reserves set to zero. These values
were chosen to make the structural closure diagnostic pass; they are **not**
fitted to any historical target (no target enters a run), and
`diagnose_kernel_closure` now reports `collapsed` rather than `ok` whenever
liveness < 0.5, so a dead economy can no longer be certified.

C2 is judged on the **stock/output ratio** (P05 §0.7): the stock level drifts
(+5.8 %/yr) while the ratio stays inside the ±5 % same-season band. This is a
declared criterion change, not a stationary-level claim. The raw `stock`
residual is 0.017105 and is reported alongside.

## 5. Gate 2 — identifiability screening and baselines

`hsm calibration screen` (registry-driven, `src/hsm_lab/calibration/screen.py`):

```
status: NO_IDENTIFIABLE_PARAMETERS
admissible targets: 14 (calibration 1960–1969, fully inside the aligned training window)
target window overlap: inside 14 / overlaps 0 / outside 14
status_counts: {fixed: 4, unidentified: 6}
identifiable_set: []      linkage: []      inference_status: NOT_RUN
blocking: 6 parameters are declared UNIDENTIFIED: no declared observable constrains them
blocking: no declared parameter is linked to an admissible target variable
```

The **identification identity** is now declared explicitly in the control file
(`identification`), separate from the run disposition: every parameter keeps a
fixed value at runtime, but only the four `fixed` entries may be described as
structurally determined. The split follows the identifiability audit:

- `fixed` (4): the three P02 material priors (CMEA contract base price, CMEA
  uncertainty multiplier, pre-1960 oil warm-up) and the P04 broker block — an
  engineering assembly rule, determined by design and historical price/contract
  evidence, never by macro fitting.
- `UNIDENTIFIED` (6): the P04 behavioural blocks (coalition, culture,
  external_recipe, information, observation, opposition). Each prior file
  declares `calibration_status=not_calibrated`, and no declared observable
  constrains them; they stay prior-constrained and **must not** be reported as
  estimated. Two could be re-labelled `fixed` only on code evidence that their
  fields are pure structural rules (external_recipe) or deterministic
  measurement mappings (observation) — not on their names.
- The audit also records the identification risk that the 1968 New Economic
  Mechanism changes plan directives, enterprise autonomy, prices and investment
  decisions inside the training window, so pre/post-1968 movements cannot be
  attributed to a single political parameter without structural decomposition.

The training window was aligned to **1960Q1–1969Q4** (option 1) so the declared
calibration artifacts are admissible. The remaining blocker is a *declaration*:
no parameter currently declares an informing target, so no candidate set exists
and **no ABC/F1–F2 inference was run**. The plan requires exactly this honest
outcome from the real registry path.

`hsm calibration fidelity --stage prior` (`src/hsm_lab/calibration/fidelity.py`):

```
status: NO_IDENTIFIABLE_PARAMETERS   stage: prior   paired_study: null
blocking: no declared parameter is linked to an admissible target variable
```

No paired F1 study was run and **no ABC inference was performed**; the stage
refuses to substitute a hold-out-trained F1→F2 compensation model. When a
candidate set does exist the stage returns `PAIRED_STUDY_NOT_IMPLEMENTED` with
the declared tolerances/seed banks as `required_inputs` — the algorithm is a
declared, not silently faked, work item.

### ABC API smoke (plan §271)

`hsm calibration abc-smoke` (also callable as `abc_synthetic_recovery` /
`abc_registry_path`), executed with the declared 16-particle / 2-population
budget against a **throwaway synthetic target produced by the same kernel** at
`utilization = 0.9` over the F2 catalog:

```
status ok   parameter utilization   prior [0.5, 1.0]   truth 0.9
particles 16   populations completed 2   checkpoint_used False
posterior mean 0.8797   observed summary 1 261 764.5
real registry path: NO_IDENTIFIABLE_PARAMETERS   inference_status NOT_RUN   candidates 0
```

The posterior moves from the prior mean (0.75) toward the truth and the run
stops on its budget; this proves the inference API, budget stop and
checkpoint-free execution work, and that the real registry path yields no
candidate set. It is **not** historical-calibration evidence and its target never
enters DATA_MANIFEST.

**Annual aggregation:** `compare_annual` (`data/material.py`) aggregates a
quarterly simulated series with `quarterly_to_annual` under the target's declared
`sum`/`mean`/`end_of_period` rule, validates units and year/key alignment, and
raises when a target year has no simulated annual value; `data/frequency.py`
deliberately exposes **no** annual→quarterly interpolation API. The rule is
therefore implemented in code, but no calibration run has exercised it yet
(there is no admissible candidate set).

**Gate 2 closure:** recorded as `NO_IDENTIFIABLE_PARAMETERS` (declared and
accepted by the study owner). No calibration, no posterior, no F1→F2
convergence claim, and the hold-out was never read.

Baselines executed (compact output):

| Baseline | Scenario | run_kind | Ticks | Digest |
|---|---|---|---|---|
| historical replay | `historical_f2_replay` (25 000 households, 400 orgs) | `material_household_simulation` | 116 (1957Q1–1985Q4) | `86f44f6f…` |
| endogenous politics | `p04_endogenous` | `p04_political_simulation` | 116 (1957Q1–1985Q4) | `0f3ac465…` |

Neither baseline is a historical fit: the replay runs with **partial instrument
coverage** (policy strengths are carried-forward/literature proxies) and the
political run is a prior-constrained mechanism baseline, not an autonomous
explanation of historical policy.

## 6. Parameter classification

| Class | Count | Parameters |
|---|---|---|
| calibrated | **0** | — (no admissible linkage ⇒ nothing estimated; `inference_status = NOT_RUN`) |
| fixed (structurally determined) | 4 | `p02_material_cmea_contract_prior`, `p02_material_cmea_uncertainty_prior`, `p02_material_oil_warmup_prior`, `p04_broker_prior` |
| weakly identified | **0** | — |
| unidentified (prior-constrained) | 6 | `p04_coalition_prior`, `p04_culture_prior`, `p04_external_recipe_prior`, `p04_information_prior`, `p04_observation_prior`, `p04_opposition_prior` |

Identity and disposition are recorded separately: all ten parameters run at a
fixed value, but an `UNIDENTIFIED` label means "prior-constrained", not
"historically determined".

No hidden scalar was introduced; every declared latent parameter is accounted
for in exactly one class.

## 7. Data acquisition, rights, coverage, exposure

**Obtained (registered in DATA_MANIFEST_v1):**

- `ksh_census_2011_retrospective` — 63 XLS (21 units × tables 1.1.1.1 / 1.2.1.1 / 1.3.1.1), KSH, downloaded 2026-10-09, SHA-256 per file, `grade C`. Rights: **restricted** — public reading/citation, `redistribution_allowed=false`.
- `data/raw/ksh_stadat/nep0002.{csv,xlsx}` — KSH STADAT 22.1.1.2 national annual population (January-1 series, includes 1956/1957/1958). Downloaded and hashed; **not yet registered** as an artifact (the variable `population_anchor` is restricted to true census dates).
- `data/raw/p05_anchor_downloads.json` — full download/attempt record (65 A1 entries + 6 A2 attempts + tooling/parse verification).

**Blocked:** all six A2 probes (Hungaricana 1960/1, 1949/5, 1970/25, 1980/24,
search, API root) returned HTTP 202 with an empty body (JS/bot challenge). No
direct file endpoint is reachable from this environment; manual browser export
or a KSH library request is required. The historical-boundary A/B anchors
therefore remain **unobtained**.

**Exposure (`p05_exposure.yml`, 4 entries):** wage/active-population reader
exposure; the registry-note disclosure of terminal 1985 industrial values;
P00–P04 report spot checks; and unrecorded historical exposure. The wage series
is therefore a **non-blind** frozen-parameter hold-out, not a blind one; this
cannot be undone by deleting or renaming data.

**Rights discipline:** `access_rights` and `redistribution_rights` are recorded
separately; no source is written as CC0/unconditionally redistributable.

## 8. Mac measured profile (§G)

Measured on this machine (arm64, Python 3.12, thread-pinned to 1,
`outputs/p05-f2-benchmark/`), 116 ticks per case:

| Case | N households | O orgs | median wall | peak RSS | gate |
|---|---|---|---|---|---|
| `f2_n5000_o400_t116_statistics` | 5 000 | 400 | **9.69 s** | 0.574 GiB | pass |
| `f2_n25000_o400_t116_trajectory` | 25 000 | 400 | **24.46 s** | 1.263 GiB | pass |
| `f2_n25000_o400_t116_trajectory_ckpt44` | 25 000 | 400 | **27.73 s** | 1.142 GiB | pass |

All wall/RSS gates (600 s / 900 s; 16 / 22 GB), `all_repeats_ok`,
`digest_stable` and `measurement_too_short=false` pass. No Windows migration was
needed; no optimization was required.

## 9. Verification and regression

- `pytest -q` → **341 passed**; `ruff check src tests` → clean.
- intermediate8 H0 certificate is **bit-identical** to its pre-repair values,
  confirming the F2 repairs did not change the legacy catalogue path.
- F2 kernel: 116 ticks completed; small-run harness smoke passes.

## 10. Limitations (explicit)

1. **Anchors are grade C fixed-space proxies** (2011 boundaries/definitions); the
   1957 historical county boundary is not observed. Gate 1 B′ is therefore
   *provisional*.
2. **No parameter→target linkage is declared**, so no parameter is identifiable
   and no calibration/inference was performed. Consequently there is no F1→F2
   statistic convergence evidence and no posterior re-verification.
3. **Hold-out untouched**: the 14 hold-out/reserved targets were never read
   numerically; no calibration used them.
4. **C2 is a ratio criterion**: policy strengths, distances and boundary
   conversions remain proxies where noted in the plan.
5. Legacy `.xls` parsing requires a reader (`xlrd`); it was installed ad hoc for
   verification and is **not** declared in `pyproject.toml` yet.

### 10b. Independent observables required by the six UNIDENTIFIED blocks

Training window only (1960–1969); real dates for events, annual frequency for
annual statistics. These are acquisition candidates, not verified series:

| parameter | required observables | why the 14 targets are insufficient |
|---|---|---|
| `p04_external_recipe_prior` | physical input–output tables, fuel/steel/electricity input flows, imports by product and partner, contract quotas | total trade, steel and electricity output are not an input-flow matrix |
| `p04_information_prior` | central plan targets vs reported vs finally verified output, revision dates, report delays | only outcomes are observed; distortions cannot be separated |
| `p04_observation_prior` | independent measurements/revisions of the same indicator (first vs final reports, census reconciliation) | without repeated measurement, observation bias cannot be separated from real change |
| `p04_coalition_prior` | MSZMP central committee/politburo composition, key resolutions, cadre appointments, branch investment decisions | macro investment shows outcomes, not internal power or bargaining |
| `p04_culture_prior` | cultural facility use, press circulation, broadcast reception, participation rates; attitude surveys if any | television *production* is not ownership, exposure or identity |
| `p04_opposition_prior` | strikes, petitions, protests, sanctions and policy responses (event dated) | GDP/consumption/output contain no independent opposition signal |

Acquisition priority from the audit: `p04_external_recipe_prior` first (physical
input–output and energy import flows are the most likely independent constraint),
then `p04_information_prior` (plan versus reported versus verified values).

## 10c. F2 root-cause diagnosis (Step 1, read-only tracing)

The F2 catalogue's economy **contracts under every path** — there is no liveness
gate in the runner, so `status: completed` was never evidence of a live economy:

| run | first-10 mean | last-10 mean | ratio (window) | endpoint ratio |
|---|---|---|---|---|
| F2 `historical_f2_replay` (116 ticks) | 249,569 | 26,620 | 0.107 | 0.078 |
| intermediate8 (116 ticks) | 224,268 | 187,867 | 0.666 | 0.838 |

(ratios are last-10-mean / first-10-mean unless marked "endpoint"; the endpoint
figure is last value / first value.)

Per-commodity first-failure order (first tick below 10 % of its initial value):
`g15_market_services` t=41, `g10` t=74, `g09` t=75, industrials t=91–93, `g03`
t=99, `g07` t=100, `g08`/`g01`/`g16` t=107–114, `g02` never.

**Primary cause — initial scale/product-mix mismatch.** Capacity-weighted
potential output versus declared household demand at t0: `g15` 28×, `g16` 15×,
`g13` 82×, `g14` 165×, `g09` 1.9×, `g10` 1.5× (intermediate demand is additional
and not included here). Because the surplus commodities are non-stockable
services, the excess expires: `expired_services` is 226,230 at t0 ≈ **70 % of
gross output** (324,167). `treasury_cash` then drains linearly from 83,100 to
**zero at tick 17** and stays there; delivery is not financially blocked
(`financial_blocked_total ≈ 0`).

**Two structural defects were found and fixed** (both real, both verified, and
both secondary to the scale mismatch):

1. **Hubless goods had no retail replenishment route** (`9d474c1`). `g03` and
   `g16` declare retail stages but no hub stage, and the compiler only routed the
   first service role (`g15`) to producers, so those retail cells could never be
   stocked. The fallback to producers is now declared and gated
   (`MaterialParameters.retail_replenishment_fallback`, off by default, enabled
   in the F2 scenario). Effect: `g03` household consumption goes 0 → 1,569 at
   t0; the nine hub-based commodities and `intermediate8` are unchanged.
2. **The public-services channel carried no demand** (`6122793`).
   `form_household_demand` filled every channel except `public`, so `g16` demand
   was zero for every household and every quarter while producers kept producing
   against capacity. Effect: `g16` desired/allocated/delivered/used are 1,572.5 at
   t0 instead of zero across the whole run.

### E4-min activity-level alignment (declared diagnostic, v1)

`src/hsm_lab/calibration/alignment.py` compiles the declared household demand
onto the commodity axis and solves a four-quarter activity-level feasibility LP
(national balances with inventory for stockable commodities and an explicit
expiry term for non-stockable ones; capacity, labour and origin-capacity bounds;
objective = minimal relative capacity realignment). Result on F2:

```
status LP_FEASIBLE   matrix 2830 vars / 13207 nnz   max balance residual 1.7e-11
capacity_deviation 0.0   activities at their original ceiling 386 / 386
declared household demand: g09 8500, g10 6800, g15 2550, g16 1700, g03 1700, ...
```

Before this result the LP had two defects of its own, both fixed: the inventory
term carried the wrong sign (stock could be conjured from nothing, which made the
plan look feasible at 24 004 units of gross output) and the quarter-0 balance
ignored the opening stock. With the sign corrected and the physical opening stock
seeded the problem is feasible exactly as reported below.

**The existing profile's capacity is sufficient for the declared household
demand**: the minimal-realignment objective is zero, so E4 finds no capacity
shortage to fix. The contraction is therefore not a capacity-deficit problem; it
is consistent with the production-target rule (`target = min(u·C·season, labor)`,
which has no demand-following term) driving persistent over-production of
non-stockable goods, expiry and the treasury drain documented above. The
certificate is explicitly `scope="national_v1"`: inter-regional routing,
same-quarter service tiers and the finance pre-audit are not modelled, so it
proves static national feasibility only, never execution feasibility.

Neither fix removes the contraction: the 116-tick ratio moves 0.1067 → 0.1160
(replenishment) → 0.1116 (both). A directed probe of the replenishment defect in
isolation had already shown the same marginal effect. The scale mismatch is
therefore the primary object for the E4 activity-level alignment.

### E4-min step 4 — execution-target compatibility

The kernel does not optimise: it produces `min(u·C·season, labor_cap)` every
quarter, with no demand-following term. Comparing that target rule with the
*lean* plan (minimum gross output that still meets the declared demand and the
technology), over four quarters:

```
status TARGET_RULE_MISMATCH
engine output 1 124 272   lean plan 69 496   excess 1 054 776  (~15x the lean plan)
expiring surplus per quarter: g15 62 790 | g03 24 781 | g16 21 160
```

The surplus concentrates in exactly the three non-stockable commodities, where it
cannot be carried and must expire — the mechanism behind the observed
`expired_services` and the treasury drain.

### E4-min step 5 — frozen acceptance gates (116 synthetic ticks)

| gate | measured | threshold | verdict |
|---|---|---|---|
| liveness (last-10 / first-10 output) | 0.1116 | ≥ 0.8 | **FAIL** |
| household delivered / funded, g15 | 0.120 | ≥ 0.9 | **FAIL** |
| household delivered / funded, g16 | 0.199 | ≥ 0.9 | **FAIL** |
| household delivered / funded, g03 | 0.489 | ≥ 0.9 | **FAIL** |
| treasury cash | zero from tick 18 onward | must stay self-financing | **FAIL** |
| accounting invariants | all enforced gates pass | unchanged tolerance | PASS |

(The expiry gate is not reported per commodity here: the run exposes a single
aggregate `expired_services` series, so a per-commodity expiry ledger is still
required to apply the `expired/total ≤ 0.20` rule honestly.)

### E4-min step 6 — control-fix experiments (both negative)

Two demand-following target rules were implemented behind the declared
`production_target_rule` flag and measured over 116 ticks:

| rule | 116-tick ratio | expired tail | treasury zero |
|---|---|---|---|
| `legacy` (produce to capacity) | 0.1067 | 10 193 | tick 17 |
| `lean_plan`, all activities capped | **0.0000** | 8 | tick 14 |
| `lean_plan`, only non-stockable capped | **0.0008** | 96 | tick 14 |

Capping production to the national lean plan removes the expiry almost entirely
(tail 10 193 -> 96) and still kills the economy: the plan is a *national static*
feasibility solution with no routing, timing or finance information, so the kernel
cannot realise it and the delivery chain starves. This is the same "LP feasible,
kernel dies" gap that the routing and demand fixes exposed earlier, now measured
for the control rule itself.

### E4-min step 3 — time-expanded (regional) feasibility

The national lean plan is not executable (step 6). The next question is whether
*any* plan is: `calibration/time_expanded.py` adds regional balances (every
activity keeps its region, each region covers its own consumption) and the
same-quarter service rule (a non-stockable commodity must be produced in the
quarter it is consumed). Two modes are solved, 20 regions x 4 quarters:

| mode | status | detail |
|---|---|---|
| strict autarky (no transfers) | **INFEASIBLE** | deficits concentrated in g10 animal food (Csongrad 31, Bekes 24, Bacs-Kiskun 17) and g07 construction (Bekes/Csongrad/Vas ~20 each) |
| free inter-regional transfers, minimised | **LP_FEASIBLE** | routing requirement **841.6 units** over four quarters: g07 772.0, g10 69.6 |

So the plan **is** executable: it needs ~842 units of inter-regional exchange,
under 1% of the 117 504 units of four-quarter household demand, and the regions
that are short (Csongrad, Bekes, Bacs-Kiskun, Vas) are exactly the structural
grain and construction gaps. The lean regional plan with routing produces
**69 869** units of gross output over four quarters, against the ~1 124 272 the
kernel produces — a factor of ~16.

This is the decisive diagnostic: F2's failure is neither capacity, nor
technology, nor aggregate demand, but **routing (the kernel does not move those
$\sim$842 units) combined with a target rule that ignores demand**. The scope
statement is inside every certificate: v1 carries no explicit edge flows, no
transport/handling capacity and no finance pre-audit, so it can prove a plan is
*not* executable but never that one is.

Conclusion: F2 fails every economic acceptance gate while its accounting is
clean, and the LP shows the failure is neither a capacity deficit nor a routing
gap but the **production-target rule** — it produces to capacity, not to demand,
so non-stockable surpluses expire and the payment chain drains. F2 remains
`validation_status = not_validated`.

### E5 — where the delivery fails (measured on the 116-tick F2 run)

The regional certificate said only ~842 units need to move between regions, so the
next question was whether the kernel moves them. It does, but far too little, and
the loss is systemic rather than regional:

| all commodities | ticks 2-11 | whole run (0-115) |
|---|---:|---:|
| ordered (retail/admin orders) | 1 217 109 | 12 954 527 |
| allocated | 1 036 316 | 9 441 356 |
| delivered | 665 743 | 2 792 558 |
| **physical_delivery_blocked** | **370 336** (36% of allocated) | **6 648 452** (70%) |
| financial_delivery_blocked | 236 | 346 |

An earlier version of this table labelled the whole-run totals "ticks 2-11" and
read `allocated > ordered` as a runtime over-allocation; in the correct window
allocation is below orders, so that was a window-labelling error, not a leak.

Ordering is not the problem (`desired ~ ordered`, `financial_delivery_blocked`
is negligible). The kernel already moves goods across regions (g10 `ready`-stage
receipts of 400-800 per four ticks in deficit and surplus counties alike), but
delivery is capped by the **logistics pool**: `material.py` scales every edge by
`_group_factor(transport_need, logistics_pool)` where

```
logistics_pool[org] = transport_realized[transport activities of org]
                      * service_split[0]        (0.7)
```

and the transport activities are the early-service tier, whose realized output is
`produce_leontief(opening stock of their inputs, ...)`.

Instrumenting `_group_factor` by call site over a full run ranks the binding
constraints directly:

| site | meaning | mean factor | zero-capacity groups | need |
|---|---|---|---|---|
| `material.py:1103` | **input funding** (producer cash for inputs) | **0.606** | 14 851 | **20.8 M** |
| `material.py:1307` / `1314` | source availability, tier allocation rounds | 0.799 / **0.209** | 5 814 / 14 618 | 13.0 M / 4.2 M |
| `material.py:1328` | fallback sourcing round | 0.567 | 3 899 | 0.42 M |
| `material.py:1351` | **transport logistics pool** | **0.056** | 874 | 0.35 M |
| `material.py:1373` / `1391` / `1410` | wholesale/retail handling, bank reserves | ~1.000 | 0 | - |

So the largest loss by volume is **input funding**: organisations can fund only
~61% of the inputs they order (20.8 M of need, 14 851 groups funded at zero), which
starves production; the transport pool then caps what remains at ~6% of freight
demand, and the source cells themselves hold only ~21% of what is claimed. This is
a coupled financial-physical contraction, not a single bad parameter.

Instrumenting `_group_factor` over a full run (1 739 calls) shows most groups at
their capacity (mean factor 0.87-1.00) but a subset with **zero** capacity while
still carrying need (e.g. a group with need 30 233 against capacity 304 013
receiving factor 0.0) — those zero-pool groups supply the edges that lose 70% of
their allocation. The transport sector itself is not idle (its realized output is
~88% of target over the first ticks, 159 849 of 164 423), so the pool is simply
too small for the freight the economy's flows demand.

Measurements that pin this down:

* scaling `WHOLESALE_HANDLING_TOTAL`/`RETAIL_HANDLING_TOTAL` by x2, x4 and x8
  changes nothing (physical blocked stays 6.65 M, ratio 0.1116) — handling is not
  the ceiling;
* the ceiling is the transport logistics pool — `_group_factor(transport_need,
  logistics_pool)` at `material.py:1351`;
* **correction (this section's own earlier hypothesis was wrong).** An interim
  reading blamed the carriers' opening input cover, quoting "capacity 128 000 but
  only ~730 units realised". That number came from summing the early-service input
  cells of *every* early-service activity — which mixes the 8 transport
  organisations with 50 industrial-SOE and 20 bank activities. Measured directly on
  the 8 transport organisations: capacity 60 000, target 54 000, **realised
  54 000** at tick 0, with several quarters of inputs seeded (their input
  requirement is 0.052 per unit of output). Transport is not input-starved. What
  binds is the ratio of the pool to the freight the goods flows demand
  (pool/need ~0.54 at the declared capacity, §E6).

This also closes a diagnostic hole: before this change nothing in the ledger
recorded `allocated -> candidate` at all, so `financial_delivery_blocked = 0` was
being read as "delivery is fine" while 70% of the plan never moved. The engine now
records `physical_delivery_blocked` and enforces the identity

```
delivered + physical_delivery_blocked + financial_delivery_blocked == allocated
```

for every demand cell, which is why that table can be read directly.

### E6 — the two candidate levers, measured (steps 1-2-3)

The E5 ranking named input funding first and transport cover second, so both were
swept with the new, re-runnable tool (`hsm calibration axis-sweep`, which runs the
historical replay baseline once per declared value and reports the frozen gate
metrics; outputs stay under the git-ignored `outputs/`).

```
hsm calibration axis-sweep --axis credit_envelope_fraction --points 0.5,0.75,1.0
hsm calibration axis-sweep --axis transport_capacity_scale --points 1,4,16
```

| `credit_envelope_fraction` | liveness | expired tail | treasury zero |
|---|---|---|---|
| 0.5 (as declared) | 0.1116 | 11 273 | tick 18 |
| 0.75 | 0.1160 | 9 290 | tick 31 |
| 1.0 | **0.0396** | **5 160** | **tick 48** |

| `transport_capacity_scale` | liveness | expired tail | treasury zero |
|---|---|---|---|
| 1 (as declared) | 0.1116 | 11 273 | tick 18 |
| 4 | 0.2612 | 18 571 | tick 6 |
| 16 | 0.3190 | 32 448 | tick 4 |

Readings:

* **Raising the credit envelope does not restore liveness** and at 1.0 it makes the
  ratio worse (0.0396) while it *does* prolong the payment chain (treasury zero
  moves 18 → 48) and nearly eliminates expiry (11 273 → 5 160). It funds a longer
  run of a still-contracting economy.
* **Raising transport capacity helps but saturates**: 0.11 → 0.26 → 0.32 at x4/x16,
  with fresh expiry and an earlier treasury break because more goods now move
  through a chain the payment system cannot settle. Far from the 0.8 gate, and x32
  is refused by the Treasury working-capital gate at initialisation.
* The transport sector was never starved of *input cover* (its declared capacity is
  60 000, its target 54 000 and its realised output 54 000 at tick 0 with several
  quarters of inputs seeded); what binds is the ratio of transport *capacity* to
  the freight the goods flows demand (pool/need ~0.54 at the declared capacity).
* Handling capacity, ordering and funding are all excluded by measurement (§E5).

**Verdict: neither lever is the collapse driver, so neither is adopted.** Changing
`credit_envelope_fraction` or the transport capacity constant would move every
baseline without fixing the failure, which the project's own rules forbid. The
remaining explanation is a per-tick **value/money leak** that no single parameter
axis exposes: production, delivered goods and the payment chain all contract
together from the first quarters, and both sweeps only change *how fast* the same
contraction is reached. The next work is a stock-flow / money-flow audit of one
tick (where each unit of money and each unit of produced value goes), not another
parameter search.

## 11. Status summary — Gate 1 / Gate 2 (2026-10-09)

This is the one-page state of P05 as it actually stands after the E4/E5 work.

### Gate 1 — DATA / F2 FREEZE: **NOT PASSED** (one dimension FAILED)

| dimension | verdict |
|---|---|
| A F2 ontology freeze | PASS |
| B DATA_MANIFEST_v1 freeze | PASS |
| B' 1957 reconstruction | ADMISSION-ONLY (all anchors grade C, no code path consumes them) |
| H' **F2 kernel closure audit** | **FAILED** — `status collapsed`, `output_liveness = 0.0` at 116 and 232 diagnostic ticks |
| H F2 performance benchmark | PASS |
| warmup / run-kind cutover / RunManifest fields | PASS |

Gate 1 is a single AND: the closure audit H' fails, so Gate 1 is **not** passed and
Gate 2 was entered on the runner path only (as the plan's dependency rule requires).

### Gate 2 — CALIBRATION / VALIDATION: **NOT ACHIEVED**

| requirement | status |
|---|---|
| material → enterprise → household → social order | satisfied structurally (P02 → P04 layers), but the material layer does not close |
| F1 large-scale calibration | **not run** — `no declared parameter is linked to an admissible target variable`; `identifiable_set = []` |
| F1/F2 statistic convergence | **not measurable** — no inference was run |
| key posteriors re-verified on F2 | **none** — there are no posteriors |
| hold-out excluded from calibration | satisfied trivially (hold-out only hashed, 14 entries, no calibration ran) |
| compact outputs for every run | satisfied (`national_accounts`/`aggregates`/`tick_diagnostics`/checkpoints) |
| historical replay baseline | **completed** (`outputs/p05-historical-replay`, 116 ticks) and fails every economic acceptance gate |
| endogenous politics baseline | **completed** (`outputs/p05-endogenous-politics`, political run kind, fidelity f1 / intermediate8_v1) |
| P05_REPORT classification | done (§6) |

Frozen acceptance gates on the historical replay baseline (116 ticks):

| gate | measured | threshold | verdict |
|---|---|---|---|
| liveness (last-10 / first-10) | 0.1116 | >= 0.8 | FAIL |
| household delivered / funded (g15 / g16 / g03) | 0.120 / 0.199 / 0.489 | >= 0.9 | FAIL |
| treasury cash | zero from tick 17-18 | self-financing | FAIL |
| accounting invariants | all enforced gates pass | unchanged | PASS |

Parameter classification (unchanged, §6): **calibrated 0 / fixed 4 / weakly
identified 0 / unidentified 6**. Nothing is labelled estimated.

### Steps 1-2 of §12's list (the two candidate levers) are measured and negative

`credit_envelope_fraction` and transport capacity were swept on the replay baseline
(§E6): neither restores liveness, so neither is adopted and F2 remains
`not_validated`. The blocking work is now the stock-flow / money-flow audit.

### Can P06 start? **No.**

Three independent reasons, each from this report's own measurements:

1. **The plan's own dependency.** OMP_PLAN §9 makes Gate 1 (which includes the
   closure audit) a precondition for Gate 2, and P06 assumes a frozen engine that
   is "原则上不再大改" (§10.1). Gate 1 has a FAILED dimension and the engine is not
   frozen.
2. **P06's outputs would not be interpretable.** Its deliverables are M1-M11
   mechanism verdicts, the H0-H4 forcing ladder, the 1968/1973/political
   counterfactual arms and the final release. On the measured F2 baseline the
   economy collapses (production ratio 0.11, treasury zero at tick 17, 70% of the
   allocated plan never delivered, producers funding only 61% of ordered inputs),
   so every counterfactual difference would be read off a collapse trajectory
   instead of off the mechanisms.
3. **The classification is empty.** `calibrated = 0` and `weakly identified = 0`,
   with six priors declared UNIDENTIFIED. P06's sensitivity funnel
   (OAT → Morris → 6-10 key parameters → Sobol) needs a model whose parameters are
   at least identified; running it now would produce Sobol indices for parameters
   that no observable constrains.

What is safe to begin **before** P06, and is genuinely P06-precursor work: the
sensitivity **infrastructure** (Morris/Sobol harness on a working toy catalog) and
the mechanism-card **schema**, both of which need no validated engine. The
verdicts themselves must wait.

## 12. Next steps

Ordered by the evidence, not by the plan's original sequence:

1. **Audit one tick's stock-flow and money-flow** (§E6): the credit and transport
   axes are measured and neither is the driver, so find where the value and the
   money leave the circuit each quarter before spending another parameter. This is
   the only step that can unblock Gate 1's failed closure audit.
2. Re-run the frozen acceptance gates on 116/232 ticks after that audit, and only
   then re-test a demand-following target rule (step 6 showed that capping output
   before the circuit closes starves the delivery chain). F2 stays
   `validation_status = not_validated` until those gates pass.
4. **Declare the parameter→target linkage** (research decision), then run
   `screen` → `fidelity` → F1/F2 inference. Until then `identifiable_set = []`,
   `linkage = []`, `inference_status = NOT_RUN`, and P06 must not consume any
   "calibrated" label.
5. Acquire the independent observables in §10b to move the six UNIDENTIFIED
   priors; obtain the A2 historical volumes manually (plan recorded in
   `data/raw/p05_anchor_downloads.json` → `a2_ingestion_plan`) and register 1957
   as a grade-S derivation.
6. Declare `xlrd` (or add a conversion step) before the census tables are parsed,
   and re-freeze DATA_MANIFEST as a **new version** once Gate 1 finally passes.
