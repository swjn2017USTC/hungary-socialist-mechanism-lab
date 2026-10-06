# hsm-lab — Hungary Socialist Mechanism Lab (P00 foundation)

Research simulation foundation for the 1957–1989 Hungary project defined in
`BASELINE.md`. **P00 delivers engineering contracts only**: research data
roles/provenance/admission, a deterministic RNG registry, run manifests, a
synthetic smoke workload and benchmarks. No historical simulation exists yet —
see `docs/phases/P00_REPORT.md`.

> Simulation is an argument, not evidence.
> A probability produced by an agent or decision model is not a historical probability.

## Layout

- `src/hsm_lab/contract/` — research contract schema + baseline byte-hash gate
- `src/hsm_lab/data/` — source/rights/provenance schemas, registry admission, audit, frequency boundaries
- `src/hsm_lab/provenance/` — run manifests and canonical digests
- `src/hsm_lab/engine/` — RNG registry and the synthetic smoke workload
- `src/hsm_lab/storage/` — Parquet + DuckDB writers (compact/full policies)
- `src/hsm_lab/integrations/socioverse.py` — lazy, real SocioVerse2 store smoke
- `src/hsm_lab/cli/`, `src/hsm_lab/benchmarks/` — Typer CLI and isolated benchmark harness
- `config/`, `data/manifests/` — pinned contract, scenario, benchmark and registry manifests
- `outputs/` — local run artifacts (gitignored)

## Setup

```bash
uv sync --frozen      # Python 3.12, locked dependencies
```

## Commands (run from the repo root)

```bash
uv run pytest -q                                # behaviour-gate tests
uv run ruff check .                             # lint
uv run mypy src/hsm_lab                         # strict types
uv run hsm --help                               # CLI tree
uv run hsm baseline verify --json               # BASELINE.md byte-hash gate
uv run hsm doctor --json                        # env/deps/contract/lock checks
uv run hsm doctor --socioverse-smoke --json     # real SocioVerse2 store smoke
uv run hsm data audit --json                    # offline registry audit
uv run hsm run --scenario smoke --seed 1729 --json
uv run hsm benchmark smoke --json
uv run hsm benchmark scaling --json
```

Exit codes: `0` success, `1` environment/I-O/research-gate failure,
`2` input/config validation failure. All commands accept `--json` and print a
single JSON object on stdout.

## Non-goals (P00)

No historical core, no Toy-4 material loop, no calibration/ABC/sensitivity, no
1986–88 unlock, no microdata downloads (TÁRKI/OSA untouched), no LLM agents.
Data registry entries are candidates with rights metadata — no dataset has
been obtained or admitted.
