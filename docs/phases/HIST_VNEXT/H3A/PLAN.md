# HIST_VNEXT H3A — service capability, schedule, provision, use and loss

## Status
Coding and commit authorized by the user on 2026-10-18. The executable
specification remains the root file `H3A_服务语义分型_PLAN.md`; this phase copy
records the exact implemented boundary and the acceptance mapping.

## Prerequisite
- H2B `REVIEW.md` final verdict: **PASS** (independent read-only re-audit).
- H3A is an observation-only layer. It does not change the legacy material,
  finance, household or expiry behaviour and is never called by the default
  runner.

## Write boundary (exact)
Added:
- `src/hsm_lab/measurement/service_semantics.py`
- `tests/test_hist_service_semantics.py`
- `config/ontology/hist_service_semantics_v1.json`
- `docs/phases/HIST_VNEXT/H3A/{PLAN,REPORT,REVIEW}.md`

Not modified:
- `src/hsm_lab/engine/{material,policy,state,accounting,initial,network,household_*}.py`
- `src/hsm_lab/storage/**`, CLI, frozen catalogs, scenarios, `BASELINE.md`,
  research contract, `uv.lock`, mechanism cards, priors, sources.
- No engine hook was added: the opening snapshot, closing state, tick flows and
  `InvariantSummary.expired_leftover_by_cell` are sufficient for a read-only
  measurement.

## Measurement contract
`measure_service_tick(opening, state, flows, network, invariant_summary)` returns
frozen dataclasses:

- `ServiceCommodityMeasurement`: `capacity`, `scheduled`, `provided`,
  `unscheduled_capacity`, `schedule_shortfall`, `opening`, `imports`,
  `used_productive`, `used_logistics`, `used_household`, `used_other`,
  `exports`, `lost`, `closing`, `balance_residual`.
- `ServiceInputUse`: one row per `K` input of every service-producing activity.
- `HousingStockMeasurement`: regional dwelling stock plus formal/private
  completion and allocation.
- `ServiceTickMeasurement`: `schema_version="hist-service-metrics-v1"`,
  `ontology_id="hist-service-semantics-v1"`, tick, quarter, the three tuples and
  the unchanged `legacy_expired_services` scalar.

Selection is `commodity_spec(cid).stockable == False` in network commodity-axis
order. `capacity` uses opening organization capacity (plot activities keep the
network capacity); `scheduled`/`provided` are `B.T @ target` and
`B.T @ realized`. `lost` is only the gate's per-cell expiry sink. The balance
identity is per commodity and every legacy expiry scalar remains reported
unchanged.

## Acceptance mapping
| Requirement | Evidence |
|---|---|
| target=3 binds, target=0 supplies nothing, autonomy=1 is legitimately nonbinding | `test_service_target_controls_real_provision` |
| real fuel input is consumed only as the service is realised; unused service leaves fuel in stock | `test_fuel_consumption_survives_unused_service` |
| housing is an independent dwelling stock, not a quarterly service | `test_housing_stock_is_not_quarterly_public_service` |
| read-only byte identity and no ndarray aliases | `test_service_measurement_preserves_kernel_bytes` |
| clock/shape/non-finite/negative/forged-loss/failed-gate rejection | `test_service_measurement_rejects_unreconciled_boundary` |
| same-quarter pool draw not double counted, gross provision not netted | `test_service_input_pool_is_not_double_counted` |
| no non-stockable service means an empty tuple, not a fake zero row | `test_no_nonstockable_services_has_no_fake_zero_row` |
| 4Q then 16Q, three seeds, control/observed byte identity | `outputs/hist-vnext-h3a-20261018/smoke{4,16}-<seed>` |

## Non-goals
No demand scheduler, target rule, LP, LLM actor, service rewrite, storage schema,
historical source download, target access, historical support claim, or H3B
work. Historical verdict remains `UNIDENTIFIED/NOT_RUN`.
