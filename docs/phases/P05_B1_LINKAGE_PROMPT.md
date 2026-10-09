# Prompt for ChatGPT (web) — propose the B1 parameter→target linkage

Copy everything below the line into a ChatGPT conversation. It is self-contained: the model
has no access to the repository, so all facts it needs are included. Attach nothing else.

---

You are helping make an identifiability decision for a research simulation model of the
Hungarian socialist economy, 1957Q1–1988Q4 (quarterly; the study window is 1957Q1–1985Q4 =
116 quarters; 1986Q1–1988Q4 is a reserved window that must never be used here).

## Task

The model has 15 declared parameter blocks. Nine are declared **structural rules** and are
out of scope. Six are **behavioural blocks** currently labelled UNIDENTIFIED because no
declared observable constrains them. I need you to propose a **parameter→target linkage**:

1. which of the six blocks can be informed by which observed target variable, in the exact
   schema below, with the mechanism path and the expected direction;
2. which blocks **must stay UNIDENTIFIED** even after your proposal, and exactly which
   observable would be needed to identify them;
3. the *identification label change* that must accompany each proposed linkage (explained
   below — a linkage alone is not enough in this pipeline).

Be willing to conclude that most blocks cannot be linked. **Do not invent linkages to make
the pipeline produce results.** A linkage that cannot survive the discriminating test below
is worse than none.

## Hard constraints

- **Admissible targets for identification are only those observed inside 1960–1969** (the
  calibration window). Targets observed in 1970–1978 exist and are for later validation, not
  for identification.
- A **hold-out** exists: the same variables observed 1979–1985, stored hash-only. It must
  never inform a linkage, a prior, or a direction. Do not reason from it; you do not have it.
- **Never** propose a linkage whose only justification is correlation, coincidence of trends,
  or "it is the only thing available". The justification must be a causal chain through the
  model's own mechanisms.
- **Directionality is required**: for each linkage, state what the model mechanism does, and
  in which direction the parameter must move to produce a movement in the target, and what a
  *falsifying* observation would look like.
- If two blocks would both load on the same target by mechanisms of similar strength, say so
  and treat them as **jointly unidentified** unless an additional observable separates them.
- If a block has no candidate observable among the admissible set, say so plainly and name
  the observable that would be needed.

## The model, in brief

Four layers, run in one quarterly loop: (1) **material** — 16 commodities, ~20 historical
regions ("counties"), production by technology with capacity and labour, a transport sector
that consumes fuel and provides freight, wholesale/retail handling, stockpiles, and service
output that expires if unsold; (2) **finance** — organisations, banks, treasury, deposits,
bank credit for working capital, wages paid before input purchases, interest accrued on
outstanding principal; (3) **households** — income, consumption budget, savings that are
currently never drawn down, rationed purchases, second economy, housing; (4) **political** —
a policy mode selected each quarter by coalition bargaining over observable features, with
cultural, information and opposition subsystems.

Calibration windows: training 1960Q1–1969Q4; internal validation 1970Q1–1978Q4; hold-out
1979Q1–1985Q4; reserved 1986Q1–1988Q4. Note a structural break **inside** the training
window: the 1968 New Economic Mechanism changed plan directives, enterprise autonomy, prices
and investment decisions, so pre/post-1968 movements cannot be attributed to one behavioural
parameter without a decomposition.

## The nine blocks that are OUT OF SCOPE (declared structural rules, not estimated)

`p02_material_cmea_contract_prior`, `p02_material_cmea_uncertainty_prior`,
`p02_material_oil_warmup_prior` (CMEA contract price, uncertainty multiplier, pre-1960 oil
warm-up), `p04_broker_prior` (an engineering assembly rule),
`p05_input_credit_earmark_prior` (purpose-tied working-capital credit),
`p05_interest_sink_remittance_prior` and `p05_interest_sink_recipient_prior` (disposition of
paid interest), `p05_fiscal_turnover_remittance_prior` (turnover remittance to the treasury),
`p05_household_savings_reentry_prior` (bounded savings draw). All are currently at their
legacy values; several are known to be unreachable under the current settlement layer.

## The six candidate blocks (currently UNIDENTIFIED), with their internal parameters

All are declared with `calibration_status = not_calibrated`, `sensitivity_status =
not_assessed`, and envelope bounds.

1. **`p04_coalition_parameters`** — bounds [0, 2]. Policy-transition coefficients ("betas")
   linking observable features to the weight of each political mode
   (administrative_conservative, reform_technocratic, social_contract_pragmatist,
   sectoral_industrial, …). Features include: growth, shortage, debt_pressure, elite_cohesion,
   external_pressure, soviet_constraint, technology_capacity, previous_policy_error,
   contract_gap. Selection is a softmax/weighted comparison over these feature scores.
2. **`p04_culture_parameters`** — bounds [-2, 2]. Cultural exposure/identification dynamics:
   `exposure_alpha`, `identification_alpha`, `initial_exposure`, `initial_ideology`,
   `official_loading`, `western_loading`, `supported_multiplier`, `tolerated_multiplier`,
   `prohibited_multiplier`. Households update exposure and identification from official and
   western media content; multipliers weight tolerated/supported/prohibited content.
3. **`p04_external_recipe_parameters`** — bounds [-100, 2]. Levels and dynamics of external
   signals available to the model: `base_cmea_demand`, `base_credit_availability`,
   `base_energy_quota`, `base_geopolitical_tension`, `base_soviet_constraint`,
   `base_technology_access`, `base_western_demand`, `base_western_inflation`,
   `debt_reference`, `default_loading`, `signal_persistence`, `signal_clip/lower/upper`.
   These set the exogenous environment the planning layer reacts to.
4. **`p04_information_parameters`** — bounds [0, 8]. The planning information system:
   `latency_scale`, `reporting_scale`, `computational_cost_scale`, `lag_cap`, `learning`,
   `measurement_sigma`, `depreciation`, `information_investment_weight`. Determines how
   stale and how noisy the state the planners observe is.
5. **`p04_observation_parameters`** — bounds [0, 2]. How the observed state is formed from
   the true state: `declared_scale.<feature>` (per feature: growth, shortage, debt_pressure,
   elite_cohesion, external_pressure, soviet_constraint, technology_capacity, worker_unrest,
   contract_gap, previous_policy_error), `bias_incentive_loading`, feature biases,
   `capacity_reference`.
6. **`p04_opposition_parameters`** — bounds [0, 2]. Opposition capacity dynamics: alphas on
   network_size, intellectual_density, worker_linkage, foreign_linkage, samizdat_capacity,
   repression_exposure, perceived_efficacy; plus `attrition_rate`, exposure decay and
   repression/efficacy weights. Outputs a latent opposition pressure, not an observed series.

## Admissible observed targets (only 1960–1969 rows count for identification)

All are real KSH series, annual, compared against annual aggregates of the quarterly
simulation. Read each variable's warning — they constrain what a linkage may claim.

| variable_id | unit | what it is, and what it must NOT be treated as |
|---|---|---|
| `gdp` | index 1960=100 | annual GDP index; comparison only. **Gross material output must never be passed off as GDP.** |
| `consumption` | index 1960=100 | household actual final consumption index; comparison only. |
| `investment` | index 1960=100 | gross fixed capital formation index; comparison only, must not double as forcing. |
| `industrial_output` | index 1960=100 | volume index of industrial production; **independent** of the five featured physical product variables below; not one aggregated "goods". |
| `industrial_electricity` | million kWh (sum) | gross electricity production, energy group. |
| `industrial_crude_steel` | thousand tonnes (sum) | crude steel, raw-materials group. |
| `industrial_fertilizer` | thousand tonnes (sum) | mineral/chemical fertilizers, raw-materials group. |
| `industrial_cement` | thousand tonnes (sum) | cement — a **construction input**, not completed housing. |
| `industrial_television` | thousand units (sum) | television sets, durable-goods group. |
| `ag_cereals` | thousand tonnes (sum) | cereals harvest; **never** used to schedule actual farm output. |
| `ag_wheat` | thousand tonnes (sum) | wheat harvest. |
| `ag_maize` | thousand tonnes (sum) | maize harvest. |
| `trade_export_volume_index` | index 1960=100 | volume index of goods exports (annual mean). |
| `trade_import_volume_index` | index 1960=100 | volume index of goods imports; an import **outcome**, never an imports quota; CMEA composition is never inferred from the total index. |

Model-side counterparts you may reason about: the material layer has 16 commodities (solid
fuels, oil/gas, electricity/heat, basic metals, chemicals/fertilizer, machinery/capital,
construction, agricultural raw, basic food, animal food, textiles, household non-durables,
household durables, vehicles/transport equipment, market services, housing/public services),
regional production by stage (raw / ready / standard), household consumption, investment
installation, and exports/imports split into a CMEA channel and a convertible-currency
channel.

## Seven further target-role variables exist but are NOT in the frozen target registry

`wage`, `cpi`, `trade`, `debt`, `housing`, `retail`, `employment` are declared in the project's
variable registry with a target role, but no frozen target artifact has been admitted for
them (no rows in the target registry). `retail` is described as a commodity-level shortage
proxy availability that is still open; `cpi` is an administrative price index and explicitly
**not** a scarcity measure; `debt` is hard-currency debt context.

Treat these as **acquisition candidates**: if a block can only be identified with one of them,
say so explicitly and name which — do not treat them as if they were admitted. Admitting any
of them is a registry decision outside your task.

## What the pipeline requires (so your output is usable)

- The linkage is stored as a list of `{"parameter": "<artifact_id>", "targets":
  ["<variable_id>", ...]}` entries in the study control file.
- **A linkage entry alone does not make a parameter identifiable in this pipeline**: an
  explicitly declared identity of `fixed` or `unidentified` wins over the linkage. So each
  proposal must come with an explicit statement of the identity label to set (or remove) for
  that block. A block is only "identified" if it is linked **and** its declared identity is
  not `fixed`/`unidentified`.
- Only targets observed inside 1960–1969 and marked `observed` are admissible.

## Deliverable format

**1. Proposed linkage table** — one row per (block, target) pair you propose:

| block | target | mechanism path in the model (which equations/quantities carry it) | expected sign | what would falsify it | confidence (high/medium/low) |

**2. Machine-ready linkage array** (JSON, ready to paste into the control file):

```json
[{"parameter": "<artifact_id>", "targets": ["<variable_id>"]}]
```

**3. Identity-label decisions** — for every one of the six blocks: set to `identified` (with
the linkage above), keep `fixed`, or keep `unidentified`. For each block kept unidentified,
state the single most valuable observable to acquire next and why it discriminates.

**4. Identification risks** — joint-identification collisions between your proposed blocks,
the 1968 break's effect on your proposal, and any place where the target's own warning (see
the table) forbids the claim you would otherwise make.

**5. Honest summary** — one paragraph: after your proposal, how many of the six blocks are
actually identified, and what the calibration can and cannot claim. If the answer is "at most
one block", say exactly that.

Think carefully about mechanisms before writing the table. Correctness and honesty matter far
more than the number of linkages proposed.
