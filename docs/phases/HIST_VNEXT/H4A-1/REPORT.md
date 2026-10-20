# H4A-1 report: prerequisite completion and source-less experiment admission

Run date: 2026-10-20 (UTC). Run root: `outputs/hist-vnext-h4a-1-20261020T125432Z/`.

## Verdicts

| Dimension | Verdict | Evidence |
|---|---|---|
| H1A independent re-review | **PASS** (round 14, `H1A_REREVIEW_ROUND14.md`) | 198 targeted H1A+H4A-0 tests, real H1A/H4A-0 CLI audits, repaired R1/F2–F6/R2–R6 contracts |
| Experiment initial-state admission | **EXPERIMENT_ONLY** | approved declaration, 3 experiment records, derived units/regions/national totals |
| Historical evidence | **NOT_ESTABLISHED / UNIDENTIFIED** | no historical observation admitted; `historical_inputs_admitted=0` |
| Runtime wiring | **NOT CONNECTED** | `runtime_connected=false`; no `src/` consumer |
| Production initialization / measurement | **BLOCKED** | no engine/storage wiring; H4A-1 production acceptance not claimed |
| C0/C1 frozen regressions | **PASS** | digests and run identities match the frozen pins |
| Full suite | **PASS** | 1688 passed, 180 warnings |
| Baseline / offline lock | **PASS** | baseline exit 0; `uv lock --check --offline` exit 0 |
| Independent final review | pending | see `REVIEW.md` after this report |
| Commit | pending | only after final review PASS |

## Start state and preservation

- Branch `codex/audit-hsm-vnext-2026-10-11`; start HEAD
  `37bceaa9c81b42567d2dd14f2ae1be342674b661`.
- Existing user changes were recorded by SHA256 and left untouched:
  `docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md`,
  `06_OMP_MINIMAX_HANDOFF.md`, and 11 untracked root plan files plus
  `09_BATCH02_YEARBOOKS_D08_D10_INTAKE.md`.
- Start-state log: `outputs/hist-vnext-h4a-1-20261020T125432Z/logs/start_state.txt`.
- `BASELINE.md` and `DATA_MANIFEST_v1.json` remain at their frozen hashes:
  `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` and
  `5d91e014c2b80651eb87d3515147468cb84fe77430bf336ba52e357000e58fdd`.

## H1A prerequisite repair

The first independent H1A review returned PATCH. The user then explicitly authorized a bounded
repair of the six reported areas. The repair was independently re-reviewed through rounds 1–14.
Round 14 returned **PASS**; the full chain and repair record are:

- `H1A_REREVIEW.md` (round 1 PATCH)
- `H1A_REREVIEW_ROUND2.md` … `H1A_REREVIEW_ROUND13.md` (PATCH rounds)
- `H1A_REREVIEW_ROUND14.md` (**PASS**)
- `H1A_REPAIR.md` (bounded changes and evidence)

Round-14 reviewer observed 198 targeted tests passed, ruff clean, real H1A CLI
exit 1 / structural PASS / historical BLOCKED (4 candidates, 0 admitted, 63 blocked anchors),
and H4A-0 exit 1 / structural PASS / historical UNIDENTIFIED with 0 approved inputs.

## Experiment declaration

Files:

- `history/HIST_VNEXT/h4_sources/experiment_admission.py`
- `config/initial_state/hist_vnext_h4_v1/experiment_inputs.json`
- `tests/test_hist_experiment_initial_admission.py`
- `docs/phases/HIST_VNEXT/H4A-1/ASSUMPTION_LEDGER.md`

Declaration binding:

| Field | Value |
|---|---|
| `schema_version` | `hist_vnext_h4a1_experiment_v1` |
| `experiment_id` | `h4exp_synthetic_dwelling_sensitivity_v1` |
| classification / evidence kind | `synthetic` / `experiment_assumption` |
| data role / purpose | `initial_state` / `initial_state` |
| target | `1957-01-01` |
| historical status | `NOT_ESTABLISHED` |
| runtime connected | `false` |
| base scenario SHA256 | `c58cdc794b1409f0d4da650e324edebe0757f8bf652fc010f656a12c14f69c3c` |
| household recipe canonical SHA256 | `c879be08f156c389567b8d0cde2caa97f2dce3e83192930c329eea586718b140` |
| material recipe canonical SHA256 | `b2c4122faf5f2059214297ca2b77221d2b3ec10db99d63e8643b37dba9b6157d` |
| upstream approved set SHA256 | `4a1cbb3ae0637b8a0ae1c064db89a2890fc0c40c4def5103b0030234dd96a5ac` |
| ledger SHA256 | `55620c401ea3c685df7795cc654581a8fb3c5a79c2d5143be31cbfcf4eee83a9` |

The three records are exactly:

| `assumption_id` | target field | unit | basis |
|---|---|---|---|
| `h4exp_inherited_persons` | `household_initial.counties[].persons_total` | `persons` | `inherited_baseline_synthetic` |
| `h4exp_inherited_households` | `household_initial.counties[].household_total` | `households` | `inherited_baseline_synthetic` |
| `h4exp_dwelling_ratio` | `material_initial.dwelling_per_person` | `dwellings/person` | `explicit_experiment_design` |

Settings are fixed to `low=0.3`, `baseline=0.4`, `high=0.5`; baseline equals the base recipe.
The declaration has no `source_id`, `source_sha256`, `source_path`, `pdf_page`, `value_ref`, or
`rights` field. The ledger states that this is a source-less design, not a historical estimate.

## Derived quantities

`audit_experiment_admission` derives `D_r = ratio * P_r` and aggregates with `math.fsum`.
For the declared 20-region base recipe:

| Quantity | Value |
|---|---:|
| persons | 17000.0 |
| households | 5000.0 |
| dwellings low (0.3) | 5100.0 |
| dwellings baseline (0.4) | 6800.0 |
| dwellings high (0.5) | 8500.0 |

`by_region` contains all 20 model regions, each with persons, households, and the three dwelling
settings. No historical value is forwarded into state; the result is design-time only.

## Independent review and approval

Before approval, the CLI returned:

```text
exit_code=1, structural=PASS, admission=PENDING, historical=NOT_ESTABLISHED,
runtime_connected=false, historical_inputs_admitted=0, approved_inputs=[]
```

The independent `@review` returned `PASS` as
`EXPERIMENT_INPUT_REVIEW.json`; reviewer identity
`omp:review-subagent/h4a1-step3-experiment`, reviewed at
`2026-10-20T14:52:26+00:00`. The review scopes exactly seven files:

1. experiment module
2. experiment config
3. experiment tests
4. assumption ledger
5. base scenario
6. original H4A-0 approved set
7. H1A round-14 PASS review

`EXPERIMENT_INPUT_APPROVAL.json` binds the review file SHA256
`4100afb8b3cf7e965668c1011cd3653155a89d69d14b16788f885f067057a543`, the same seven hashes,
the same three IDs, purpose/date, null expiry, reviewer identity, and issue time. The implementer
identity differs from the reviewer identity. With approval the CLI returns:

```text
exit_code=0, structural=PASS, admission=EXPERIMENT_ONLY, historical=NOT_ESTABLISHED,
runtime_connected=false, historical_inputs_admitted=0, approved_inputs=3
```

A copied config with `dwellings/person` changed to `M_forint` returns:
`exit_code=2, structural=BLOCKED, admission=BLOCKED, approved_inputs=[]`.

## Verification log

| Check | Result |
|---|---|
| `pytest tests/test_hist_experiment_initial_admission.py` | 36 passed |
| `pytest tests/test_hist_experiment_initial_admission.py tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py` | 234 passed |
| real experiment CLI, no approval | exit 1 / PENDING |
| real experiment CLI, valid approval | exit 0 / EXPERIMENT_ONLY |
| copied config, `M_forint` unit | exit 2 / BLOCKED |
| ruff new module/tests | clean |
| full suite | 1688 passed, 180 warnings in 103.17s |
| `hsm baseline verify --json` | exit 0 |
| `uv lock --check --offline` | exit 0 |
| 4Q synthetic control (`history_f2_replay`, seed 1729, until 1957Q4) | exit 0; run `467b7d5a2ad747ecbc0f176d51c3ea8d`, digest `0d360553a9066dc60515bffd34abae80b5f556ed188609f0063ba6fd73e9fa03`; 1.85 s real, 366,313,472 B max RSS |
| C0 (`historical_f2_replay`, seed 1729, until 1985Q4) | exit 0; digest `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`, run `974acc9622f94172ad1e68e61d620030`; 7.59 s, 601,112,576 B |
| C1 (`historical_f2_trade_scenario`, seed 1729, until 1985Q4) | exit 0; digest `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`, run `33bc9a0dab07408eabf07e20bf58be9b`; 7.85 s, 609,271,808 B |
| `verify_run_identity` C0/C1 | both passed against the frozen digests |

`ACTUAL_INPUT_MANIFEST.json` lists the three approved but unconsumed experiment records and an
empty `consumed_by_model`. `SAME_SEED_CONTROL.json` records the pure synthetic 4Q control and the
H4 initialization arm as `BLOCKED` with `run_id=null` and `difference=null`.

## Model roles

| Role | Configured | Actual observation |
|---|---|---|
| Phase review | `minimax-code-cn/MiniMax-M3:high` (`@review`) | round-14 H1A PASS and experiment input PASS through `phase-reviewer`; selector reported by the probe as `minimax-code-cn/MiniMax-M3:high` |
| Default implementation | `minimax-code-cn/MiniMax-M2.7-highspeed:medium` | implementation executed by the runtime selector `deepseek/deepseek-flash`; recorded as a role deviation, not a silent claim |
| Commit | `deepseek/deepseek-flash` | not yet used; commit follows final review PASS |

Review-model delta during the run: the start state had
`review: openai-codex/gpt-6.1-sol:high`. Three round-14 attempts returned
`usage_limit_reached`; the next selector, `zhipu-coding-plan/glm-5.3:high`, returned
`429 余额不足或无可用资源包`. The user then changed `@review` to the funded
`minimax-code-cn/MiniMax-M3:high`, which produced the round-14 H1A PASS and the experiment
review PASS. `.omp/config.yml` is therefore modified in the working tree relative to HEAD; it is
a user configuration change, is disclosed here, and is **not** part of the planned commit.

Token and paid-cost counters are not exposed by the runtime → **unknown / NOT_RUN**, not estimated.

## Residual gaps

1. H3F-D3 strict full-file C0/C1 byte gate remains **UNMET**; this run does not create a waiver or
   normalize outputs.
2. H3G same-tick household `realized/unmet` structural null and missing standalone review remain.
3. H4A-0 statistical approved sets remain empty; no real 1957 household/regional evidence was
   admitted.
4. The experiment declaration is `EXPERIMENT_ONLY`; it is not production initialization,
   measurement, or a historical PASS.
5. No push and no runtime connection.

## Byte-identity status

| Layer | Status | Evidence |
|---|---|---|
| Canonical JSON/state | **NOT_RUN** | No H4 initialization differential or roundtrip was executed in this step. |
| Checkpoint/resume | **NOT_RUN** | No H4 initialized state or resume pair exists to compare. |
| Strict full-file bytes | **UNMET** | H3F-D3's independent record remains UNMET; this run does not normalize outputs, change run ids/clocks/Git provenance, re-pin, or cite a P06 waiver. |
| Digest identity | **PASS** | C0/C1 digests and parameter hashes match the frozen pins; a digest match is not a full-file byte proof. |

## Explicit BLOCKED / NOT_RUN acceptance items

| Item | Status | Reason |
|---|---|---|
| 1957 regional population and regional housing stock | **BLOCKED** | No dated county/city -> 20-region boundary crosswalk; no 1957 regional stock. |
| 1957 national/regional household counts | **BLOCKED** | No admitted 1957 household definition/count. |
| Date/unit/role separation | **PASS for declarations / BLOCKED for values** | Candidate dates retain year/month/day precision; no historical value was admitted. |
| Forcing vs target vs initial role | **PASS for declared boundary** | No target leakage or forcing substitution observed. |
| Future-information guard | **NOT_RUN** | No historical pilot or counterfactual run. |
| Double injection | **NOT_RUN** | No initialized historical arm. |
| Checkpoint/resume and anchor-changes-state production acceptance | **BLOCKED / NOT_RUN** | Production initialization is not wired; no state-changing anchor is admitted. |
| Experiment-only derived dwellings | **PASS as design-time derivation** | `D_r = ratio * P_r`; not an engine-generated 1957 stock. |

## 63 anchors

### 63-anchor completion / gap list (by original `anchor_id`)

| `anchor_id` | classification | gap |
|---|---|---|
| `dwelling_1960_orszagos_00` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_01` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_02` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_03` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_04` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_05` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_06` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_07` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_08` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_09` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_10` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_11` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_12` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_13` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_14` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_15` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_16` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_17` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_18` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_19` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `dwelling_1960_orszagos_20` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 regional housing stock |
| `household_1960_orszagos_00` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_01` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_02` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_03` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_04` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_05` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_06` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_07` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_08` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_09` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_10` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_11` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_12` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_13` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_14` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_15` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_16` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_17` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_18` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_19` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `household_1960_orszagos_20` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no 1957 household count or definition |
| `population_1960_orszagos_00` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_01` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_02` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_03` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_04` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_05` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_06` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_07` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_08` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_09` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_10` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_11` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_12` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_13` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_14` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_15` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_16` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_17` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_18` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_19` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |
| `population_1960_orszagos_20` | `blocked` | 1957 administrative/legal boundary and dated county/city -> 20-region mapping; no direct 1957 regional observation |


### Derived quantities by region and setting

Units: persons, households, dwellings. `D_r = ratio * P_r`; national uses `math.fsum` over the regions.

| region_id | persons | households | dwellings low 0.3 | dwellings baseline 0.4 | dwellings high 0.5 |
|---|---:|---:|---:|---:|---:|
| `budapest` | 686.8686869 | 202.020202 | 206.0606061 | 274.7474747 | 343.4343434 |
| `pest` | 704.040404 | 207.0707071 | 211.2121212 | 281.6161616 | 352.020202 |
| `borsod_abauj_zemplen` | 721.2121212 | 212.1212121 | 216.3636364 | 288.4848485 | 360.6060606 |
| `heves` | 738.3838384 | 217.1717172 | 221.5151515 | 295.3535354 | 369.1919192 |
| `nograd` | 755.5555556 | 222.2222222 | 226.6666667 | 302.2222222 | 377.7777778 |
| `fejer` | 772.7272727 | 227.2727273 | 231.8181818 | 309.0909091 | 386.3636364 |
| `komarom` | 789.8989899 | 232.3232323 | 236.969697 | 315.959596 | 394.9494949 |
| `veszprem` | 807.0707071 | 237.3737374 | 242.1212121 | 322.8282828 | 403.5353535 |
| `gyor_sopron` | 824.2424242 | 242.4242424 | 247.2727273 | 329.6969697 | 412.1212121 |
| `vas` | 841.4141414 | 247.4747475 | 252.4242424 | 336.5656566 | 420.7070707 |
| `zala` | 858.5858586 | 252.5252525 | 257.5757576 | 343.4343434 | 429.2929293 |
| `baranya` | 875.7575758 | 257.5757576 | 262.7272727 | 350.3030303 | 437.8787879 |
| `somogy` | 892.9292929 | 262.6262626 | 267.8787879 | 357.1717172 | 446.4646465 |
| `tolna` | 910.1010101 | 267.6767677 | 273.030303 | 364.040404 | 455.0505051 |
| `hajdu_bihar` | 927.2727273 | 272.7272727 | 278.1818182 | 370.9090909 | 463.6363636 |
| `szabolcs_szatmar` | 944.4444444 | 277.7777778 | 283.3333333 | 377.7777778 | 472.2222222 |
| `szolnok` | 961.6161616 | 282.8282828 | 288.4848485 | 384.6464646 | 480.8080808 |
| `bacs_kiskun` | 978.7878788 | 287.8787879 | 293.6363636 | 391.5151515 | 489.3939394 |
| `bekes` | 995.959596 | 292.9292929 | 298.7878788 | 398.3838384 | 497.979798 |
| `csongrad` | 1013.131313 | 297.979798 | 303.9393939 | 405.2525253 | 506.5656566 |
| **national (fsum)** | 17000 | 5000 | 5100 | 6800 | 8500 |
