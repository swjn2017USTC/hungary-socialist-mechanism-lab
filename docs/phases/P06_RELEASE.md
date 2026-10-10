# P06 release manifest

This manifest freezes the reproduction-scope evidence for the P06 close-out. The frozen source HEAD is the repository state before this close-out change; the close-out commit records this manifest and its checks.

- Frozen source HEAD: `fd025a5bdedf698100e05f736b4209ddc62dd144` (`main`)
- Legacy `historical_f2_replay` digest: `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`
- F1 parent digest: `45999d895dac3b84bc69918273eed0c3b51489cba9ddae4fdbb2a20c54411f27`
- `config/calibration/p06_reproduction_crosswalk.json` SHA-256: `43353fdd09643bc963b2f7002a508284b7e153bcd9ebae5ffb55f88820826aeb`
- Final clearance: **26 PASS / 4 WAIVED / 0 OPEN**
- Full suite: **416 passed, 0 failed** (after close-out tests)
- Scope: `calibrated = 0`; no parameter is identified. Reserved window 1986Q1–1988Q4 was never read; hold-out values were not used.

## Rebuilt reproducibility bundles

| Run | Source | Recorded digest | Rebuilt digest | Result |
|---|---|---|---|---|
| Legacy baseline | `outputs/p05-historical-replay` (current canonical C0 baseline; copied from the completed C0 run) | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` | exact digest and parameter-hash match |
| Trade scenario | `outputs/p06-trade-transmission/C1` (`historical_f2_trade_scenario`; crosswalk scenario source) | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` | exact digest and parameter-hash match |

Bundle directories: `outputs/p06-release-bundles/p05-historical-replay` and `outputs/p06-release-bundles/trade-scenario`; verification replays are under the corresponding `replayed-*` directories. The crosswalk comparison replay itself is paused at 1978Q4 by its declared comparison window and is refused by the bundle tool, which only accepts completed runs; C1 is the completed 116-tick run for the same declared trade scenario and the bundle verifies its exact digest. The older bytes originally at `outputs/p05-historical-replay` are preserved at `outputs/p05-historical-replay-pre-closeout-86f44f6f`. Their digest `86f44f6f7c91e5d3d514d3e5ac723bf640f5b6be087f2b1cf98f5f73938eead8` could not be rebuilt with the current parameter schema: the captured old declaration lacks the five P05 structural fields, and bundle verification returned parameter hash `e27ade6a…` / digest `2013ebe5…`, mismatching the recorded run. The close-out uses the already completed canonical C0 run, whose legacy digest is exactly the frozen `92f9ea0a…`; the failed old attempt and bundle are retained as evidence.

## Unadmitted target-role variables

The seven target-role variables outside the admitted 14-variable comparison are `wage`, `cpi`, `trade`, `debt`, `housing`, `retail`, and `employment`. They remain unadmitted.

## P05 §10b independent-observable acquisition candidates

These six observable families remain acquisition candidates, not verified series: (1) physical input-output tables, fuel/steel/electricity input flows, imports by product and partner, and contract quotas; (2) plan targets versus reported and finally verified output, revision dates and report delays; (3) independent repeated measurements/revisions of the same indicators; (4) MSZMP central committee/politburo composition, key resolutions, cadre appointments and branch investment decisions; (5) cultural facility use, press circulation, broadcast reception, participation rates and possible attitude surveys; (6) dated strikes, petitions, protests, sanctions and policy responses.

## Waivers (verbatim reasons)

- `gate1_closure_audit` — The F2 kernel closure audit fails (status collapsed, output_liveness 0.0). Track A reached its honest exit A7: no tested structural rule met both terminal floors.
- `frozen_acceptance_gates` — Liveness, household service ratios, treasury self-financing and expiry still fail on the replay. Under the reproduction scope the gate table is reported as a result, not cleared.
- `calibration_and_inference` — identifiable_set is empty and no linkage exists, so no paired F1/F2 study and no ABC inference can run. Inference_status stays NOT_RUN.
- `data_path_acquisition` — Admitting the seven unadmitted target-role variables and the P05_REPORT 10b observables is a rights/coverage workstream owned by the user and is not required for the reproduction scope.
