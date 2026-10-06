# P00 Report — Foundation / Research Contract / Data Audit Skeleton

Date: 2026-10-07 · Platform: macOS 25.5.0, arm64, 34,359,738,368 B RAM ·
Python 3.12.14 (Homebrew CPython via uv) · cwd: repository root throughout.

**Status: P00 complete.** Every gate below was executed on this machine; exit
codes are recorded as observed. No historical simulation is claimed anywhere
in this phase.

## 1. Verification battery (commands and exit codes)

| Command | Result |
|---|---|
| `uv sync --frozen` | 0 (99 packages resolved by `uv lock --python 3.12`) |
| `uv run pytest -q` | 0 — **89 passed** in ~7.1 s |
| `uv run ruff check .` | 0 — all checks passed |
| `uv run mypy src/hsm_lab` | 0 — strict, no issues in 23 source files |
| `uv run hsm --help` / `uv run python -m hsm_lab --help` | 0 — identical command tree |
| `uv run hsm baseline verify --json` | 0 — see §2 |
| `uv run hsm doctor --json` | 0 — 17 checks, `status: ok` |
| `env -u OPENAI_API_KEY -u SV_LLM_API_KEY -u SV_EVENT_API_KEY -u SV_EVENT_API_URL uv run hsm doctor --socioverse-smoke --json` | 0 — see §5 |
| `uv run hsm data audit --json` | 0 — `registry_valid=true`, `sources_ready=false`, artifacts=0 (report under `outputs/data_audit/…/audit_report.json`) |
| `uv run hsm run --scenario smoke …` ×4 (proof a/b/c/full) | 0 — see §4 |
| `uv run hsm benchmark smoke --json` | 0 — gate pass |
| `uv run hsm benchmark scaling --json` | 0 — gate pass |
| one-off proof assertions (Python, manifests+Parquet+DuckDB) | all assertions passed |

## 2. Baseline immutability

- `BASELINE.md` SHA-256 (raw bytes):
  `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`
- Pinned as `expected_baseline_sha256` in `config/research_contract.json`;
  `hsm baseline verify` compares bytes and refuses runs on drift; the pinned
  hash is never recomputed-and-overwritten. BASELINE.md is untouched
  (`git status` shows no modification).
- Corrupted-copy drill (tmp file + `--path`, and a wrong-hash contract in
  tests): refused with exit 1, no run directory created.

## 3. Environment / resolved versions

| Package | Version |
|---|---|
| numpy | 2.5.3 |
| scipy | 1.18.1 |
| polars | 1.44.2 |
| duckdb | 1.5.6 |
| pyarrow | 25.0.1 |
| pydantic | 2.13.5 |
| PyYAML | 6.0.3 |
| socioverse2 | 0.2.0 (import name `socioverse`) |
| networkx | 3.7 |
| SALib | 1.6.0 |
| pyabc | 0.13.0 |
| typer | 0.27.3 |
| pytest / ruff / mypy | 8.x / 0.x / 1.x (dev group, frozen in `uv.lock`) |

All plan dependency ranges resolved on the first `uv lock`; no upper bound had
to be relaxed. Single worker; `OMP/OPENBLAS/MKL/VECLIB/POLARS` threads pinned
to 1 in benchmark workers, DuckDB `threads TO 1`.

## 4. Synthetic run evidence (proof directory `outputs/p00-proof.*/`)

Runs `a`, `b` (seed 1729), `c` (seed 1730), `full` (seed 1729, research_full):

- **Determinism**: digest(a) = digest(b) = digest(full) ≠ digest(c); 4 distinct
  `run_id`s; all `status=completed`, `run_kind=synthetic_engine_smoke`,
  `political_mode=null`.
- **RNG accounting**: 42,000 draws per run (households 40,000 + enterprises
  2,000), active modules exactly {smoke.households, smoke.enterprises}; last
  quarter 1959Q2; digest excludes run_id/time/paths/perf/git/output bytes.
- **Aggregates**: 1,600 rows = 10 ticks × 20 regions × 4 commodities × 2 actor
  kinds; group keys unique; household count 50/region; enterprise counts match
  `id % 20` (3 for regions 0–9, 2 for 10–19); DuckDB and Parquet agree
  key-by-key; 10 `synthetic_tick_completed` events.
- **Full vs compact**: households micro 40,000 rows, enterprises 2,000 rows;
  per-(region, commodity) micro sums equal compact `probe_sum` within
  rtol=atol=1e-12; compact run contains no micro files or views (writer never
  creates them).
- **Manifests**: every `output_hashes` entry recomputes; manifest self-excluded;
  lock/data-manifest/parameter/scenario hashes recompute identically;
  deterministic (seed 0) run: zero draws, empty active list, tick-2 values 2.0,
  `deterministic_no_replicates` warning — no fake replicate claims.

## 5. SocioVerse2 integration (real, no mocks)

`hsm doctor --socioverse-smoke` (API keys stripped): real
`DuckDbTrajectoryStore` + `TrajectoryRecord` from the installed wheel; 2 agents
× 2 steps written, finalized, reopened read-only:

- panel: 4 rows, unique (agent_id, step) primary keys, state `probe_value`
  0/1 per step;
- metrics: step 0 → 0, step 1 → 2;
- events: only step 1 carries `p00-synthetic-event`;
- `panel.parquet` / `metrics.parquet` round-trip equal to the DB; temp
  directory removed afterwards.

Permanent test additionally monkeypatches `socket.connect` to fail loudly —
the smoke passes with networking disabled; no LLM, no event client, and
`import hsm_lab.engine.smoke` does not pull in `socioverse` (lazy integration).

## 6. Benchmarks (engineering probe only — NOT F2 historical performance)

Compact JSON copies tracked at `benchmarks/p00_smoke.json` and
`benchmarks/p00_scaling.json`; full outputs under `outputs/p00-proof.*/`.
Workload = `synthetic_array_rng_aggregation_storage`. 1 warmup + 3 repeats per
case, median wall/CPU, max peak RSS from worker
`resource.getrusage(RUSAGE_SELF).ru_maxrss` (Darwin bytes).

Smoke (N=1000, E=50, T=10):

| case | median wall | median CPU | peak RSS | worker elapsed (incl. startup) |
|---|---:|---:|---:|---:|
| ensemble_compact | 0.185 s | 0.168 s | 182,976,512 B (0.170 GiB) | 0.437 s |
| research_full | 0.197 s | 0.181 s | 187,711,488 B (0.175 GiB) | 0.449 s |

Scaling (six BASELINE §29 sizes × T∈{10,116}, compact):

| case | median wall | peak RSS | updates/s |
|---|---:|---:|---:|
| n1,000 t10 / t116 | 0.185 / 0.213 s | 0.170 / 0.193 GiB | 227k / 2.29M |
| n5,000 t10 / t116 | 0.190 / 0.225 s | 0.171 / 0.193 GiB | 1.07M / 10.5M |
| n10,000 t10 / t116 | 0.192 / 0.235 s | 0.171 / 0.194 GiB | 2.12M / 20.1M |
| n20,000 t10 / t116 | 0.194 / 0.261 s | 0.171 / 0.194 GiB | 4.20M / 36.1M |
| n30,000 t10 / t116 | 0.194 / 0.285 s | 0.173 / 0.194 GiB | 6.24M / 49.3M |
| n50,000 t10 / t116 | 0.203 / 0.336 s | 0.173 / 0.195 GiB | 9.97M / 69.7M |

- Resource gates: max peak RSS 209,207,296 B ≈ 0.195 GiB « 16 GB warning / 22 GB
  hard cap — `peak_rss_ok` everywhere.
- Linearity: 10k→20k compute+aggregate ratio **1.655** (T=10) and **1.778**
  (T=116), both < 3.5 → no `needs_profile`.
- Honest measurement limits: `measurement_too_short=true` for every case whose
  compute+aggregate median is < 0.1 s (all except n50,000×116 at 0.130 s); wall
  time is dominated by output writing + manifest, and no absolute throughput
  promise is made for the future historical model.

## 7. Data registry / audit outcome

19 source candidates registered with role expectations and rights metadata;
17 variables registered; **0 artifacts** (no data obtained). Offline audit:
`registry_valid=true`, `sources_ready=false`, blocked/unverified list includes
ksh_cpi_long, ksh_cpi_groups, ksh_agriculture_a/b/c, ksh_retail,
ksh_census_regional, ksh_census_detailed, worldbank_pink_sheet, fred_fedfunds,
mnb_official_fx, imf_hungary_external, tarki_catalogue, osa_public_opinion,
cmea_energy_reconstruction. 14 gap items from BASELINE §41 recorded as
`not_audited`. No TÁRKI/OSA microdata requested or downloaded; no raw table
fetched; online audit not required for the gate (metadata reachability ≠
rights).

## 8. Baseline ↔ package-reality conflicts and deviations

1. **SocioVerse2 0.2.0 `TrajectoryRecord` has no `action_source` field** (the
   P00 plan, written from the `main` branch, listed it). Adapted: records are
   written with `agent_id/step/state/action_kind/action_payload` only. Store
   API otherwise matched the plan (`record_events(step, notes)`, `finalize`,
   `open_readonly`, parquet export; `open()` unlinks existing DBs, hence the
   fresh-directory requirement).
2. **pyarrow ships no `py.typed` marker** (pyarrow 25.0.1) → precise
   `# type: ignore[import-untyped]` on the two imports in
   `src/hsm_lab/storage/output.py` only; no module- or directory-wide ignores.
3. **Typer's `Option(...)` default idiom trips ruff B008** → per-file ignore
   for `src/hsm_lab/cli/app.py` only (documented in `pyproject.toml`).
4. **FRED legal terms restrict ML-related use** of FRED content/services
   (BASELINE §22 expects a global-rate forcing): registered
   `restricted`/`blocked`; P00 ingests nothing. Resolving usage rights is a
   user decision before any future ingestion.
5. Python 3.12 `StrEnum` used for all enums (ruff UP042); JSON values
   unchanged.

## 9. Limitations / non-claims

- P00 runs a **synthetic array/RNG/aggregation/storage workload**. `probe_value`
  is not income, output, inventory or satisfaction; `mechanism_diagnostics`
  stays `{}`. No historical simulation, calibration, validation, or mechanism
  verdict exists.
- Deterministic replay digest equality is claimed **within one locked
  environment** (uv.lock hashes recorded per manifest), not across
  NumPy/BLAS/platform changes.
- Benchmark repeats are timing repetitions of one fixed seed, not stochastic
  replicates; the RNG divergence evidence lives in tests and the a/b/c proof
  runs instead.
- Reserved 1986–88 outcomes: metadata-only, numeric loads refused by code; no
  unlock flag exists.
- `outputs/` (proof runs, benchmark trees, audit reports) is local and
  gitignored; only the two compact benchmark JSONs under `benchmarks/` are
  tracked.
