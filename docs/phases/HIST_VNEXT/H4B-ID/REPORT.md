# H4B-ID report — deterministic run identity

## Verdict

| Dimension | Verdict |
|---|---|
| Deterministic identity (opt-in) | **PASS** |
| Strict full-file C0/C1 byte gate, same host/commit/tree, fresh directories | **PASS** |
| Legacy default path | **PASS — unchanged** |
| Checkpoint/resume byte identity | **NOT CLAIMED** — pre-existing checkpoint residual gate fails on `historical_f2_replay` |
| H4B pilot execution | **STILL BLOCKED** — price/investment mapping and H4A runtime/measurement remain open |

This step closes the third H4B blocker **for fresh runs under the declared scope**. It does not run
Pilot A and does not clear the other two technical blockers.

## 1. Measured problem and fix

Before the change, two fresh C0 runs differed only in `manifest.json`, `summary.json`, and
`trajectory.duckdb`:

- random `uuid4` run id;
- wall-clock `started_at`/`finished_at`;
- wall/CPU `performance` values;
- DuckDB single-file bytes (verified in isolation to differ even for identical logical tables).

Implemented, opt-in via `--deterministic-identity`:

| File | Change |
|---|---|
| `src/hsm_lab/provenance/manifest.py` | `content_addressed_run_id()`; injectable `started_at`/`finished_at` |
| `src/hsm_lab/engine/material.py` | deterministic run id (scenario/parameter/recipe/input/baseline/lock hashes, seed, counts, engine, policy, fixed clock, `until`, `checkpoint_every`, resume boundary); fixed clock; zeroed timing fields; deterministic trajectory writer |
| `src/hsm_lab/storage/output.py` | `write_trajectory_tables()` — one Parquet per table |
| `src/hsm_lab/storage/material_output.py` | default DuckDB vs deterministic `trajectory_tables/` selection |
| `src/hsm_lab/cli/app.py` | `--deterministic-identity`, `--fixed-clock`; rejected for smoke/political runs |
| `tests/test_hist_deterministic_identity.py` | 6 new tests |

Default behavior is untouched: no flag → random run id, wall clock, nonzero timings, DuckDB.

## 2. Strict byte evidence

Deterministic run root: `outputs/hist-vnext-h4b-id-20261021T022120Z/runs/`.

| Check | Result |
|---|---|
| C0 pair (`historical_f2_replay`, seed 1729, 116 ticks, clock `2020-01-01T00:00:00Z`) | `diff -rq` **exit 0**, no differences; 32 files, 9,771,034 B each |
| C1 pair (`historical_f2_trade_scenario`, same flags) | `diff -rq` **exit 0**, no differences; 32 files, 9,107,710 B each |
| C0 digest / parameter | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` / `e27ade6a…0445` — frozen pins |
| C1 digest / parameter | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` / `632ee6a6…b90` — frozen pins |
| C0/C1 run ids | `887a6826a9d78a940116c32f4ca98afb` / `512f26408836c95169fd1f1ac930ac66`, identical within each pair; changed `until`, `checkpoint_every`, or fixed clock produces a different id |
| `verify_run_identity` | both **VERIFIED**: `status=completed`, 116 ticks, digests and parameter hashes match |
| Trajectory store | `trajectory_tables/` present; no `trajectory.duckdb` |
| Checkpointed 4Q pair (`--until 1957Q4 --checkpoint-every 1`) | `diff -rq` **exit 0**; run id `109829c14dab9e1a0126f9b98e06120f`; 104 files / 27,691,230 B |

### Legacy control

`hsm run --scenario historical_f2_replay --seed 1729` with no new flags: exit 0, digest
`92f9ea0a…` unchanged, `trajectory.duckdb` present, random run id, nonzero wall fields. 19 files,
20,111,461 B. The default path is not silently rewritten.

## 3. Gate definition and limits

- Equality is **content** equality of every file in two fresh output directories (`diff -rq`),
  same host, same commit, same dependency set, same dirty-tree state. Modification times are not
  part of the comparison.
- Cross-platform bit reproducibility is **not claimed**; `python`/`platform`/dependency fields are
  recorded, not normalized.
- The deterministic mode writes `trajectory_tables/` instead of `trajectory.duckdb`. This is a
  storage-format change, not output normalization, and the verifier already accepts it.
- `--fixed-clock` is bound into the run id, so a different clock produces a different id.
- `--resume`: paths are stored repo-relative, but checkpoint-resume byte identity is **not claimed**.
  The historical scenario's checkpoint currently fails its own `stage_balances` residual gate
  (`checkpoint stage_balances stores a residual beyond tolerance at tick 0 for
  ('bacs_kiskun','g09_basic_food','ready')`). The same failure reproduces on the legacy path without
  the new flags, so it is pre-existing and out of this step's scope.

## 4. Verification log

Evidence root: `outputs/hist-vnext-h4b-id-20261021T022120Z/`.

| Check | Exit | Result |
|---|---:|---|
| `pytest -q tests/test_hist_deterministic_identity.py` | 0 | 6 passed |
| `pytest -q -p no:cacheprovider` | 0 | **1694 passed, 180 warnings, 109.41 s** |
| `ruff check --no-cache src tests` | 0 | All checks passed |
| `hsm baseline verify --json` | 0 | `status=ok`, `1f5b233f…` |
| `uv lock --check --offline` | 0 | 101 packages |
| C0/C1 pair diff | 0 | no differences |
| `verify_run_identity` C0/C1 | 0 | both VERIFIED |
| legacy C0 control | 0 | digest pin unchanged, DuckDB present |

Per-run wall/RSS for the deterministic C0/C1 runs were not instrumented → `NOT_MEASURED`; the
seven-run command block (four C0/C1, two checkpoint, one legacy) took 41.74 s total. Exact command lines are in the evidence `COMMANDS.md`.

## 5. Effect on the H4B blocker certificate

| Blocker | Before | After |
|---|---|---|
| `STRICT_FULL_FILE_BYTE_GATE_UNMET` | UNMET | **CLOSED for fresh runs under the declared same-host scope**; legacy unchanged; resume not claimed |
| `H4A_RUNTIME_MEASUREMENT_NOT_CONNECTED` | BLOCKED | unchanged |
| `PRICE_INVESTMENT_EXECUTION_MAPPING_ABSENT` | BLOCKED | unchanged |

The H4B blocker package remains the accurate record for the other two gates. Do not rewrite the
committed `BLOCKER_CERTIFICATE.json` as if the pilot were now runnable.

## 6. Model/runtime usage

Implementation used the session runtime `deepseek/deepseek-flash`; configured default is MiniMax.
Review uses `phase-reviewer` (`@review`). Tokens/cache/cost are not exposed → `NOT_MEASURED`, not
estimated. No paid fallback.

## 7. Stop

Do not start Pilot A or H4C/H5 from this step. The next executable work is the price/investment
execution bridge under a separately authorized plan.
