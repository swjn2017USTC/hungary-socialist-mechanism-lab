# hsm-lab — Hungary Socialist Mechanism Lab (P02 material economy)

Research simulation laboratory for Hungary 1957Q1–1985Q4. P02 delivers an
Intermediate-8 synthetic material-economy mechanism model plus role-gated,
auditable historical source ingestion. The mechanism recipes and organization
profiles are structural assumptions, not historical estimates; KSH outcomes
remain TARGETS and never initialize or force runtime state. See `BASELINE.md`,
`MATERIAL_ECONOMY_EXPANSION_PLAN.md`, and `docs/phases/P02_REPORT.md`.

> Simulation is an argument, not evidence.
> A probability produced by an agent or decision model is not a historical probability.

## Layout

- `src/hsm_lab/contract/` — baseline-bound schemas plus Intermediate-8 commodity/organization contracts
- `src/hsm_lab/data/` — rights-gated ingestion, immutable raw cache, strict adapters, forcing/target admission
- `src/hsm_lab/provenance/` — run manifests, canonical digests, provenance gates
- `src/hsm_lab/engine/` — sparse CSR material network, vectorized tick kernel, finance and accounting
- `src/hsm_lab/storage/` — compact Parquet/DuckDB output and material checkpoints
- `src/hsm_lab/cli/`, `src/hsm_lab/benchmarks/` — Typer CLI and isolated material benchmarks
- `config/`, `data/manifests/` — pinned scenarios, benchmarks, sources, variables and artifact roles
- `outputs/` — local run artifacts (gitignored)

## Setup

```bash
uv sync --locked      # Python 3.12, locked dependencies
```

## Commands (run from the repo root)

```bash
uv run pytest -q
uv run hsm --help
uv run hsm baseline verify --json
uv run hsm doctor --json
uv run hsm data audit --json
uv run hsm data ingest --source ksh_industry --json
uv run hsm data ingest --source ksh_industry --offline --json
uv run hsm data build-material-forcing --profile synthetic --json
uv run hsm run --scenario intermediate8 --households 5000 --organizations 200 --seed 1729 --json
uv run hsm summary --run-dir outputs/p02-full --json
uv run hsm benchmark material --json
```

`intermediate8_external` is available only after downloading/admitting the
required World Bank and Federal Reserve forcing and explicitly building the
external pack. The FRED adapter remains rights-blocked; the admitted Federal
Reserve H.15 source is the selected rate feed. `--offline` reads only
SHA-256-verified immutable cache entries. Material `--organizations` accepts
100/200/400 profiles; formal household runs accept 1,000–30,000 cohorts.


Exit codes: `0` success, `1` environment/I-O/research-gate failure,
`2` input/config validation failure. All commands accept `--json` and print a
single JSON object on stdout.

## P02 material contract

The runtime commodity axis is fixed to `energy`, `capital_goods`, `food`,
`consumer_goods`, `raw_materials`, `construction`, `durable_goods`, and
`services_transport`. Units are explicit engineering units: `energy`=`p02_energy_unit`,
`capital_goods`=`p02_capital_unit`, `food`=`p02_food_unit`,
`consumer_goods`=`p02_consumer_unit`, `raw_materials`=`p02_raw_unit`,
`construction`=`p02_construction_unit`, `durable_goods`=`p02_durable_unit`,
and `services_transport`=`p02_service_unit`; these are not historical
Hungarian tonnes or HUF. Food inventories carry `raw` or `ready` stage; only
processing converts raw to ready. Transport services are non-stockable.
Department I/II are derived from actual use, not permanent commodity labels.

Organization profiles contain industrial SOEs, agricultural cooperatives,
state farms, construction and transport providers, wholesale procurement,
retail, and banks. Bank organizations have no material stock cells or
physical outputs. Housing completion increases dwelling stock only; it is not
consumer goods or durable production. Over-ordering and hoarding default to
zero and are explicit mechanism parameters.

KSH GDP, industry, agriculture, and trade series are role-tagged TARGETS.
Targets can be compared to runs but are not arguments to initialization or
quarterly ticks. World Bank oil, Federal Reserve H.15 rates, and dated MNB FX
quotes are separate forcing/diagnostic inputs. CMEA contract energy prices
are labeled reconstructed; 1957–1959 oil is a structural warm-up, not an
observation. Parser header/unit drift and corrupt hashes fail closed.

Synthetic organization counts, coefficients, prices, household strata and
mechanism outcomes are structural assumptions, not historical estimates or
empirical theory support. P02 does not include politics, social attitudes,
LLM agents, or the P03 household panel.

## Boundaries

P02 leaves 1986Q1–1988Q4 reserved, does not perform calibration or claim a
historical fit, and does not add politics, social attitudes, LLM agents,
microdata, or P03 household panels. FRED live ingestion remains blocked by its
source rights gate. The P00 smoke workload and its contract remain available.
