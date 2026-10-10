# P06 run report

## Plan C — trade transmission probe (partial; 2026-10-10)

**Household-consumption failure first.** In the declared C1 trade scenario, the descriptive normalized-index comparison remains outside tolerance in **18 of 18 informative years** (1960 is only the normalization base). Mean absolute residual is **120.2651 index points** and maximum absolute residual is **214.6777**; tolerance remains the frozen 0.5. This is not a calibration or validation claim. The full annual series is below.

| Year | Window | Target index | Model index | Residual | Verdict |
|---:|---|---:|---:|---:|---|
| 1960 | calibration | 100.000 | 100.000 | 0.000 | within_tolerance |
| 1961 | calibration | 101.000 | 87.040 | -13.960 | outside_tolerance |
| 1962 | calibration | 105.000 | 48.830 | -56.170 | outside_tolerance |
| 1963 | calibration | 110.000 | 47.891 | -62.109 | outside_tolerance |
| 1964 | calibration | 116.000 | 46.481 | -69.519 | outside_tolerance |
| 1965 | calibration | 118.000 | 43.960 | -74.040 | outside_tolerance |
| 1966 | calibration | 123.000 | 40.061 | -82.939 | outside_tolerance |
| 1967 | calibration | 131.000 | 35.380 | -95.620 | outside_tolerance |
| 1968 | calibration | 137.000 | 29.892 | -107.108 | outside_tolerance |
| 1969 | calibration | 145.000 | 23.912 | -121.088 | outside_tolerance |
| 1970 | internal_validation | 155.000 | 18.444 | -136.556 | outside_tolerance |
| 1971 | internal_validation | 163.000 | 14.001 | -148.999 | outside_tolerance |
| 1972 | internal_validation | 169.000 | 11.038 | -157.962 | outside_tolerance |
| 1973 | internal_validation | 176.000 | 8.996 | -167.004 | outside_tolerance |
| 1974 | internal_validation | 187.000 | 6.520 | -180.480 | outside_tolerance |
| 1975 | internal_validation | 196.000 | 3.239 | -192.761 | outside_tolerance |
| 1976 | internal_validation | 199.000 | 1.632 | -197.368 | outside_tolerance |
| 1977 | internal_validation | 208.000 | 1.325 | -206.675 | outside_tolerance |
| 1978 | internal_validation | 216.000 | 1.322 | -214.678 | outside_tolerance |

The C1 comparison table also gives `trade_import_volume_index` a numeric normalized-index row (19 annual rows, with the 1960 base uninformative): **18 of 18 informative years outside tolerance**, mean absolute residual 159.4211 and maximum 403.0. The model index stays at 100 because the scenario demand is constant; this is a descriptive mismatch, not an adjustment target.

| Year | KSH target | Model index | Residual |
|---:|---:|---:|---:|
| 1960 | 100.000 | 100.000 | 0.000 |
| 1961 | 108.000 | 100.000 | -8.000 |
| 1962 | 124.000 | 100.000 | -24.000 |
| 1963 | 142.000 | 100.000 | -42.000 |
| 1964 | 159.000 | 100.000 | -59.000 |
| 1965 | 158.000 | 100.000 | -58.000 |
| 1966 | 168.000 | 100.000 | -68.000 |
| 1967 | 197.000 | 100.000 | -97.000 |
| 1968 | 203.000 | 100.000 | -103.000 |
| 1969 | 215.000 | 100.000 | -115.000 |
| 1970 | 274.000 | 100.000 | -174.000 |
| 1971 | 326.000 | 100.000 | -226.000 |
| 1972 | 309.000 | 100.000 | -209.000 |
| 1973 | 318.000 | 100.000 | -218.000 |
| 1974 | 374.000 | 100.000 | -274.000 |
| 1975 | 398.000 | 100.000 | -298.000 |
| 1976 | 406.000 | 100.000 | -306.000 |
| 1977 | 447.000 | 100.000 | -347.000 |
| 1978 | 503.000 | 100.000 | -403.000 |

### Declared scenario and non-circular provenance

`config/scenarios/historical_f2_trade_scenario.json` copies `historical_f2_replay`, starts at 1957Q1, runs 116 ticks through 1985Q4, seed 1729. Its vectors use the registered P04 external pack `data/fixtures/p04_external_synthetic_pack.json` (`source_id=p04_fixture`, internal digest `71642a27e454097b2c52b2948daaa5492e263a3084c3cfe9a46b6d04b76ed0a8`) and declared external recipe `data/fixtures/p04_priors/p04_external_recipe_parameters.json` (base CMEA and Western demand 1.0; SHA-256 `e4e7e8c9b2ad638a679b2ed96cb6fc9b1141a8f4e833ad0c938f25b5f2237b00`). Each channel signal is multiplied by its declared recipe base demand and divided by `build_material_prices(parameters).standard`; because the external pack has aggregate channel signals but no commodity composition, this is an equal-admin-value structural basket, not an asserted historical composition. No KSH index or target series entered vector construction. Scenario SHA-256: `3ad4510064daa6e0b6f37893eb6a5721c3ad0b34f3284175c2cde77a33397a5f`. Credit envelopes/reserves/loan limits are deliberately high; the distribution working-capital guard did not trigger. The existing model exposes no CMEA opening-reserve parameter: its settlement balance starts at zero, with the declared credit envelope setting the import cap. The initial all-groups compile hit the current housing-edge guard for construction imports; C1 therefore sets g07 construction imports to zero while retaining its declared exports. The failed compile evidence is preserved in `outputs/p06-trade-transmission/C1-network-guard-attempt`.

### Arm outcomes and transmission

| Arm | Scenario | Parameter hash | Seed | Replay digest | Imports CMEA / convertible / total | Exports CMEA / convertible / total | Accounting residual maxima (finance; material) |
|---|---|---|---:|---|---:|---:|---|
| C0 | `historical_f2_replay` | `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445` | 1729 | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` | 0.0000 / 0.0000 / 0.0000 | 0.0000 / 0.0000 / 0.0000 | 4.19e-09; 1.46e-11 |
| C1 | `historical_f2_trade_scenario` | `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90` | 1729 | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` | 1226.7000 / 1226.7000 / 2453.4000 | 126.7297 / 126.7297 / 253.4594 | 4.19e-09; 2.91e-11 |
| C2 | `historical_f2_trade_wage_diagnostic` | `fd3d4f87833b8fb137a350709e4641342f73ec9e13785ae1f12b96d4a33ea5f3` | 1729 | `29dc3d615adf366647c56401ea2cce2092febb12bfb367f790611daa015589a7` | 1226.7000 / 1226.7000 / 2453.4000 | 74.1846 / 74.1846 / 148.3692 | 6.75e-09; 1.46e-11 |

C0 reproduces the frozen zero-trade baseline digest `92f9ea0a…` with all trade flows zero. C1 proves the external channel transmits imports: all declared import demand is realized each quarter in 15 import-enabled commodity groups, with maximum demand mismatch zero in each channel. Its exports initially transmit, but Treasury payable cash depletes: cash reaches zero at 1961Q2 and the first zero-export quarter is 1960Q2; only 9.8645% of declared export volume is realized over the full horizon. C2 was therefore run as the requested wage-factor knife-edge diagnostic (`wage_rate=6.6`, 1.1×); it does not restore export throughput, reduces aggregate exports to 148.3692, and lacks a positive 1960 export index base. C2 is not a remedy. The external channel transmits conditionally: imports are nonbinding in this scenario, while export transmission is Treasury constrained.

C1 full-window commodity quantities (cumulative 1957Q1–1985Q4; CMEA and convertible columns remain separate):

| Commodity group | Imports CMEA | Imports convertible | Exports CMEA | Exports convertible |
|---|---:|---:|---:|---:|
| `g01_solid_fuels` | 116.0000 | 116.0000 | 15.0000 | 15.0000 |
| `g02_oil_gas_fuels` | 116.0000 | 116.0000 | 14.6884 | 14.6884 |
| `g03_electricity_heat` | 96.6667 | 96.6667 | 0.8333 | 0.8333 |
| `g04_basic_metals_materials` | 58.0000 | 58.0000 | 4.5669 | 4.5669 |
| `g05_chemicals_fertilizer` | 77.3333 | 77.3333 | 10.0000 | 10.0000 |
| `g06_machinery_capital` | 29.0000 | 29.0000 | 0.9252 | 0.9252 |
| `g07_construction` | 0.0000 | 0.0000 | 3.2500 | 3.2500 |
| `g08_agricultural_raw` | 145.0000 | 145.0000 | 18.4375 | 18.4375 |
| `g09_basic_food` | 116.0000 | 116.0000 | 8.6825 | 8.6825 |
| `g10_animal_food` | 46.4000 | 46.4000 | 2.3688 | 2.3688 |
| `g11_textiles_footwear` | 77.3333 | 77.3333 | 9.6991 | 9.6991 |
| `g12_household_nondurables` | 96.6667 | 96.6667 | 12.1233 | 12.1233 |
| `g13_household_durables` | 14.5000 | 14.5000 | 1.8750 | 1.8750 |
| `g14_vehicles_transport_equipment` | 5.8000 | 5.8000 | 0.7500 | 0.7500 |
| `g15_market_services` | 116.0000 | 116.0000 | 11.5000 | 11.5000 |
| `g16_housing_public_services` | 116.0000 | 116.0000 | 12.0297 | 12.0297 |

### Crosswalk and evidence status

Trade imports are `mapped` at `normalized_index`, sourced only from the declared scenario vectors with scenario id, digest and non-circularity note. Trade exports remain `blocked`: they have a model counterpart and positive initial flow, but Treasury cash makes transmission binding and prevents a nonbinding comparison; this is an observed block, not `no_counterpart`. Remaining variables retain their previous dispositions. Current crosswalk counts: **2 mapped / 11 no_counterpart / 1 blocked**; grades: **2 normalized_index / 11 no_counterpart / 1 blocked**, 0 allocation-assumed. Reproduction table ends 1978Q4, digest `6362001deaf055af6c005acc7d6fc6c4bbaf05b7f417b0c3bec5b7c25b8508b0`; hold-out and reserved values were not read.



### Clearance item table after Plan C regeneration

**24 PASS / 4 WAIVED / 0 OPEN**. The four waivers are the existing closure audit, frozen acceptance gates, calibration/inference and data-path acquisition; frozen failures remain reported as such.

| id | status | evidence |
|---|---|---|
| `gate1_closure_audit` | **WAIVED** | not satisfied: hsm calibration audit-closure --scenario historical_f2_replay reports status collapsed with output_liveness 0.0 |
| `frozen_acceptance_gates` | **WAIVED** | not satisfied: liveness, household service ratios, treasury self-financing and expiry still fail on the replay |
| `calibration_and_inference` | **WAIVED** | not satisfied: identifiable_set is empty and no linkage exists, so no paired F1/F2 study or ABC inference can run |
| `morris_screening` | **PASS** | 4 artifacts present |
| `data_path_acquisition` | **WAIVED** | not satisfied: the seven unadmitted target-role variables and the P05_REPORT 10b observables are not admitted |
| `suite_and_lint` | **PASS** | ruff clean; pytest evidence 414 passed, 0 failed |
| `legacy_digest_reproduces` | **PASS** | historical_f2_replay digest 92f9ea0adcfce1b0... (expected 92f9ea0adcfce1b0...) |
| `registry_consistency` | **PASS** | all 2 control-file scenario names are registered |
| `control_structure` | **PASS** | terminal floors declared; linkage empty; identification {'fixed': 9, 'unidentified': 6} |
| `scope_statement_recorded` | **PASS** | P05_REPORT.md records the reproduction-scope decision |
| `reserved_window_unread` | **PASS** | 105 recorded runs end at or before 1985Q4 |
| `data_manifest_frozen` | **PASS** | data/manifests/DATA_MANIFEST_v2.json[missing_required] = [] |
| `performance_benchmark` | **PASS** | outputs/p05-f2-benchmark/benchmark.json[overall_gate] = 'pass' |
| `mechanism_cards` | **PASS** | 15 artifacts present |
| `forcing_ladder` | **PASS** | 3 artifacts present |
| `window_protocol` | **PASS** | 2 artifacts present |
| `reproducibility_bundle` | **PASS** | 2 artifacts present |
| `p06_oat_sensitivity` | **PASS** | 4 artifacts present |
| `p06_h4_disposition` | **PASS** | 2 artifacts present |
| `p06_1968_runs` | **PASS** | all 17 required W5-W7 arms completed 116 ticks through 1985Q4 with hashes and metrics |
| `p06_1973_runs` | **PASS** | all 17 required W5-W7 arms completed 116 ticks through 1985Q4 with hashes and metrics |
| `p06_political_runs` | **PASS** | all 17 required W5-W7 arms completed 116 ticks through 1985Q4 with hashes and metrics |
| `p06_window_protocol_wired` | **PASS** | 5 artifacts present |
| `p06_bundle_cli` | **PASS** | 3 artifacts present |
| `p06_seedbank_spread` | **PASS** | 1 artifacts present |
| `p06_final_report` | **PASS** | 2 artifacts present |
| `p06_reproduction_table` | **PASS** | crosswalk {'mapped': 2, 'no_counterpart': 11, 'blocked': 1}; 38 numeric rows limited to mapped open windows |
| `p06_trade_transmission` | **PASS** | C0/C1/C2 identities, 116-tick windows, per-commodity channels and residual evidence recorded |

## Final P06 close-out (partial reproduction result; 2026-10-10)

The frozen conclusion is in [P06_FINAL_REPORT.md](P06_FINAL_REPORT.md), immediately after its scope boundary. It records `calibrated = 0`, nothing identified, consumption falling against a rising observed index (18/18 informative years outside tolerance; mean absolute residual 91.7414 in the base replay and 120.2651 in the trade scenario), 2 mapped / 1 Treasury-rationed blocked / 11 no-counterpart crosswalk rows, partial external-channel transmission, and no SUPPORTED mechanism card as a result. The required sentence is reproduced verbatim there. No mechanism or crosswalk verdict changed.

The release manifest is [P06_RELEASE.md](P06_RELEASE.md). Frozen source HEAD: `fd025a5bdedf698100e05f736b4209ddc62dd144`; crosswalk SHA-256: `433f53dd09643bc963b2f7002a508284b7e153bcd9ebae5ffb55f88820826aeb`. Both final bundle replays match their recorded digests and parameter hashes: legacy `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` and C1 trade scenario `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`. The stale pre-closeout bytes and their mismatch are preserved and explained in the release manifest.

Final clearance after regeneration: **26 PASS / 4 WAIVED / 0 OPEN**. The final suite result and lint evidence are recorded at `outputs/p06-clearance/pytest.json` and in the generated clearance checklist. This close-out adds only documentation, bundle evidence and clearance checks; it does not alter mechanisms, crosswalk dispositions or verdicts.


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
