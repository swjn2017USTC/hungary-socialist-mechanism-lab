# P05 — Historical F2 / Calibration / Validation / Performance — Report

Scope: this report records what P05 actually executed and measured. It does not
restate the plan. Every number below is a produced artifact under `outputs/` or
a frozen registry file; nothing is projected.

- Baseline window: **1957Q1–1985Q4** (116 quarterly ticks). Reserved: 1986Q1–1988Q4 (not opened).
- Ontology: `f2_v1` (16 commodities) + `f2_regions_v1` (20 historical node ids).
- Control file: `config/calibration/p05.json` (windows, tolerances, seed banks, ABC budget, gate thresholds, registry references, parameter→target linkage).
- Commit state: working tree only; nothing in P05 is committed yet.

## 1. Gate results (per dimension)

| # | Gate 1 dimension | Verdict | Evidence |
|---|---|---|---|
| A | F2 ontology freeze | **PASS** | `config/ontology/f2_v1.json` (16 commodities, roles/units/stages), `f2_regions_v1.json`; `catalog_id="f2_v1"` bound; `tests/test_historical_p05.py` |
| B | DATA_MANIFEST_v1 freeze | **PASS** | `data/manifests/DATA_MANIFEST_v1.json` — 144 artifacts (`exogenous_forcing 29 / initial_state 63 / latent_parameter 10 / target 42`), `missing_required=0`, `sha256=5d91e014…`; `p05_targets.yml` (28) / `p05_holdout.yml` (14, hash-only) / `p05_exposure.yml` (4) / `p05_parameters.yml` (10); `hsm data freeze-p05` refuses a second freeze (exit 1) |
| B′ | 1957 reconstruction | **PASS (provisional)** | `hsm data reconstruct-p05` → `ok`; 21 population + 21 household + 21 dwelling anchors, **all grade C / `literature_proxy`** (see §3) |
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
artifact so no consumer can mistake it for an A/B observation. 1957 itself must
be a grade-S derivation (1949/1960 comparable re-coded pair plus the official
national 1957-01-01 total of 9,829 thousand).

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

- `pytest -q` → **325 passed**; `ruff check src tests` → clean.
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

## 11. Next steps

1. Acquire the independent observables in §10b, then declare the parameter→target
   linkage (research decision) and run `screen` → `fidelity` → F1/F2 inference.
   Until then `identifiable_set = []`, `linkage = []`, `inference_status = NOT_RUN`.
2. Obtain the A2 historical volumes manually (registration plan, target grades
   and required metadata are recorded in `data/raw/p05_anchor_downloads.json`
   under `a2_ingestion_plan`); register them as grade A/B anchors and 1957 as a
   grade-S derivation, then re-freeze as a new manifest version.
3. Declare `xlrd` (or add a conversion step) before the census tables are parsed
   by the ingestion pipeline.
4. Re-freeze DATA_MANIFEST as a **new version** once Gate 1 is finally passed.
