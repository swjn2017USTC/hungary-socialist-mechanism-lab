# H4C Pilot B report

Status: **executed; technical PASS; structural mixed/null as reported; historical
`NOT_ESTABLISHED`.**

This report records the actual H4C Pilot B execution only. It does not authorize
Pilot A, H5 or any later stage. No user-dirty file, `.omp/config.yml`, output
directory, source body, target value or sealed window was modified or committed.

## 1. Execution identity

| Item | Value |
|---|---|
| Repository HEAD at start | `603b0da1d084268af29a055443cf5e1b0001dfdf` |
| Pinned BASELINE SHA-256 | `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` |
| Frozen plan | `docs/phases/HIST_VNEXT/H4C/PLAN.md`, SHA-256 `424f4e14f45e4741d9b24568958f16a39eb7f07a22bc41a9a5d0e1fc69f963d5`; source `H4C_PILOT_B_PLAN.md` SHA-256 `275db3fe48bfaef28c71e4a8dac4a9147fc8beef360b8ba294bbfbadb1e50f07` (one extra trailing blank line removed for `git diff --check`; content otherwise byte-identical) |
| Study spec | `studies/HIST_VNEXT/pilot_B/spec.json`, SHA-256 `cf8e4e035edbacfa311c4f86400f546cca2421263e90d2ceddcedf6c651a0b28` |
| Study forcing pack | `studies/HIST_VNEXT/pilot_B/forcing_pack.json`, SHA-256 `cec97170b6e66cd144263f7693d7dd324e16a3518f6fef3a7da372bae2cc7fed` |
| Runner | `studies/HIST_VNEXT/pilot_B/runner.py`, SHA-256 `a2bd9a4c6b07591691a7398fe25e681c67ba55debdded8c6494b7a980042aa4a` |
| H4C tests | `tests/test_hist_pilot_b.py`, SHA-256 `630ceb49cc3faeeb1224184c009a72c2248717e85a71eb8b2f46e265cec70766` |
| Run root | `outputs/hist-vnext-h4c-20261021T082050Z/` (gitignored; not committed) |
| Experiment admission | `exit_code=0`, `structural=PASS`, `admission=EXPERIMENT_ONLY` |

The runner re-ran the H4A-1 admission with the current UTC clock before any
branch state was built. The H4A approval hash scope matched.

## 2. Commands and logs

All commands used the existing `.venv`; no install/sync/upgrade was run.

| Command | Result | Log / artifact |
|---|---|---|
| `python tools/verify_intake.py .` in batch01 | PASS: 112 hashed files; 4 PDFs; 89 native pages; 83 OCR pages; 0 admitted excerpts | `$OUT/batch01_intake.log` |
| `python tools/verify_intake.py .` in batch02 | PASS: 1943 hashed files; 7 originals; 3553 page metadata rows; 368 selected/OCR pages; 70 groups; 0 admitted value records | `$OUT/batch02_intake.log` |
| `python -m history.HIST_VNEXT.h4_sources.experiment_admission ...` | exit 0; `EXPERIMENT_ONLY` | `$OUT/experiment_admission.json` |
| `runner.py --window-ticks 4` | `COMPLETED`, `pilot_id=c4eadca9f320cfa8c66b1b09a14b7b36` | `$OUT/pilot4/` |
| `runner.py --window-ticks 8` | `COMPLETED`, `pilot_id=43701b1c16656ad137c0a3eed34f9d2e` | `$OUT/pilot8/` |
| `runner.py --window-ticks 8` repeat | same `pilot_id`; identical scientific manifest/trace/journal | `$OUT/pilot8_repeat/` |
| `pytest -q -p no:cacheprovider` | **1728 passed**, 180 warnings | `$OUT/pytest_full.log` |
| `ruff check --no-cache src tests studies/HIST_VNEXT/pilot_B` | all checks passed | `$OUT/ruff.log` |
| `hsm baseline verify --json` | `status=ok`; hash equals the pin | `$OUT/baseline_verify.json` |
| `uv lock --check --offline` | resolved 101 packages | `$OUT/uv_lock_check.log` |

Resource measurements are in `pilot4/resources.json`, `pilot8/resources.json` and
the external `/usr/bin/time -l` logs:

| Run | Wall | Peak RSS | Journal rows |
|---|---:|---:|---:|
| Pilot 4Q | 42.7 s | 342,261,760 bytes | 2,415,665 |
| Pilot 8Q | 80.1 s | 378,404,864 bytes | 4,819,281 |
| Pilot 8Q repeat | 80.6 s | 352,534,528 bytes | 4,819,281 |
| Full pytest | 189.6 s | 796,475,392 bytes | — |

The simulation itself makes **zero LLM calls**. The development model selector,
reasoning setting, input/output/cache tokens and monetary cost were not exposed
to this runner or session log; they are **`NOT_MEASURED`**, not 0.

## 3. Branch and forcing identity

| Episode | Warm-up | Window (8Q) | Branch state SHA-256 |
|---|---|---|---|
| `pre75` | 64 ticks to 1973Q1 | 1973Q1–1974Q4 | `7f5d224b14dfbc958ebffabde201f77cd1fa94d3caadf1b2ebc963e0927cb779` |
| `post75` | 72 ticks to 1975Q1 | 1975Q1–1976Q4 | `125f2b3a231ab37304887f2fb72ec6cd91cbc21b68554b0c5afae2d7de1c3b0a` |

The 4Q profile windows are 1973Q1–1973Q4 and 1975Q1–1975Q4. All arms in one
episode receive the same deep-copied branch, network and raw forcing; the
`placebo` and `base` comparison traces and ledgers are identical in both
episodes.

The study forcing copy removes `official_fx` and recomputes `binding_hash` to
`0478afa84659b7a5ae2567fef6e6531cd34d090c94a8dbd55f3c7c8bc5b34e7b`. It uses
the admitted oil, Fed H.15 and reconstructed CMEA artifacts:

- oil: `e1381c632823adef70df51d7e7dcbd32d8be975c11cc5128dd5236ef0ebda7bb`
- Fed H.15: `86578c05e49146968e107b46448802de5b11538a98c1636f6d7fdcd25f0d60cc`
- CMEA reconstructed: `19c9b487b34a9756ec007e44b4e975411393215dbf97b17af57b2fe738e5ed48`

The 1975Q1 anchor is `2.270245328563804`. The model price rule is
`h4c-price-index-v1`: NaN before 1975Q1 (structural prior 1.0), then
`raw_quote[t] / raw_quote[1975Q1]`. This is a model index, not a historical
conversion. No official FX, moving average or interpolation is used.

## 4. Results

### 4.1 First stage (8Q, short / later windows)

Values are cumulative over the window except stocks, which are the last quarter's
close. S is the realized bailout grant, W the realized D1 draw and export
outlay, R the opened receivables (USD and CMEA are kept separately in the machine
result), C the realized g02 CMEA import quantity (`C_import_quantity_g02`, not a
cross-commodity sum), and USD the new external draw.

| Arm | S grant short/later | W draw short/later | R opened short/later | C imports short/later | USD draw short/later |
|---|---:|---:|---:|---:|---:|
| `base` | 0 / 0 | 0 / 0 | 0 / 0 | 8 / 8 | 0 / 0 |
| `s` | 80,638 / 2,392 | 0 / 0 | 0 / 0 | 8 / 8 | 0 / 0 |
| `w` | 0 / 0 | 0 / 0 | 0 / 0 | 8 / 8 | 0 / 0 |
| `r` | 0 / 0 | 0 / 0 | 0 / 0 | 8 / 8 | 0 / 0 |
| `c` | 0 / 0 | 0 / 0 | 0 / 0 | 8 / 2 | 0 / 0 |
| `c_quota20` | 0 / 0 | 0 / 0 | 0 / 0 | 8 / 8 | 0 / 0 |
| `c_price_half` | 0 / 0 | 0 / 0 | 0 / 0 | 8 / 8 | 0 / 0 |
| `c_price_high` | 0 / 0 | 0 / 0 | 0 / 0 | 6.7 / 0 | 0 / 0 |
| `c_term2` | 0 / 0 | 0 / 0 | 0 / 0 | 8 / 2 | 0 / 0 |
| `r_receipt_delay2` | 0 / 0 | 0 / 0 | 0 / 0 | 8 / 8 | 0 / 0 |
| `p_fixed` | 0 / 0 | 0 / 0 | 0 / 0 | 8 / 8 | 0 / 0 |
| `p_spot` | 0 / 0 | 0 / 0 | 0 / 0 | 6.2 / 5.6 | 0 / 0 |
| `usd_limit_probe` | 0 / 0 | 0 / 0 | 0 / 0 | 8 / 8 | 0 / 0 |

`pre75` is the same pattern with its own branch. The joint arms `sw`, `sr`, `sc`
report the S grant and their single supported H3F mechanism; `sw`/`sr` are
observed only through S because their W/R first stage is zero.

### 4.2 What the run actually shows

1. **CMEA imports are real and cumulative under D3.** `c` exhausts its quota 10
   in the later window: the final position is `-10`, five import entries, and
   the later window realizes 2 units before the quota binds. `c_quota20`
   continues importing 8 in the later window. `c_price_high` exhausts faster;
   `c_price_half` does not bind in this window. This is a genuine
   quota/price first stage.
2. **D3 import obligations are not extinguished.** Every import entry keeps
   `settled=0`; export settlement does not pay imports. This is reported as
   `NOT_IMPLEMENTED`, not as a paid import.
3. **D1 is a real zero, not a fabricated draw.** The simulated export demand
   cells allocate the requested 2 units but are physically blocked. The per-tick
   trace records, in `trade_channels.cmea_export` and
   `.convertible_export`, `desired=2.0`, `ordered=2.0`, `delivered=0.0`,
   `physical_delivery_blocked=2.0`, so the discarded-kernel D1 probe sees no
   incremental outlay. `W` draws 0 in both episodes. The tiny P02 fixture
   (below) proves the D1 bridge itself can draw and service when a deliverable
   export exists.
4. **D2 is a real zero.** With no delivered export there is no receivable and no
   receipt. The D2 interface and the study's delayed-receipt rule are tested on
   the tiny P02 fixture, not inferred from the F2 null.
5. **S is active.** `s` grants about 80.6k in the first 4 quarters and 2.4k in
   the later 4 quarters of `post75`. The total grant is invariant at
   `83,029.55` in both episodes; `s_envelope50` shifts the same total earlier
   (83,025 in the first 4 quarters vs 80,638 for `s`) because the envelope is
   constrained by available Treasury cash. The grant is a Treasury→enterprise
   bailout of existing claims, not an import subsidy.
6. **The price rules separate.** `p_spot` imports less than `base`/`p_fixed`
   under the higher post-1975 oil index; `p_fixed` matches the fixed 1.0 rule.
7. **New USD financing is zero.** Even with desired convertible imports 2 and
   `convertible_loan_limit=4`, `usd_limit_probe` draws 0 and pays 0 in both
   episodes. The code path is the P02 `COMMODITY_INDEX` gap, not a market
   result. New F2 external financing remains `REDESIGN`.
8. **Repeat and placebo controls pass.** The 8Q repeat has the same
   `pilot_id=43701b1c16656ad137c0a3eed34f9d2e`, the same scientific digest, and
   byte-identical `trace.jsonl`/`journal.parquet`. The 4Q reverse-order and
   single-arm tests give the same per-arm trace/ledger hashes.

## 5. Verdicts (three dimensions)

| Dimension | Verdict | Scope |
|---|---|---|
| Technical | **PASS** | All 20 declared arms ran in both episodes; every tick passed the existing material/finance invariant gate; no fallback; atomic rollback tests pass. |
| Structural | **MIXED / NULL WHERE OBSERVED** | D3 imports/quota and S grants are nonzero first stages. D1/D2 are structural nulls on this F2 branch because export delivery is physically blocked. No welfare interpretation is attached. |
| Historical | **NOT_ESTABLISHED** | The branches are model-generated; the parameters are experiment settings; the sources are metadata-only; the approved-excerpt set is empty. |

## 6. Not run / redesign

The following are explicit, not silently missing:

- `D1+D2`, `D1+D3`, `D2+D3`, all-four joint active: **REDESIGN** (the kernel
  rejects the combinations).
- D3 dynamic contract repricing, import-obligation extinguishment, formal
  rollover: **NOT_IMPLEMENTED**.
- D2/D3 heterogeneous terms: **NOT_RUN** (one frozen term per D2/D3 regime and
  one D1 facility).
- New F2 USD external financing: **REDESIGN** (COMMODITY_INDEX gap).
- Import price subsidy via S: **NOT_RUN** (S is a bailout).
- 1977–1978: **NOT_RUN**; 1979–1985 is **NOT_OBSERVED** and is not opened for
  pilot interpretation.

## 7. Tests

`tests/test_hist_pilot_b.py` has 21 tests:

- 15 `tiny4q` tests on the real P02 fixture: D1 real draw/limit/window/no-stock/
  no-demand/rollback; D2 delivery, due/overdue, delayed receipt, gross closure,
  term-0 schema rejection and rollback; D3 cumulative quota, zero quota, frozen
  price, early-settlement rejection, `settle_export` event-id shape, and
  import-obligation retention; per-commodity `used` grouping.
- 6 runner tests: invalid window/unknown/duplicate/empty selection, existing
  output, path escape, full 20-arm 4Q completeness, shared branch/raw forcing,
  placebo equality, real first-stage/null reporting, end-of-window stock
  semantics, repeat/reverse/single-arm identity.

The plan-required subset also passes:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_hist_pilot_b.py tests/test_hist_export_finance.py \
  tests/test_hist_export_receivables.py tests/test_hist_cmea_clearing.py \
  tests/test_hist_h4a_runtime.py tests/test_hist_deterministic_identity.py
```

## 8. C0/C1 fresh regression and identity

| Check | Result |
|---|---|
| `C0` digest | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` |
| `C1` digest | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` |
| `C0` parameter hash | `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445` |
| `C1` parameter hash | `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90` |
| `verify_run_identity` C0/C1 | accepted the expected digests from the real manifests/outputs |
| `diff -rq C0a C0b` | empty |
| `diff -rq C1a C1b` | empty |

These fresh deterministic pairs are same-host/same-version full-file checks.
They do **not** establish checkpoint-resume identity, cross-platform byte
identity, or a repair of the old D3 full-file issue. Canonical, checkpoint,
full-file and digest scopes are separate; a digest match is not by itself
strict full-file identity.

## 9. Known limitations

- The F2 branch has no historically observed 1973/1975 initial state.
- The D1/D2 mechanisms are structurally null on this branch because the export
  demand is physically blocked; the tiny fixture proves the bridge, not a
  historical effect.
- H3G's same-tick procurement→household structural null remains a recorded
  limitation; no standalone H3G `REVIEW.md` exists.
- The study does not estimate a historical contract price, term, quota,
  subsidy envelope or welfare effect.
