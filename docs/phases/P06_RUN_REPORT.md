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

Detailed family tables: [1968 forks](P06_1968_FORK.md), [1973 shock arms](P06_1973_SHOCK.md), [political arms](P06_POLITICAL_COUNTERFACTUAL.md). The full local `outputs/p06-arms/summary.json` records parameter/intervention hashes and all available §3 metric families; bank-reserve series were not emitted in compact output and remain null. Relevant M5/M6/M8/M9/M10 verdicts remain UNIDENTIFIED due their registered unidentified dependencies.

W9 crosswalk counts: **1 mapped / 3 no_counterpart / 10 blocked**. Numeric reproduction table: one variable (`consumption`), 19 years from calibration/internal validation, 1 within tolerance and 18 outside; mean absolute residual 91.74, maximum 173.64 index points. Overall row summary is `outside_tolerance`, descriptive only. The mapped model index uses its own 1960 base and fixed 0.5-point published-rounding threshold. No hold-out or reserved target values were read. The command was invoked twice: after the first output labelled internal validation simply `validation`, I corrected the output label and reran to a fresh directory. Both replay digests are `f75ba776…`; the final report uses only the second result and no outcome-driven mapping or tolerance change occurred.

Clearance: `.venv/bin/hsm calibration p06-clearance --with-runs --json` is green: **23 PASS / 4 WAIVED / 0 OPEN**. The four WAIVED items preserve the user-declared reproduction scope; no required item remains open. Frozen gates remain failed/unchanged, `calibrated = 0`, no parameter identified, no Sobol/ABC, and no validation claim.

W0.5 commit: `3a3ad69`. W9 implementation/report commit: `28a9bbf2f33e57d1c46339685660ef91ded9cdfe`. `.omp/config.yml` remains a pre-existing user-local edit and is excluded from commits.
