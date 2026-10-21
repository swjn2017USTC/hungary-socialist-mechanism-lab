# H4C Pilot B independent review

**Final verdict: PASS**

Reviewer role: `@review` independent read-only phase review (`phase-reviewer`).
Reviewers did not edit implementation, test, spec or data files. This file is
the authoritative review record; the four review rounds are summarized below.

## 1. Scope and identity reviewed

| Item | Value |
|---|---|
| HEAD | `603b0da1d084268af29a055443cf5e1b0001dfdf` |
| BASELINE SHA-256 | `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` |
| Frozen plan | `docs/phases/HIST_VNEXT/H4C/PLAN.md`, SHA-256 `424f4e14f45e4741d9b24568958f16a39eb7f07a22bc41a9a5d0e1fc69f963d5`; source SHA-256 `275db3fe48bfaef28c71e4a8dac4a9147fc8beef360b8ba294bbfbadb1e50f07` (one trailing blank line normalized; content otherwise identical) |
| Final run root | `outputs/hist-vnext-h4c-20261021T082050Z/` (gitignored) |
| Pilot 4Q | `pilot_id=c4eadca9f320cfa8c66b1b09a14b7b36` |
| Pilot 8Q | `pilot_id=43701b1c16656ad137c0a3eed34f9d2e` |
| Pilot 8Q repeat | `pilot_id=43701b1c16656ad137c0a3eed34f9d2e` |
| Branch hashes | pre75 `7f5d224b14dfbc958ebffabde201f77cd1fa94d3caadf1b2ebc963e0927cb779`; post75 `125f2b3a231ab37304887f2fb72ec6cd91cbc21b68554b0c5afae2d7de1c3b0a` |
| Full verification | 1728 pytest passed; ruff clean; baseline verify ok; `uv lock --check --offline` ok |
| H4C test file | 21 tests passed after the final assertion tightening |

The reviewer confirmed the whitelist: only
`studies/HIST_VNEXT/pilot_B/{runner.py,spec.json,forcing_pack.json}`,
`tests/test_hist_pilot_b.py`, and `docs/phases/HIST_VNEXT/H4C/` are new phase
artifacts. User-dirty `.omp/config.yml`, `05`, `06`, the pre-existing root PLAN
files, and `09_BATCH02_YEARBOOKS_D08_D10_INTAKE.md` were not touched. No
`src/`, config, history, institutions, old test, old doc, lock or source-package
edit was made.

## 2. Final PASS evidence

The final review independently checked:

- **Forcing admission.** `forcing_pack.json` copies the three admitted external
  artifacts, omits `official_fx`, and recomputes the binding hash to
  `0478afa84659b7a5ae2567fef6e6531cd34d090c94a8dbd55f3c7c8bc5b34e7b`.
  The loaded FX array is all-NaN; the runner refuses non-NaN FX. The 1975Q1
  anchor is `2.270245328563804`.
- **Branches and arms.** Two independent 64/72-tick branches, 20 arms in each
  episode, correct 4Q/8Q windows, shared branch/raw forcing, and identical
  placebo/base comparison traces and ledgers.
- **Repeat identity.** `pilot8` and `pilot8_repeat` have the same scientific
  digest; `trace.jsonl` and `journal.parquet` are byte-identical (runtime
  timestamps excluded as intended).
- **Real executors.** The runner calls the existing D0/D1/D2/D3 executors and
  the existing bailout path; there is no second finance implementation.
- **First stage.** D3 imports/quota and S grants are real. D1 and D2 are honest
  structural nulls on this F2 branch because the g02 export demand cells are
  physically blocked (`trade_channels.*.physical_delivery_blocked=2.0`); the
  tiny P02 fixture proves the D1/D2 bridges themselves. The USD probe draws 0
  with desired imports 2 and limit 4, matching the code boundary.
- **Aggregation.** Per-commodity stocks are end-of-window, not sums; `used`
  excludes destination `-1` household rows and maps the two export channels
  explicitly; C quantity is `C_import_quantity_g02` plus a per-commodity map,
  not a cross-commodity sum. USD and CMEA amounts are never added.
- **D2/D3 semantics.** D2 uses `lot.gross` (engine outstanding) for selection
  and amount; `d2_lots.outstanding` is `lot.gross`; D3 event ids use
  `settle_export`; import obligations remain `settled=0` with
  `d2_import_obligation_extinguishment=NOT_IMPLEMENTED`.
- **C0/C1.** Digests `92f9ea0a...a42d` / `c4810481...18d5`, parameter hashes
  `e27ade6a...0445` / `632ee6a6...3b90`; `verify_run_identity` accepted both;
  `diff -rq C0a C0b` and `C1a C1b` are empty. This is a fresh same-host
  full-file check, not a checkpoint-resume or cross-platform claim.
- **Three-dimensional verdict.** Technical PASS; structural mixed/null as
  reported; historical `NOT_ESTABLISHED`. The joint D1+D2, D1+D3, D2+D3,
  all-four, dynamic D3 repricing, import extinguishment, rollover and new F2
  USD financing rows remain `REDESIGN` / `NOT_IMPLEMENTED` / `NOT_RUN` as
  listed in `PILOT_RESULT.json` and `REPORT.md`.
- **Document consistency.** `REPORT.md`, `PILOT_RESULT.json`,
  `INPUT_MANIFEST.json`, `MEASUREMENT_MANIFEST.json`, `ASSUMPTION_LEDGER.md`
  and `ORIGINAL_COVERAGE.md` agree on identities, hashes, statuses, units and
  the no-aggregation rules.

## 3. Review rounds and repairs

| Round | Verdict | Defect(s) | Repair |
|---|---|---|---|
| 1 | PATCH | End-of-window stocks were summed; C imports were summed across commodities; trace lacked `desired/ordered/delivered/blocked`; D2 selected on outstanding rather than `lot.gross`; D3 event id used `settle` | Stock now last close; C is g02 + per-commodity map; trace and `trade_channels` added; D2/D3 rule and id corrected |
| 2 | PATCH | `used` still grouped destination `-1` into g02; `d2_lots.outstanding` double-subtracted receipts; D3 event-id test was circular; `c0_c1_run_root` stale; `s_envelope50` "grants more" false; measurement quota field missing | `used` uses the demand helper; outstanding is `lot.gross`; D3 test calls `_d3_events`; root pointer, S timing wording and quota fields corrected |
| 3 | PATCH | REPORT said D2/D3 heterogeneous terms were `NOT_IMPLEMENTED` while runner/PILOT_RESULT say `NOT_RUN` | Sentence split; statuses now identical |
| 4 | **PASS** | None | — |

The second and third repairs changed only trace/summary fields, tests and docs;
the final pilots were rerun after the functional repairs, and the full gates
were rerun after the final runner change.

## 4. Provenance note

`INPUT_MANIFEST.json` records `tests_sha256 =
630ceb49cc3faeeb1224184c009a72c2248717e85a71eb8b2f46e265cec70766`, the
test revision whose full suite produced the logged 1728 passes. The current
tree adds only the quota assertion inside an existing test and hashes
`6b9e6a2001da20e47745841112d06c72b0a15305e2df9c56f162c298170a473a`; the H4C
suite was rerun after that edit (21 passed). No runner, spec, forcing, source or
output changed.

## 5. Historical and interpretive limits

This PASS is a technical and documentary PASS for the supported runner and
gates. It does not establish a historical Hungarian subsidy envelope, contract
term, quota, price, export delivery or welfare effect. The branches are
model-generated; the source evidence is metadata-only; approved excerpts are
empty; D06/D07/D17 are missing; H3G's same-tick household null remains a
recorded limitation. No target, sealed window or official FX was read.
