# P06 final reproduction-scope report

## Scope and evidence boundary

This is a deterministic historical-reproduction study under declared behavioural assumptions. `calibrated = 0`; no parameter block is identified. The reserved 1986Q1–1988Q4 window remains closed, and hold-out values were not used for selection. No ABC/pyABC, posterior, calibration, causal identification, or validation claim is made. Results below are model outputs and replication spread across the three declared model seeds (1729, 1730, 1731), not posterior uncertainty. Seeds 1730 and 1731 follow the recorded rule “the next two integer seeds after the existing seed 1729”; this is not a posterior or seed-bank inference. Every executed run stopped at or before 1985Q4.

P05 has 14 admitted variable IDs across calibration (1960–69) and internal validation (1970–78), 28 artifacts. The crosswalk and numeric comparison follow below.


## First result: consumption fails in every informative year

The admitted household-consumption index is the first and only numeric target comparison. The model series is normalized to its own 1960 value; 1960 is exact by construction and is marked `informative: false`. In the 18 informative years, the model falls while the KSH target rises. The mean absolute residual is 91.7414 index points and the maximum is 173.6360. This is an outside-tolerance reproduction result, not a calibration or general validation claim. The tolerance remains the predeclared 0.5 index points.

| Window | Year | Target index | Model index | Residual (model − target) | Tolerance | Row verdict |
|---|---:|---:|---:|---:|---:|---|
| calibration | 1960 | 100.00 | 100.00 | +0.00 | 0.50 | within_tolerance |
| calibration | 1961 | 101.00 | 99.26 | -1.74 | 0.50 | outside_tolerance |
| calibration | 1962 | 105.00 | 69.85 | -35.15 | 0.50 | outside_tolerance |
| calibration | 1963 | 110.00 | 69.20 | -40.80 | 0.50 | outside_tolerance |
| calibration | 1964 | 116.00 | 67.62 | -48.38 | 0.50 | outside_tolerance |
| calibration | 1965 | 118.00 | 65.27 | -52.73 | 0.50 | outside_tolerance |
| calibration | 1966 | 123.00 | 62.79 | -60.21 | 0.50 | outside_tolerance |
| calibration | 1967 | 131.00 | 60.18 | -70.82 | 0.50 | outside_tolerance |
| calibration | 1968 | 137.00 | 56.55 | -80.45 | 0.50 | outside_tolerance |
| calibration | 1969 | 145.00 | 53.49 | -91.51 | 0.50 | outside_tolerance |
| internal_validation | 1970 | 155.00 | 50.60 | -104.40 | 0.50 | outside_tolerance |
| internal_validation | 1971 | 163.00 | 47.77 | -115.23 | 0.50 | outside_tolerance |
| internal_validation | 1972 | 169.00 | 45.68 | -123.32 | 0.50 | outside_tolerance |
| internal_validation | 1973 | 176.00 | 45.08 | -130.92 | 0.50 | outside_tolerance |
| internal_validation | 1974 | 187.00 | 44.71 | -142.29 | 0.50 | outside_tolerance |
| internal_validation | 1975 | 196.00 | 44.32 | -151.68 | 0.50 | outside_tolerance |
| internal_validation | 1976 | 199.00 | 43.88 | -155.12 | 0.50 | outside_tolerance |
| internal_validation | 1977 | 208.00 | 43.30 | -164.70 | 0.50 | outside_tolerance |
| internal_validation | 1978 | 216.00 | 42.36 | -173.64 | 0.50 | outside_tolerance |

Consumption summary: 19 annual rows; **18 of 18 informative years outside tolerance**; 1 uninformative normalization row; mean absolute residual 91.7414, maximum 173.6360 index points; descriptive verdict **outside_tolerance**. The model index falls 100 → 99.3 (1961) → 42.4 (1978), while the target rises 100 → 101 → 216. Replay digest: `f75ba7767eaf5987eb876413f973e07f13ece4e11906cdd14cbd3b08fbf8ba79`. Evidence: `outputs/p06-reproduction-table-widened-final2/reproduction_table.json` and `.csv`.

## Graded crosswalk and dispositions

The crosswalk still covers all 14 admitted variables exactly once. Counts are **1 mapped / 13 no_counterpart / 0 blocked**. By comparison grade: `mapped_like_for_like` 0; `normalized_index` 1; `allocation_assumed` 0; `no_counterpart` 13; `blocked` 0. Widening adds explicit dispositions but no additional numeric target fit, and it does not improve the consumption result.

| Grade | Count | Numeric verdict |
|---|---:|---|
| `mapped_like_for_like` | 0 | none |
| `normalized_index` | 1 | `consumption`: outside tolerance, 18/18 informative years |
| `allocation_assumed` | 0 | none; no independent rights-cleared allocation series found |
| `no_counterpart` | 13 | no numeric comparison rows |
| `blocked` | 0 | none |

| Variable | Grade / disposition | Reason or comparison verdict |
|---|---|---|
| `consumption` | `normalized_index` / mapped | Sole mapped series; 18/18 informative years outside 0.5-point tolerance. |
| `trade_export_volume_index` | `no_counterpart` | `national_accounts.exports` and both channel flows are zero throughout 1957–1978, including 1960; own-1960 normalization is undefined. No alternate base or target-derived mapping is used. |
| `trade_import_volume_index` | `no_counterpart` | `national_accounts.imports` and both channel flows are zero throughout 1957–1978, including 1960; own-1960 normalization is undefined. Imports remain outcomes, never quotas. |
| `industrial_electricity` | `no_counterpart` | No independent rights-cleared split/share series is registered; the registered KSH product series are targets and cannot be used to derive a share. Model split is absent. |
| `industrial_crude_steel` | `no_counterpart` | No independent rights-cleared split/share series is registered; the registered KSH product series are targets and cannot be used to derive a share. Model split is absent. |
| `industrial_fertilizer` | `no_counterpart` | No independent rights-cleared split/share series is registered; the registered KSH product series are targets and cannot be used to derive a share. Model split is absent. |
| `industrial_cement` | `no_counterpart` | No independent rights-cleared split/share series is registered; the registered KSH product series are targets and cannot be used to derive a share. Model split is absent. |
| `industrial_television` | `no_counterpart` | No independent rights-cleared split/share series is registered; the registered KSH product series are targets and cannot be used to derive a share. Model split is absent. |
| `ag_cereals` | `no_counterpart` | F2 has one `g08_agricultural_raw` series; household axis, plot recipes and stage catalog do not distinguish crops. Permanently no counterpart under this ontology. |
| `ag_wheat` | `no_counterpart` | F2 has one `g08_agricultural_raw` series; household axis, plot recipes and stage catalog do not distinguish crops. Permanently no counterpart under this ontology. |
| `ag_maize` | `no_counterpart` | F2 has one `g08_agricultural_raw` series; household axis, plot recipes and stage catalog do not distinguish crops. Permanently no counterpart under this ontology. |
| `gdp` | `no_counterpart` | The model has no GDP aggregate; summed gross material output is not GDP. |
| `industrial_output` | `no_counterpart` | No weighted industrial-production index; summing broad commodity groups invents weights. |
| `investment` | `no_counterpart` | No gross fixed capital formation aggregate; capital-goods production is not investment. |

For the attempted Group 1 rule, the declared price vector is `build_material_prices(parameters).standard`; the methodological difference would be KSH index weights/base versus an admin-price quantity total. CMEA/convertible composition is not inferred. The final reproduction CSV keeps CMEA and convertible import/export admin-price values in separate diagnostic columns, not as targets; they are all zero over the reported years. Since both total series have a zero 1960 denominator, neither is presented as a normalized-index mapping. The registered-source search covered `data/manifests/sources.yml`, `data/manifests/artifacts.yml`, and `data/raw`; the industry and agriculture source records are target-role data, not independent allocation shares. The F2 crop check is grounded in `config/ontology/f2_v1.json` (`g08_agricultural_raw`), `src/hsm_lab/contract/households.py`, `src/hsm_lab/engine/network.py`, and the F2 stage/plot recipes in `src/hsm_lab/contract/material.py`.

## Frozen gates and guardrails

| Gate/metric | Historical F2 baseline | Required / disposition |
|---|---:|---|
| Liveness | 0.1116 | ≥0.8 — FAIL |
| Delivered/funded service ratios g03 / g15 / g16 | 0.489 / 0.120 / 0.199 | each ≥0.9 — FAIL |
| Treasury cash first reaches zero | tick 17–18 | self-financing criterion — FAIL |
| Tail expired services share | about 0.94 | ≤0.20 — FAIL |
| T1 production last-10 mean | 28,074 | ≥35,092 — diagnostic FAIL |
| T2 household-consumption last-10 mean | 1,668 | ≥2,085 — diagnostic FAIL |
| T3 treasury / rescue rule | passes | diagnostic PASS |
| Accounting invariants | pass | PASS; no new residual accepted |

Frozen gates remain unchanged and blocked. Every completed W2/W3 arm passed its accounting invariants; no residual gate was introduced, waived, or tolerated. No defaults were changed.

## W2 OAT arm replication spread

Each cell is min–max across the three model seeds; units are model units. `T1/T2/T3` records number of passing replicates. All runs are 116 ticks. Full per-arm hashes/digests are in local `outputs/p06-w2-oat/sensitivity.json` and `outputs/p06-w8-seedbank/seedbank.json`. The baseline includes original seed 1729 and matching seed-1730/1731 arms.

| Axis | Value | Production last-10 min–max | HH consumption last-10 min–max | T1/T2/T3 passes | Accounting |
|---|---:|---:|---:|---:|---|
| `bailout_envelope_fraction` | 0.2 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `bailout_envelope_fraction` | 0.25 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `bailout_envelope_fraction` | 0.3 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `handling_work_per_unit.scale` | 0.8 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `handling_work_per_unit.scale` | 1 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `handling_work_per_unit.scale` | 1.2 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `service_split.0` | 0.56 | 18,406.53–18,416.48 | 437.21–442.23 | 0 / 0 / 3 | PASS |
| `service_split.0` | 0.7 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `service_split.0` | 0.84 | 27,355.57–27,362.18 | 1,247.97–1,251.18 | 0 / 0 / 3 | PASS |
| `service_split.1` | 0.16 | 43,905.35–43,921.27 | 1,427.73–1,431.97 | 3 / 0 / 3 | PASS |
| `service_split.1` | 0.2 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `service_split.1` | 0.24 | 32,906.15–32,908.14 | 656.81–660.59 | 0 / 0 / 3 | PASS |
| `service_split.2` | 0.08 | 30,383.31–30,389.01 | 1,044.50–1,050.40 | 0 / 0 / 3 | PASS |
| `service_split.2` | 0.1 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `service_split.2` | 0.12 | 25,891.98–25,893.41 | 1,592.48–1,594.80 | 0 / 0 / 3 | PASS |
| `trade.cmea_export_demands.scale` | 0.8 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `trade.cmea_export_demands.scale` | 1 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `trade.cmea_export_demands.scale` | 1.2 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `trade.convertible_export_demands.scale` | 0.8 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `trade.convertible_export_demands.scale` | 1 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `trade.convertible_export_demands.scale` | 1.2 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `wage_rate` | 6 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `wage_rate` | 6.6 | 15,970.10–15,980.24 | 249.31–255.52 | 0 / 0 / 3 | PASS |
| `wage_rate` | 7.2 | 14,516.58–14,524.69 | 205.86–213.18 | 0 / 0 / 3 | PASS |

The preflight wage-rate 4.8 point remains rejected before tick 0 by the Treasury opening-deposit guard and is not counted as a replicate or outcome. Trade-demand vectors remained inert on this replay path. Sensitivity ordering by largest absolute movement remains service_split.1, wage_rate, service_split.0, service_split.2; bailout envelope and handling-work scale move neither selected terminal aggregate. These are structural responses, not historical fit improvements.
## W3 Morris screen across model seeds

For each factor, the table reports μ* (production units per full factor range) across three model seeds, with the same two Morris trajectories (trajectory generator seed 1729). Ranking stability is descriptive only; with two trajectories it is exploratory.

| Factor | μ* across seeds 1729 / 1730 / 1731 | Rank across seeds |
|---|---:|---:|
| `service_split.2` | 52,851.01 / 62,394.28 / 57,142.11 | 1 / 1 / 1 |
| `service_split.0` | 47,222.21 / 48,648.05 / 42,626.02 | 2 / 2 / 2 |
| `service_split.1` | 31,708.41 / 27,824.75 / 32,438.42 | 3 / 3 / 3 |
| `wage_rate` | 14,378.44 / 13,871.08 / 13,898.21 | 4 / 4 / 4 |
| `trade.cmea_export_demands.scale` | 1,073.11 / 1,019.13 / 477.18 | 5 / 5 / 6 |
| `trade.convertible_export_demands.scale` | 327.61 / 550.33 / 640.02 | 6 / 6 / 5 |
| `handling_work_per_unit.scale` | 6.27 / 8.76 / 45.54 | 7 / 7 / 7 |
| `bailout_envelope_fraction` | 0.00 / 0.00 / 0.00 | 8 / 8 / 8 |

No Sobol calculation was run; its entry point refuses empty/non-identified parameter sets.

## Card dispositions (evidence caps)

| Card | Disposition | Evidence boundary |
|---|---|---|
| M1 | UNIDENTIFIED | coalition/observation dependency; no early/late political cut |
| M2 | CONDITIONAL | shortage is present and bailout OAT is terminally inert; no direct hard-budget/credit intervention |
| M3 | CONDITIONAL | structural wage-rate sensitivity only; labour arrears/policy wage-factor channel not tested |
| M4 | UNIDENTIFIED | cultural block; mechanism not exercised |
| M5 | UNIDENTIFIED | v4 1968 forks ran, but coalition/information dependencies remain unidentified |
| M6 | UNIDENTIFIED | v4 1973 arms ran; external-recipe dependency remains unidentified |
| M7 | UNIDENTIFIED | opposition/coalition dependency; no regional test |
| M8 | UNIDENTIFIED | v4 1968 and political forks ran; coalition/observation/information dependencies remain unidentified |
| M9 | UNIDENTIFIED | digital-nem and political arms ran; information dependency remains unidentified |
| M10 | UNIDENTIFIED | v4 1973 shock arms ran; external-recipe dependency remains unidentified |
| M11 | CONDITIONAL | service composition moves terminal aggregates; department-I/durable-wait mechanism not tested |

No card is validated or promoted to SUPPORTED.

## Arm completion and blocked work

| Work | Status | Evidence / limit |
|---|---|---|
| W1 mechanism preregistration | PASS | 11 validated cards, five result categories; no verdicts at registration |
| W2 OAT | PASS with rejection/inert axes | 24 original arms plus 48 seed replications; rejected wage 4.8 excluded |
| W3 Morris | PASS, exploratory | 18 original arms plus 36 seed replications; no estimator or Sobol |
| W4 forcing ladder | CONDITIONAL H4 | residual 1.3666269856210904e-6 vs fixed 1e-6; H0–H3 pass |
| W5 1968 forks | PASS (counterfactual evidence) | [five arms including same-checkpoint empty control](P06_1968_FORK.md); all 116 ticks, accounting pass |
| W6 1973 shock arms | PASS (counterfactual evidence) | [six arms including tick-0064 empty control](P06_1973_SHOCK.md); all 116 ticks, accounting pass |
| W7 political counterfactuals | PASS (counterfactual evidence) | [six arms including same-checkpoint empty control](P06_POLITICAL_COUNTERFACTUAL.md); all 116 ticks, accounting pass |
| W8 protocol/bundle/report | PASS | hold-out/reserved authorization is in target-loading path; bundle CLI assemble/verify tested; seed spread reported |

A new v4 parent run completed in 5.42 seconds. All 17 political forks ran in 4.316–6.050 seconds each (26.29 seconds concurrent batch wall time), each ending at 1985Q4. No degradation ladder was needed. The three control arms use empty `hist-nem` interventions from the corresponding checkpoint. The result tables are scenario-conditional model responses and do not validate historical mechanisms.

## Assumptions versus inference

Assumed: declared behavioural inputs, seed bank rule, historical-F2 scenario, compact output definitions and frozen T1–T3 thresholds. Inferred: none of the unidentified political, cultural, information, opposition, coalition or external-policy processes. Deterministic sensitivity and seed spread do not identify those processes. No target-error comparison is claimed in this W0.5 report state; W9 will declare mappings and published-precision thresholds before numeric target reads. The residual frozen gates remain failed as shown above.
