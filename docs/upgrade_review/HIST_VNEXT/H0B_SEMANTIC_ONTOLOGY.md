# H0B semantic ontology — 11 legacy cards, real metrics, units and research status

Phase: HIST-VNEXT H0B. Written 2026-10-16.

```json
{
  "ontology_version": "hist_vnext_h0b_v1",
  "status": "provisional_overlay_awaiting_independent_review",
  "registered_legacy_cards": 11,
  "registered_metrics": 41,
  "supersedes": {
    "path": "docs/upgrade_review/evidence/P08_DIAGNOSTIC_ONTOLOGY.md",
    "sha256": "ee19929746f261fa9fe2eb3bbe47214a0caf808faf5f2e17515d690b843d0841",
    "status": ["historical_draft", "NOT_ACCEPTED_AS_CANONICAL"]
  }
}
```

## 0. Status of this document and of the old ontology

* This file is the **H0B overlay**: the first ontology version that registers all 41 metrics the 11
  legacy cards declare, at `(legacy_card_id, metrics-array index, verbatim metric string)` granularity.
* The pre-H0B ontology `docs/upgrade_review/evidence/P08_DIAGNOSTIC_ONTOLOGY.md`
  (SHA-256 `ee19929746f261fa9fe2eb3bbe47214a0caf808faf5f2e17515d690b843d0841`) is **`historical_draft`**
  and **`NOT_ACCEPTED_AS_CANONICAL`**. The 40 nodes and 22 non-existent columns it registers are an audit-time
  reading of the then-current registry, not a re-run; nothing in it is silently rewritten — this overlay
  supersedes it for new work while the draft stays on disk.
* Old research declarations (`studies/manifest.json`, SHA
  `0332e12d45ebf2ec2fbfb15e2345650288440c9c59517ac2493039a028acaafa`, and each `studies/Mxx/study_decl.json`)
  are preserved; research status is revised through
  [`studies/HIST_VNEXT/declarations/research_status_overlay.json`](../../../studies/HIST_VNEXT/declarations/research_status_overlay.json).
* Every statement below carries a level. This document contains no historical support claim.

## 1. Source of truth

| item | value |
| --- | --- |
| legacy cards | `config/p06/cards/M1.json` … `M11.json`, SHA-256 frozen in `hsm_lab.evidence.adapter.FROZEN_V1_CARD_SHA256` |
| identity map | `M1`…`M11` → `M01`…`M11`, one to one, resolved through H0A's `canonical_mechanism_id` (not `study_mechanism_id`, which rejects M10/M11) |
| card metrics registered | 41 (14 mapped, 27 blocked) |
| table schema authority | the writer's own `*_COLUMNS` lists in `hsm_lab.storage.material_output` / `hsm_lab.storage.political_output`; 14/14 tables match them exactly |
| reference run | `outputs/hist-vnext-audit-20261015/C0-r1`, run_id `ebe44a8a7af2423e9de6eb85fd2ffb24`, seed `1729`, `116` ticks, digest `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` |
| reference run manifest | SHA-256 `9f012c760cc4121a079a1914a06a049621a46e378bdf251742f7c23c22bd9821` |
| reference run summary | SHA-256 `925a9f8fe603e03892784bcd0756b3d42a5c62d828749520604825437bb9af09`, scenario `historical_f2_replay` |
| ontology (units) | `config/ontology/f2_v1.json`, read-only |
| observability vocabulary | `hsm_lab.evidence.adapter.ObservationStatus` |

Level: VERIFIED_BY_CODE (registry, units, schema match) and VERIFIED_BY_RUN (dtypes/rows/observability
read from the reference run's Parquet files).

## 2. Table registry: 14 core tables, and the schema corrections H0B made

`F2_TABLE_COLUMNS` previously carried columns the model never writes and omitted columns it does write.
Rows below give the corrected column count and the correction.

| table | columns | commodity axis | region axis | stage axis | rows (reference run) | correction in H0B |
| --- | ---: | :---: | :---: | :---: | ---: | --- |
| `aggregates` | 29 | x | x | – | 37120 | added `wholesale_open/close`, `retail_open/close`, `household_desired`, `household_budget_unmet`, `household_availability_unmet`, `plot_self_use`, `plot_market_sales` |
| `national_accounts` | 33 | x | – | – | 1856 | added `wholesale_close`, `retail_open/close`, `plot_open/close`, `project_wip_open/close`, `import_pool_open/close`, `total_stock_open/close`, `material_balance_residual`, `material_balance_tolerance_ratio` |
| `household_budgets` | 17 | – | x | – | 2320 | none (already matched) |
| `tick_diagnostics` | 12 | – | – | – | 116 | none (already matched) |
| `departments` | 7 | – | – | – | 580 | none (already matched) |
| `opposition_regions` | 15 | – | x | – | 0 | none (already matched) |
| `organization_diagnostics` | 28 | – | x | – | 20880 | added `bailout_requested/granted`, `principal_sum`, `wage_arrears_sum`, `interest_arrears_sum`, `cash_sum`, `shortage_expectation_mean`, `bailout_expectation_mean` |
| `financial_accounts` | 13 | – | – | – | 1508 | none (already matched) |
| `political_quarters` | 33 | – | – | – | 0 | removed the non-existent `soviet_relation_quality`; added `soviet_bound`, `soviet_violation`, `selected_candidate`, `information_capability`, `coalition_contributions_json` |
| `information_quarters` | 18 | – | – | – | 0 | none (already matched) |
| `stage_balances` | 13 | x | x | x | 38976 | none (already matched) |
| `policy_decisions` | 6 | – | – | – | 0 | none (already matched) |
| `political_events` | 10 | – | – | – | 0 | none (already matched) |
| `events` | 4 | – | – | – | 116 | removed the non-existent `entity_id`, `entity_type`, `payload`; the real payload column is `details_json` |

### 2.1 Sidecars the legacy cards name and no F2 run writes

| sidecar | consequence |
| --- | --- |
| `money_stock` | no F2 run writes a money_stock table or sidecar, so money_total_close has no producer to read |
| `commodity_circuit` | no F2 run writes a commodity_circuit table or sidecar, so stock_close has no producer to read |

A metric bound to one of these is reported `sidecar_absent`; it is never read from a stand-in table.

### 2.2 Region axis values

The 20 F2 regions every region-axis metric selects (all 20 declared, in
`hsm_lab.evidence.metric_enricher._ALL_REGIONS`): `budapest`, `pest`,
`borsod_abauj_zemplen`, `heves`, `nograd`, `fejer`, `komarom`, `veszprem`,
`gyor_sopron`, `vas`, `zala`, `baranya`, `somogy`, `tolna`, `hajdu_bihar`,
`szabolcs_szatmar`, `szolnok`, `bacs_kiskun`, `bekes`, `csongrad`.

Stage, department, account and currency selectors are *not* declared by any
metric: `MetricSpec` has no such axis, which is why `stage_balances`,
`departments.actual_use_value split by department`, `treasury_cash` and the
`money_stock` items are blocked rather than bound (see §7).

## 3. Commodity-specific physical units

An F2 physical flow is denominated in the commodity's own 1960 unit. Units are read from the read-only
ontology; `hsm_lab.evidence.metric_enricher.physical_aggregate_unit` refuses an unweighted cross-commodity
total, because the 16 commodities carry 16 different units.

| commodity | unit | stockable | household channel |
| --- | --- | :---: | :---: |
| `g01_solid_fuels` | `f2_solid_fuel_1960_unit` | yes | yes |
| `g02_oil_gas_fuels` | `f2_liquid_fuel_1960_unit` | yes | yes |
| `g03_electricity_heat` | `f2_electricity_heat_1960_unit` | no | yes |
| `g04_basic_metals_materials` | `f2_basic_material_1960_unit` | yes | no |
| `g05_chemicals_fertilizer` | `f2_chemical_1960_unit` | yes | no |
| `g06_machinery_capital` | `f2_machinery_1960_unit` | yes | no |
| `g07_construction` | `f2_construction_1960_unit` | yes | no |
| `g08_agricultural_raw` | `f2_agri_raw_1960_unit` | yes | no |
| `g09_basic_food` | `f2_basic_food_1960_unit` | yes | yes |
| `g10_animal_food` | `f2_animal_food_1960_unit` | yes | yes |
| `g11_textiles_footwear` | `f2_textile_1960_unit` | yes | yes |
| `g12_household_nondurables` | `f2_nondurable_1960_unit` | yes | yes |
| `g13_household_durables` | `f2_durable_1960_unit` | yes | yes |
| `g14_vehicles_transport_equipment` | `f2_vehicle_1960_unit` | yes | yes |
| `g15_market_services` | `f2_market_service_1960_unit` | no | yes |
| `g16_housing_public_services` | `f2_public_service_1960_unit` | no | yes |

Physical metrics declare `unit = f2_v1_commodity_physical_unit`; `metric_commodity_units(mechanism, metric)`
resolves that token to one unit per commodity, and a claim naming a different commodity's unit is refused.

## 4. The 41 MetricNodes

Columns: `idx` = position in the card's `metrics` array; `verbatim metric` = the card's original string,
unmodified; `unit` = the declared unit (per-commodity token resolved in §3); `dtype`/`rows` are read from the
reference run's Parquet schema; `observed` is the per-run observability status.

### M1 → M01 (5 metrics: 5 mapped, 0 blocked)

Card: `config/p06/cards/M1.json`, SHA-256 `7a3beaa4be817cfb745a163c579b0ec472fcfb3f55c8caaca7db15854c74352d`

| idx | verbatim metric | status | table.column | unit | dtype | rows | observed |
| ---: | --- | --- | --- | --- | --- | ---: | --- |
| 0 | `household_consumption` | mapped | `national_accounts.household_consumption` — 16 commodities | `f2_v1_commodity_physical_unit` (§3) | double | 1856 | `observable` |
| 1 | `household_budgets.spending` | mapped | `household_budgets.spending` — 20 regions, sum | `M_forint` | double | 2320 | `observable` |
| 2 | `opposition_regions.weighted_grievance` | mapped | `opposition_regions.weighted_grievance` — 20 regions, mean | `dimensionless_index` | double | 0 | `table_empty` |
| 3 | `political_quarters.policy_welfare_provision` | mapped | `political_quarters.policy_welfare_provision` | `policy_scalar` | double | 0 | `table_empty` |
| 4 | `forced_saving` | mapped | `household_budgets.forced_saving` — 20 regions, sum | `M_forint` | double | 2320 | `observable` |

### M2 → M02 (4 metrics: 1 mapped, 3 blocked)

Card: `config/p06/cards/M2.json`, SHA-256 `0da621e51ad436103ec3c76d820701cda84e8bb0c9cb79ef0947337856990589`

| idx | verbatim metric | status | table.column | unit | dtype | rows | observed |
| ---: | --- | --- | --- | --- | --- | ---: | --- |
| 0 | `tick_diagnostics.bottleneck_demand_count` | mapped | `tick_diagnostics.bottleneck_demand_count` | `count` | int64 | 116 | `observable` |
| 1 | `aggregates.undelivered share` | blocked | — | — | — | — | `semantics_blocked` |
| 2 | `organization_diagnostics.credit_drawn/shortage_expectation_mean` | blocked | — | — | — | — | `semantics_blocked` |
| 3 | `commodity_circuit.stock_close` | blocked | — | — | — | — | `sidecar_absent` |

Blocking reasons:

* `aggregates.undelivered share` — declares a share but no denominator; binding it to the delivered quantity would replace the card's ratio with a level, and no weighted denominator exists in the model
* `organization_diagnostics.credit_drawn/shortage_expectation_mean` — composite of two unrelated quantities (a currency stock and a dimensionless expectation) joined by '/'; until the separator is declared to mean a ratio or a joint report, neither component may stand for the whole
* `commodity_circuit.stock_close` — no F2 run writes a commodity_circuit table or sidecar, and stage_balances.closing is not the commodity circuit's stock close

### M3 → M03 (3 metrics: 0 mapped, 3 blocked)

Card: `config/p06/cards/M3.json`, SHA-256 `06adefbd144800d1ff2afd10f5f73765f6e70339d1280ba002b434bb6e32f8ba`

| idx | verbatim metric | status | table.column | unit | dtype | rows | observed |
| ---: | --- | --- | --- | --- | --- | ---: | --- |
| 0 | `organization_diagnostics.labor_mean/wage_arrears_sum` | blocked | — | — | — | — | `semantics_blocked` |
| 1 | `national_accounts.production per worker proxy` | blocked | — | — | — | — | `semantics_blocked` |
| 2 | `aggregates.household_desired vs delivered` | blocked | — | — | — | — | `semantics_blocked` |

Blocking reasons:

* `organization_diagnostics.labor_mean/wage_arrears_sum` — composite: the card requires both the mean labour force and the wage-arrears stock; truncating it to one component loses the discipline-versus-arrears comparison the card is about, and no declared rule combines them
* `national_accounts.production per worker proxy` — per-worker productivity needs a worker denominator comparable to the physical production numerator; the card itself calls this a proxy, and no headcount is declared alongside national_accounts production
* `aggregates.household_desired vs delivered` — the comparison needs a household-specific delivered quantity, but aggregates.delivered covers every use, so pairing it with household_desired would measure non-delivery to households with deliveries to everyone else

### M4 → M04 (4 metrics: 2 mapped, 2 blocked)

Card: `config/p06/cards/M4.json`, SHA-256 `c9e70e5ca07bca8e7865f274dc052cb1ed5aed795787a9a07f16ec37fb5323ac`

| idx | verbatim metric | status | table.column | unit | dtype | rows | observed |
| ---: | --- | --- | --- | --- | --- | ---: | --- |
| 0 | `aggregates.plot_self_use/plot_market_sales` | blocked | — | — | — | — | `semantics_blocked` |
| 1 | `household_budgets.plot_income_formal/plot_income_direct` | blocked | — | — | — | — | `semantics_blocked` |
| 2 | `formal household_availability_unmet` | mapped | `aggregates.household_availability_unmet` — 16 commodities | `f2_v1_commodity_physical_unit` (§3) | double | 37120 | `observable` |
| 3 | `departments.service_use_household` | mapped | `departments.service_use_household` | `M_forint` | double | 580 | `observable` |

Blocking reasons:

* `aggregates.plot_self_use/plot_market_sales` — composite of two physical plot flows joined by '/'; both are declared components and neither may stand for the pair
* `household_budgets.plot_income_formal/plot_income_direct` — composite of two income channels joined by '/'; both are declared components and the model has no declared routing between them

### M5 → M05 (4 metrics: 1 mapped, 3 blocked)

Card: `config/p06/cards/M5.json`, SHA-256 `cdcbbfbd8d99b8b0d55f1afeaf564d2fac5cef3cd53d7058f75943af611bd879`

| idx | verbatim metric | status | table.column | unit | dtype | rows | observed |
| ---: | --- | --- | --- | --- | --- | ---: | --- |
| 0 | `organization_diagnostics.investment_approved/credit_drawn` | blocked | — | — | — | — | `semantics_blocked` |
| 1 | `national_accounts.production/used` | blocked | — | — | — | — | `semantics_blocked` |
| 2 | `tick_diagnostics.bottleneck_demand_count` | mapped | `tick_diagnostics.bottleneck_demand_count` | `count` | int64 | 116 | `observable` |
| 3 | `money_stock.money_total_close` | blocked | — | — | — | — | `sidecar_absent` |

Blocking reasons:

* `organization_diagnostics.investment_approved/credit_drawn` — composite pairing an investment approval with a credit drawdown; binding it to the credit column alone would drop the investment outcome the card's two-outcome claim needs
* `national_accounts.production/used` — composite of the physical production and use flows joined by '/'; both are declared components
* `money_stock.money_total_close` — no F2 run writes money_stock.money_total_close, and summing financial_accounts.closing over every account is not the total money stock: the account set, currency and consolidation rule are undeclared

### M6 → M06 (4 metrics: 1 mapped, 3 blocked)

Card: `config/p06/cards/M6.json`, SHA-256 `047db0a8473f326c8a6a2609bc18ea42c24cb979a96f0a20cf254575dde5e6c6`

| idx | verbatim metric | status | table.column | unit | dtype | rows | observed |
| ---: | --- | --- | --- | --- | --- | ---: | --- |
| 0 | `national_accounts.imports by channel` | blocked | — | — | — | — | `semantics_blocked` |
| 1 | `money_stock (credit/principal)` | blocked | — | — | — | — | `sidecar_absent` |
| 2 | `household_consumption` | mapped | `national_accounts.household_consumption` — 16 commodities | `f2_v1_commodity_physical_unit` (§3) | double | 1856 | `observable` |
| 3 | `treasury_cash` | blocked | — | — | — | — | `semantics_blocked` |

Blocking reasons:

* `national_accounts.imports by channel` — the card demands imports decomposed by channel; one column cannot carry the CMEA/convertible split, and substituting the total would drop exactly the channel contrast the mechanism is about
* `money_stock (credit/principal)` — names a sidecar no F2 run writes and pairs a credit flow with a principal stock; a single credit flow cannot stand for both
* `treasury_cash` — treasury cash is one account in one currency; MetricSpec carries no account_label/currency selector, so binding it to financial_accounts.closing would sum every account and currency

### M7 → M07 (2 metrics: 0 mapped, 2 blocked)

Card: `config/p06/cards/M7.json`, SHA-256 `f6383c8b16fa5f16e2517ec992da2524a2ba1eb31612ff4c542515f3d3399d90`

| idx | verbatim metric | status | table.column | unit | dtype | rows | observed |
| ---: | --- | --- | --- | --- | --- | ---: | --- |
| 0 | `aggregates and household_budgets by region_id` | blocked | — | — | — | — | `semantics_blocked` |
| 1 | `opposition_regions by region` | blocked | — | — | — | — | `semantics_blocked` |

Blocking reasons:

* `aggregates and household_budgets by region_id` — names a region-axis read over two tables with different measures and no metric column; a national scalar is not a 20-region vector, and no shared regional measure is declared
* `opposition_regions by region` — names the opposition table's region axis but no metric column, and opposition_regions carries 0 rows in a C0-style run, so an empty table would be reported as a null result

### M8 → M08 (2 metrics: 1 mapped, 1 blocked)

Card: `config/p06/cards/M8.json`, SHA-256 `f4761f7f7b3865e61d285ccdd058c91ee0cfd463964cb2b7c4b6f03e22dd0bd1`

| idx | verbatim metric | status | table.column | unit | dtype | rows | observed |
| ---: | --- | --- | --- | --- | --- | ---: | --- |
| 0 | `political_quarters mode weights and selected_candidate` | blocked | — | — | — | — | `semantics_blocked` |
| 1 | `policy_decisions.utility` | mapped | `policy_decisions.utility` | `model_utility` | double | 0 | `table_empty` |

Blocking reasons:

* `political_quarters mode weights and selected_candidate` — composite naming four coalition weights plus a selected candidate; no single column expresses which coalition won, and the table has 0 rows in a C0-style run

### M9 → M09 (3 metrics: 2 mapped, 1 blocked)

Card: `config/p06/cards/M9.json`, SHA-256 `fa1b30703cda0009471e03cdf6b88b47d20a7ce525385adfdd554f595e55273c`

| idx | verbatim metric | status | table.column | unit | dtype | rows | observed |
| ---: | --- | --- | --- | --- | --- | ---: | --- |
| 0 | `information_quarters.data_latency/measurement_error/forecast_accuracy/optimization_capacity` | blocked | — | — | — | — | `semantics_blocked` |
| 1 | `policy_decisions.binding_constraints` | mapped | `policy_decisions.binding_constraints` | `binding_constraint_label` | large_string | 0 | `table_empty` |
| 2 | `tick_diagnostics.bottleneck_demand_count` | mapped | `tick_diagnostics.bottleneck_demand_count` | `count` | int64 | 116 | `observable` |

Blocking reasons:

* `information_quarters.data_latency/measurement_error/forecast_accuracy/optimization_capacity` — composite of four information columns, and the card's forecast measure is a definition score (capability), not a realized prediction residual; without issued/realized pairs the research question is blocked rather than answered by the fourth column

### M10 → M10 (4 metrics: 0 mapped, 4 blocked)

Card: `config/p06/cards/M10.json`, SHA-256 `c23d545b59432e6f9412c512824aba5af40cc242daaa4c65239c6f4ae129b880`

| idx | verbatim metric | status | table.column | unit | dtype | rows | observed |
| ---: | --- | --- | --- | --- | --- | ---: | --- |
| 0 | `national_accounts.imports/exports by channel` | blocked | — | — | — | — | `semantics_blocked` |
| 1 | `money_stock.money_total_close` | blocked | — | — | — | — | `sidecar_absent` |
| 2 | `treasury_cash` | blocked | — | — | — | — | `semantics_blocked` |
| 3 | `later-window aggregates.household_availability_unmet` | blocked | — | — | — | — | `semantics_blocked` |

Blocking reasons:

* `national_accounts.imports/exports by channel` — names both trade directions and both channels; four columns cannot be represented by one, and dropping the channel split removes the transmission the external-shock card measures
* `money_stock.money_total_close` — no F2 run writes money_stock.money_total_close; the total money stock cannot be reconstructed from financial_accounts.closing without a declared account/currency consolidation rule
* `treasury_cash` — treasury cash is one account in one currency and MetricSpec has no account_label/currency selector; the account is unknown, so it is not guessed
* `later-window aggregates.household_availability_unmet` — the card requires a later window that was never pre-registered; choosing one after seeing the outcome would be an ex-post window

### M11 → M11 (6 metrics: 1 mapped, 5 blocked)

Card: `config/p06/cards/M11.json`, SHA-256 `c65318dc1d4c149d7d15b49db229c19768a282f5e6c59307197fe194d1c86887`

| idx | verbatim metric | status | table.column | unit | dtype | rows | observed |
| ---: | --- | --- | --- | --- | --- | ---: | --- |
| 0 | `aggregate consumer-goods volume (national_accounts.household_consumption)` | mapped | `national_accounts.household_consumption` — 16 commodities | `f2_v1_commodity_physical_unit` (§3) | double | 1856 | `observable` |
| 1 | `assortment/availability (aggregates.household_availability_unmet, tick_diagnostics.bottleneck_demand_count)` | blocked | — | — | — | — | `semantics_blocked` |
| 2 | `regional distribution (by region_id)` | blocked | — | — | — | — | `semantics_blocked` |
| 3 | `durable waiting (aggregates.household_desired vs delivered for g13_household_durables)` | blocked | — | — | — | — | `semantics_blocked` |
| 4 | `household welfare loss (household_budgets saving/substitution columns)` | blocked | — | — | — | — | `semantics_blocked` |
| 5 | `departments.actual_use_value split by department` | blocked | — | — | — | — | `semantics_blocked` |

Blocking reasons:

* `assortment/availability (aggregates.household_availability_unmet, tick_diagnostics.bottleneck_demand_count)` — composite pairing a physical unmet quantity with a bottleneck cell count; the two have different units and no declared combination rule
* `regional distribution (by region_id)` — names a region axis but no measure; a regional distribution needs a declared allocation vector, and the model exposes no regional budget or regional delivery vector to read
* `durable waiting (aggregates.household_desired vs delivered for g13_household_durables)` — durable waiting needs a household-specific delivered series for g13; aggregates.delivered covers every use, so the waiting gap would be overstated
* `household welfare loss (household_budgets saving/substitution columns)` — names a column group ('saving/substitution') with no single column, and the model has no substitution column to read; the saving columns alone measure saving, not welfare loss
* `departments.actual_use_value split by department` — requires a department split, but MetricSpec carries no department axis; one row per department cannot be bound to a single column without silently choosing a department

## 5. Composite components (evidence that each composite was read in full)

A composite card metric stays blocked; listing its components is evidence that none of its parts was
silently substituted for the whole.

| card#idx | component | unit | dtype | note |
| --- | --- | --- | --- | --- |
| `M2#1` | `aggregates.desired` | `f2_v1_commodity_physical_unit` | double |  |
| `M2#1` | `aggregates.delivered` | `f2_v1_commodity_physical_unit` | double |  |
| `M2#2` | `organization_diagnostics.credit_drawn` | `M_forint` | double | credit drawn over the quarter, M_forint |
| `M2#2` | `organization_diagnostics.shortage_expectation_mean` | `dimensionless_ratio` | double | mean shortage expectation per organization |
| `M2#3` | `stage_balances.closing` | `f2_v1_commodity_physical_unit` | double | per-stage closing stock: a different quantity from the circuit's stock close |
| `M3#0` | `organization_diagnostics.labor_mean` | `persons` | double | mean available organization labour |
| `M3#0` | `organization_diagnostics.wage_arrears_sum` | `M_forint` | double | outstanding wage arrears, model currency |
| `M3#1` | `national_accounts.production` | `f2_v1_commodity_physical_unit` | double | physical production per commodity |
| `M3#1` | `organization_diagnostics.labor_mean` | `persons` | double | labour is per region x organization type, not national |
| `M3#2` | `aggregates.household_desired` | `f2_v1_commodity_physical_unit` | double |  |
| `M3#2` | `aggregates.delivered` | `f2_v1_commodity_physical_unit` | double | all-use deliveries, not a household counterpart |
| `M3#2` | `aggregates.household_availability_unmet` | `f2_v1_commodity_physical_unit` | double | the household-specific unmet quantity that does exist |
| `M4#0` | `aggregates.plot_self_use` | `f2_v1_commodity_physical_unit` | double |  |
| `M4#0` | `aggregates.plot_market_sales` | `f2_v1_commodity_physical_unit` | double |  |
| `M4#1` | `household_budgets.plot_income_formal` | `M_forint` | double |  |
| `M4#1` | `household_budgets.plot_income_direct` | `M_forint` | double |  |
| `M5#0` | `organization_diagnostics.investment_approved` | `M_forint` | double |  |
| `M5#0` | `organization_diagnostics.credit_drawn` | `M_forint` | double |  |
| `M5#1` | `national_accounts.production` | `f2_v1_commodity_physical_unit` | double |  |
| `M5#1` | `national_accounts.used` | `f2_v1_commodity_physical_unit` | double |  |
| `M5#3` | `financial_accounts.closing` | `M_forint` | double | per-account closing balance, not a money aggregate |
| `M6#0` | `national_accounts.cmea_imports` | `f2_v1_commodity_physical_unit` | double |  |
| `M6#0` | `national_accounts.convertible_imports` | `f2_v1_commodity_physical_unit` | double |  |
| `M6#0` | `national_accounts.imports` | `f2_v1_commodity_physical_unit` | double |  |
| `M6#1` | `financial_accounts.credit_drawn` | `M_forint` | double | per-account credit flow, not a principal stock |
| `M6#1` | `organization_diagnostics.principal_sum` | `M_forint` | double | enterprise principal stock, no historical counterpart |
| `M6#3` | `financial_accounts.closing` | `M_forint` | double | requires account_label + currency selectors |
| `M7#0` | `aggregates.(axis only)` | `—` | — | region_id axis only; no column named by the card |
| `M7#0` | `household_budgets.(axis only)` | `—` | — | region_id axis only; no column named by the card |
| `M7#1` | `opposition_regions.(axis only)` | `—` | — | region_id axis only; table is empty in C0 |
| `M8#0` | `political_quarters.weight_reform_technocratic` | `policy_scalar` | double |  |
| `M8#0` | `political_quarters.weight_administrative_conservative` | `policy_scalar` | double |  |
| `M8#0` | `political_quarters.weight_social_contract_pragmatist` | `policy_scalar` | double |  |
| `M8#0` | `political_quarters.weight_sectoral_industrial` | `policy_scalar` | double |  |
| `M8#0` | `political_quarters.selected_candidate` | `binding_constraint_label` | large_string | string label of the winning candidate |
| `M9#0` | `information_quarters.data_latency` | `dimensionless_ratio` | double |  |
| `M9#0` | `information_quarters.measurement_error` | `dimensionless_ratio` | double |  |
| `M9#0` | `information_quarters.forecast_accuracy` | `dimensionless_ratio` | double | defined as capability in the engine: not a real forecast error |
| `M9#0` | `information_quarters.optimization_capacity` | `dimensionless_ratio` | double |  |
| `M10#0` | `national_accounts.cmea_imports` | `f2_v1_commodity_physical_unit` | double |  |
| `M10#0` | `national_accounts.convertible_imports` | `f2_v1_commodity_physical_unit` | double |  |
| `M10#0` | `national_accounts.imports` | `f2_v1_commodity_physical_unit` | double |  |
| `M10#0` | `national_accounts.cmea_exports` | `f2_v1_commodity_physical_unit` | double |  |
| `M10#0` | `national_accounts.convertible_exports` | `f2_v1_commodity_physical_unit` | double |  |
| `M10#0` | `national_accounts.exports` | `f2_v1_commodity_physical_unit` | double |  |
| `M10#1` | `financial_accounts.closing` | `M_forint` | double | per-account closing balance |
| `M10#2` | `financial_accounts.closing` | `M_forint` | double | requires account_label + currency selectors |
| `M10#3` | `aggregates.household_availability_unmet` | `f2_v1_commodity_physical_unit` | double | the quantity itself is declared; only the window is not |
| `M11#1` | `aggregates.household_availability_unmet` | `f2_v1_commodity_physical_unit` | double |  |
| `M11#1` | `tick_diagnostics.bottleneck_demand_count` | `count` | int64 |  |
| `M11#2` | `aggregates.(axis only)` | `—` | — | region_id axis only; no measure named by the card |
| `M11#3` | `aggregates.household_desired` | `f2_v1_commodity_physical_unit` | double | restricted to g13_household_durables |
| `M11#3` | `aggregates.delivered` | `f2_v1_commodity_physical_unit` | double | all-use deliveries for g13, not household-specific |
| `M11#4` | `household_budgets.voluntary_saving` | `M_forint` | double |  |
| `M11#4` | `household_budgets.forced_saving` | `M_forint` | double |  |
| `M11#5` | `departments.actual_use_value` | `M_forint` | double | requires a department selector |

## 6. Research status

All 11 records keep their intent and their declared source hash; none is complete, none is
historically identified, and the two P07 'prior identified' assertions are revoked in the overlay.
The priors those assertions named (`p04_coalition_prior`, `p04_observation_prior`,
`p04_information_prior`) are themselves **UNIDENTIFIED** model parameters: `config/calibration/p05.json`
records the six P04 behavioural blocks as UNIDENTIFIED and *prior-constrained* — no declared observable
constrains them — and lists them only as a declaration's `calibrated_parameter_dependencies`. A
declaration may call its *design* `declared`; it may not call its *priors* identified.

| study | intent | legacy status | metrics mapped/blocked | structural | historical identification | complete |
| --- | --- | --- | --- | --- | --- | :---: |
| M01 | `social_contract_ratchet_verification` | declared | 5/0 | NOT_RUN | UNIDENTIFIED | false |
| M02 | `soft_budget_investment_shortage` | blocked | 1/3 | NOT_RUN | UNIDENTIFIED | false |
| M03 | `full_employment_labor_hoarding` | blocked | 0/3 | NOT_RUN | UNIDENTIFIED | false |
| M04 | `second_economy_stabilization_erosion` | blocked | 2/2 | NOT_RUN | UNIDENTIFIED | false |
| M05 | `enterprise_autonomy_1968` | declared | 1/3 | NOT_RUN | UNIDENTIFIED | false |
| M06 | `external_debt_social_contract` | blocked | 1/3 | NOT_RUN | UNIDENTIFIED | false |
| M07 | `regional_distribution_stability` | blocked | 0/2 | NOT_RUN | UNIDENTIFIED | false |
| M08 | `political_coalition_crisis` | declared | 1/1 | NOT_RUN | UNIDENTIFIED | false |
| M09 | `information_optimization_failure` | blocked | 2/1 | NOT_RUN | UNIDENTIFIED | false |
| M10 | `external_buffer_shock_transmission` | blocked | 0/4 | NOT_RUN | UNIDENTIFIED | false |
| M11 | `departmental_i_ii_composition` | blocked | 1/5 | NOT_RUN | UNIDENTIFIED | false |

Revocations:

* **M01** — source `studies/M01/study_decl.json#declared_reason` said: "p04_coalition_prior and p04_observation_prior are identified; ratchet metric already wired via household_welfare adaptive expectations; paired checkpoint design ready"
  * revoked 2026-10-16 by H0B: the referenced priors identify nothing. `config/calibration/p05.json` records `p04_coalition_prior` and `p04_observation_prior` as UNIDENTIFIED and prior-constrained (no declared observable constrains them), so they are not identification of the historical ratchet mechanism. 05 §6 separates the technical, structural and historical verdicts, and the historical verdict here is UNIDENTIFIED until a matched-reference first-stage and a political response measure are admitted.
* **M05** — source `studies/M05/study_decl.json#declared_reason` said: "p04_coalition_prior and p04_information_prior are identified; PoliticalSession→policy→material targets path exists; autonomy×hardness 2×2 design available"
  * revoked 2026-10-16 by H0B: the referenced priors identify nothing. `config/calibration/p05.json` records `p04_coalition_prior` and `p04_information_prior` as UNIDENTIFIED and prior-constrained (no declared observable constrains them), and an existing PoliticalSession→policy→material path is an implementation fact; neither identifies the historical 1968 autonomy mechanism. The declaration stays, the historical claim is withdrawn.

## 7. Residual conflicts and open items

1. **Revoked pre-H0B unit claims.** `P07A2_HISTORICAL_PAIR_UNITS` keeps three `(table, column)` claims
   (`aggregates.delivered` = `M_forint`/`share (0-1)`; `national_accounts.household_consumption` =
   `M_forint`/`M_forint (model currency)`; `financial_accounts.closing` = `M_forint`) as a **revoked
   record**: 05 §1.1 forbids silently rewriting past declarations, so they stay on disk, but they are
   **not** merged into the live accepted-unit set that the H0A unit gate binds to.
   * A physical pair (`aggregates.delivered`, `national_accounts.household_consumption`) is denominated
     only in `f2_v1_commodity_physical_unit`; the model-currency/share claims are refused, so a physical
     quantity can no longer be restated in money. `hsm_lab.evidence.table_registry.
     validate_physical_unit_claims` fails closed if a physical pair ever accepts both.
   * `financial_accounts.closing` is *not* a physical pair: it is a currency column, and `M_forint` is its
     live declaration, so the historical claim coincides with it rather than being revoked.
   * `aggregates.delivered` → `M_forint`, `share (0-1)` (revoked)
   * `financial_accounts.closing` → `M_forint` (coincides with the live currency declaration)
   * `national_accounts.household_consumption` → `M_forint`, `M_forint (model currency)` (revoked)
2. **`information_quarters.forecast_accuracy` is a capability definition**, not a realized prediction
   error; M9 stays blocked until issued/realized pairs exist.
3. **No department/account/currency selector axis exists in `MetricSpec`**, so
   `departments.actual_use_value split by department` and `treasury_cash` cannot be bound without
   silently summing or choosing; both stay blocked.
4. **`commodity_circuit` and `money_stock` have no producer.**
5. **Empty is not zero.** 4 of the 41 registrations read a 0-row table (`table_empty`); they are reported
   as unobservable, never as 0.

## 8. Verification ledger

| assertion | level |
| --- | --- |
| 11/11 cards read with frozen SHA-256 and 41/41 metrics registered | VERIFIED_BY_CODE |
| 14/14 registry column lists equal the writer's own `*_COLUMNS` | VERIFIED_BY_CODE |
| 16/16 commodity units equal the read-only ontology | VERIFIED_BY_CODE |
| dtypes, row counts and observability statuses | VERIFIED_BY_RUN (reference run C0-r1) |
| structural results | NOT_RUN |
| historical identification | UNIDENTIFIED |
