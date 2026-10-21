# H4B-ID — deterministic run identity for the strict full-file gate

Status: implementation authorized by the user's 2026-10-21 instruction ("先修确定性身份").
Scope: make same-host, same-commit, fresh-directory material runs byte-identical **under an
opt-in flag**, without changing legacy behavior, replay digests, BASELINE, research contract, or
frozen scenario pins.

## 1. Problem (measured)

Two fresh C0 runs (`historical_f2_replay`, seed 1729) differ in exactly three files:

| File | Cause |
|---|---|
| `manifest.json` | random `run_id` (`uuid4`), wall-clock `started_at`/`finished_at`, dependent output hashes |
| `summary.json` | same random `run_id`, wall/CPU `performance` timings |
| `trajectory.duckdb` | DuckDB single-file format is not byte-deterministic even for identical logical tables (verified in isolation) |

All Parquet tables, `parameters.json`, and `initial_recipe.json` were already byte-identical.

## 2. Design

Add an opt-in `--deterministic-identity` mode to the material runner. Default off; legacy output
bytes and C0/C1 digests remain unchanged.

1. **Content-derived `run_id`** — `sha256` of a canonical tuple containing scenario hash, parameter
   hash, initial recipe hash, input artifact hashes, baseline/lock hashes, seed, households,
   organizations, ticks, engine version, run kind, output policy, and resume boundary if any.
2. **Fixed clock** — `--fixed-clock <ISO-8601>`; default `1970-01-01T00:00:00Z`. Sets
   `started_at` and `finished_at`. Rejected without `--deterministic-identity`.
3. **Zeroed timing fields** — in deterministic mode all `*_wall_s`/`cpu_s` values in
   `summary.performance` are `0.0`; `effective_scalar_updates` and all physical/accounting fields
   stay real. A `"deterministic_identity": true` marker is added inside `performance`.
4. **Deterministic trajectory serialization** — in deterministic mode write
   `trajectory_tables/<table>.parquet` instead of `trajectory.duckdb`. Parquet output is already
   byte-stable across runs; DuckDB is not. `verify_run_identity` already accepts this directory.
5. **Checkpoint paths** — deterministic mode stores checkpoint paths relative to the output
   directory (already the case) and rejects an absolute `--resume` path outside the repository;
   no absolute run-directory path enters the manifest.
6. **Strict gate definition** — two runs on the same commit, same host, same dependency set, same
   working-tree dirty state, different fresh output directories, compared with `diff -rq`. This is
   a same-host reproducibility gate, not a cross-platform bit-reproducibility claim.

## 3. File whitelist

- `docs/phases/HIST_VNEXT/H4B-ID/PLAN.md`, `REPORT.md`, `REVIEW.md`
- `src/hsm_lab/provenance/manifest.py` — deterministic run-id helper; optional fixed timestamps
- `src/hsm_lab/engine/material.py` — opt-in flags, deterministic run-id/clock, zeroed timings
- `src/hsm_lab/storage/output.py` — deterministic trajectory-table writer
- `src/hsm_lab/storage/material_output.py` — select trajectory writer mode
- `src/hsm_lab/cli/app.py` — `--deterministic-identity`, `--fixed-clock`
- `tests/test_hist_deterministic_identity.py` — new tests

No change to BASELINE, research contract, `uv.lock`, scenarios, recipes, targets, or user files.

## 4. Acceptance

1. Two fresh deterministic C0 runs: `diff -rq` exits 0; same for C1.
2. Deterministic C0/C1 `deterministic_replay_digest` and `parameter_hash` equal the frozen pins.
3. `verify_run_identity` passes on a deterministic run with `trajectory_tables/` and no
   `trajectory.duckdb`.
4. Default (legacy) run still writes `trajectory.duckdb`, keeps the same digest, and the existing
   full suite passes.
5. Invalid usage fails closed: `--fixed-clock` without the flag; deterministic mode on a non-material
   scenario; malformed clock.
6. Unit test: identical inputs → identical run id; changed seed/scenario → different run id.
7. Integration test: two short deterministic runs produce byte-identical trees (excluding nothing).
8. Ruff, baseline verify, lock check, full pytest.

## 5. Rollback

The flag defaults off. Reverting the commit restores the previous runner without touching scenario
or frozen files; deterministic outputs are separate new directories and are never overwritten.
