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
digest `56eab3619cbdac6b47970128b583b9f28ac01b820dfbfebb0173d41fdb646e5c`.

- Re-run into a second directory with identical inputs → same digest
  `56eab361…`; pause/resume equivalence is pinned by
  `test_run_material_pause_then_resume_matches_uninterrupted` and
  `test_resume_refuses_a_terminal_checkpoint` (both passing).
- Every table row-count equals the pinned grid: `aggregates` 18560,
  `stage_balances` 21924 (21×9 per tick), `national_accounts` 928,
  `household_budgets` 2320, `organization_diagnostics` 18560,
  `financial_accounts` 464, `departments` 580, `tick_diagnostics` 116,
  `events` 116; Parquet and DuckDB contents agree.
- Invariant maxima over the 116 admitted ticks: material tolerance ratio
  `3.717e-03`, finance tolerance ratio `2.577e-04` (both ≤ 1), max absolute
  material residual `7.276e-12`, max absolute finance residual `7.637e-08`;
  `parameter_hash=a6aa7ca637f0525f3da950a1c085f57a3da11d76361f2f67224bf398cdc553e3`,
  `initial_recipe_hash=5a893a75f2637113bbc2b8d51b4eec7a6a854def310010135a1cea525ac7e465`
  (both unchanged by the capacity calibration below, which lives in the contract
  capacity totals rather than in the recipe or parameter vectors).
- Shortage mechanism diagnostics are active, not synthesised: 18,725 bottleneck
  demand events across the run; financial delivery blocking is ~`6e-13` (nil),
  as expected now that clearing-limited deliveries are charged at the delivered
  quantity; all `departments` attribution rows are finite.
- No politics, LLM or social-attitude fields exist in state, and the summary
  carries `assessment_status="not_assessed"` mechanism diagnostics only.

### External forcing run

`uv run hsm data build-material-forcing --profile external` then
`uv run hsm run --scenario intermediate8_external --output-dir outputs/p02-external --json`
→ status ok, 116 ticks, digest
`046efacfcebe2e656e238afeb7b715b887d7a76ce5d93cb85e28a85fd8b94129`. The
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
worker wall **3.446 s**, peak RSS **0.408 GB**. Checkpoint case
(`checkpoint_every=20`): **3.733 s**, ratio vs F1 **1.083**, **9.06 MB** per
checkpoint. Max peak RSS across all cases **0.442 GB** (≤ 16 GB normal gate).
Scaling medians (households 2,500→5,000→10,000 at O=200; organizations
200→400 at N=5,000): **1.371 / 1.552 / 1.146** (≤ 3.5 threshold). Every case
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

## Fixture calibration: input feasibility of the declared target vector (committed)

An audit of the declared synthetic target vector against the declared sector
capacities (all activities at `utilization = 0.9`, technology coefficients from
`contract/material.py`) showed the fixture was **physically infeasible**:

| commodity | whole-economy input requirement at target | declared supply | ratio |
|---|---|---|---|
| `raw_materials` | 22,590 | 18,000 | **0.797** |
| `energy` | 23,715 | 27,000 | 1.139 |
| `capital_goods` | 819 | 7,200 | 8.79 |
| `food` | 45,000 | 90,000 | 2.00 |

`raw_materials` demand exceeded supply by 25%, and the sector also consumes
itself (`0.08` per unit), so the shortage compounded instead of clearing. No
ordering, buffering or routing rule can repair an infeasible input-output
vector, so this was corrected at the declared fixture rather than in the
mechanism: `INDUSTRIAL_CAPACITY_TOTALS` raw materials `20,000 → 34,000` and
energy `30,000 → 36,000`. Both totals were solved, not guessed, from the
self-input fixed point (`0.828·C_raw ≥ 21,150`; `0.855·C_energy ≥ 22,365`) and
now hold supply/use ratios of ~1.30 and ~1.35. This remains a synthetic
structural assumption with no historical claim; `parameter_hash` and
`initial_recipe_hash` are unchanged because capacities live in the contract
totals, and the run digest changes to `56eab361…`.

**Effect (default scenario, 116 ticks).** The exact-zero absorption state is
gone: previously the run flatlined to exactly `0`; it now never reaches zero,
with a floor of `161`–`581` units alternating at period two over the last
quarters. Aggregate output still decays from `369,294` (tick 0) through
`60,408`, `371,411`, `32,018`, `39,029`, `27,614`, `18,492`, `13,994`, i.e. the
economy remains **degenerate**, at ~0.1% of the declared target scale. All
invariants, determinism, checkpoint and benchmark gates remain green.

## Known limitation: the material chain still decays to a degenerate floor

The remaining decay is a property of the pinned quarter sequence, not an
accounting break: within every admitted tick `delivered ≤ allocated ≤ ordered ≤
gross`, stocks are continuous, every Journal transaction is paired, and the run
completes all 116 ticks.

Per-tick tracing (temporary instrumentation, reverted) isolates the chain on the
default scenario (5,000 households / 200 organizations):

- ticks 0–2 run at target (`224,300`, `234,385`, `233,432` against a growing
  target of `206,300` → `248,445`);
- **tick 3: the transport sector dies** (`63,000 → 59,835 → 594 → 0` realized
  against a `68,258` target) and `services_transport@region-0` becomes the
  binding input with ratio `0`, starving `132 → 383` of 648 input rows;
- intermediate-input deliveries collapse with it (`ordered 155,419 → allocated
  68,612 → delivered 38,808`, and progressively less thereafter);
- the deep floor is a joint material and monetary deadlock: intermediate orders
  fall to `837` while `allocated → 0` (seller cells empty) because no production
  means no sales, no cash and therefore no funded orders.

The structural reason transport cannot stay alive is that `services_transport`
never carries over between quarters — its cells open at zero, are filled only by
same-quarter deliveries, and any unused remainder expires within the quarter
(step 9) — while it is *also* a production input of
`capital_goods_production`, `consumer_goods_production`,
`durable_goods_production` and `building_construction`, and its own delivery
occupies a transport route. The sector consumes only its *opening* input stock
the pinned transport-first exception), so its buffer must be laid down a quarter
ahead; under the pinned net-order rule there is no positive-stock fixed point for
that buffer, and one short quarter is sufficient to stop the sector that every
cross-region route depends on.

### Levers measured (all temporary, none committed except the capacity calibration)

| configuration (116 ticks) | mean activity | zero ticks | floor |
|---|---|---|---|
| default profile, baseline capacities | 3,665 | 110 | 0 |
| + raw/energy capacity calibration | 5,216 | **0** | 100 |
| + `input_stock_quarters = 4` | 9,571 | **0** | 100 |
| + `hoarding_quarters = 2` (order-up-to-cover) | 11,908 | **0** | 200 |
| 1,000 hh / 100 org, cover 0.5 / 1 / 2 quarters | 4,457 / 4,759 / 5,039 | 107 / 107 / 108 | 0 |
| 1,000 hh / 100 org, raw capacity 34,000 alone | 3,779 | 111 | 0 |
| 1,000 hh / 100 org, transport self-haul | 3,924 | 110 | 0 |
| 1,000 hh / 100 org, transport self-haul + cover 1 / 2 | 4,768 / 5,041 | 107 / 108 | 0 |

Every lever moves which constraint binds without restoring a viable economy: the
capacity calibration removes the exact-zero trap, order-up-to-cover and larger
input buffers raise the floor and the transient, and exempting the transport
sector's own inputs from the route service does not prevent the sector's decay
because its fuel must still be *stocked* a quarter ahead.

### Next step (approved, not yet implemented)

A self-consistent steady-state initial state: solve the model's own fixed point
over the input matrix, the transport pipeline, the tiered rationing and the
monetary bridge, and declare that solution as the synthetic initial recipe
instead of "one quarter of target". That is calibration engineering and is
tracked as the follow-up to this phase; the engine, ledger, determinism,
checkpoint and benchmark contracts are unaffected by it.

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
- **Capacity calibration is a structural assumption.** `INDUSTRIAL_CAPACITY_TOTALS`
  energy `36,000` and raw materials `34,000` are the smallest declared totals that
  make the declared target vector input-feasible with ~1.3 headroom (see the
  fixture-calibration section). They are synthetic engineering values chosen for
  internal consistency, not calibrated historical capacities.
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
