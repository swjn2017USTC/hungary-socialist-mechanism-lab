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

---

## 10. Revision 1 — independent-review patches (P1–P7)

Round-1 independent review verdict: **PATCH** (6 major, 1 minor). All defects
were repaired; the verification battery was then re-run in full.

| Repair | Change |
|---|---|
| P1 wrong-loader admission | Every public loader now enforces its concrete artifact type before admission, hashing or parsing (`_require_role`); `load_targets` keeps requiring an explicit `TargetUse`. |
| P2 payload/metadata binding | Numeric payloads must fall inside the declared target/forcing windows and match declared initial anchor dates; reserved-window rows are refused by payload year even under lying metadata; unit and original frequency must be *known* and agree between table, provenance and variable; `goods` is banned in data tables and an optional explicit commodity vocabulary (`DataRegistry.load(allowed_commodities=…)`) is enforced when declared. |
| P3 lineage | Admission requires a real `raw_sha256`; non-synthetic provenance must match the source's institution/dataset/locator and rights fields; `anchor_ids` join `derived_from` in cycle detection; reconstruction anchors must be grade A/B initial-state artifacts (acyclic + every grade B requires anchors ⇒ grounding in grade A); grade-S assumptions cannot anchor anything. |
| P4 prior declarations | `validate_parameter` compares literature_refs, prior_description, bounds.lower/upper, uncertainty_notes and status fields between the prior file and the registry declaration; any disagreement is refused. |
| P5 failed-run honesty | Failed manifests record the RNG draws actually taken at the point of failure (and the modules that took them); the replay digest stays absent rather than invented. |
| P6 SocioVerse round trip | Parquet↔DuckDB equality is content-level (all fields, JSON parsed semantically) and disagreement raises instead of flagging; the doctor gate therefore fails on corruption. |
| P7 dead weight | Removed `EVENT_COLUMNS`, `MICRO_COLUMNS`, `_AGGREGATE_SCHEMA`, `check_core_window`, `import_socioverse`, `SMOKE_TICKS` and the vacuous import-guard test. |

Re-verification after patches (this machine, frozen env):

- `uv run pytest -q` → **103 passed** (89 → 103: +15 adversarial tests covering
  wrong-loader calls with a read spy, hidden reserved rows, unit/vocabulary
  violations, missing raw digests, attribution drift, self/acyclic anchor
  rules, grade-A date binding, prior-file field drift, failure-time draw
  accounting, and Parquet content corruption);
- `uv run ruff check .` → pass; `uv run mypy src/hsm_lab` → strict pass (23 files);
- `hsm run` smoke → completed, 42,000 draws, replay digest `1fda99b1a923320d…`
  unchanged versus the original proof (workload untouched);
- `hsm doctor --socioverse-smoke` → pass with content-level equality true;
- `hsm data audit` → unchanged honest state (`registry_valid=true`,
  `sources_ready=false`, artifacts 0).

The reviewer's original counterexamples (validation TARGET through
`load_forcing`/`load_initial`; 1986 row under 1970-declared metadata; missing
raw digest with wrong attribution; self-anchored grade B; prior-file bounds
[20,30] vs [0,1]; failed manifest reporting zero draws; corrupted
metrics.parquet flagged as matching) all now fail closed.

## 11. Revision 2 — round-2 review patches (R1–R5)

Round-2 independent review verdict: **PATCH** (4 major, 1 minor). Repairs:

| Repair | Change |
|---|---|
| R1 explicit purpose | `load_targets` refuses `None` and non-`TargetUse` purposes at runtime before admission — numeric target access without a declared purpose is impossible, and invalid types get a gate error instead of `AttributeError`. |
| R2 complete rights agreement | Provenance rights must match source rights on every field except free-text `notes` (license_status/name, terms_locator, evidence_quote, checked_at, download_allowed, redistribution_allowed). |
| R3 full failure lifecycle | All fallible setup (RNG construction, array allocation, micro-writer construction) moved inside the protected region; any setup failure converts the `running` manifest into an honest `failed` one (real zero-draw accounting when no draw happened, absent replay digest), and opened writers are closed. |
| R4 complete observations | Frequency-boundary aggregations require Float64, non-null, finite values; undeclared aggregation names raise instead of silently behaving like end-of-period. A complete set of period labels is no longer treated as complete observations. |
| R5 anchor chronology | Anchor comparison keys keep full (year, month, day) granularity — a dated observation on 1960-01-31 is strictly later than 1960-01-01, so posing it as an earlier "observed" state requires grade B reconstruction. No implicit near-date tolerance exists. |

Re-verification after Revision 2: `pytest -q` → **117 passed** (+14 adversarial tests:
purpose None/invalid/type confusion, four rights-field drifts, null/all-null/NaN/Inf/
non-numeric values, undeclared aggregation fallback, within-month chronology, setup
MemoryError, second-writer failure); `ruff` and strict `mypy` pass; CLI smoke digest
unchanged (`1fda99b1a923320d…` — the workload itself is untouched); doctor with the
real SocioVerse store smoke and the offline data audit behave exactly as before.

## 12. Revision 3 — round-3 review patches (N1–N4)

Round-3 independent review verified all five round-2 repairs (R1–R5) as closed and
returned **PATCH** with four new defects. Repairs:

| Repair | Change |
|---|---|
| N1 transitive anchor admission | `load_initial` recursively passes every anchor through the full admission and payload gates (role, rights, raw/artifact digests, payload binding) before returning a reconstruction's numbers. A missing/corrupted/rights-denied anchor anywhere in the chain refuses the descendant. |
| N2 grade-A chronology | Anchor comparison keys now use real calendar endpoints (quarter → its end date, year → Dec 31, dated → validated real dates; `1960-02-31` is refused). Grade A requires the observation to coincide *exactly* with the initial instant — no near-date tolerance is invented; any temporal distance (earlier or later, including mixed-precision pairs like `1960Q1` vs `1960-03-01`) requires grade B/C/S. |
| N3 declared aggregation binding | Frequency-changing artifacts require the variable to declare an aggregation rule, and the transformation's aggregation must equal it; target `comparison_aggregation` must equal a declared variable rule. Identity artifacts are exempt (they aggregate nothing). |
| N4 finite aggregation results | Overflowed aggregations (e.g. summing three 1e308 values) are refused instead of emitting Inf; polars' mean traverses the same overflowing sum and is refused likewise — no fabricated finite substitutes. Representable arithmetic is unchanged. |

Re-verification after Revision 3: `pytest -q` → **129 passed** (+12: multilevel
chain positive, missing/denied/corrupted anchor refusals, ancient and
mixed-precision grade-A refusals, impossible calendar date, transformation-rule
disagreement/undeclared/match, comparison-rule disagreement, overflow refusals);
`ruff` and strict `mypy` pass; CLI smoke digest unchanged
(`1fda99b1a923320d…`); doctor with real SocioVerse store smoke passes.

## 13. Revision 4 — round-4 review patch (D1)

Round-4 review verified N1/N2/N4 closed and N3 partially (one remaining edge), verdict
**PATCH** with the single defect D1: numeric TARGET admission with an undeclared
variable aggregation rule. Repair: `TargetArtifact` numeric admission now *requires*
the variable to declare its aggregation rule and `comparison_aggregation` to equal it
(BASELINE §24: the comparison rule belongs to the variable, not the artifact
declarer). Legitimate target fixtures now declare `sum` explicitly; unacquired
real-data candidates in `data/manifests/variables.yml` keep `aggregation: null` and
therefore remain numerically inadmissible until someone declares the rule.

Re-verification: `pytest -q` → **132 passed** (+3: undeclared-rule refusal for each
of sum/mean/end_of_period); `ruff`/strict `mypy` pass; CLI smoke digest unchanged
(`1fda99b1a923320d…`, 42,000 draws).

## 14. Final gate — independent review verdict

Five independent review rounds (fresh frozen-env audits, executed counterexamples,
full gates each round):

| Round | Verdict | Defects | Fixed in |
|---|---|---|---|
| 1 | PATCH | P1–P7 (6 major, 1 minor) | ae680cf |
| 2 | PATCH | R1–R5 (4 major, 1 minor); P1/P2/P4/P6/P7 verified | 6dcb58d |
| 3 | PATCH | N1–N4 (3 major, 1 minor); R1–R5 verified | 3e171a0 |
| 4 | PATCH | D1 (1 major); N1/N2/N4 verified | bdb4720 |
| 5 | **PASS** | none; P1–P7, R1–R5, N1–N4, D1 all independently verified | — |

Round-5 evidence highlights (reviewer-executed): `uv sync --frozen --no-cache` into a
fresh environment (95 packages, CPython 3.12.14 arm64); pytest **132 passed**; ruff
and strict mypy clean; baseline byte-hash `1f5b23…61b6f` unchanged from the original
commit; doctor with the real offline SocioVerse store smoke passed with API keys
stripped; D1 challenged with three undeclared-rule counterexamples plus six
positive/mismatch controls — all behaved correctly; fresh smoke/scaling benchmarks
reproduced (max peak RSS 224,395,264 B ≈ 0.209 GiB; 10k→20k ratios 1.697/1.759,
no needs_profile; 11/12 scaling cases honestly flagged measurement_too_short);
original and fresh manifests/benchmark artifacts independently verified.

Scope of this verdict: the P00 engineering foundation only. Historical simulation,
calibration, material balance, data acquisition and F2 performance remain
unimplemented and unclaimed.
