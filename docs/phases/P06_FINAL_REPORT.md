# P06 final reproduction-scope report

## Scope and evidence boundary

This is a deterministic historical-reproduction study under declared behavioural assumptions. `calibrated = 0`; no parameter block is identified. The reserved 1986Q1–1988Q4 window remains closed, and hold-out values were not used for selection. No ABC/pyABC, posterior, calibration, causal identification, or validation claim is made. Results below are model outputs and replication spread across the three declared model seeds (1729, 1730, 1731), not posterior uncertainty. Seeds 1730 and 1731 follow the recorded rule “the next two integer seeds after the existing seed 1729”; this is not a posterior or seed-bank inference. Every executed run stopped at or before 1985Q4.

P05 has 14 admitted variable IDs across calibration (1960–69) and internal validation (1970–78), 28 artifacts. Model output is quarterly and the admitted target series do not yet have a declared commodity/unit crosswalk plus annual aggregation/error tolerances. Therefore a like-for-like numeric target-error table cannot be computed without inventing a mapping; this report records that comparison as OPEN rather than fabricating residuals. Hold-out 1979–85 and reserved 1986–88 series were omitted.

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

Each cell is min–max across the three model seeds; units are model units. `T1/T2/T3` records number of passing replicates. All runs are 116 ticks. Full per-arm hashes/digests are in the raw ignored artifacts `outputs/p06-w2-oat/sensitivity.json` and `outputs/p06-w8-seedbank/seedbank.json`. The baseline is included as the original seed-1729 arm plus its matching seed-1730/1731 arms.

| Axis | Value | Production last-10 min–max | HH consumption last-10 min–max | T1/T2/T3 passes | Accounting |
|---|---:|---:|---:|---:|---|
| `bailout_envelope_fraction` | 0.2 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `bailout_envelope_fraction` | 0.25 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `bailout_envelope_fraction` | 0.3 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `handling_work_per_unit.scale` | 0.8 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `handling_work_per_unit.scale` | 1.0 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
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
| `trade.cmea_export_demands.scale` | 1.0 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `trade.cmea_export_demands.scale` | 1.2 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `trade.convertible_export_demands.scale` | 0.8 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `trade.convertible_export_demands.scale` | 1.0 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `trade.convertible_export_demands.scale` | 1.2 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
| `wage_rate` | 6.0 | 28,072.90–28,074.08 | 1,666.16–1,667.96 | 0 / 0 / 3 | PASS |
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
| M5 | UNIDENTIFIED | coalition/information dependency; political forks blocked |
| M6 | UNIDENTIFIED | external recipe dependency; 1973 arms registered but not run |
| M7 | UNIDENTIFIED | opposition/coalition dependency; no regional test |
| M8 | UNIDENTIFIED | political information dependency; no executable fork evidence |
| M9 | UNIDENTIFIED | observation dependency; no executable fork evidence |
| M10 | UNIDENTIFIED | external-recipe dependency; shock arms not run |
| M11 | CONDITIONAL | service composition moves terminal aggregates; department-I/durable-wait mechanism not tested |

No card is validated or promoted to SUPPORTED.

## Arm completion and blocked work

| Work | Status | Evidence / limit |
|---|---|---|
| W1 mechanism preregistration | PASS | 11 validated cards, five result categories; no verdicts at registration |
| W2 OAT | PASS with rejection/inert axes | 24 original arms plus 48 seed replications; rejected wage 4.8 excluded |
| W3 Morris | PASS, exploratory | 18 original arms plus 36 seed replications; no estimator or Sobol |
| W4 forcing ladder | CONDITIONAL H4 | residual 1.3666269856210904e-6 vs fixed 1e-6; H0–H3 pass |
| W5 1968 forks | OPEN | all available tick-0044 checkpoints are v3; current loader refuses v3, requires v4 |
| W6 1973 shock arms | OPEN | five interventions registered and schema-valid; no political arm executed |
| W7 political counterfactuals | OPEN | five interventions registered and schema-valid; no political arm executed |
| W8 protocol/bundle/report | PASS with W5–W7 blockers | hold-out/reserved authorization is in target-loading path; bundle CLI assemble/verify tested; seed spread reported |

The checkpoint pilot refused `material-checkpoint-v3` in about 0.633 seconds. That is refusal overhead, not a political-run runtime measurement. The plan’s political-arm runtime prerequisite is therefore unmet; no degradation ladder was applied and no simulation beyond 1985Q4 was attempted. To resume W5–W7, provide a compatible current v4 tick-0044 checkpoint or a current compatible pre-shock political run with that checkpoint.

## Assumptions versus inference

Assumed: declared behavioural inputs, seed bank rule, historical-F2 scenario, compact output definitions and frozen T1–T3 thresholds. Inferred: none of the unidentified political, cultural, information, opposition, coalition or external-policy processes. Deterministic sensitivity and seed spread do not identify those processes. No target-error validation was possible without a declared crosswalk and tolerances. The residual frozen gates remain failed as shown above.
