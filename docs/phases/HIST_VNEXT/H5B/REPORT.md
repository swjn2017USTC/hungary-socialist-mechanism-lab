# H5B M04 — Second-Economy F2 Recipe and Opportunity Cost

> Historical status: **UNIDENTIFIED**.  This is a synthetic structural
> experiment on the declared `f2_v1` commodity axis.  No primary source is
> admitted, no parameter is calibrated, and no output below is a historical
> Hungarian estimate.  The old M4 card's net-stabilisation/erosion composite
> is not claimed as measured; only the real F2 material, cash, time and
> delivery components are reported.

## 1. Frozen inputs

| Input | SHA-256 |
|---|---|
| `BASELINE.md` | `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` |
| `config/research_contract.json` | `6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82` |
| `uv.lock` | `9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9` |
| `config/p06/cards/M4.json` | `c9e70e5ca07bca8e7865f274dc052cb1ed5aed795787a9a07f16ec37fb5323ac` |
| `config/scenarios/historical_f2_replay.json` | `c58cdc794b1409f0d4da650e324edebe0757f8bf652fc010f656a12c14f69c3c` |
| `studies/HIST_VNEXT/M04/PLAN.md` | `f8f8c9f721eac86c618909abb792e275fcd0c33a6fa850ec7f18bbaa17b68519` |

All protected bytes were re-checked by `runner.py verify`; the C0/C1 reference
runs remain at 116 ticks through 1985Q4 with their original deterministic
digests and parameter hashes, and the F1 `intermediate8` four-quarter run is
byte-identical before/after the H5B engine hooks.

## 2. Design

- Source: `historical_f2_replay`, synthetic initial state and admitted forcing
  pack, shrunk **in memory** to 1 000 households and 4/16 ticks.  Scenario and
  forcing files are never mutated.
- Household axis: `f2_v1` (15 channels over the 16-commodity F2 axis).
- Recipe `hist-vnext-m04-nonplot-v1` (structural assumption, not calibrated):
  inputs `g02_oil_gas_fuels=0.02`, `g04_basic_metals_materials=0.03` per
  activity; outputs `g11_textiles_footwear=0.10`, `g15_market_services=0.25`;
  4 hours/activity, capacity 10 activities per participating worker.
- Arms: `tolerance_0`, `tolerance_05`, `tolerance_1` = raw
  `second_economy_tolerance` 0.0, 0.5, 1.0.  All other policy coordinates are
  fixed.
- Seeds: 1729, 1730, 1731.  Per-seed opening state, network and forcing are
  built once and deep-copied per arm.  Seeds are household-heterogeneity
  repetitions, not independent historical samples.

## 3. What the engine does

- The F2 recipe is a frozen named-commodity view attached to the reviewed
  `MaterialNetwork`; the original network dataclass field table and matrices
  are unchanged, and no non-F2 caller dispatches into the adapter.
- Planning multiplies requested second-economy hours by the raw tolerance,
  keeps formal hours fixed, and jointly compresses plot + second requests
  against the residual household endowment.  Queue/search draw only from the
  remaining time; leisure is the residual.
- Settlement buys inputs only from organisation-owned output/wholesale/retail
  cells (never plot ready-market, Treasury/import, input or WIP cells), funds
  them from the participating working cohort in proportion to positive cash,
  writes the real cell-level `second_input_used`, pays the selling
  organisations, and produces into `second_output_stock`.
- Household allocation splits formal and second substitution sources, consumes
  each real shelf at most once, pays second-economy sales only to the
  participating working cohort using the working share (no double weight), and
  keeps plot self-use, plot direct sale, formal retail and the non-plot second
  pool mutually exclusive.
- Non-stockable F2 services (`g15_market_services`) expire at quarter end;
  `g11_textiles_footwear` remains in stock.  Expiry is taken from the
  commodity spec's `stockable` flag, not a legacy string.
- `check_f2_second_economy` runs after the existing material gate every tick:
  per-region/commodity pool identity, per-region input use, reserved-hour
  bound, funding-to-seller closure, direct-sale receipts and journal
  counterparties.  The trace is bound to the current tick and recipe hash.

## 4. Realised results (16 ticks × 3 seeds × 3 arms = 144 admitted ticks)

Every tick passed both `check_material_invariants` and the F2 pool/ledger
checker; no seed or arm failed.  Max F2 pool residual was `1.14e-13`; max
input residual was `1.42e-14`.

Mean over the three seeds (sums across the 16 ticks):

| Arm | activity | produced g11 | produced g15 | input use | funding | end g11 pool |
|---|---:|---:|---:|---:|---:|---:|
| `tolerance_0` | 0 | 0 | 0 | 0 | 0 | `~0` |
| `tolerance_05` | 305 371 | 30 537 | 76 343 | 15 268 | 24 430 | 19 732 |
| `tolerance_1` | 370 737 | 37 074 | 92 684 | 18 537 | 29 659 | 25 752 |

The zero arm is an exact negative control: no reserved second hours, no input
purchase, no production, no funding.  Reserved second hours do halve between
the full and half arms (281 526 vs 562 420, ratio 0.501), but realised
activity and material throughput are 0.824× (the full arm saturates the
10-activities-per-worker capacity ceiling from tick 1, while the half arm
remains labour-bound).  The tolerance ordering is the same in every seed.
This is a first-stage structural response with a capacity ceiling, not
evidence about historical Hungarian second-economy size.

## 5. Counterexamples reproduced before the green path

`reproduce` (saved under `outputs/hist-vnext-h5b-20261021T145305Z/reproduce-final/`):

| Case | Observed |
|---|---|
| F2 network without opt-in | second input/output tuples empty |
| F2 attach | inputs `(1,3)` = g02/g04; outputs `(10,14)` = g11/g15; parent unchanged |
| Endowment equals formal hours | plot and second reserved hours = 0 |
| Four durable shortages, one repair shelf | analytic counterfactual: the legacy formula would consume 4 units; F2 room split consumes ≤1 (legacy loop not executed) |

The permanent tests also cover non-unit-weight receipts (`[0.875, 1.75]`
for weights `[2,3]`, working `[1,2]`, sale 7), zero participants/cash/input,
joint time compression, formal/second substitution exclusivity, the stockable
expiry, and trace tampering.

## 6. Verdicts

| Dimension | Verdict | Basis |
|---|---|---|
| Technical | **VERIFIED_BY_RUN** | 144/144 study ticks pass both gates; C0/C1/F1 identity re-verified; full suite passed |
| Structural | **FIRST_STAGE_SUPPORTED** (with capacity ceiling) | tolerance 0 < 0.5 < 1 raises reserved second hours, real input use, production and funding in all three seeds; the full arm saturates the 10-activities/worker ceiling |
| Historical | **UNIDENTIFIED** | no admitted primary source; recipe/participation are declared structural assumptions |
| Calibration | **NOT_RUN** | no calibration target admitted |

Not claimed: historical second-economy size or stability, welfare/political
support, a full M4 net-stabilisation composite, or a formal-effort production
feedback (the existing `household_formal_effort` field still has no producer).

## 7. Evidence and limits

- Commands are logged under `outputs/hist-vnext-h5b-20261021T145305Z/runs/`
  with argv, cwd, allowlisted env, exit status, wall time, sampled process-tree
  RSS and output bytes.
- `verification-final/verification.json` re-hashes the artefacts and records
  C0/C1 identity, F1 before/after equality and all protected hashes.
- `EVIDENCE_MANIFEST.json` binds the committable source/test/study bytes; it
  excludes itself and the verification output directory to avoid a hash cycle.
- No target, sealed-window or restricted historical file was read.
- Legacy C0/C1 and F1 paths are unchanged; no state/storage/accounting/finance
  schema was modified.

### 7.1 Process provenance

- The first implementation session hit the 3600 s timeout
  (`runs/impl/usage.json`: `status=timeout`, `exit_code=-9`,
  `wall_s=3600.084`).  It had already written the first adapter/engine/test/
  runner/spec versions.  The scheduler then completed the implementation
  between 23:54 and 00:12 (engine hooks, allocator branch, tests, runner,
  spec, report) before the round-1 independent review; this is a documented
  process deviation from the single-session rule, not a claim that the
  timeout itself produced those bytes.  The round-1 reviewer inspected the
  resulting bytes and returned PATCH.
- Partial first-session usage, extracted by the scheduler from
  `runs/impl/stdout.log` (killed mid-turn, so labelled partial): 408 assistant
  usages, input 385 629, output 214 669, cache-read 82 828 226, total
  83 428 524 tokens, cost 5.3429851 (USD units as reported by the CLI).
- The round-1 checker hardening (produced/expiry re-derivation, per-household
  receipts, direct-sale leg matching) was applied in a separate, explicit
  `minimax-code-cn/MiniMax-M3` fix session after that PATCH.
- Fix-session metadata (`runs/fix-impl/stdout.log`): 91 assistant turns,
  input 146 233, output 67 563, cache-read 9 207 860, total 9 421 656 tokens,
  cost 0.6774171.
- The round-2 PATCH repairs (funding/input-journal anchoring, report number,
  runner evidence/spec binding, provenance, `REVIEW.md`, hygiene) were applied
  after the round-2 review.
- The round-3 review found a real regression: the new funding-shape anchor
  rejected the legitimate no-activity trace, so the then-current study
  admitted only 96/144 ticks (all `tolerance_0` arms PARTIAL at tick 0).  The
  fix writes full-length zero `funding`/`seller_credit` arrays, adds a
  zero-activity integration test, and makes the runner reject any arm whose
  status is not `COMPLETED` or whose `completed_ticks` differs from the
  declared tick count.  The superseded 96/144 artifact is retained only as
  review history in `REVIEW.md`; the final study is 144/144.
- The round-3/4 repairs were applied by the scheduler and the final regression
  was re-run and recorded.  The process deviation is recorded here rather
  than hidden in the manifest.
