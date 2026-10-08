# P04 — Politics / External History / Technology / Culture / Orchestration

Status: **mechanism delivered; not a historical fit.** Every political, external
and information quantity in this phase is a declared engineering fixture
(`structural_assumption / not_calibrated / not_assessed`). Nothing here is
calibrated against observed Hungarian series, and no historical probability is
claimed for any simulated outcome.

Contract: `P04_POLITICS_EXTERNAL_PLAN.md`, `BASELINE.md` §§7, 11–19, 20–24, 35.

---

## 1. What was built

New modules (all under `src/hsm_lab/`):

| Module | Role |
|---|---|
| `contract/politics.py` | Frozen P04 contracts: axes, `PolicyVector` (19 coords), `PolicyReplayRegistry`, `PoliticalRunSpec`, `PoliticalParameters` (+ coalition/broker/information/observation/culture/opposition/external-recipe blocks), `EventRegistry`, `ExternalWorldPack`, `InterventionSpec`, `BranchSpec`, and the runtime IO dataclasses. |
| `data/external.py` | The only P04 input boundary: external pack build/load, 16-event registry, policy replay schedule compile/admit, information-program build/load. |
| `engine/politics.py` | Coalition multinomial-logit update + broker candidate/utility rule. |
| `engine/technology.py` | Information capability and the seven `I` dimensions (channel-only). |
| `engine/observation.py` | Enterprise reports (strategic bias) + `observe_state` (independent measurement noise, clipping, decomposition). |
| `engine/culture.py` | 3T content classification, visibility multipliers, household identification/exposure/efficacy EMAs. |
| `engine/opposition.py` | County opposition-capacity update + household action propensity. |
| `engine/policy.py` | Policy bridge → runtime `MaterialParameters`/`HouseholdParameters`/catalog + `TickControls` (central-vs-local planning mix). |
| `engine/political_state.py` | Flat, spec-declared P04 state arrays + canonical political digest. |
| `engine/political_run.py` | The single admission owner for a politics-enabled quarter. |
| `storage/fork.py` | Strict counterfactual origin loader + `BranchSpec` assembly. |
| `storage/political_output.py` | Five compact P04 tables. |

Modified: `contract/schemas.py` (`ScenarioSpec.politics`), `data/schemas.py`
(`SemanticKind.POLICY_INPUT`), `data/registry.py` (`load_policy_input`, explicit
`load_forcing` semantic gate), `engine/material.py` (`tick_material(controls=…)`,
mixed central/local target), `engine/state.py` (P04 history buffers,
`material-state-v3`), `engine/accounting.py` (mixed-target rule + capacity
ceiling), `storage/checkpoint.py` (`material-checkpoint-v3`, political payload,
P04 table validation, parameter-hash merge), `storage/material_output.py` (P04
tables), `provenance/manifest.py` (`p04_political_simulation`, political mode and
branch fields), `cli/app.py` (`run` dispatch, `fork`, `data build-p04-inputs`).

Inputs committed: `data/manifests/external_events.yml` (16 events, explicit
channels), `data/manifests/policy_replay.yml`, and generated fixtures under
`data/fixtures/` + `data/reconstructed/` (`p04 data build-p04-inputs`).

---

## 2. The user's requirements, and where each is enforced

**Every external event goes through an explicit channel.** The 16-event registry
declares `signal_channels` from the fixed nine-channel vocabulary
(`western_comparison, official_policy, opposition_success, public_action_risk,
foreign_linkage, intellectual_linkage, worker_linkage, regime_threat,
repression_cost`); `EventSpec` rejects an unknown channel or an unknown economic
series reference at load time. Events activate channels; they never touch a
quantity.

**No `event → support +20` magic constant.** A per-channel signal recurrence
(`signal_t = clip(persistence·signal_{t−1} + Σ_active default_loading, −1, 1)`)
plus 3T-filtered broadcast delivery is the only path from an event to a
political quantity. There is no `support` variable anywhere; the coalition rule
consumes the ten declared feedback features and the broker rule consumes the
five declared objectives, each scaled by flattened, bounded, auditable
parameters. An event naming a *bound continuous series* (oil, rates, CMEA
price) adds no second shock — the event only annotates.

**Coalition weights are latent state with provenance/parameter status.** The
four weights live in the checkpointed political state; their rule coefficients
are `p04.coalition.*` scalars registered as `latent_parameter` artifacts with
`structural_assumption / not_calibrated / not_assessed` prior files. The
declared engineering betas make a bad-growth/Soviet quarter favour the
conservative coalition and the sign-flipped set reverses it (tested).

**Mode A and Mode B on the same initial/external state.** `p04_replay` and
`p04_endogenous` share identical material/household/organization recipes and the
same immutable external pack; they differ only in `politics.mode`. Mode A demands
a replay registry (and is refused without one); Mode B forbids one. `load_forcing`
rejects `policy_input` variables and `load_policy_input` rejects `external`
variables, so replay can never leak into the external world (tested).

**Mode C only by fork from the same checkpoint.** `PoliticalRunSpec` *rejects* a
scenario that declares `mode=counterfactual`. `hsm fork` restores the parent
boundary through the strict material loader (same gates, no relaxation), records
the source-checkpoint hash, base mode, declared and inherited interventions, and
continues only the suffix. A no-op fork is bit-identical to a plain resume of the
same boundary (verified end-to-end: `hist-nem` digest
`d2ad01279984d993…` == `--resume` continuation digest).

**State observation separates measurement error from strategic bias.** Each
published feature is stored as `raw_truth + measurement_noise + strategic_bias`
with the raw pieces kept separately; noise is independent zero-mean uniform with
scale `σ(c)·noise_scale·declared_scale`, while bias is the declared
`(F,3)` projection of enterprise demand-overstatement / inventory-concealment /
capacity-misstatement — **never** multiplied by `(1−c)`. Raising capability from
0.2 to 1.0 with identical draws strictly shrinks the measurement noise and leaves
the strategic bias unchanged (tested).

**Technology only improves information channels.** `engine/technology.py`
contains no production, capacity, IO or productivity term; it maps capability to
`data_latency, measurement_error, forecast_accuracy, optimization_capacity,
inventory_visibility, reporting_speed, computational_cost`. The material kernel
never receives capability. Physical outputs differ only through the declared
observation → policy/planning chain.

**SocioVerse2 branching** — see §5 (gap).

**1968 institutional fork fixture.** One origin checkpoint at 1967Q4 (`tick-0044`)
forks five arms from the *same* boundary: `hist-nem` (empty, no-op),
`no-reform`, `nem-plus`, `nos-hu`, `digital-nem`. Each ran the full 116 quarters
with a distinct behavior digest; NÖS-HU is labelled an institutional experiment,
not a Hungarian historical plan.

**1980–81 Poland spillover, dual-channel.** The same event drives
`opposition_success`/`worker_linkage` (→ county efficacy, worker linkage) *and*
`regime_threat`/`repression_cost` (→ broker objective weights and risk), and
1981Q4 raises `public_action_risk`. Observed in the admitted run: county
`perceived_efficacy` rises 0.0267 (1980Q1) → 0.0867 (1981Q3) while
`repression_exposure` rises 0.230 → 0.246; 1981Q4 lifts household
`weighted_risk` 0.30 → 0.50 and efficacy falls to 0.078 — the risk channel and
the efficacy channel move independently, and grievance is never deleted.

---

## 3. A quarter, end to end

1. read the immutable external slice + active events; compile 3T/audience/TTL
   broadcast deliveries;
2. advance the per-channel signal recurrence; apply one-shot/windowed
   interventions to *temporary* views; select the lagged published observation
   (`source = max(t−1−total_lag, cursor)`); assemble the ten feedback features
   (domestic ones from the published view, `soviet_constraint`/`external_pressure`
   from the current external slice, `technology_capacity` from the previous
   closing capability); update coalitions; form the policy (replay / broker);
3. commit the transition, accumulate information capability (usable from the next
   decision), compile the effective material/household parameters and the
   central-vs-local planning mix;
4. run the material kernel — the only producer of realized quantities;
5. update county opposition / household culture / action, write the closing
   observation ring, the objective/prediction rings, the planner forecast;
6. material invariants + P04 gates; only then advance the digest chain, append
   the material and P04 rows, and checkpoint.

---

## 4. Verification evidence (exercised, not asserted)

- `uv run pytest -q` → **290 passed** (13 new P04 tests across
  `test_politics.py`, `test_information.py`, `test_opposition.py`,
  `test_external_history.py`, `test_political_run.py`, plus extensions to
  `test_data_roles.py` and `test_output.py`).
- Full CLI smoke: `p04_replay` and `p04_endogenous` each completed
  **116 ticks → 1985Q4**; `p04_replay` 1968Q1 `enterprise_autonomy == 0.7` with
  `policy_source == replay`; `p04_endogenous` used `policy_source == broker`
  throughout and its 1968Q1 autonomy shows the Soviet bound binding at 0.76.
- `hsm fork` from `tick-0044` produced the five 1968 arms (all 116 ticks, distinct
  digests) and the `p04-pest-broadcast` branch; the Pest broadcast delivered to
  `pest` only, `ttl=2`, two quarters of rows.
- Material/finance tolerance ratios over the full A run: max ≤ 0.0073 / 0.0009
  (well inside the unchanged tolerances).
- P04 tables cover every tick: `political_quarters`=116,
  `information_quarters`=1160 (116×10), `opposition_regions`=2320 (116×20);
  `policy_decisions` is empty for Mode A (no dummy utility rows).

---

## 5. Known gaps / honest limitations

1. **SocioVerse2 longitudinal adapter layer is not implemented.** Branching uses
   the project's own checkpoint/replay (the fallback the plan explicitly permits
   when the framework's `WarmStartSpec` action replay cannot serve as a state
   branch), and the existing real-store smoke (`hsm doctor --socioverse-smoke`)
   still passes. The `EnvironmentProvider/PopulationProvider/DecisionModel/
   MetricCollector` adapters and a real `LongitudinalSimulator` panel over the
   26 institutional IDs are **not** wired. Plan acceptance criterion 7 is
   therefore **partial**.
2. **P02 material-chain degeneration persists.** With the mandated
   `p02_100`/N=1000 recipe the synthetic economy collapses toward zero realized
   production over the horizon (this is the pre-existing P02/P03 degeneration;
   e.g. `outputs/p03-full-horizon` shows the same trajectory). P04 deliberately
   does **not** paper over it with political parameters; consequently the late
   political features (worker unrest, contract gap) are near their floors and
   no arm is claimed to fix shortages or debt.
3. **Policy replay coverage is explicitly partial.** Exactly one
   source-confirmed date is registered (1968Q1 *enterprise autonomy*); every
   other coordinate is carried forward from the declared initial vector. The
   0.7 magnitude is an engineering structural assumption, not an observed policy
   intensity.
4. **Political parameter registration granularity.** Latent priors are
   registered per parameter *module* (`p04_<module>_prior`), with per-scalar
   values and bounds recorded inside each prior file. The plan's "one artifact
   per flattened scalar" was not followed, to keep the registry tractable; this
   is recorded here rather than silently widened.
5. **`p04_*_external` scenarios** require the admitted P02 external pack
   (`hsm data build-material-forcing --profile external`); the external P04
   profile refuses without it and never falls back to synthetic.
