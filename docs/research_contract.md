# Research contract (P00)

The research contract is the frozen, code-enforced boundary between the
project and `BASELINE.md`. It lives in `config/research_contract.json`,
validates into `ResearchContract` (`src/hsm_lab/contract/schemas.py`), and is
checked by `hsm baseline verify` and by every `hsm run`.

## What is pinned

| Item | Value |
|---|---|
| baseline_version | 1.1 |
| expected_baseline_sha256 | `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` (raw bytes of `BASELINE.md`) |
| core window | 1957Q1 .. 1985Q4 (116 quarters) |
| reserved window | 1986Q1 .. 1988Q4 (hold-out; numeric loads refused) |
| spatial nodes | 19 megye + Budapest = 20 regions (BASELINE §5.2 names) |
| macroregions | 6 analysis groups, exact partition of the 20 nodes |
| political modes | historical_replay / endogenous_politics / counterfactual (vocabulary only) |
| output policies | research_full / ensemble_compact |
| research warnings | the two BASELINE epistemic warnings, carried into every run output |

## Gates the contract enforces in code

- **Baseline immutability** — `verify_baseline` hashes the original bytes and
  refuses any run on drift. The pinned hash is never rewritten; a baseline
  version change is a user decision.
- **Time discipline** — `Quarter` accepts only `YYYYQ[1-4]`; scenarios must fit
  the core window; scenario region lists must equal the contract's 20 nodes.
- **Role discipline** — `DataRole` (`exogenous_forcing`, `initial_state`,
  `target`, `latent_parameter`) is decided by variable semantics, never by file
  path. An annual outcome cannot be relabelled into a forcing; targets are
  loaded only through `load_targets(purpose=...)`.
- **Hold-out gate** — reserved-window targets are registered as metadata but
  never numerically loaded, and calibration may not consume
  validation/holdout/reserved targets.
- **Deterministic digests** — `canonical_json` (sorted keys, compact
  separators, UTF-8, no NaN) underpins scenario/data/parameter hashes and the
  synthetic replay digest.

## Scenario

`config/scenarios/smoke.json` is the single implemented scenario: the Toy-4
commodities `energy, capital_goods, food, consumer_goods`, 1000 households,
50 enterprises, 10 ticks from 1957Q1, seed 1729, stochastic, compact policy,
and empty forcing/initial/parameter lists (the P00 workload takes no data
inputs). `kind` is literally `"smoke"`: requesting anything else is a
validation error, not a fallback to a historical run.
