# H3A Report — service capability, schedule, provision, use and loss

## Authorization and scope
User authorized H3A coding, independent review, repair and commit on 2026-10-18.
The phase remains observation-only: `measure_service_tick` is never imported or
called by the default runner, and no engine, storage, CLI, catalog, scenario,
`BASELINE.md`, research-contract or lockfile byte changed.

The formal budget fields in `H3A_服务语义分型_PLAN.md` were not supplied as
phase values (`max_wall_s`, `max_rss_bytes`, `max_new_output_bytes`,
`max_run_count`, model tokens, paid-cost cap, reasoning effort all `NOT_SET`).
No paid model call was made. The main session ran the implementation and local
kernel; the independent review was the repository `phase-reviewer` subagent.
This report does not invent token, cost or RSS readings.

## Implemented
Added only:
- `src/hsm_lab/measurement/service_semantics.py`
- `tests/test_hist_service_semantics.py`
- `config/ontology/hist_service_semantics_v1.json`
- `docs/phases/HIST_VNEXT/H3A/{PLAN,REPORT,REVIEW}.md`

The measurement returns frozen dataclasses:
`ServiceCommodityMeasurement`, `ServiceInputUse`, `HousingStockMeasurement`,
`ServiceTickMeasurement` (`schema_version="hist-service-metrics-v1"`,
`ontology_id="hist-service-semantics-v1"`). The service selection is
`commodity_spec(cid).stockable == False` in network commodity order. `lost` is
the gate's `expired_leftover_by_cell` only. The legacy
`flows.expired_services` scalar is reported unchanged as
`legacy_expired_services`.

## Independent review round 1 → PATCH → repairs
The `phase-reviewer` subagent returned **PATCH** with three findings:

| Finding | Repair |
|---|---|
| `network.A.sort_indices()` / `network.B.sort_indices()` mutated caller-owned sparse matrices | removed both in-place sorts; added `test_service_measurement_does_not_sort_network_matrices` over deliberately unsorted F2 matrices |
| only an all-cells-missing network was rejected; one declared service with no cells could produce a fake zero row | reject **each** declared non-stockable commodity with no stock cell; added `test_service_measurement_rejects_partial_missing_service_cells` |
| evidence lacked REPORT, raw gate sink, household observations and hash manifests | added REPORT, raw per-cell `expired_leftover_by_cell`, weighted household realized/unmet by commodity, input/output hash files and `manifest.json` under `outputs/hist-vnext-h3a-20261018/` |

The reviewer's round-1 reproduction (reversed A/B row → measurement re-sorted it)
now fails to reproduce: the matrices remain byte-identical.

## Verification (final bytes)
All commands ran from the repository root.

| Check | Command | Result |
|---|---|---|
| new tests | `pytest -q tests/test_hist_service_semantics.py` | **9 passed** |
| focused regression | new + `test_material`, `test_hist_tiny_execution`, `test_f2_retail_replenishment`, `test_households`, `test_historical_p05` | **79 passed** |
| full suite | `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider` | **1109 passed, 180 warnings** |
| lint | `ruff check --no-cache src tests` | **all checks passed** |
| lock | `uv lock --check --offline` | **resolved 101 packages** |
| baseline | `hsm baseline verify --json` | **ok**, SHA-256 `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` |
| C0 | `hsm run --scenario historical_f2_replay` | digest `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`, 116 ticks, 1985Q4 |
| C1 | `hsm run --scenario historical_f2_trade_scenario` | digest `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`, 116 ticks, 1985Q4 |
| replay identity | `verify_run_identity` on the fresh C0/C1 directories | both passed |

C0/C1 scenario, parameter, lock and initial-recipe hashes match the frozen
values in the H3A plan:
- C0 `a1881537…`, parameter `e27ade6a…`
- C1 `a8c70922…`, parameter `632ee6a6…`
- lock `9fd79b62…`, recipe `10655b07…`

## Control-arm evidence (`--mode reproduce`)
Deterministic seed 1729, capability 5, same demand/cash/capacity. Scheduled /
provided / logistics / lost / seller→hub delivery:

| Arm | scheduled | provided | logistics | lost | delivery |
|---|---:|---:|---:|---:|---:|
| legacy local | 5 | 5 | 3 | 2 | 10 |
| central 3, autonomy 0 | 3 | 3 | 3 | 0 | 10 |
| central 0, autonomy 0 | 0 | 0 | 0 | 0 | 0 |
| central 3, autonomy 1 | 5 | 5 | 3 | 2 | 10 |

`target=0` produces zero loss because it schedules and provides nothing; it is
not an improvement. `autonomy=1` legitimately ignores central 3.

## Real fuel-input evidence
Same fixture, hauler technology `energy → services_transport` (coefficient 1),
opening energy 5. Opening + delivered − used = closing:

| Arm | fuel used | fuel closing | provided | logistics | lost | delivery |
|---|---:|---:|---:|---:|---:|---:|
| legacy | 5 | 0 | 5 | 3 | 2 | 10 |
| target 3 | 3 | 2 | 3 | 3 | 0 | 10 |
| target 0 | 0 | 5 | 0 | 0 | 0 | 0 |

The unused-service case leaves the fuel in stock; the service balance closes per
commodity and the input row keeps `p02_energy_unit`.

## 4Q → 16Q observation
`run_h3a.py --mode smoke` rebuilds two independent F2 trajectories from
`historical_f2_replay` (seed override in memory), gates every tick, measures the
observed arm before the clock advance, and compares canonical bytes. Seeds
`1729, 1730, 1731` completed 4Q and then 16Q; every tick reported
`control_observed_bytes_identical=true`. The 16Q runs end at 1960Q4 with finite
gate ratios. Evidence:
`outputs/hist-vnext-h3a-20261018/final/{reproduce,smoke4-*,smoke16-*}`.

The measured F2 service rows are `g03_electricity_heat`,
`g15_market_services`, `g16_housing_public_services`. Each keeps its declared
unit; no cross-commodity sum is formed. `g16` remains
`f2_public_service_1960_unit`; dwelling stock is reported only in the separate
housing axis. Large service expiry in 1957Q1 is reported as measured legacy
behaviour, not as an improvement or a historical conclusion.

## Verdicts
- **technical: PASS** — all final tests, lint, lock, baseline, C0/C1 replay
  identity and read-only checks passed on the final bytes.
- **structural: PASS for the implemented observation contract** — capability,
  schedule, provision, four use channels, gate-authoritative loss and the
  independent housing stock are separated and conserved in the exercised
  fixtures and the F2 smoke.
- **historical: UNIDENTIFIED / NOT_RUN** — no new historical source was
  admitted, no target was opened, and synthetic technical measurements are not
  historical support.

## Known limits
- `measure_service_tick` is default-off and not wired into the runner; H3A
  delivers the observation API and evidence, not a new service engine.
- No demand scheduler, LP, LLM actor, storage schema, target access, source
  download or H3B work was added.
- Formal resource budgets and model token/cost/RSS readings remain `NOT_SET`;
  `resource-usage.json` records that fact rather than a fabricated value.
- The F2 smoke is a structural/technical observation, not a calibrated
  historical result.
