# P06 run report

W0.5 parent run command: `.venv/bin/hsm run --scenario p04_endogenous --until 1973Q1 --checkpoint-every 4 --output-dir outputs/p06-fork-parent --json`. Wall time: **5.42 s**; manifest digest: `45999d895dac3b84bc69918273eed0c3b51489cba9ddae4fdbb2a20c54411f27`. Checkpoints: `outputs/p06-fork-parent/checkpoints/tick-0044` (material-checkpoint-v4, 44 completed ticks, last 1967Q4, next 1968Q1) and `outputs/p06-fork-parent/checkpoints/tick-0064` (v4, 64 completed ticks, last 1972Q4, next 1973Q1).

All 17 arms finished 116 ticks through 1985Q4; per-arm time 4.316–6.050 s, concurrent batch 26.29 s. Every arm accounting check passed; none was rejected and the 10-minute degradation trigger did not apply. Values below are counterfactual simulation metrics, not historical evidence. Production is the sum of model commodity-group production over the run, not GDP.

| Family | Arm | Replay digest | Production sum | HH consumption | Availability unmet | Undelivered share | Disposition |
|---|---|---|---:|---:|---:|---:|---|
| 1968 | control | `1e7e4d846c9ba5cefa86669bce0a441caac934959ad08108e212b6b0481530b8` | 16,792,937 | 3,403,745 | 3,357,464 | 0.3671 | completed; accounting PASS; conditional model response |
| 1968 | no-reform | `4085927ae177ce1f4a03ac49e8def73af68618fcf263452c98f11d8bd69a2ee7` | 13,268,845 | 3,120,818 | 3,636,733 | 0.4443 | completed; accounting PASS; conditional model response |
| 1968 | nem-plus | `d582ea5f8bb8e9e6b2560b91bcff577ab78e114057a454fe95b594918cf5f995` | 14,774,722 | 3,133,476 | 3,622,826 | 0.4531 | completed; accounting PASS; conditional model response |
| 1968 | nos-hu | `dd9dee2640b646869d680530b5af8734443ed243f06d93c174967e13084c6db9` | 13,268,243 | 3,121,714 | 3,635,807 | 0.4441 | completed; accounting PASS; conditional model response |
| 1968 | digital-nem | `f767d15146de81f4c5cf23cf8dfc0a3b2779470dea45cbbd832649c1712463df` | 16,777,397 | 3,401,401 | 3,359,658 | 0.3672 | completed; accounting PASS; conditional model response |
| 1973 | control | `1e7e4d846c9ba5cefa86669bce0a441caac934959ad08108e212b6b0481530b8` | 16,792,937 | 3,403,745 | 3,357,464 | 0.3671 | completed; accounting PASS; conditional model response |
| 1973 | borrowing-smoothing | `6652c64cd73195c00b60b55fc279ce514452889e784405e37c960a0a5136c2e0` | 16,744,647 | 3,396,753 | 3,364,165 | 0.3674 | completed; accounting PASS; conditional model response |
| 1973 | consumption-restraint | `df2ed7890c94dec3d2c50605429b4e5b07fb20b50a8043a753266ab0b43ff6a8` | 16,772,253 | 3,400,700 | 3,362,853 | 0.3678 | completed; accounting PASS; conditional model response |
| 1973 | investment-restraint | `530904688c9acdf97de289a3e7432207118a385e708ccdd4923912f9dac77f72` | 15,906,319 | 3,272,853 | 3,487,420 | 0.3750 | completed; accounting PASS; conditional model response |
| 1973 | price-wage-compensation | `05fa044c24499494ea23464ea9aabec3c1e19d988fb4952692daaa1ba387c873` | 17,935,148 | 3,551,108 | 3,213,774 | 0.3319 | completed; accounting PASS; conditional model response |
| 1973 | hard-budget | `52b81ff6d60a5deec93411842e854e32970989b130bda9d2eb45123c863bc27b` | 14,926,215 | 3,111,171 | 3,646,694 | 0.4421 | completed; accounting PASS; conditional model response |
| political | control | `1e7e4d846c9ba5cefa86669bce0a441caac934959ad08108e212b6b0481530b8` | 16,792,937 | 3,403,745 | 3,357,464 | 0.3671 | completed; accounting PASS; conditional model response |
| political | coalition-weights | `47bd3c4d8741ab20944759dd4d90557febae846637d57d9620e80815865b7632` | 16,792,937 | 3,403,745 | 3,357,464 | 0.3671 | completed; accounting PASS; conditional model response |
| political | soviet-constraint | `129f0833ab06faeaca0f0f9d27d9d0eb4097ad35addef9f37b2bbc4324e21fe2` | 16,792,937 | 3,403,745 | 3,357,464 | 0.3671 | completed; accounting PASS; conditional model response |
| political | consumer-import | `007533bd922b0663b31201739291fac04c2bc7dcf685bb68189a6fcd1d3ed324` | 16,761,562 | 3,396,817 | 3,364,240 | 0.3673 | completed; accounting PASS; conditional model response |
| political | cultural-openness | `72571643d578c436efc0e99178ac99d1950b69a4872c5c0c5406e5aa7e943171` | 16,792,937 | 3,403,745 | 3,357,464 | 0.3671 | completed; accounting PASS; conditional model response |
| political | second-economy | `dd1cf22a50482a7ef58ca30dc35ef1f42ca8d0560eff26b5f22e7962581ebc88` | 16,785,315 | 3,406,375 | 3,354,408 | 0.3668 | completed; accounting PASS; conditional model response |

Detailed family tables: [1968 forks](P06_1968_FORK.md), [1973 shock arms](P06_1973_SHOCK.md), [political arms](P06_POLITICAL_COUNTERFACTUAL.md). The full local `outputs/p06-arms/summary.json` records parameter/intervention hashes and collected §3 metric families; bank reserves are not collected by compact fork output and are excluded from the declared metric vocabulary. The three arm documents state the F1 parent, `intermediate8_v1` ontology, `f1` fidelity and parent manifest digest; their magnitudes are not comparable with the F2 historical material replay. The political report declares `coalition-weights`, `soviet-constraint` and `cultural-openness` as inert on every reported metric despite distinct replay digests, and a regression test checks the local arm summary against that declaration. Relevant M5/M6/M8/M9/M10 verdicts remain UNIDENTIFIED due their registered unidentified dependencies.

Part 2 crosswalk result (partial): `.venv/bin/hsm calibration reproduction-table --output-dir outputs/p06-reproduction-table-widened-final2 --json` completed the historical F2 replay through 1978Q4 with digest `f75ba7767eaf5987eb876413f973e07f13ece4e11906cdd14cbd3b08fbf8ba79`. The first Group 1 probe found exports, imports and all four CMEA/convertible channels were zero in every replay year 1957–1978, including 1960. The own-1960 normalization is therefore undefined. No trade targets were read during that failed probe; both trade variables are `no_counterpart` rather than being assigned a fabricated base. The final table reads only mapped consumption targets, 19 rows, with **18 of 18 informative years outside tolerance**, mean absolute residual 91.7414, maximum 173.6360. Hold-out and reserved values were not read; simulation ended 1978Q4.

Crosswalk totals: **1 mapped / 13 no_counterpart / 0 blocked**. Grade counts: `mapped_like_for_like` 0; `normalized_index` 1; `allocation_assumed` 0; `no_counterpart` 13; `blocked` 0. Consumption is the only numeric verdict (`outside_tolerance`, 18/18 informative years). The added four admin-price CMEA/convertible import/export diagnostics are columns, not targets; they are zero over the reported years. The implementation uses `build_material_prices(parameters).standard`; KSH index weights/base differ from the model's admin-price quantity total, no CMEA/convertible composition is inferred, and imports remain outcomes, never quotas.

Per-variable dispositions: `consumption` mapped at grade `normalized_index`; `trade_export_volume_index` and `trade_import_volume_index` no counterpart because their model flows have a zero 1960 denominator; `industrial_electricity`, `industrial_crude_steel`, `industrial_fertilizer`, `industrial_cement`, and `industrial_television` no counterpart because no independent rights-cleared share series appears in `data/manifests/sources.yml`, `data/manifests/artifacts.yml`, or `data/raw` (registered KSH series are target-role); `ag_cereals`, `ag_wheat`, and `ag_maize` permanently no counterpart because the F2 ontology exposes one `g08_agricultural_raw` and no crop split across the household axis, plot recipes, or stage catalog; `gdp`, `industrial_output`, and `investment` retain their prior no-counterpart reasons. No `allocation_assumed` mapping was found or created. The table builder validates every mapped entry's source artifact IDs and SHA-256 values against the admitted target manifest and refuses a missing source.

Part 1 fixes (F1–F4): F1 run identity is in `docs/phases/P06_1968_FORK.md`, `docs/phases/P06_1973_SHOCK.md`, and `docs/phases/P06_POLITICAL_COUNTERFACTUAL.md`; F2 inert-arm disclosure/front matter are in `docs/phases/P06_POLITICAL_COUNTERFACTUAL.md`, checked by `tests/test_p06_reproduction_table.py`; F3 the informative flag/count are implemented in `src/hsm_lab/calibration/reproduction_table.py`, tested in `tests/test_p06_reproduction_table.py`, and reported in `docs/phases/P06_FINAL_REPORT.md`; F4 the bank-reserve family is removed from §3 in `docs/phases/P06_EXECUTION_PLAN.md` and disclosed as uncollected in all three arm documents. Part 1 commit: `497210260e825facf42b77bcad345693e4e7813c`.

Clearance table after regeneration: **23 PASS / 4 WAIVED / 0 OPEN**. The WAIVED items are the F2 closure audit, frozen acceptance gates, calibration/inference, and new-observable acquisition. The frozen gate failures remain visible and waived under the declared reproduction scope; no new residual gate was introduced.

| Clearance item | Status | Evidence |
|---|---|---|
| `gate1_closure_audit` | WAIVED | F2 closure audit remains collapsed; Track A exited without meeting both terminal floors. |
| `frozen_acceptance_gates` | WAIVED | Liveness, service ratios, treasury self-financing and expiry remain failed. |
| `calibration_and_inference` | WAIVED | Empty identifiable set/linkage; inference remains NOT_RUN. |
| `morris_screening` | PASS | Four required artifacts present; no Sobol calculation. |
| `data_path_acquisition` | WAIVED | Seven unadmitted target-role variables and P05 §10b observables remain unadmitted. |
| `suite_and_lint` | PASS | Ruff clean; pytest 412 passed, 0 failed. |
| `legacy_digest_reproduces` | PASS | Digest `92f9ea0a…` reproduced. |
| `registry_consistency` | PASS | Both control-file scenarios registered. |
| `control_structure` | PASS | Floors declared; linkage empty; 9 fixed / 6 unidentified. |
| `scope_statement_recorded` | PASS | P05 reproduction-scope decision recorded. |
| `reserved_window_unread` | PASS | 100 recorded runs stop by 1985Q4. |
| `data_manifest_frozen` | PASS | `missing_required = []`. |
| `performance_benchmark` | PASS | Existing Mac F2 benchmark gate passes. |
| `mechanism_cards` | PASS | M1–M11 artifacts present. |
| `forcing_ladder` | PASS | H0–H4 artifacts present. |
| `window_protocol` | PASS | Hold-out/reserved protocol artifacts present. |
| `reproducibility_bundle` | PASS | Bundle artifacts present. |
| `p06_oat_sensitivity` | PASS | OAT evidence present. |
| `p06_h4_disposition` | PASS | H4 disposition remains conditional. |
| `p06_1968_runs` | PASS | Five 1968 arms completed through 1985Q4 with hashes and metrics. |
| `p06_1973_runs` | PASS | Six 1973 arms completed through 1985Q4 with hashes and metrics. |
| `p06_political_runs` | PASS | Six political arms completed through 1985Q4 with hashes and metrics. |
| `p06_window_protocol_wired` | PASS | DataRegistry target-load path enforces windows. |
| `p06_bundle_cli` | PASS | Bundle CLI checks present. |
| `p06_seedbank_spread` | PASS | Three-seed replication evidence present. |
| `p06_final_report` | PASS | Final and run reports present. |
| `p06_reproduction_table` | PASS | Crosswalk 1 mapped / 13 no_counterpart / 0 blocked; 19 open-window rows. |

Final checks: `.venv/bin/ruff check src tests` clean; `.venv/bin/python -m pytest -q -p no:cacheprovider` → **412 passed**; `outputs/p06-clearance/pytest.json` records 412 passed / 0 failed; `.venv/bin/hsm calibration p06-clearance --with-runs --json` → **23 PASS / 4 WAIVED / 0 OPEN**. Part 1 commit: `497210260e825facf42b77bcad345693e4e7813c`. Part 2 commit is the commit containing this Part 2 report; its hash is in the task completion record.

W0.5 commit: `3a3ad69`. W9 implementation/report commit: `28a9bbf2f33e57d1c46339685660ef91ded9cdfe`. `.omp/config.yml` remains a pre-existing user-local edit and is excluded from commits.
