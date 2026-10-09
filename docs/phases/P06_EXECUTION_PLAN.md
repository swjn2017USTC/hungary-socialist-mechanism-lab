# P06 execution plan — mechanism experiments under the reproduction scope

**Scope.** Execute P06 on the basis of the path-B decision (`P05_REPORT` §6.1): the study is a
*historical reproduction under declared behavioural assumptions*, `calibrated = 0`, no parameter
block promoted to `identified`. This plan turns the P06 deliverables of `OMP_PLAN` §10.1 into
work items with exit criteria, evidence, and a prohibition list. The clearance checklist
(`docs/phases/P06_CLEARANCE.md`, `hsm calibration p06-clearance`) is the entry gate and currently
reports **12 PASS / 5 WAIVED / 0 open**.

- Base: `d8762f2`, `main`. Suite **388 passed**, `ruff` clean, Mac only, `.venv` python 3.12.
- Legacy digest: `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`.
- Reserved window 1986Q1–1988Q4 stays closed; the hold-out is never used for selection.

## 0. Prohibitions (apply to every work item)

1. Do not promote any parameter block to `identified`, and do not report Sobol or
   second-order indices for unidentified parameters: `p04_coalition_prior`,
   `p04_culture_prior`, `p04_external_recipe_prior`, `p04_information_prior`,
   `p04_observation_prior`, `p04_opposition_prior` stay UNIDENTIFIED.
2. Do not write `SUPPORTED` for a card whose mechanism needs an unidentified parameter.
   Such a card's verdict is `CONDITIONAL` at best, `UNIDENTIFIED` when the mechanism cannot be
   exercised without assuming the block.
3. Do not change a default, a scenario value, or a frozen registry to make an arm behave.
4. Do not fabricate observed series; the seven unadmitted target-role variables stay unadmitted.
5. Do not compare against hold-out or reserved values; the window protocol refuses them and
   must stay in force.
6. Every arm records its parameter hash, seed, intervention hash and replay digest.

## 1. What already exists (use it; do not rebuild)

| piece | path | state |
|---|---|---|
| mechanism-card schema + validator | `config/p06/mechanism_card.schema.json`, `src/hsm_lab/calibration/mechanism_cards.py` | present; `extra="forbid"`, frozen; fields: mechanism_id `M1..M11`, hypothesis, manipulated_variables, controlled_variables, metrics, falsification_criterion, minimum_replicates, result_categories, calibrated_parameter_dependencies |
| the 11 mechanism definitions | `BASELINE.md` §M1–M11 (lines ~2255–2300) | present as one research question each (social-contract ratchet, soft-budget shortage, labour-power feedback, second-economy valve, reform paradox, debt-financed stability, regional contract inequality, political reform cycle, information capacity, external-shock absorption, departmental composition / consumer bottleneck) |
| forcing ladder | `config/p06/forcing_ladder.json`, `src/hsm_lab/calibration/forcing_ladder.py`, `docs/phases/P06_FORCING_LADDER.md` | H0–H4 = `credit_envelope_fraction` 0.5→0.9 ramp on `intermediate8`, 232 ticks, seed 1729; H0–H3 certificate pass, **H4 periodic output residual 1.3666e-6 vs 1e-6** |
| per-axis sweeps | `src/hsm_lab/calibration/axis_sweep.py`, `hsm calibration axis-sweep` | axes: credit envelope, input-credit earmark, transport capacity, interest remittance, turnover remittance |
| paired comparator | `src/hsm_lab/calibration/fidelity.py` | smoke comparison (bias, p90, Spearman, direction) with refusal paths; the real command refuses without a linkage |
| window protocol | `src/hsm_lab/calibration/window_protocol.py` | hold-out/reserved refusal; **not yet wired into the target-loading path** |
| reproducibility bundle | `src/hsm_lab/calibration/reproducibility_bundle.py` | 1-tick replay smoke; **not yet CLI-integrated** |
| 1968 fork arms | `config/interventions/{hist-nem,no-reform,nem-plus,nos-hu,digital-nem,pest-western-broadcast}.json` | present; `hist-nem` is the empty (replayed) control |
| fork command | `hsm fork --checkpoint <dir> --intervention <file> --until <YYYYQn>` | present |
| 1968Q1 fork point | `outputs/*/checkpoints/tick-0044` (e.g. `outputs/p04-replay/checkpoints/tick-0044`) | present |
| intervention targets | `INTERVENTION_TARGETS` = `coalition_weights`, `broker.objective_weights`, `technology.capability`, `soviet_constraint_multiplier`, `information.broadcast`; plus `policy.<coordinate>` for the 19 coordinates (`plan_utilization`, `enterprise_autonomy`, `investment_intensity`, `industrial_priority`, `admin_price_factor`, `wage_factor`, `credit_fraction`, `budget_hardness`, `housing_factor`, `borrowing_factor`, `consumer_import_factor`, `second_economy_tolerance`, `welfare_provision`, `private_autonomy`, `cultural_openness`, `supported_boundary`, `tolerance_boundary`, `repression`, `information_investment`) | present |

Available artifacts for metrics: `national_accounts`, `aggregates`, `tick_diagnostics`,
`stage_balances`, `money_stock`, `sector_circuit`, `commodity_circuit`, `bank_circuit`,
`household_budgets`, `organization_diagnostics`, `departments`, `political_quarters`,
`opposition_regions`, `policy_decisions`, `information_quarters`.

## 2. Work items

### W1 — Register the eleven mechanism cards (pre-registration, no results)

Write `config/p06/cards/M1.json` … `M11.json` using **Annex A verbatim**, add a loader
(`load_mechanism_cards(root) -> list[MechanismCard]`) plus a test that (a) all eleven ids are
present exactly once, (b) every card validates against the frozen model, (c) every card admits
all five result categories, and (d) any card whose `calibrated_parameter_dependencies` names an
UNIDENTIFIED block cannot be pre-registered with a `SUPPORTED`-only category list.
*Exit:* eleven files, loader, tests green; a `docs/phases/P06_MECHANISM_CARDS.md` table listing
id, hypothesis and dependencies. **No verdict is written in W1.**

### W2 — Structural audit and OAT/invariant perturbation (funnel steps 1–2)

Extend `axis_sweep` with the declared structural parameter axes that are not yet swept
(`bailout_envelope_fraction`, `wage_rate`, `service_split` shares, `handling_work_per_unit`,
`trade` demand vectors) and run a one-at-a-time perturbation table on `historical_f2_replay`,
116 ticks, with the terminal criteria (§T) reported. Record which axes move the reproduction
metrics and which are inert. *Exit:* a sensitivity table in `docs/phases/P06_SENSITIVITY.md`
with the axis, the perturbed value, the metric delta, and the digest for each arm.

### W3 — Morris screening (the deferred D3)

Implement elementary-effects screening over the declared structural parameter set (the fixed
rules plus the material parameters), with the same refusal discipline as the fidelity stage:
Morris is a *screening* of declared inputs, never an estimator. Select the 6–10 inputs with the
largest elementary effects and record the ranking. **Sobol is out of scope in this plan** — it is
forbidden for unidentified parameters and no identified parameter exists. *Exit:* a Morris
implementation with a smoke test on `intermediate8`, a recorded screening table, and a test that
the Sobol entry point refuses to run without an identified parameter set.

### W4 — Close or document the forcing-ladder certificate

The H4 rung fails the periodic output residual (`1.3666e-6` vs `1e-6`). Either (a) find and fix
the cause inside the ladder's own configuration and re-run, or (b) if it is a kernel property,
record it as a finding in `P06_FORCING_LADDER.md` with the exact residual and the arm's
disposition, and state that the ladder is reported as `conditional` for H4. Do not widen the
tolerance. *Exit:* either all five rungs pass, or the failure is documented with its cause and
the ladder's H4 disposition is explicit.

### W5 — 1968 institutional fork (five arms + control)

Fork from `outputs/<run>/checkpoints/tick-0044` (1968Q1) with each intervention file, control =
`hist-nem` (empty list). Record per arm: the policy path (`political_quarters`), the material
reproduction metrics, the household outcomes, the opposition measures, and the digest.
*Exit:* `docs/phases/P06_1968_FORK.md` reporting the five arms against the control, each card
that touches 1968 (M5, M6, M8, M9) marked with the verdict its evidence supports — which cannot
exceed `CONDITIONAL` because the political blocks are unidentified.

### W6 — 1973 external-shock arms (five arms)

The OMP_PLAN §10.4 list maps onto the existing intervention vocabulary as **Annex B**; create
`config/interventions/1973-*.json` for the five arms and run each as a fork or as a full-window
scenario run (record which and why). *Exit:* `docs/phases/P06_1973_SHOCK.md` with the arm table,
the propagation metrics (trade channels, investment, consumption, shortage proxies), and the
M6/M10 dispositions.

### W7 — Political counterfactual (five arms)

Fork from 1968Q1 with: `coalition_weights` (one-shot, W weights), `soviet_constraint_multiplier`,
`policy.consumer_import_factor`, `policy.cultural_openness`, `policy.second_economy_tolerance`.
Report the policy path, opposition measures, information state, and the reproduction metrics.
*Exit:* `docs/phases/P06_POLITICAL_COUNTERFACTUAL.md`; every verdict capped at `CONDITIONAL` or
`UNIDENTIFIED` (the blocks that would make them identified are precisely the unidentified ones).

### W8 — Uncertainty intervals, final reproduction report, reproducibility bundle

1. Wire `window_protocol` into the target-loading path so the refusal is a pipeline property,
   not a library function, with the existing tests extended (this closes audit finding R4).
2. CLI-integrate `reproducibility_bundle` so a recorded run's digest can be rebuilt from the
   bundle, with a test.
3. For every arm, report intervals across the declared seed bank
   (`seed_banks.initial_seed_pairs 3`, `f2_replicates_per_vector 3`) — as *replication spread*
   of a deterministic model, never as a posterior.
4. Write `docs/phases/P06_FINAL_REPORT.md`: the reproduction-scope baseline table (admitted
   series vs simulated annual aggregates with the declared tolerances), the eleven card verdicts
   with their evidence, the sensitivity ranking, the arm tables, and the explicit statement of
   what is assumed rather than inferred.
*Exit:* the final report plus a green `hsm calibration p06-clearance` with the P06 items added.

## 3. Metric vocabulary (§T: the reproduction metrics)

Reported for every arm, from compact outputs only:

- **material reproduction**: annual aggregates of `national_accounts.production` by commodity
  compared with the admitted series where a counterpart exists;
- **household**: `household_consumption`, `household_budgets.spending/voluntary_saving/forced_saving`,
  `aggregates.household_availability_unmet`, `household_budgets.deferred_close`;
- **shortage/assortment proxies**: `tick_diagnostics.bottleneck_demand_count`,
  `aggregates.undelivered` share, `commodity_circuit.stock_close` piles by commodity;
- **finance**: `money_stock.interest_paid/principal_close/money_total_close`,
  `treasury_cash` path, `bank_circuit` reserves;
- **political**: `political_quarters` weights and policy coordinates, `elite_cohesion`,
  `soviet_bound/soviet_violation`, `selected_candidate`;
- **opposition**: `opposition_regions.capacity`, `weighted_grievance`, `weighted_voice`,
  `weighted_risk`;
- **information**: `information_quarters.data_latency/measurement_error/forecast_accuracy/
  optimization_capacity`;
- **departmental**: `departments.actual_use_value` split by department, plus
  `service_use_productive` vs `service_use_household`.

Terminal criteria T1–T3 from `config/calibration/p05.json` are reported for material arms
(they are diagnostic here, not a pass/fail gate, because the reproduction scope waives the
frozen acceptance gates).

## 4. Budget and prerequisites

- Material 116-tick run ≈ 8 s; a political 116-tick run **must be measured first** (run one and
  record the wall time) before scheduling W5–W7; if a single political arm exceeds ~10 minutes,
  report that and reduce the arm count with the user rather than migrating platforms.
- W1–W4 are cheap (< 10 minutes total) and can run immediately.
- W5–W7 need a political run that reaches 1968Q1 with checkpoints; verify
  `outputs/<run>/checkpoints/tick-0044` exists (it does for `p04-replay`, `p04-endogenous`,
  `p04-1968-origin`, `rp-endo`, `rp-origin`) before scheduling.
- W8's clearance rerun needs the pytest evidence file regenerated
  (`outputs/p06-clearance/pytest.json`).

## 5. Ordering

```
W1 ─ W2 ─ W3 ─ W4            (cards, sensitivity, Morris, ladder — all on material catalogs)
W5 ─ W6 ─ W7                 (forks; measure one political run first)
W8                          (protocol wiring, bundle, intervals, final report)
```

W1 must precede W5–W7: the cards are pre-registrations, and a verdict recorded before its card
exists is invalid.

---

## Annex A — the eleven mechanism card faces (write these into `config/p06/cards/M*.json`)

Every card lists all five result categories. `minimum_replicates` is 3 (the declared seed bank
`f2_replicates_per_vector`), and replication spread is reported as spread, not as a posterior.
Where a card's mechanism requires an unidentified block, that block is named in
`calibrated_parameter_dependencies` and the card's verdict is capped at CONDITIONAL/UNIDENTIFIED.

**Identifier convention.** Dependencies name the registry **`artifact_id`** — the canonical
parameter key, which is also the key of `config/calibration/p05.json` `identification` — not the
registry's `variable_id`. So the six unidentified blocks are written `p04_coalition_prior`,
`p04_culture_prior`, `p04_external_recipe_prior`, `p04_information_prior`,
`p04_observation_prior`, `p04_opposition_prior`, and each currently carries the label
`unidentified`. A loader test must resolve every dependency string to a registry artifact_id and
fail on an unknown one.

**M1 — Social-contract ratchet** (`BASELINE.md` M1)
- hypothesis: consecutive consumption improvement raises the political cost of a later
  welfare/real-income cut nonlinearly, so an equal cut provokes a larger response after a long
  improvement run than early in the window.
- manipulated: `policy.welfare_provision` one-shot cut of equal size applied at 1961Q1 vs
  1967Q1; `policy.consumer_import_factor` as a second real-income lever.
- controlled: external history and the intervention files; seed; the remaining policy vector.
- metrics: `household_consumption`, `household_budgets.spending`, `opposition_regions.
  weighted_grievance`, `political_quarters.policy_welfare_provision`, `forced_saving`.
- falsification: the late cut's response in the grievance/consumption metrics is not larger than
  the early cut's by the declared margin.
- dependencies: `p04_coalition_prior`, `p04_observation_prior` (both UNIDENTIFIED).

**M2 — Soft-budget shortage**
- hypothesis: soft budget plus investment hunger is sufficient to sustain systemic shortage
  independently of the demand regime.
- manipulated: `policy.budget_hardness`, `policy.credit_fraction`, `bailout_envelope_fraction`,
  `credit_envelope_fraction`.
- controlled: demand shocks, external history, seed.
- metrics: `tick_diagnostics.bottleneck_demand_count`, `aggregates.undelivered` share,
  `organization_diagnostics.credit_drawn/shortage_expectation_mean`, `commodity_circuit.stock_close`.
- falsification: with hardness raised and credit cut, the shortage metrics do not fall.
- dependencies: none beyond declared structural rules (this card can reach SUPPORTED).

**M3 — Labour-power feedback**
- hypothesis: full employment weakens enterprise discipline and feeds wage/hoarding feedback.
- manipulated: `policy.wage_factor`, `policy.plan_utilization`.
- controlled: output targets, external history, seed.
- metrics: `organization_diagnostics.labor_mean/wage_arrears_sum`,
  `national_accounts.production` per worker proxy, `aggregates.household_desired` vs delivered.
- falsification: a wage-factor raise does not increase labour hoarding/arrears or reduce
  discipline metrics.
- dependencies: none beyond declared rules.

**M4 — Second-economy valve**
- hypothesis: the second economy is net stabilising or net eroding for the formal system.
- manipulated: `policy.second_economy_tolerance`, `policy.private_autonomy`.
- controlled: formal-sector parameters, external history, seed.
- metrics: `aggregates.plot_self_use/plot_market_sales`, `household_budgets.plot_income_formal/
  plot_income_direct`, formal `household_availability_unmet`, `departments.service_use_household`.
- falsification: tolerance changes move neither the household availability gap nor the formal
  sector's delivery metrics.
- dependencies: `p04_culture_prior` (UNIDENTIFIED) for any cultural channel claim.

**M5 — Reform paradox**
- hypothesis: enterprise autonomy rising while soft-budget constraints persist produces
  efficiency gains and macro imbalance simultaneously.
- manipulated: `policy.enterprise_autonomy` (the replayed 1968 patch is 0.7), separately
  `policy.budget_hardness`.
- controlled: external history, seed, the other coordinates.
- metrics: `organization_diagnostics.investment_approved/credit_drawn`,
  `national_accounts.production/used`, `tick_diagnostics.bottleneck_demand_count`,
  `money_stock.money_total_close`.
- falsification: autonomy raises do not change the efficiency proxy without also changing the
  imbalance proxy (or vice versa).
- dependencies: `p04_coalition_prior`, `p04_information_prior` (UNIDENTIFIED).

**M6 — Debt-financed stability**
- hypothesis: external debt lengthens the social contract and shifts its cost forward.
- manipulated: `policy.borrowing_factor`, `convertible_loan_limit`, `convertible_credit_envelope`.
- controlled: external demand, seed, domestic policy.
- metrics: `national_accounts.imports` by channel, `money_stock` (credit/principal),
  `household_consumption`, `treasury_cash`.
- falsification: additional borrowing does not defer the consumption/treasury deterioration.
- dependencies: `p04_external_recipe_prior` (UNIDENTIFIED, and it has no path to trade —
  see `P05_REPORT` §6.2), so post-1973 arms may only be reported as CONDITIONAL.

**M7 — Regional contract inequality**
- hypothesis: uneven distribution of social-contract gains across Budapest, the industrial belt
  and the agricultural counties creates different stability paths.
- manipulated: regional allocation via `policy.investment_intensity` plus
  `policy.housing_factor`; the 20 historical regions are the observation axis.
- controlled: national aggregates, external history, seed.
- metrics: `aggregates` and `household_budgets` by `region_id`; `opposition_regions` by region.
- falsification: regional dispersion of the delivery/consumption metrics does not respond to
  the regional allocation levers.
- dependencies: `p04_opposition_prior`, `p04_coalition_prior` (UNIDENTIFIED).
- note: the county geometry is a reconstructed proxy (`P05_REPORT` §3), so any regional claim
  carries that caveat.

**M8 — Political reform cycle**
- hypothesis: economic deterioration strengthens administrative conservatism under some
  conditions and the reform coalition under others.
- manipulated: the fork's `coalition_weights` and the reported feature path (via the 1968 arms).
- controlled: external history, seed.
- metrics: `political_quarters` mode weights and `selected_candidate`, `policy_decisions.utility`.
- falsification: coalition weights do not switch modes under the declared deterioration path.
- dependencies: `p04_coalition_prior`, `p04_observation_prior`,
  `p04_information_prior` (all UNIDENTIFIED) ⇒ verdict capped at UNIDENTIFIED.

**M9 — Information-capacity hypothesis**
- hypothesis: stronger statistical/computational/feedback capacity removes a measurable share of
  shortage and planning error.
- manipulated: `technology.capability` (one-shot), `policy.information_investment` (the
  `digital-nem` arm).
- controlled: the replayed policy path, external history, seed.
- metrics: `information_quarters.data_latency/measurement_error/forecast_accuracy/
  optimization_capacity`, `policy_decisions.binding_constraints`,
  `tick_diagnostics.bottleneck_demand_count`.
- falsification: capability/investment raises do not reduce latency/error or the shortage metrics.
- dependencies: `p04_information_prior` (UNIDENTIFIED) ⇒ verdict capped at CONDITIONAL.

**M10 — External-shock absorption**
- hypothesis: subsidies, borrowing and CMEA terms postpone an external shock, and the
  postponement raises later fragility.
- manipulated: the 1973 arms in Annex B.
- controlled: seed, the pre-1973 path.
- metrics: `national_accounts.imports/exports` by channel, `money_stock.money_total_close`,
  `treasury_cash`, later-window `aggregates.household_availability_unmet`.
- falsification: the absorption arms do not differ in the size or timing of the postponement.
- dependencies: `p04_external_recipe_prior` (UNIDENTIFIED, no path to trade) ⇒ CONDITIONAL.

**M11 — Departmental composition / consumer bottleneck**
- hypothesis: continued investment and input priority for Department I crowds out
  Department II through raw-material, capital-good and labour competition, raising assortment
  shortage, durable waiting, forced substitution and the social-contract gap even when aggregate
  output grows.
- manipulated: `policy.investment_intensity`, `policy.industrial_priority`.
- controlled: aggregate output path, external history, seed.
- metrics (the five distinctions the mechanism requires): aggregate consumer-goods volume
  (`national_accounts.household_consumption`), assortment/availability
  (`aggregates.household_availability_unmet`, `tick_diagnostics.bottleneck_demand_count`),
  regional distribution (by `region_id`), durable waiting
  (`aggregates.household_desired` vs `delivered` for `g13_household_durables`),
  household welfare loss (`household_budgets` saving/substitution columns),
  plus `departments.actual_use_value` split by department.
- falsification: raising I-priority does not shift the department split or worsen the four
  consumer-side dimensions while output is held up.
- dependencies: none beyond declared structural rules (this card can reach SUPPORTED).

## Annex B — 1973 arm → intervention mapping

| arm (OMP_PLAN §10.4) | intervention target(s) | note |
|---|---|---|
| historical borrowing / consumption smoothing | `policy.borrowing_factor` ↑ (with `policy.consumer_import_factor` ↑) | control-like arm for the shock |
| immediate consumption restraint | `policy.consumer_import_factor` ↓, `policy.welfare_provision` ↓ | |
| investment restraint | `policy.investment_intensity` ↓ | |
| price adjustment + wage compensation | `policy.admin_price_factor` ↑ with `policy.wage_factor` ↑ | two specs in one arm |
| hard budget | `policy.budget_hardness` ↑, `policy.credit_fraction` ↓ | |

Each arm's intervention file declares `effective_quarter: 1973Q1`, `until_quarter: null`, and a
`provenance` string stating it is a declared counterfactual, not a historical estimate.

---

## Execution prompt (paste into a local Codex)

```text
Execute docs/phases/P06_EXECUTION_PLAN.md in this repository (commit d8762f2 or later, main).
First read: P05_REPORT §6 and §11 (reproduction scope), docs/phases/P06_CLEARANCE.md,
docs/phases/P06_CLEARANCE_LOG.md, and this plan's §0 prohibitions and Annex A.

Rules:
- Work one work item at a time; an item is done only when its own exit criterion is met and its
  evidence is committed. Append each completed item to docs/phases/P06_CLEARANCE_LOG.md.
- W1 first: write the eleven cards from Annex A verbatim (no verdicts), with the loader and tests.
  A card depending on an unidentified block must name that block and cannot be SUPPORTED-capable.
- Never promote a parameter block to identified; never report Sobol/second-order indices; no
  calibration claim anywhere. Morris is screening only.
- Do not change defaults, scenarios or frozen registries. Do not fabricate observed series.
- Keep the reserved window closed and the hold-out unused; keep the window-protocol refusal tests
  in force.
- Measure one political run's wall time before scheduling W5-W7 and report it; do not migrate
  platforms. Mac only, ruff clean, run the suite after each code change.
- Report partial results as partial and falsified mechanisms as falsified.

Finish by running `hsm calibration p06-clearance --with-runs` and reporting: the item table, the
card table with verdicts and their evidence, the sensitivity ranking, the arm tables, the commit
hashes, and pytest/ruff results.
```
