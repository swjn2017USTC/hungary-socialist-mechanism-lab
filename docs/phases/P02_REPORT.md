# P02 Report — Material Economy Expansion

Date: 2026-10-08 · Plan: `MATERIAL_ECONOMY_EXPANSION_PLAN.md` · Baseline:
`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` (unchanged, verified)

## What was built

An Intermediate-8 material economy (1957Q1–1985Q4, 116 ticks, 20 contract
regions, 5,000 default households, 200 default organizations) with an explicit
heterogeneous organization layer, endogenous agriculture and distribution, a
closed credit/wage/bailout ledger, sparse `A`/`B` production matrices, per-cell
accounting invariants, deterministic replay digests, pause/resume checkpoints,
compact Parquet/DuckDB output, and a same-path benchmark. Every synthetic
organization count, technology coefficient, price and mechanism parameter is a
structural assumption — not a historical estimate and not evidence for any
mechanism theory.

New modules:

| Module | Content |
|---|---|
| `contract/base.py` | shared strict-model primitives (breaks the schemas↔material import cycle) |
| `contract/material.py` | Intermediate-8 commodity/unit registry, `OrganizationType` (8 types), `OrganizationSpec`, `TechnologySpec`, `MaterialRouteSpec`, `OrganizationRecipe`, `PrivatePlotRecipe`, `MaterialParameters`, `TradeParameters`, `MaterialInitialRecipe`, `ForcingBinding`, `MaterialInitialConditions` |
| `engine/initial.py` | `build_material_initial_conditions` — one seed draw of households, canonical organization ids/capacities/labor/handling, plot cohort |
| `engine/network.py` | `MaterialNetwork` stock-cell catalog, `compile_material_network`, default nearest-neighbour route graph, `produce_leontief` (sparse segmented minimum) |
| `engine/state.py` | `MaterialState`/`MaterialForcing`/`MaterialTickFlows`/`MaterialHistory`/`MaterialPrices`/`MaterialStockSnapshot`, `initialize_material`, `capture_material_stocks` |
| `engine/material.py` | `tick_material` (10-step pinned quarter sequence), `run_material`, canonical digests, `--until`/`--checkpoint-every`/`--resume` |
| `engine/finance.py` | closed-ledger working capital, wages, interest, principal, bailout, rolling one-project-per-org investment, paired Journal |
| `engine/trade.py` | USD debt service, channel-separated (CMEA/convertible) imports, export boundary demands, closing settlement, official-FX diagnostic |
| `engine/accounting.py` | 72-ledger `check_material_invariants`, per-cell stock continuity, `derive_departments` (I/II/service/exports/unclassified) |
| `data/ingestion.py`, `data/adapters.py` | rights-gated download/cache, immutable raw store with retrieval metadata, five strict parsers plus the FRED gated adapter |
| `data/material.py` | synthetic fixture + forcing packs, external forcing pack composition, `load_material_forcing`, `load_material_targets`, `compare_annual` |
| `storage/material_output.py` | nine compact tables (Parquet + DuckDB) |
| `storage/checkpoint.py` | `material-checkpoint-v1` atomic save + strict resume gates |
| `cli/app.py`, `benchmarks/harness.py` | material run/summary, `data ingest`, `data build-material-forcing`, `benchmark material` |

Commodity axis: `energy`, `capital_goods`, `food`, `consumer_goods`,
`raw_materials`, `construction`, `durable_goods`, `services_transport`
(engineering units `p02_*_unit`). `food` is the only staged commodity
(`raw`/`ready`); `services_transport` is non-stockable. Banks hold no material
stock cell and produce no physical output. Housing completion increases
dwelling stock only. No ninth "agricultural commodity" and no `goods` scalar
exist (`FORBIDDEN_COMMODITY_IDS` still rejects it). Organization types:
`industrial_soe`, `agricultural_cooperative`, `state_farm`, `construction`,
`transport`, `wholesale_procurement`, `retail`, `bank`.

Old Toy-4 economy API, configs, fixtures, checkpoint format and `test_toy4.py`
are deleted (clean cutover); the P00 smoke workload is unchanged.

## Verification evidence

### Test suite, lint, types

`uv run pytest -q` → **257 passed**. `uv run ruff check .` → **clean**.
`uv run mypy src/hsm_lab` → **Success: no issues found in 37 source files**.
`uv run hsm baseline verify --json` → `sha256 == expected_sha256`
(`1f5b233f…6b6f`).

Permanent regression coverage (`tests/test_material.py`,
`test_material_network.py`, `test_material_finance.py`, `test_checkpoint.py`,
`test_ingestion.py`): the five user-required bottleneck fixtures (energy with
opening-stock lag; raw-material bottleneck independent of energy; food
processing + distribution delay; transport reservation never delivers or
charges; regional shortage with national surplus) plus over-order/hoarding
toggles, credit/grant/debt/wage closure, plot raw/ready/self-use/direct market,
foreign-channel rates and official-FX isolation, services expiry and
completed-stock non-food behaviour, Department I/II investment valuation,
disconnected-investment backlog, network invariants (≤2 suppliers, weights sum
to 1, canonical edge order, free same-region edges, no bank cells, stage
immutability), checkpoint refusal/roundtrip, and the KSH-outcome-cannot-be-bound
guard.

Hand-checked plan §8 cases exercised end-to-end on real kernels: 1–6, 7
(investment priority + Department I valuation), 8 (loan 6 / grant 4 / wage 10 /
interest 0.06 accrual), 10 (plot), 11 (CMEA vs convertible, FX diagnostic,
external rates), 12 (services expiry, housing/durable stock, bank no-goods).

### Real default run (frozen code)

`uv run hsm run --scenario intermediate8 --output-dir outputs/p02-default --json`
(5,000 households / 200 organizations / seed 1729 declared by the scenario)
→ status ok, 116 ticks, last 1985Q4, `run_kind=intermediate8_material_simulation`,
digest `cbb42e5a17999ce8451c82230ee0f48e3e71f95b45201903a2f01e65204eca03`.

- Re-run into a second directory with identical inputs → same digest
  `cbb42e5a…`; pause/resume equivalence is pinned by
  `test_run_material_pause_then_resume_matches_uninterrupted` and
  `test_resume_refuses_a_terminal_checkpoint` (both passing).
- Every table row-count equals the pinned grid: `aggregates` 18560,
  `stage_balances` 21924 (21×9 per tick), `national_accounts` 928,
  `household_budgets` 2320, `organization_diagnostics` 18560,
  `financial_accounts` 464, `departments` 580, `tick_diagnostics` 116,
  `events` 116; Parquet and DuckDB contents agree.
- Invariant maxima over the 116 admitted ticks: material tolerance ratio
  `2.728e-03`, finance tolerance ratio `2.354e-04` (both ≤ 1), max absolute
  material residual `7.276e-12`, max absolute finance residual `8.848e-08`;
  `parameter_hash=a6aa7ca637f0525f3da950a1c085f57a3da11d76361f2f67224bf398cdc553e3`,
  `initial_recipe_hash=5a893a75f2637113bbc2b8d51b4eec7a6a854def310010135a1cea525ac7e465`.
- Shortage mechanism diagnostics are active, not synthesised: 18,593 bottleneck
  demand events and 71.7 units of financial delivery blocking across the run;
  all `departments` attribution rows are finite.
- No politics, LLM or social-attitude fields exist in state, and the summary
  carries `assessment_status="not_assessed"` mechanism diagnostics only.

### External forcing run

`uv run hsm data build-material-forcing --profile external` then
`uv run hsm run --scenario intermediate8_external --output-dir outputs/p02-external --json`
→ status ok, 116 ticks, digest
`5a199187ae26ed128de34e50e982ab3bc8ee2df242a650a8dbfdbefe7815bbb2`. The
synthetic pack rebuilds byte-identically (`raw_sha256 = 92d143a7…5de7b`).

### Real data ingestion (download → hash-cache → parse → derive → admission)

| Source | Result | Raw SHA-256 |
|---|---|---|
| `ksh_gdp` | 9 target artifacts (3 vars × 3 splits), 1960–1985 | `ecd87575…61a16` |
| `ksh_industry` | 18 target artifacts (6 series × 3 splits) | `a450b2b9…b83b39b` |
| `ksh_agriculture_b` | 9 target artifacts (3 series × 3 splits) | `2cf17d5b…f9722e528` |
| `ksh_trade` | 6 target artifacts (2 series × 3 splits) | `04dd2c60…76eb1617` |
| `worldbank_pink_sheet` | 1 forcing artifact, 312 monthly | `bd89b83e…000c7e11` |
| `federalreserve_h15` | 1 forcing artifact, 348 monthly | `dbdfd78e…5c4bdc34a0` |
| `mnb_official_fx` | 1 dated forcing artifact, 244 quotes (1985) | `85ad1967…095931b50` |
| `fred_fedfunds` | rights-blocked, exit 1, zero network calls | — |

Spot values match the audited sources: WB oil `1960-01 = 1.63000011444`,
Fed 1957Q1 quarterly mean `2.9333333333333336`, MNB `1985-01-03 = 51.30` and
`1985-03-30 = 50.88`, KSH electricity 1960 `7617 million_kWh`, cereals 1960
`6960 thousand_tonnes`, trade import index 1960 `100`. Cache reuse is
SHA-256-verified (`--offline` re-run reports `cache_hit=true`,
`downloaded=false`, same artifact ids). Derived CMEA energy price covers
exactly 1975Q1–1985Q4 (artifact sha `19c9b487…e5ed48`); 1957–1959 oil is a
labelled structural warm-up, never observed.

### Acceptance gates exercised

Reserved-window refusal (`1985Q1..1986Q4` and a 1986Q1 start both raise
`ConfigError`); `--scenario toy4` exits 2; annual targets cannot claim quarterly
observation; target role cannot be bound as forcing; parser header/unit drift,
missing years, HTTP error pages, DOCTYPE/entity XML and corrupt hashes fail
closed; `--offline` miss exits 1; `--offline --refresh` exits 2.

### Material benchmark (`config/benchmarks/material.json`, 13 cases, isolated workers)

`uv run hsm benchmark material --output-dir outputs/p02-benchmark --json` →
`status=ok`, `overall_gate=pass`, 13 cases, single-threaded worker
(`OMP/MKL/OPENBLAS/VECLIB/NUMEXPR/POLARS/duckdb` threads pinned to 1).
F1 (5,000 households / 200 organizations / 116 ticks, no checkpoints): median
worker wall **5.906 s**, peak RSS **0.413 GB**. Checkpoint case
(`checkpoint_every=20`): **6.382 s**, ratio vs F1 **1.081**, **9.21 MB** per
checkpoint. Max peak RSS across all cases **0.440 GB** (≤ 16 GB normal gate).
Scaling medians (households 2,500→5,000→10,000 at O=200; organizations
200→400 at N=5,000): **1.128 / 1.605 / 1.159** (≤ 3.5 threshold). Every case
passes `digest_stable`, `invariants_ok`, `peak_rss_ok` (long cases also
`wall_s_ok`); each case's protected dimensions (`S,K,D,M,P`) and
`effective_scalar_updates` are recorded in the report JSON. The kernel builds
the CSR network once and never loops per organization or per edge per tick
(only fixed 8-commodity/3-purpose/≤2-bank loops).

## Defects found and fixed during P02 hardening

All three were caught by the pinned invariants or by the checkpoint load gate,
not by inspection; each fix is covered by the permanent suite.

1. **Cash- and clearing-limited deliveries were charged at the pre-rationing
   quantity** (`engine/material.py`, delivery step). Freight and goods charges
   were computed from `candidate = allocated × phys_factor` while the delivered
   quantity was `candidate × fin_factor` (the buyer's cash and interbank
   clearing factors). A cash-limited buyer therefore paid for goods it never
   received. Symptom: the organization deposit book went below zero (17
   overdrawn organizations at tick 2 of the 1,000-household profile), after
   which `wage_pay = min(cash, wage_arrears)` in the bailout step became
   *negative* and the M2 identity broke by 36.2956 units at tick 2. Fix: charge
   `delivered_edges`, so the clearing factor scales the goods value and the
   freight fee together with the delivery and no buyer can overdraw. Evidence:
   the M2 identity closes over all 116 ticks (max finance residual `8.848e-08`)
   and no organization holds negative cash.
2. **Plot-food stock retained machine-epsilon dust, which poisoned the
   Department attribution** (`engine/material.py` self-use decrement,
   `engine/accounting.py` share normalisation). The plot self-use cell was
   decremented by a draw that nearly equalled its stock, leaving a residual of
   ~`1e-16` of the previous value and decaying geometrically each quarter
   (`2.6e-287 → 2.9e-303 → 3.2e-319`). The residual became subnormal, and
   `share = 1.0 / total_out` then overflowed to `inf`, making
   `attributed_output_value` non-finite and refusing the terminal checkpoint
   (`departments.attributed_output_value has non-finite values`). Fix: flush
   plot-stock residuals at or below `_STOCK_DUST` to zero, and treat a
   non-finite share as unattributed nil output. Evidence:
   `test_resume_refuses_a_terminal_checkpoint` failed before the fix and passes
   after; all 580 `departments` rows are now finite.
3. **Hub collection demands were ordered gross of the hub's own stock.** A
   wholesale hub could reserve up to the full downstream need while its
   wholesale cell still carried the previous quarter's stock, inflating
   `ordered`/`allocated` far above any real replenishment requirement. Collection
   gross demand is now formed net of the destination's opening wholesale stock,
   which keeps the hub's reservation equal to its genuine pipeline need.

## Known limitation: material-chain absorption under the pinned fixed-point rules

The synthetic fixture is *not* self-sustaining over the full horizon, and this is
a property of the pinned fixed-point rules rather than an accounting break. None
of the growth-scalar logic or state/ledger invariants is affected: within every
admitted tick `delivered ≤ allocated ≤ ordered ≤ gross`, stocks are continuous,
every Journal transaction is paired, and the run completes all 116 ticks.

Measured on the frozen default scenario (5,000 households / 200 organizations):

- gross attributed output by tick 0…4 = `344,901`, `59,713`, `352,762`,
  `28,607`, `35,860`, alternating at period two and decaying; by tick 17 the
  1,000-household profile is at exactly `0` and stays there.
- the funnel narrows at every stage in the trough quarters: intermediate-input
  orders `131,742 → allocated 82,844 → delivered 9,324` (tick 1) and
  `49,782 → 20,887 → 4,119` (tick 3).
- the binding constraint is the transport sector: its realized activity is
  `63,000`, `0`, `30,371`, `0`, `0` for ticks 0…4, with `min_input_ratio = 0`
  in every dead quarter (its own opening energy/capital-goods buffer is empty).
  Once transport output is zero, every cross-region route factor is zero, so
  deliveries stop; production then has no same-quarter inputs and the state is
  absorbing. Raising only the transport input buffer is not sufficient
  (`input_stock_quarters` 2/3/4/6/8 all still collapse), while an effectively
  unbounded transport buffer sustains the same fixture for the whole horizon
  (mean activity 77,006, minimum 51,232), which isolates the cause to the
  input-buffer/pipeline interaction and not to a leak in the ledger.

Cause chain, all of it pinned by the approved plan: input orders are
`max(desired − opening_input, 0)` with `desired` equal to one quarter of need, so
a full opening buffer suppresses the order that would replenish it; deliveries
arrive in the same quarter the inputs are consumed; regional sourcing is limited
to the nearest two producers; and a production input may only be delivered
through a transport route, including the transport sector's own fuel. The
combination has a feasible steady state but also an absorbing deadlock, and the
initial transient can land in it.

Resolving this requires a *mechanism* decision that the approved P02 plan does
not authorise (it pins the net-order rule, the nearest-two sourcing rule and the
transport-service requirement).

### Order-up-to-cover experiment (run, measured, rejected)

The pinned `hoarding_quarters` parameter already implements order-up-to-cover
(`gross = max(desired × (1 + hoarding) − opening_input, 0)`), so the candidate
remedy was measured by switching that existing toggle on rather than by changing
code. It softens the transient but does **not** remove the absorbing state, and
it was therefore not committed:

| configuration (1,000 households / 100 organizations, 116 ticks) | mean activity | zero ticks |
|---|---|---|
| baseline (`hoarding_quarters = 0`) | 3,665 | 110 |
| cover 0.5 quarter | 4,457 | 107 |
| cover 1 quarter | 4,759 | 107 |
| cover 2 quarters | 5,039 | 108 |
| raw-materials capacity 34,000, no cover | 3,779 | 111 |
| cover 1 quarter + raw-materials capacity 34,000 | 5,333 | 109 |
| transport self-haul, no cover | 3,924 | 110 |
| transport self-haul + cover 1 / 2 quarters | 4,768 / 5,041 | 107 / 108 |

Per-tick tracing (temporary instrumentation, reverted) shows three compounding
constraints rather than one, and cover only moves which of them binds:

1. *Delivery collapse, baseline.* Intermediate-input orders
   `131,742 → allocated 82,845 → delivered 9,324` at tick 1: 63% is allocated
   but only 11% of the allocation is delivered, because transport output is
   `63,000, 0, 30,371, 0, 0` for ticks 0…4 and cross-region routes carry ~89% of
   the intermediate edges. Allocation itself is fine in this configuration.
2. *Allocation collapse, cover on.* With a cover the orders run closer to
   target (`181,032` at tick 1) and now the sellers ration instead:
   `ordered 181,032 → allocated 74,269` (41%), and the binding input becomes a
   *regional* raw-materials shortage (`raw_materials@region-19` ratio 0.587,
   then `food@region-11` 0.084, then `raw_materials@region-0/1` at 0), with
   42 → 221 of 354 input rows below ratio 1. Regional sourcing is limited to the
   nearest two domestic producers, so raising the national raw-materials
   capacity total does not help a region whose two declared sources are empty.
3. *Transport decay.* The transport sector consumes only its *opening* input
   stock (the pinned transport-first exception), so its buffer must be built one
   quarter ahead; under any of these configurations its realized activity decays
   `63,000 → 52,524 → 43,887 → 12,775 → 0` because its own energy/capital-goods
   replenishment is itself rationed (and, in the baseline, gated by the transport
   service it provides).

A fix therefore needs a *re-balancing package* over fixture topology and
capacity — enough raw-material producers (or a source fallback) so that every
region can actually reach a universal input, a capacity total consistent with
the declared target vector (aggregate raw-materials supply/use is 0.797 at
target), a buffer policy that covers the transport sector's one-quarter pipeline,
and a decision on whether the transport sector's own inputs are self-hauled.
None of that is implemented or committed; the shipped default remains the
baseline above, and the engine, invariants, determinism, checkpointing and
benchmark gates are unaffected.

## Deviations and boundaries

- `MaterialTickFlows` field `journal_kind` was restored after an intermediate
  edit dropped it; state/flows field sets are covered by the shared
  serialization field-spec used by digest, checkpoint save and checkpoint load.
- `derive_departments` requires the network catalog and the closing state (and
  `housing_completed`) — purpose/commodity axes are not derivable from flows
  alone — and is documented as such.
- Department I values the physical material installed (from investment demand
  `used`), not capacity units; the earlier capacity-unit valuation was corrected.
- Investment demand cells with no declared supplier now resolve their owning
  project from the destination cell and stay a legal observable backlog instead
  of failing the tick.
- `--organizations` switches the stock profile only when the scenario carries no
  explicit `organization_recipe` overrides; otherwise exit 2.
- FRED live ingestion stays rights-blocked; the admitted Federal Reserve H.15
  source is the selected rate feed. MNB data is restricted
  (`redistribution_allowed=false`); only its normalized numeric output is
  derived, and no raw/normalized MNB or Fed bytes are committed.
- **Distribution-layer working capital (structural assumption, M2-neutral).** The
  pinned net-order rule (`max(desired − opening_input, 0)`) funds purchases out
  of existing deposit cash, and a wholesale/retail layer that starts with no
  stock and no consumer revenue has nothing to order with, so the goods chain
  cannot start at all. `MaterialInitialRecipe.distribution_working_capital_quarters`
  therefore capitalises the wholesale and retail slots as a function of the
  declared quarterly goods flow (`wholesale_procurement 180,000` / `retail
  80,000` handling work). The transfer is M2-neutral by construction: the
  Treasury's idle opening deposit is reduced by exactly the amount the traders'
  opening deposits are raised, and `initialize_material` refuses a negative
  Treasury deposit. This is an explicit engineering bridge, not a calibrated
  historical credit stock.
- **Stock-dust tolerance.** `_STOCK_DUST = 1e-9` is used both as the
  non-negativity tolerance at the gates and as the flush threshold for residual
  plot-cell stock, so physical stocks never carry machine-epsilon residue that
  would later underflow into subnormal flow quantities (see defect 2 above).
- No calibration, no mechanism verdicts, no 1986–1988 unlock, no politics/LLM/
  social attitudes, and no P03 household panel are included. Synthetic mechanism
  validation is not a historical fit.
