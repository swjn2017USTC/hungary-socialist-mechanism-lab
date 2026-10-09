# P06 W7 — Political counterfactual — OPEN (checkpoint prerequisite)

Five one-shot counterfactual intervention files have been created and validated against `InterventionSpec`. All begin at 1968Q1, contain declared-counterfactual provenance and are not historical estimates. No fork could run: all five plan-listed 1968Q1 checkpoints are v3 while the current loader requires v4, as documented in [W5](P06_1968_FORK.md). The political wall-time prerequisite remains unavailable.

| Arm | Target and value | Intervention file | Canonical intervention hash | Status / verdict ceiling |
|---|---|---|---|---|
| Coalition weights | `coalition_weights=[0.4,0.2,0.2,0.2]` | `config/interventions/p06-political-coalition-weights.json` | `cb0774e0416005bc978dc8bad55d23ca18421ea40b5f945b3cadf2349bc40747` | OPEN; at most UNIDENTIFIED |
| Soviet constraint | `soviet_constraint_multiplier=0.75` | `config/interventions/p06-political-soviet-constraint.json` | `aadbb9c1e68128c0140ed343fda0aef866a2aac71fa601e8231e6731daebc69d` | OPEN; at most UNIDENTIFIED |
| Consumer imports | `policy.consumer_import_factor=0.7` | `config/interventions/p06-political-consumer-import.json` | `42ab454bfbdb88f25284a73b7028c06161fec2eee03105482a85010777ceb0a8` | OPEN; at most CONDITIONAL |
| Cultural openness | `policy.cultural_openness=0.7` | `config/interventions/p06-political-cultural-openness.json` | `8b8f5739188d6666e3c5f18b0f86422d32fcfa25320608bf86fd702ce3bc2547` | OPEN; at most UNIDENTIFIED |
| Second-economy tolerance | `policy.second_economy_tolerance=0.7` | `config/interventions/p06-political-second-economy.json` | `172b8a30c716c58ee177f8d65d8133165fa0ed92ef4aa9051d888b8f878aab2a` | OPEN; at most UNIDENTIFIED |

No policy path, opposition or information metrics, reproduction metrics, arm seed, parameter hash or replay digest is reported because no arm was executed. M8/M9 and other political-block-dependent cards remain UNIDENTIFIED or CONDITIONAL at best. This is an infrastructure blocker, not a negative finding about the political hypotheses. Frozen baseline gates are unchanged and remain blocked.

Validation: `.venv/bin/python` loaded all five `p06-political-*.json` entries with `InterventionSpec.model_validate` → valid.
