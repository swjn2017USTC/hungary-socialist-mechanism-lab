# P08 — Diagnostic Ontology

**Phase:** P07 (Final)  
**Author:** Implementer (P07A1–P07B2)  
**Status:** Machine-verified specification

---

## Purpose

This document defines the diagnostic ontology for the Hungary Socialist Mechanism
Lab. It formalizes what constitutes evidence for or against each mechanism
hypothesis, defines the diagnostic question tree used to assess mechanism validity,
and establishes the criteria for evidence quality assessment.

This is a **machine-verified specification**: all question-tree nodes map to
declared metrics in `studies/manifest.json` and are covered by
`test_metric_binding_validation.py`.

---

## 1. Core Definitions

### 1.1 Evidence

**Evidence** is a structured observation consisting of:

- A `MetricSpec` (table, column, unit, fidelity, time window)
- An `ObservedState` (the actual values produced by a model run)
- A `LinkedEvidenceRecord` tying the observation to a mechanism hypothesis

Evidence is **for** a hypothesis if the observed pattern is consistent with the
predicted mechanism dynamics. Evidence is **against** a hypothesis if the observed
pattern contradicts the predicted dynamics.

### 1.2 Mechanism Hypothesis

A **mechanism hypothesis** is a named, falsifiable claim about how a policy
intervention causes observable economic change. Each hypothesis is declared in a
`M{n}.json` card and has:

- `mechanism_id`: M01–M11
- `intent`: natural-language description of the mechanism
- `status`: `declared` or `blocked`
- `v1_card_sha256`: immutable anchor to the card source
- `study_decl.json`: phase-specific declaration with metric specs

A hypothesis is **supported** when interventions on its policy parameters produce
changes in its linked metrics that are statistically distinguishable from the
counterfactual (historical_f2_replay baseline). It is **refuted** when no such
change is observed despite correctly targeted interventions.

### 1.3 Diagnostic Question Tree

A **diagnostic question tree** is a directed graph of questions that guides the
assessment of whether a mechanism hypothesis is supported. Each node is either:

- **Metric node**: a `MetricSpec` that can be measured (table, column, fidelity)
- **Structural node**: a logical condition (AND/OR/NOT) combining child nodes
- **Terminal node**: a conclusion (SUPPORTS / REFUTES / INCONCLUSIVE)

A hypothesis is SUPPORTS when all its required metric nodes show the expected
pattern. It is REFUTES when a required metric node contradicts the prediction.
It is INCONCLUSIVE when data is missing or fidelity is insufficient.

---

## 2. Evidence Quality Framework

### 2.1 Fidelity Levels

| Level | Label | Description |
|---|---|---|
| F0 | Engine trace | Raw engine output, unnormalized |
| F1 | Normalized index | Scaled to 1957Q1=100, comparable across runs |
| F2 | F2_run | Post-normalization, engine-stable output |

Higher fidelity does not mean higher quality; F2 is the highest-quality
run because it incorporates engine stability corrections.

### 2.2 Validation Fidelity

| Level | Label | Description |
|---|---|---|
| `proxy` | Proxy | Metric is an indirect proxy for the mechanism |
| `normalized_index` | Normalized index | Metric is a normalized index with a known baseline |
| `full_magnitude` | Full magnitude | Metric captures absolute economic magnitude |

Evidence from `normalized_index` or `full_magnitude` metrics is preferred.
Evidence from `proxy` metrics requires additional corroboration.

### 2.3 Data Role

| Role | Description |
|---|---|
| `target` | Primary outcome metric for the mechanism |
| `candidate_linkage` | Secondary metric that should co-move with target |
| `corroborating` | Independent line of evidence |
| `negative_control` | Metric that should NOT change under the intervention |

A hypothesis is **well-supported** when targets and candidate-linkage metrics
show the expected change, corroborating metrics are consistent, and negative
controls do not change.

---

## 3. Mechanism Question Trees

Each section below gives the diagnostic question tree for one mechanism hypothesis.
Question tree format:

`**Q{n}.{sub}** *MetricNode*` → what to check
`AND` / `OR` → logical combination
`→ TERMINAL: {SUPPORTS|REFUTES|INCONCLUSIVE}` → conclusion

Required metrics are marked **(R)**; corroborating metrics are marked **(C)**.

---

### M01 — Household Consumption and Forced Saving

**Hypothesis:** Welfare provision cuts force households to increase forced saving,
reducing consumption. The mechanism operates through the household budget
constraint, not through price channels.

**Key policy parameters:** `policy.welfare_provision`, `policy.consumer_import_factor`

**Question tree:**

```
Q1. Does welfare_provision intervention change household_consumption?
    └─ MetricNode: national_accounts.household_consumption (R)
       └─ ObservedState: Δ consumption ≠ 0 at intervention quarter
           AND Δ consumption persists as predicted by budget model
           → SUPPORTS if yes
           → REFUTES if consumption change ≠ predicted magnitude
           → INCONCLUSIVE if data missing (zero_fill or skip)

Q2. Does forced_saving increase when welfare_provision decreases?
    └─ MetricNode: household_budgets.forced_saving (R)
       └─ ObservedState: forced_saving ↑ at intervention quarter
           → SUPPORTS if yes
           → REFUTES if forced_saving unchanged

Q3. Is the consumption change NOT driven by import price shifts?
    └─ MetricNode: national_accounts.imports (C)
       └─ ObservedState: imports change ≠ significant at intervention quarter
           → AND: if Q1 AND Q2 SUPPORTS AND Q3: consumption not import-driven
               → TERMINAL: SUPPORTS
           → OR: if any of Q1/Q2 REFUTES
               → TERMINAL: REFUTES
           → INCONCLUSIVE: if any metric has missing_policy=skip or
               fidelity < F2_RUN and no corroborating data
```

**Negative controls:**
- `national_accounts.government_consumption` (should not change under welfare intervention)
- `national_accounts.exports` (should not change under household budget intervention)

---

### M02 — Enterprise Bottleneck

**Hypothesis:** Hard budget constraints expose enterprise bottleneck constraints,
generating tick diagnostics signals (queue buildup, demand overhang). The
mechanism is activated when `policy.budget_hardness` increases.

**Key policy parameters:** `policy.budget_hardness`, `policy.credit_fraction`

**Question tree:**

```
Q1. Does budget_hardness intervention increase bottleneck_demand_count?
    └─ MetricNode: tick_diagnostics.bottleneck_demand_count (R)
       └─ ObservedState: bottleneck_demand_count ↑ at intervention quarter
           → SUPPORTS if yes
           → REFUTES if count unchanged or decreases

Q2. Does enterprise_autonomy intervention affect bottleneck diagnostics?
    └─ MetricNode: tick_diagnostics.bottleneck_demand_count (R)
       └─ ObservedState: sensitivity of bottleneck to autonomy change
           → SUPPORTS if enterprise autonomy amplifies bottleneck signal
           → REFUTES if no sensitivity

Q3. Are tick diagnostics signals correlated with department-level output drops?
    └─ MetricNode: departments.department_output (C)
       └─ MetricNode: tick_diagnostics.bottleneck_demand_count (C)
       └─ ObservedState: Pearson correlation across departments at each quarter
           → SUPPORTS if correlation < -0.3 (bottleneck reduces output)
           → REFUTES if correlation ≥ -0.3

→ TERMINAL: SUPPORTS if Q1 AND Q2 both support AND Q3 supports
→ TERMINAL: REFUTES if Q1 OR Q2 refutes OR Q3 refutes
→ TERMINAL: INCONCLUSIVE if missing_policy blocks required metric
```

**Negative controls:**
- `tick_diagnostics.bottleneck_demand_count` in quarters before intervention
- `organization_diagnostics.labor_allocation` (should not be affected by budget hardness)

---

### M03 — Wage-Price Spiral

**Hypothesis:** Enterprise autonomy increases wage drift, triggering a
wage-price spiral. The mechanism operates through `policy.wage_factor` and
`policy.plan_utilization`.

**Question tree:**

```
Q1. Does wage_factor intervention increase nominal household consumption?
    └─ MetricNode: national_accounts.household_consumption (R)
       └─ ObservedState: consumption ↑ in nominal terms, real terms unchanged
           → SUPPORTS if nominal ↑ and real ≈ baseline
           → REFUTES if real consumption changes significantly

Q2. Does plan_utilization change with wage_factor?
    └─ MetricNode: organization_diagnostics.plan_fulfillment (R)
       └─ ObservedState: plan_utilization changes with wage_factor
           → SUPPORTS if utilization ↑ with wage increases
           → REFUTES if utilization decreases or unchanged

Q3. Are consumption changes explained by price-level shifts?
    └─ Composite: national_accounts.household_consumption (R)
       + household_budgets.spending (C)
       └─ ObservedState: decompose into price × quantity
           → SUPPORTS if price channel accounts for ≥ 60% of change
           → REFUTES if quantity channel dominates

→ TERMINAL: SUPPORTS if Q1 AND Q2 AND Q3 all support
→ TERMINAL: REFUTES if any required metric refutes
→ TERMINAL: INCONCLUSIVE if fidelity < F2 or missing_policy=skip
```

---

### M04 — Import Compression

**Hypothesis:** Consumer import factor caps force domestic substitution,
reducing import volumes. The mechanism operates through
`policy.consumer_import_factor`.

**Question tree:**

```
Q1. Does consumer_import_factor decrease imports?
    └─ MetricNode: national_accounts.imports (R)
       └─ ObservedState: imports ↓ in intervention arm vs baseline
           → SUPPORTS if imports decrease by ≥ expected substitution ratio
           → REFUTES if imports unchanged or increase

Q2. Does domestic production compensate for import reduction?
    └─ MetricNode: national_accounts.production (C)
       └─ MetricNode: national_accounts.imports (C)
       └─ ObservedState: domestic production ↑ as imports ↓
           → SUPPORTS if substitution coefficient > 0.7
           → REFUTES if substitution coefficient < 0.3

Q3. Does household consumption remain stable (no demand destruction)?
    └─ MetricNode: household_budgets.spending (R)
       └─ ObservedState: spending change ≠ statistically significant
           → SUPPORTS if spending stable despite import reduction
           → REFUTES if spending drops significantly

→ TERMINAL: SUPPORTS if Q1 AND Q2 AND Q3 all support
→ TERMINAL: REFUTES if Q1 refutes
→ TERMINAL: INCONCLUSIVE if substitution data missing
```

---

### M05 — Enterprise Autonomy and Bottleneck Propagation

**Hypothesis:** Enterprise autonomy amplifies bottleneck propagation: autonomous
enterprises chase inputs more aggressively, worsening queue dynamics. Shares
signals with M02 but the causal direction differs.

**Key shared metric:** `tick_diagnostics.bottleneck_demand_count`

**Question tree:**

```
Q1. Does enterprise_autonomy intervention increase bottleneck_demand_count?
    └─ MetricNode: tick_diagnostics.bottleneck_demand_count (R)
       └─ ObservedState: bottleneck_demand_count ↑ beyond M02 baseline
           → SUPPORTS if M05 intervention produces larger Δ than M02 baseline
           → REFUTES if Δ is within M02 noise band

Q2. Does the bottleneck pattern differ qualitatively from M02?
    └─ Composite: tick_diagnostics.bottleneck_demand_count (R)
       + organization_diagnostics.labor_allocation (C)
       └─ ObservedState: M05 bottleneck concentrated in high-autonomy sectors
           → SUPPORTS if geographic/sectoral concentration differs from M02
           → REFUTES if bottleneck distribution identical to M02

Q3. Is the M05 effect separable from M02 after controlling for budget_hardness?
    └─ Interaction: M05 intervention × budget_hardness level
       └─ ObservedState: partial correlation of bottleneck with autonomy
           controlling for hardness
           → SUPPORTS if partial correlation significant (p < 0.05)
           → REFUTES if correlation disappears after controls

→ TERMINAL: SUPPORTS if Q1 AND Q2 AND Q3 all support
→ TERMINAL: REFUTES if Q1 or Q3 refutes (Q2 is corroborating)
→ TERMINAL: INCONCLUSIVE if cannot separate M02/M05 effects
```

**Key diagnostic insight:** M05 and M02 both affect `bottleneck_demand_count`.
The diagnostic question tree uses the **mechanism prefix** in `metric_id`
(`m2.tick_diagnostics.bottleneck_demand_count` vs
`m5.tick_diagnostics.bottleneck_demand_count`) to distinguish which card's
enrichment is being applied.

---

### M06 — Borrowing Constraint Channel

**Hypothesis:** Credit envelope tightening tightens borrowing constraints,
reducing investment and amplifying output drops. The mechanism operates through
`policy.credit_fraction`.

**Question tree:**

```
Q1. Does credit_fraction intervention reduce financial_accounts.credit_flow?
    └─ MetricNode: financial_accounts.credit_flow (R)
       └─ ObservedState: credit_flow ↓ in intervention arm
           → SUPPORTS if credit_flow ↓ by ≥ expected tightening magnitude
           → REFUTES if credit_flow unchanged

Q2. Does reduced credit flow affect investment proxies?
    └─ MetricNode: financial_accounts.investment (R) [if available]
       OR organization_diagnostics.capital_allocation (C)
       └─ ObservedState: investment ↓ following credit flow reduction
           → SUPPORTS if investment ↓ within 2 quarters of credit reduction
           → REFUTES if investment unchanged or delayed > 4 quarters

Q3. Is the output drop channel consistent with credit mechanism?
    └─ Composite: stage_balances.output (R)
       + financial_accounts.credit_flow (C)
       └─ ObservedState: output drop lags credit reduction
           → SUPPORTS if correlation significant and lag ≤ 2 quarters
           → REFUTES if output drop precedes credit reduction

→ TERMINAL: SUPPORTS if Q1 AND Q2 AND Q3 all support
→ TERMINAL: REFUTES if Q1 or Q2 refutes
→ TERMINAL: INCONCLUSIVE if financial_accounts data unavailable
```

**Note:** `policy.bailout_envelope_fraction` and `policy.credit_envelope_fraction`
are declared in the v1 M2 card but are NOT in `political_quarters` and are
therefore BLOCKED interventions at this phase. They require separate engine
parameterisation before they can be validated.

---

### M07 — Second Economy Tolerance

**Hypothesis:** Second economy tolerance policy (`policy.second_economy_tolerance`)
shifts labor allocation between formal and informal sectors. The mechanism is
detected through changes in `stage_balances` composition.

**Question tree:**

```
Q1. Does second_economy_tolerance intervention shift labor allocation?
    └─ MetricNode: organization_diagnostics.labor_allocation (R)
       └─ ObservedState: informal sector labor ↑ when tolerance increases
           → SUPPORTS if informal labor allocation shifts as predicted
           → REFUTES if allocation unchanged

Q2. Does formal sector output change consistently with labor shift?
    └─ MetricNode: departments.department_output (C)
       └─ MetricNode: organization_diagnostics.labor_allocation (C)
       └─ ObservedState: department output inversely correlated with informal labor
           → SUPPORTS if correlation consistent across departments
           → REFUTES if no consistent pattern

Q3. Is the effect consistent across multiple tolerance levels?
    └─ Dose-response: policy.second_economy_tolerance value vs labor shift
       └─ ObservedState: monotonic or threshold response
           → SUPPORTS if dose-response relationship significant
           → REFUTES if non-monotonic or threshold absent

→ TERMINAL: SUPPORTS if Q1 AND Q2 AND Q3 all support
→ TERMINAL: REFUTES if Q1 refutes
→ TERMINAL: INCONCLUSIVE if second economy metrics unavailable
```

---

### M08 — Private Autonomy Effects

**Hypothesis:** Private sector autonomy (`policy.private_autonomy`) drives
productivity differences through competition dynamics. The mechanism operates
through `organization_diagnostics` and `financial_accounts`.

**Question tree:**

```
Q1. Does private_autonomy intervention affect productivity metrics?
    └─ MetricNode: organization_diagnostics.productivity_index (R)
       └─ ObservedState: productivity ↑ with autonomy increase
           → SUPPORTS if productivity change ≥ predicted competition effect
           → REFUTES if productivity unchanged or decreases

Q2. Does financial structure change consistent with autonomy effect?
    └─ MetricNode: financial_accounts.enterprise_investment (C)
       └─ ObservedState: investment patterns shift toward high-autonomy firms
           → SUPPORTS if investment reallocation consistent with autonomy
           → REFUTES if investment patterns unchanged

Q3. Is the effect distinct from M03 (wage-price) and M05 (autonomy-bottleneck)?
    └─ Partial correlation analysis controlling for wage and bottleneck effects
       └─ ObservedState: private_autonomy effect remains significant
           after controlling for M03/M05 confounders
           → SUPPORTS if private_autonomy effect independent
           → REFUTES if effect absorbed by M03/M05

→ TERMINAL: SUPPORTS if Q1 AND Q2 AND Q3 all support
→ TERMINAL: REFUTES if Q1 refutes
→ TERMINAL: INCONCLUSIVE if confounders cannot be adequately controlled
```

---

### M09 — Information and Forecasting

**Hypothesis:** Technology/forecast accuracy changes
(`information_quarters.forecast_accuracy`) affect plan utilization and price
stability. The mechanism operates through information asymmetry channels.

**Question tree:**

```
Q1. Does forecast_accuracy change with technology intervention?
    └─ MetricNode: information_quarters.forecast_accuracy (R)
       └─ ObservedState: forecast accuracy ↑ or ↓ as predicted
           → SUPPORTS if accuracy change matches intervention direction
           → REFUTES if accuracy moves opposite to prediction

Q2. Does improved forecast accuracy reduce plan utilization volatility?
    └─ MetricNode: organization_diagnostics.plan_fulfillment (R)
       └─ ObservedState: plan utilization variance ↓ with better forecasts
           → SUPPORTS if volatility reduction statistically significant
           → REFUTES if volatility unchanged

Q3. Is price stability affected consistent with information mechanism?
    └─ Composite: national_accounts.price_index (C)
       + information_quarters.forecast_accuracy (C)
       └─ ObservedState: price variance inversely correlated with accuracy
           → SUPPORTS if correlation significant
           → REFUTES if no information-price link found

→ TERMINAL: SUPPORTS if Q1 AND Q2 AND Q3 all support
→ TERMINAL: REFUTES if Q1 or Q2 refutes
→ TERMINAL: INCONCLUSIVE if information data unavailable or low-fidelity
```

---

### M10 — Departmental Planning Friction

**Hypothesis:** Department-level planning friction (`departments.department_output`)
generates systemic misallocation. The mechanism is detected through
cross-department output variance.

**Question tree:**

```
Q1. Does department_output variance increase under plan-based allocation?
    └─ MetricNode: departments.department_output (R)
       └─ MetricNode: aggregates.inter_department_variance (R)
       └─ ObservedState: inter-department variance ↑ above historical baseline
           → SUPPORTS if variance increase significant (F-test p < 0.05)
           → REFUTES if variance unchanged or decreases

Q2. Is the variance concentrated in specific sectors?
    └─ Sectoral decomposition of department_output variance
       └─ ObservedState: high-variance sectors identified
           → SUPPORTS if sectors match planning-heavy sectors
           → REFUTES if variance evenly distributed

Q3. Does output misallocation correlate with downstream bottlenecks?
    └─ MetricNode: tick_diagnostics.bottleneck_demand_count (C)
       └─ MetricNode: departments.department_output (C)
       └─ ObservedState: misallocation precedes or predicts bottleneck spikes
           → SUPPORTS if lag correlation significant (p < 0.05)
           → REFUTES if bottleneck precedes misallocation

→ TERMINAL: SUPPORTS if Q1 AND Q2 AND Q3 all support
→ TERMINAL: REFUTES if Q1 refutes
→ TERMINAL: INCONCLUSIVE if department-level data unavailable
```

---

### M11 — Stage-Balance Composition Shift

**Hypothesis:** Policy interventions shift the composition of stage_balances
(Inputs → Processing → Outputs). The mechanism operates through the
material balance accounting system.

**Question tree:**

```
Q1. Does intervention shift stage_balance composition?
    └─ MetricNode: stage_balances.input_stage (R)
       └─ MetricNode: stage_balances.processing_stage (R)
       └─ MetricNode: stage_balances.output_stage (R)
       └─ ObservedState: share of output_stage in total balance changes
           → SUPPORTS if output_stage share shifts as predicted by mechanism
           → REFUTES if composition unchanged

Q2. Is the composition shift consistent across multiple intervention types?
    └─ Cross-mechanism comparison: M01–M11 interventions vs stage shift
       └─ ObservedState: stage composition responds consistently
           → SUPPORTS if multiple mechanisms produce similar composition shifts
           → REFUTES if composition shift mechanism-specific only

Q3. Does the stage balance shift correlate with aggregate economic indicators?
    └─ Composite: national_accounts.gdp (C)
       + stage_balances.output_stage (C)
       └─ ObservedState: output_stage share correlates with GDP growth
           → SUPPORTS if correlation consistent across quarters
           → REFUTES if no aggregate linkage

→ TERMINAL: SUPPORTS if Q1 AND (Q2 OR Q3) support
→ TERMINAL: REFUTES if Q1 refutes
→ TERMINAL: INCONCLUSIVE if stage balance data fidelity < F2
```

---

## 4. Cross-Mechanism Conflict Resolution

When two mechanism hypotheses make contradictory predictions about the same
metric, the conflict is resolved by:

1. **Isolation:** Run each mechanism's intervention in isolation (other
   parameters held at baseline)
2. **Partial correlation:** Control for the confounding mechanism when
   assessing the target mechanism
3. **Dose-response:** Vary the intervention intensity to identify the
   dominant mechanism

**Known conflicts:**

| Conflict | Mechanism A | Mechanism B | Resolution approach |
|---|---|---|---|
| `bottleneck_demand_count` | M02 (budget hardness) | M05 (enterprise autonomy) | Partial correlation; M05 requires additional enterprise-specific metrics |
| `household_consumption` | M01 (welfare cuts) | M03 (wage-price) | Decompose price vs quantity channel using real vs nominal consumption |
| `labor_allocation` | M07 (second economy) | M08 (private autonomy) | Separate by sector: M07 affects informal; M08 affects formal private |

---

## 5. Evidence Conclusion Criteria

An **evidence package** for a mechanism consists of:

- All metric specs linked to that mechanism (from `enrich_card_metrics`)
- The observed states from the intervention arm run
- The counterfactual baseline from `historical_f2_replay`
- The diagnostic question tree evaluation

The package is **conclusive** when:

1. All required (R) metric nodes are available at F2 fidelity or higher
2. No required metric node is blocked by `missing_policy=skip`
3. The diagnostic question tree reaches a terminal node (SUPPORTS or REFUTES)
4. The result is robust to alternative specifications (sensitivity analysis)

The package is **inconclusive** when any required metric node is missing or
low-fidelity, or when the question tree contains an INCONCLUSIVE branch that
is not outweighed by other strong evidence.

---

## 6. Relationship to Evidence Registry

The diagnostic ontology is **anchored** to the evidence registry as follows:

- Each `MetricSpec` produced by `enrich_metric_spec()` carries the
  mechanism prefix in its `metric_id` (e.g. `m2.tick_diagnostics_bottleneck_demand_count`)
- Each `InterventionBinding` in an `EvidenceRecord` links the intervention
  to its parameter path through `POLICY_PATH_TO_COLUMN`
- The `TimeWindow` on every spec is verified to be 1957Q1–1985Q4 (no reserved window)
- The `missing_policy` field is verified to never be `"0"` (no silent filling)

The evidence registry can be queried by `(mechanism_id, metric_name)` to
retrieve all evidence relevant to a specific diagnostic question.

---

## 7. Machine-Verification Summary

| Check | Location | Test |
|---|---|---|
| All 11 mechanism cards declared/blocked in manifest | `studies/manifest.json` | `test_manifest_declared_card_count` |
| Each card has machine-readable study_decl.json | `studies/M{n}/study_decl.json` | `test_each_mechanism_has_study_decl_json` |
| All enriched metric specs have `missing_policy != "0"` | `src/hsm_lab/evidence/metric_enricher.py` | `test_missing_policy_not_zero` |
| Reserved window (1986Q1+) never used in evidence | `src/hsm_lab/evidence/schemas.py` | `test_reserved_window_application_quarter_rejected` |
| All policy paths resolve to `political_quarters` columns | `src/hsm_lab/evidence/table_registry.py` | `test_policy_column_exists_in_registry` |
| M2/M5 duplicate metric names use unique keys | `src/hsm_lab/evidence/metric_enricher.py` | `test_m5_and_m2_same_metric_name_both_mapped` |
| No `research_package_complete=true` anywhere | `studies/` | `test_manifest_no_research_package_complete_true` |

---

*This document is P07P08. It is part of the P07 evidence identity and is
anchored to the P07A1 commit (6adb607) and subsequent phase commits.*
