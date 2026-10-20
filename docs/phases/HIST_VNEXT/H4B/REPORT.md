# H4B Pilot A report — technical blocker delivery

## Verdict

| Dimension | Verdict |
|---|---|
| Evidence/blocker package | **REVIEWABLE** (pending independent review) |
| Pilot execution | **BLOCKED** |
| Technical | **BLOCKED** — price/investment execution mapping absent; H4A runtime/measurement not connected |
| Structural | **NOT_RUN** — no H4B arm executed |
| Historical | **NOT_ESTABLISHED / UNIDENTIFIED** |

This step did **not** run Pilot A, produce a run id, trace, paired delta, first stage, seed outcome,
or resource profile. That is the intended deliverable: a complete, auditable blocker package rather
than a procurement-only or global-scalar stand-in presented as a three-mechanism pilot.

## 1. Start state and policy

| Item | Observed |
|---|---|
| HEAD / branch | `92d727f8762e6493db0ac5ac2634cdbb13f3597b` / `codex/audit-hsm-vnext-2026-10-11` |
| Tracked dirty | `.omp/config.yml` (`2e90b9c6…`), 05 (`bc45bc84…`), 06 (`5fcb75b4…`) |
| Untracked user files | `09_BATCH02…md` and 12 root `*_PLAN.md` (11 pre-existing + this step's plan); none staged |
| Policy hashes | 05 and 06 match the frozen plan values exactly |
| Frozen files | `BASELINE.md` `1f5b233f…`, `config/research_contract.json` `6f54522a…`, `uv.lock` `9fd79b62…` — all match |

The H4A-1 REVIEW line 62 staging requirement does not apply: the H1A repair files are not dirty at
this HEAD. No user change was reset, overwritten, or staged.

## 2. What was read

Read at metadata level only: batch01/batch02 README, manifest, page indexes, QA, deferred archives,
exposure/access, TABLE_LOCATOR, D08 anchor notes; H4A-0 source/candidate/shared/measurement
registries; H4A-1 declaration, actual-input manifest, approval and final review; H1A/H1B/H2A/H2B/
H3A–H3G final technical records; the cited code anchors; 05/06/08/09.

Not opened: original PDFs, OCR/native body, HOLD pages, sealed targets, private value payloads. Both
source packages report **0 admitted excerpts**. No numeric value was transcribed or admitted.

### Inherited access deviation (disclosed, not repaired)

During planning, the `EvidenceIntake` subagent self-reports that, after confirming the approved
excerpt set was empty, it opened candidate native text for D01 pp. 10–18, D02-ch02 pp. 1–2, 1968
yearbook pp. 105/106/144/272/350/351 and 1975 yearbook p. 120, and passed some candidate content to
the main agent. This is recorded in `SOURCE_MANIFEST.json#access_deviations` with paths and pages.

Consequences, as required:

- No proposition, numeric value, candidate selection, or parameter in this package derives from
  those reads.
- Those pages are not treated as unseen; blindness is not restored and no retrospective approval is
  implied.
- The subagent reports no image/OCR/original/HOLD/sealed-target access and no file writes; this is a
  self-report and was **not** independently verified.
- This step did not re-read those pages to repair the deviation and did not wait for substitute
  excerpts.

H4A-0 LOG-002/003 already records analogous inadvertent native-text reads of 1960/371, 1960/372 and
1968/367; those remain disclosed and unratified.

## 3. Authority findings

Full row-by-row evidence is in `ORIGINAL_AUTHORITY_MATRIX.md`. The decisive result:

- **1968 procurement / price categories / investment approval:** candidate secondary locations exist
  (D01, D02-ch02), but the read level is metadata only and the approved-excerpt set is empty. The
  narrowest supported proposition is **none**. No organization scope, commodity coverage, category
  list, approval threshold, or effective date is established.
- **1972/1973/1974/1975/1976:** no read page establishes an institutional adjustment. The 1973
  yearbook pp. 94–97 are one **1972** IO matrix in organizational delimitation, not a reform act and
  not a 1973 observation. The 1975 p. 120 definition change is not behavioural-mechanism evidence.
  The 1978 p. 370 statement is a comparison-price basis change (a measurement fact). No unified
  "recentralization" is synthesized.
- **Enterprise implementation chain:** D03/D04/D05/D16 are absent. The only executable chain is the
  **synthetic** H2B procurement bridge, which is not a historical firm.
- **Model vs history:** H1B synthetic grants are fixtures (`synthetic_flag=true`, source
  `synthetic_h1b_design_note`). They may be queried but are not historical authority. Historical
  authority stays `UNIDENTIFIED`.

## 4. Frozen competing settings

`ASSUMPTION_LEDGER.md` freezes:

- `A_delegated_choice` — authority transmitted through actual procurement, price proposal, and
  project approval/decision.
- `B_binding_bottlenecks` — nominal authority changes absorbed by money, inventory, transport, or
  approval scope; explicitly not a single NEM autonomy scalar.
- Procurement axis `granted/revoked/unknown` (`unknown` = undecidable → not executed, not central
  approval); price `fixed/authorized-adjustment`; investment `central-approval/delegated-approval`.
- Paired design: same initial state, same external forcing, seed 1729, singles plus combination,
  no-permission-change control, procurement-revocation arm. Local 4Q window per dated institutional
  point; no 1957→1968 rename; no sealed target.
- Numeric price magnitudes and approval amounts/waits: `UNIDENTIFIED`. No percentage is invented.

All arms are `NOT_RUN` because of the technical gates below, not because of missing originals.

## 5. Technical blockers (see `BLOCKER_CERTIFICATE.json`)

### 5.1 `H4A_RUNTIME_MEASUREMENT_NOT_CONNECTED`

- H4A-0 `APPROVED_INPUT_SET.json`: all three approved sets empty.
- H4A-1 `ACTUAL_INPUT_MANIFEST.json`: three records are `approved_but_unconsumed`;
  `consumed_by_model=[]`; `runtime_connected=false`.
- H4A-1 REVIEW:60: PASS does not authorize production initialization, measurement wiring, runtime
  connection, or any historical claim.
- The CLI below exits 0/`EXPERIMENT_ONLY` with 3 approved inputs, 0 historical inputs,
  `runtime_connected=false`, `errors=[]`. That proves the approval is valid and still declarative —
  not that runtime is connected.
- The nine measurement mappings are definition-only (`1 proxy`, `8 no_counterpart`); no missing value
  is an observed zero.

### 5.2 `PRICE_INVESTMENT_EXECUTION_MAPPING_ABSENT`

- `src/hsm_lab/institutions/execution_adapter.py:363–371` accepts only an exact
  `ProcurementDecision`; other types return `is_committed=false` with the real reason "no existing
  TickControls mapping for this decision type; the minimal H2B bridge currently supports procurement
  requests".
- H2B REVIEW "Known limits" confirms price and investment decisions are not bridged.
- `engine/policy.py:89–94` applies one global `admin_price_factor`; `:100–102` scales `hunger_base`
  by one global `investment_intensity`. Neither is per-category price authority or per-project
  approval.
- `engine/finance.py:1611–1615` approves `min(requested, remaining_budget/unit_cost)`;
  `engine/material.py:1594–1605` forms `new_request` from capacity × hunger. No per-enterprise
  project approval exists.
- Schema/authority-query availability is not an execution path.

### 5.3 `STRICT_FULL_FILE_BYTE_GATE_UNMET`

- H3F-D3 REVIEW:8–11,75–80 and H4A-1 REPORT:177–195 keep strict full-file bytes **UNMET**.
- H4A-1 PLAN:75 forbids normalization, provenance changes, re-pinning, or citing a P06 waiver.
- 06 line 212 provides no exception; no applicable waiver was found.
- The new C0/C1 digest runs are a different regression check and do **not** close this gate.

### 5.4 H3G scope and missing review

`H3G/REPORT.md` records a same-tick household `realized/unmet` structural null in its synthetic 4Q
procurement profile: forced-order sweeps up to 1,000,000 units move edge deliveries but household
realized/unmet by exactly 0.0; production is exogenous with no recipe/investment optimization. The
report claims an independent PASS, but **`H3G/REVIEW.md` does not exist**. This step records both the
existing structural null (only in that scope) and the missing standalone review. It does not
extrapolate the null to all later quarters and does not merge it with any H4B null.

### 5.5 P06 collapsed snapshot

`config/calibration/p06_clearance.json:22–29,48–58` retains the F2 closure `collapsed` /
`output_liveness=0.0` and the reproduction-only scope. Not re-measured here. It is neither a
missing-original blocker nor an H4 byte waiver. Even a non-zero local procurement first stage would
not license a historical welfare interpretation of a collapsed F2 run.

## 6. Chain status (no fabricated trace)

| Segment | Existing kernel capability | Current mapping | H4B status |
|---|---|---|---|
| Application / legal admissibility | H2A proposal validation and H1B authority query exist | Procurement only; no price-category or per-project admission | `NOT_RUN` |
| Approval | Three-valued authority query; procurement admission | No per-project investment approval input; price/investment returns not committed | `NOT_RUN` |
| Financing / procurement | H2B procurement bridge settles against kernel prices | Not connected to any H4B initial state or measurement | `NOT_RUN` |
| Delivery | Kernel settlement measurable in synthetic H2B tests | No H4B run | `NOT_RUN` |
| Input / output | Kernel material production exists | No historical authority mapping; no H4B run | `NOT_RUN` |
| Household realized/unmet | H3G observed exact null **in its own synthetic 4Q profile** | H4B channel not exercised | `NOT_RUN` |

No trace, submitted/delivered quantity, first stage, or welfare delta is reported.

## 7. Verification log

Output root (gitignored, not committed):
`outputs/hist-vnext-h4b-20261020T181104Z/`. Exact command lines, exits, and which wall/RSS values
were actually measured are in its uncommitted `COMMANDS.md`; unmeasured fields are `NOT_MEASURED`.
All commands ran from the repository root with the existing `.venv`; nothing was installed or
upgraded.

| ID | Command | Exit | Observed result |
|---|---|---:|---|
| A1 | `python3 -B data/private/hist_vnext_sources/batch01_20261016/tools/verify_intake.py …` | 0 | `PASS: 112 hashed files; 4 original PDFs; 89 native pages; 83 OCR pages; 0 admitted excerpts.` (0.10 s) |
| A2 | `python3 -B data/private/hist_vnext_sources/batch02_20261020/tools/verify_intake.py …` | 0 | `PASS: 1943 hashed files; 7 originals; 3553 page metadata rows; 368 selected/OCR pages; 70 groups; 0 admitted value records.` (2.12 s) |
| A3 | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.experiment_admission … --approval …/EXPERIMENT_INPUT_APPROVAL.json` | 0 | `structural=PASS`, `admission=EXPERIMENT_ONLY`, `historical=NOT_ESTABLISHED`, `approved_inputs=3`, `historical_inputs_admitted=0`, `runtime_connected=false`, `errors=[]` |
| B1 | targeted six test modules | 0 | **319 passed in 7.21 s** |
| B2 | full `pytest -q -p no:cacheprovider` | 0 | **1688 passed, 180 warnings in 195.97 s** |
| B3 | `.venv/bin/ruff check --no-cache src tests` | 0 | `All checks passed!` |
| B4 | `.venv/bin/hsm baseline verify --json` | 0 | `status=ok`, `1f5b233f…` |
| B5 | `uv lock --check --offline` | 0 | `Resolved 101 packages in 14ms` |
| C0 | `hsm run --scenario historical_f2_replay --seed 1729 --output-dir …/C0 --json` | 0 | digest `92f9ea0a…a42d`, parameter hash `e27ade6a…0445`, run `cb3473e72a794e1d9e0b749e8b8107fc`, 116 ticks, 12.43 s, 617,512,960 B max RSS |
| C1 | `hsm run --scenario historical_f2_trade_scenario --seed 1729 --output-dir …/C1 --json` | 0 | digest `c4810481…18d5`, parameter hash `632ee6a6…b90`, run `2a78b3a3ab544c58b07ebaafa4669764`, 116 ticks, 12.83 s, 610,385,920 B max RSS |
| C-verify | `verify_run_identity(root=Path('.'), scenario_id=…, seed=1729, expected_digest=…, output_dir=…)` | 0 | Both **VERIFIED**: 116 ticks, `status=completed`, digests and parameter hashes equal the frozen pins, baseline hash `1f5b233f…` |

The frozen digests are exactly the plan's C0/C1 pins. Per plan, this step did **not** re-run the
already-reported known failures to confirm them.

## 8. Byte-identity status

| Layer | Status | Basis |
|---|---|---|
| Canonical JSON/state | **NOT_RUN** | No H4B initial-state differential or roundtrip exists. |
| Checkpoint/resume | **NOT_RUN** | No H4B checkpoint pair exists. |
| Strict full-file bytes | **UNMET** | H3F-D3's independent record; not waived, normalized, or re-pinned here. |
| Digest identity | **PASS with caveat** | C0/C1 digests and parameter hashes match the pins and identity verification passes; digest equality is not byte identity. |

## 9. Existing results cited only in original scope

- H3G same-tick household null: synthetic 4Q, exogenous production, no recipe/investment
  optimization; report claims PASS but no standalone REVIEW exists.
- H2B procurement execution: synthetic tiny, procurement only.
- P06 F2 collapse: retained historical reproduction snapshot; not re-measured.

## 10. Deliverables

| File | Content |
|---|---|
| `PLAN.md` | Frozen start state, whitelist, method, verification plan |
| `ASSUMPTION_LEDGER.md` | A/B settings, mechanism freeze, paired design, `NOT_RUN` status |
| `ORIGINAL_AUTHORITY_MATRIX.md` | Nine authority rows; read level, null excerpts, supported/unproven, gaps |
| `SOURCE_MANIFEST.json` | Metadata/source hashes, page pointers, roles, shared roots, access deviation |
| `INPUT_MANIFEST.json` | Pilot `NOT_RUN`, `run_id=null`, unconsumed approved inputs, regression-only C0/C1 |
| `MEASUREMENT_MANIFEST.json` | Nine definition-only mappings; no values; comparisons `NOT_RUN` |
| `BLOCKER_CERTIFICATE.json` | Five blockers with evidence and scope |
| `REPORT.md` | This report |
| `REVIEW.md` | Independent reviewer output (separate authorship) |

## 11. Model/runtime usage

| Role | Selector | Usage |
|---|---|---|
| Implementation | `deepseek/deepseek-flash` (session runtime; configured default is MiniMax) | tokens/cache/cost `NOT_MEASURED` |
| Review | `minimax-code-cn/MiniMax-M3:high` via `phase-reviewer` | recorded in `REVIEW.md`; tokens/cost `NOT_MEASURED` |
| Commit | `deepseek/deepseek-flash` | used only after independent PASS |

Deviations are recorded, not silently normalized. No paid fallback was used.

## 12. Limits and stop

- This is a **technical blocker certificate**, not a completed conditional simulation.
- Missing originals are not the blocker; missing runtime connection and missing price/investment
  execution mappings are.
- The pilot remains **BLOCKED** after this commit. No H4C/H5 work is started.
- If the independent review returns PATCH, only these nine documents are repaired and re-reviewed.
  REDESIGN or an out-of-whitelist requirement stops the step without commit.
