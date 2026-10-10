---
inert_arms:
  - coalition-weights
  - soviet-constraint
  - cultural-openness
---

# P06 political counterfactual forks

Run identity: parent `outputs/p06-fork-parent` (`p04_political_simulation`, `ontology_id = intermediate8_v1`, `fidelity = f1`, manifest digest `45999d89…`). These are F1 political-run counterfactuals; their magnitudes are not comparable with the F2 historical material replay's numbers elsewhere in this report.

All arms completed 116 ticks through 1985Q4. These are counterfactual simulation outputs under declared assumptions, not historical probabilities, fitted histories, or validation. Material values below aggregate broad model commodity groups and are not GDP or observed-series crosswalks. Accounting invariants passed for each arm; frozen historical-F2 gates were not reclassified by these forks.

## Setup

Each arm starts at the shared tick-0044 checkpoint (1967Q4; next tick 1968Q1). Control is the empty-intervention hist-nem fork from that checkpoint.

Parent manifest digest: `45999d895dac3b84bc69918273eed0c3b51489cba9ddae4fdbb2a20c54411f27`; parameter hash: `2cff7aaee486fad0c38d809c6112b8a286d3e215353f674fd2e0e65aed48d2bf`. Full compact metric payloads and identities are in the local `outputs/p06-arms/summary.json` (ignored run evidence).

| Arm | Replay digest | Production sum | Household consumption | Availability unmet | Undelivered share | Treasury first-zero tick | Mean opposition risk | Mean information latency | Accounting |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `control` | `1e7e4d846c9ba5cefa86669bce0a441caac934959ad08108e212b6b0481530b8` | 16,792,937 | 3,403,745 | 3,357,464 | 0.3671 | none | 0.3386 | 0.4741 | PASS |
| `coalition-weights` | `47bd3c4d8741ab20944759dd4d90557febae846637d57d9620e80815865b7632` | 16,792,937 | 3,403,745 | 3,357,464 | 0.3671 | none | 0.3386 | 0.4741 | PASS |
| `soviet-constraint` | `129f0833ab06faeaca0f0f9d27d9d0eb4097ad35addef9f37b2bbc4324e21fe2` | 16,792,937 | 3,403,745 | 3,357,464 | 0.3671 | none | 0.3386 | 0.4741 | PASS |
| `consumer-import` | `007533bd922b0663b31201739291fac04c2bc7dcf685bb68189a6fcd1d3ed324` | 16,761,562 | 3,396,817 | 3,364,240 | 0.3673 | none | 0.3386 | 0.4741 | PASS |
| `cultural-openness` | `72571643d578c436efc0e99178ac99d1950b69a4872c5c0c5406e5aa7e943171` | 16,792,937 | 3,403,745 | 3,357,464 | 0.3671 | none | 0.3386 | 0.4741 | PASS |
| `second-economy` | `dd1cf22a50482a7ef58ca30dc35ef1f42ca8d0560eff26b5f22e7962581ebc88` | 16,785,315 | 3,406,375 | 3,354,408 | 0.3668 | none | 0.3386 | 0.4741 | PASS |

The output digest is retained per fork. Policy weights, policy coordinates, opposition and information distributions, per-commodity stocks/flows, finances, and department splits are present in `summary.json`. The bank-reserve metric family is not collected by compact fork output. No arm exceeded the 10-minute runtime ceiling.

`coalition-weights`, `soviet-constraint` and `cultural-openness` match the control on every reported metric while their replay digests differ — the intervention changed internal state but no reported outcome in this configuration; that is a finding about those levers, not an omission.

## Mechanism disposition

M8 and M9 remain **UNIDENTIFIED** because their coalition, observation, and information dependencies are unidentified. Changed political outputs are conditional model responses, not evidence about historical mechanism truth.
