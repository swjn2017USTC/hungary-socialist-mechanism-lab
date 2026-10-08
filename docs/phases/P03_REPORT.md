# P03 Report — Households / Social Contract / Durables / Second Economy

Date: 2026-10-08 · Plan: `P03_HOUSEHOLDS_SYNTHETIC_ECONOMY_PLAN.md` · Baseline:
`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` (unchanged)

## Scope delivered

The **mechanism nucleus** (user-approved cut): a county-conditioned weighted
synthetic household population, a vectorized quarterly demand system, channel
rationing with forced substitution / queueing / postponement, durable ownership
as a stock, an independent housing stock, an aggregate per-county second
economy that changes both income and the availability of specific goods and
services, and an entitlement/grievance/compliance layer that is explicitly
**not** political support and does **not** trigger protest. All of it runs inside
the existing `tick_material` quarter sequence and the P02 ledger
(`material-state-v2` / `material-engine-v2` / `material-network-v2` /
`material-checkpoint-v2`).

### New modules

| Module | Content |
|---|---|
| `contract/households.py` | `H` (11 sub-channels), `D` (4 durables), `E` (7 entitlement components), `Q` (5 substitution pairs) axes; `HouseholdParameters` (demand/allocation/durables/housing/time/welfare/expectations/second_economy), `CountyHouseholdSpec`, `HouseholdInitialRecipe`, `default_household_recipe` (20 pure-engineering county rows), `HouseholdCatalog` + `compile_household_catalog` (`to_material`, `price_h`, quota split, substitution mapping) |
| `engine/households.py` | `build_synthetic_households` (maximum-entropy size tilt, Hamilton apportionment with ≥1 representative per positive cell), `form_household_demand` (pure array kernel), `household_equivalence` |
| `engine/household_allocation.py` | budget tiers, plot self-use (capacity share), formal-retail and second-pool channel rationing through the network household edges, plot direct market, forced substitution (`Q`, one pass), queue/search hours, forced/voluntary saving |
| `engine/household_stocks.py` | durable desire/retirement/maintenance/waiting; housing gap/overcrowding/`allocate_housing`/private construction installation |
| `engine/second_economy.py` | `plan_household_time` (labour reservation), `settle_second_economy` (real input purchase → real production → regional pool → seller income), `second_expiry` |
| `engine/household_welfare.py` | material satisfaction (bounded logistic), 7-component entitlement, grievance and political compliance (separate slow rules), `update_household_expectations` (adaptive + experience ratchet) |

### Modified modules

`contract/material.py` (owner kind `second_economy`, purpose `second_economy`,
`HouseholdInitial` static attributes, `MaterialInitialConditions.household_*`,
removal of `desired_per_person` / `equivalent_households` /
`housing_request_per_person`), `engine/state.py` (~40 new typed arrays + flows,
`durable_stock[R]` removed), `engine/network.py` (household catalogue and
derived second-economy commodity axes), `engine/initial.py` (generator wiring),
`engine/material.py` (P03 household subsystem replacing the old household step;
frozen demand; gap-based housing request; second-economy expiry; new gates),
`engine/accounting.py` (household cash identity with second income/funding,
per-household durable continuity, private housing completion, second-economy
cell draws, signed welfare/gap exemption), `storage/checkpoint.py` (v2 field
spec incl. multi-axis arrays, new RNG profile), `storage/material_output.py`
(second-economy draws in the stage ledger), `contract/schemas.py`
(`household_parameters`/`household_initial` required for material scenarios),
`provenance/manifest.py` + `cli/app.py` (`intermediate8_household_simulation`).

## The declared mechanisms

* **Population conservation** — changing the household *sample* size never
  changes `Σweight` (5000), `Σ weight·size` (17000) or the weighted
  county/urban/occupation margins; only attribute resolution improves.
* **Vectorized demand** — one `(N, H)` array kernel per tick, no per-household
  Python object, dict or history.
* **Explicit shortage outcomes** — each channel carries its own desired /
  affordable / realized / budget-unmet / availability-unmet; `Q` substitution is
  afford-only, one pass, non-recursive, credit-tagged; queue/search hours are
  real time costs against the affordable shortfall; forced vs voluntary saving
  are separated.
* **Durable ownership is a stock** — per-household fractional ownership,
  retirement hazard, maintenance credit, backlog and waiting quarters; the
  regional `durable_stock` array is deleted (continuity is checked against the
  household-level acquired/retired flows).
* **Housing is an independent stock** — `dwelling_stock = Σ weight·access +
  vacant`; formal completion and private second-economy construction both add
  dwellings; allocation is by overcrowding/wait priority within a county.
* **Second economy changes income *and* availability** — an aggregate per-county
  activity buys real formal inputs, produces light goods / construction /
  services into a regional pool, and pays the participating cohort; buyers see
  the extra channel.
* **Entitlement ≠ political support; grievance ≠ protest** — entitlement is a
  7-component experienced-outcome vector; grievance and compliance are separate
  slow state variables (compliance is not `1 − grievance` and not material
  satisfaction); no protest/collective-action quantity exists anywhere.

## Verification evidence

* `uv run pytest -q` → **264 passed** (P02 contract intact; 6 new P03 behaviour
  tests, incl. the four required fixtures and the population-scaling check).
  `uv run ruff check .` → clean. `uv run mypy src/hsm_lab` → **no issues in 43
  files**.
* `uv run hsm run --scenario intermediate8 --output-dir outputs/p03-full-horizon
  --json` → **116 admitted ticks**, last quarter `1985Q4`, run_kind
  `intermediate8_household_simulation`, replay digest
  `19a1763a22a1c2748bde7559e34e06bb06bd8053729860b315f05695a8cb8a52`; every
  ledger ratio passes `check_material_invariants`.
* `uv run hsm summary --run-dir outputs/p03-full-horizon --json` reads the run
  back.
* Checkpoint pause/resume roundtrip and the corruption/refusal gates pass
  (`tests/test_checkpoint.py`).
* **Population scaling** (single-tick wall, seed 1729, synthetic intermediate8):
  N=1,000 → 0.0049 s; N=5,000 → 0.0111 s; N=20,000 → 0.0354 s. Doubling-guard
  ratios 5k/1k = 2.25 (≤6.25) and 20k/5k = 3.18 (≤5.0); normalised
  (wall ratio)/(N ratio) = 0.45 and 0.795 (sub-linear).

### The four required household fixtures (`tests/test_households.py`)

1. **income up but goods unavailable** — desired basic food funded, no stock:
   realized 0, planned spending > 0, forced saving == planned spending,
   availability unmet > 0, queue hours > 0.
2. **durable waiting** — durable wanted, none on the shelf: ownership 0, backlog
   and waiting grow; when the good appears the purchase lands as *stock* and
   clears the backlog.
3. **second-economy relief/income** — participating households with real inputs:
   aggregate output lands in the regional pool, input funding is paid, sellers
   are credited.
4. **entitlement ratchet** — the declared experience sequence reproduces the
   plan's expectation values `0.6024609375` (quarter 4) and `0.60041171875`
   (quarter 5); no protest quantity exists; compliance ≠ `1 − grievance`.

## Explicit deferrals (documented, not silently dropped)

Per the approved nucleus cut, the following plan items are **not** in this
commit and are the natural P03-follow-up / P04 scope:

* the seven compact household tables and the `HouseholdMicroWriter` streaming
  micro panel (incl. `research_full` unlock and checkpoint micro-payload
  hard-linking);
* `data/households.py` historical anchor loader and the
  `aggregate_household_targets` comparison surface;
* the benchmark-case additions and 1k/5k/20k F1 gates in
  `config/benchmarks/material.json` (the scaling numbers above are the
  engineering convergence check, not a gate);
* full network-cell/route integration of the second economy (G1/G2) — the
  aggregate pool is a separate state array whose continuity is checked
  explicitly, not through the shared stock-cell catalog.

## Known limitation (carried, unchanged)

The P02 material-chain degeneration reported in `docs/phases/P02_REPORT.md` is
**not** resolved here; the integrated trajectory keeps that known limitation and
is not a historical fit. Every household population, behaviour coefficient and
second-economy quantity is a declared synthetic fixture
(`population_kind="synthetic"`, `structural_assumption`, `not_calibrated`,
`not_assessed`) — not evidence for any mechanism claim.
