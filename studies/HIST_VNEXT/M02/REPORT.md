# H5A-A1 / M02 — soft budget and investment hunger on the Intermediate-8 enterprise chain

**Phase** H5A-A1 · **Study** M02 · **Mechanism** M2 · **Status** `COMPLETED` (3 seeds × 13 arms × 4 quarters = 156 conserved ticks)
**Runner** `experiments/hist_enterprise.py::run_m02_study` · **Spec** `studies/HIST_VNEXT/M02/spec.json` (SHA-256 `35b5b7ffc622193c26e9be0ca74c75e14dfe444294ae28513fb803fe849bd78b`)
**Run directory** `outputs/hist-vnext-h5a-a1-20261021T100007Z/study-final/` (manifest SHA-256 `673bff2bb7f4bb8202f3bffdcf019a9a242cc36bc01103dde7d1d45b19c583aa`, `status=COMPLETED`, `status_reason="full preregistered design executed"`)
**Evidence root** `outputs/hist-vnext-h5a-a1-20261021T100007Z/` (not committed)

---

## 1. Scope, and the design exposure this run inherits

This is an explicitly **synthetic structural experiment** on the read-only
`intermediate8` branch. It drives the existing material chain only —
`build_material_initial_conditions` → `build_material_network` →
`initialize_material` → `load_material_forcing` → one `tick_material` call per
quarter under `controls=effective.controls`, gated by
`check_material_invariants`. No cash engine, settlement rule, approval cap or
policy pathway was added.

It does **not** restore the Hungarian F2 replay, does **not** touch the F2
investment price axis, and cannot promote any historical status. The H0B
registration for M2 is unchanged: one mapped counter
(`tick_diagnostics.bottleneck_demand_count`, used here as a diagnostic only)
and three blocked metrics, none of whose registration status was altered.

### Design exposure already on the record

`outputs/hist-vnext-h5a-a1-20261021T100007Z/design-probes.json` holds the
planning-phase probes. They are **design-exposed data, not validation**, and no
number below is copied from them: every value in this report is re-derived from
the fresh `study-final` run. Three consequences are carried forward.

1. The bounded 8-arm factor probe already showed nonzero investment
   request/approval and `credit = 0` in the hard arms. The same structure
   reappears here from a fresh run.
2. The **hardness-only probe was NONBINDING**: both hardness levels produced
   byte-identical exported ticks with zero bailout requested and granted. This
   run reproduces that as a designed negative control (§5.1) rather than as
   evidence that soft budget constraints are absent.
3. Two designs were **rejected and discarded and are used nowhere here**:
   - `investment_intensity = 2.5`, written through `model_copy`, bypassing
     `POLICY_BOUNDS["investment_intensity"] = (0, 2)`. The kernel ran it, so it
     produced plausible numbers, which is exactly why it is invalid treatment
     evidence. The spec pins `high = 2.0` and the runner refuses an
     out-of-bounds coordinate before any model is initialised.
   - a re-tuned initial state with `organization_deposit_quarters` lowered from
     the scenario's own `2.0` (the rejected probe used `0.25`), which produced
     a severe output collapse in the hard arms. It is kept as a collapse
     counter-example only. The formal design keeps the original initial state
     untouched.

A pre-existing projects-vs-new-requests counter-example also stays on the
record: a fixture with a pre-approved project shows nonzero installation
differences between allocation orders while **both** orders have zero new
requests and zero new approvals. That difference cannot be read as an M2
first stage, and nothing here relies on it.

---

## 2. Design executed

| Item | Value |
|---|---|
| Source scenario | `config/scenarios/intermediate8.json`, SHA-256 `07b0a1fada377bfa8782f83fb3cdda7b08f88add58d608fddee18becb69df94b` (read-only) |
| Legacy card | `config/p06/cards/M2.json`, SHA-256 `0da621e51ad436103ec3c76d820701cda84e8bb0c9cb79ef0947337856990589` (verbatim; hypothesis and falsification text unaltered) |
| Study spec | `studies/HIST_VNEXT/M02/spec.json`, SHA-256 `35b5b7ff…9bd78b` |
| Typed overrides | `households = 1000`, `ticks = 4`, `seed` per run only |
| Window | `1957Q1–1957Q4`, no warmup, no auto-extension |
| Seeds | `1729, 1730, 1731` — household-heterogeneity robustness over the stochastic initial draw, **not** independent historical samples and **not** enterprise-decision noise |
| Arms (13) | `soft_low_base`, `hard_low_base`, `soft_high_base`, `hard_high_base`, `soft_low_reduced`, `hard_low_reduced`, `soft_high_reduced`, `hard_high_reduced`, `credit_cut_high_base`, `rescue_cut_high_base`, `credit_cut_high_reduced`, `rescue_cut_high_reduced`, `placebo_soft_low_base` |
| Demand regimes | `base` = original `HouseholdParameters`; `reduced` = per channel `base = max(original_minimum, 0.5 × original_base)`, every `minimum` unchanged |
| Budget arms | `soft` = (hardness 0.0, credit 0.5); `hard` = (1.0, 0.0); `credit_cut` = (0.0, 0.0); `rescue_cut` = (1.0, 0.5) |
| Investment levels | `low` = `investment_intensity` 1.0; `high` = 2.0 |
| Policy construction | `default_initial_policy(...).patch(...)` then `compile_effective_policy` per quarter; `model_copy` is never used to write a coordinate |
| Fixed controls | `central_target = None`, `investment_approvals = None` (confirmed in every trace row's `controls_binding`) |
| Placebo | `placebo_soft_low_base` — same treatment as `soft_low_base`, different label only |

Input identity per seed (all 13 arms of a seed enter from the **same** opening
state, verified against `per_arm[*].opening_state_digest`):

| seed | households | opening state SHA-256 | network SHA-256 | forcing SHA-256 | account directory SHA-256 | accounts |
|---|---:|---|---|---|---|---:|
| 1729 | 1000 | `3107888b4d9ebe55c6c9573be0ee8af563019fb50a0991a1a5a0b701c11b0138` | `2c29efb0dbe91145a089632f6b99d653e257f420b2f984093099d5cd9a571000` | `7c5bfc06cc32fcd4b13d4f8a92293213c927825c174a63db60a03fd3c9d9149d` | `da9078d9a6b96501f3a610eccf9fdc90628449799cc81276940568d064457a8d` | 3841 |
| 1730 | 1000 | `cabe34326b29d4b38e36c8923a29381f90be948599cb38a6e339aa72ce645484` | `b518c825a2bebdbc65b5cc1add76d44a50e3416b074284808a4eb5bfd09869f3` | `7c5bfc06cc32fcd4b13d4f8a92293213c927825c174a63db60a03fd3c9d9149d` | `da9078d9a6b96501f3a610eccf9fdc90628449799cc81276940568d064457a8d` | 3841 |
| 1731 | 1000 | `4601e0c9846b01453da80543246617de7fda5691e6b1ce97cc33f5c9d99be680` | `b798b939ee11579018cc22efd91e3fd6bdecab10657fbe384661137b4830bf88` | `7c5bfc06cc32fcd4b13d4f8a92293213c927825c174a63db60a03fd3c9d9149d` | `da9078d9a6b96501f3a610eccf9fdc90628449799cc81276940568d064457a8d` | 3841 |

---

## 3. Technical result (`VERIFIED_BY_RUN`)

| Check | Result |
|---|---|
| Ticks executed | **156 / 156** (39 arm-seeds × 4 quarters), `status = COMPLETED` |
| `max_material_tolerance_ratio` | **0.03910827217608296** (gate ≤ 1) |
| `max_finance_tolerance_ratio` | **0.0004547473508864434** (gate ≤ 1) |
| Material clock | advanced by exactly **+1** per admitted quarter, after the gate: every arm-seed ran `tick = 0,1,2,3` against `1957Q1…Q4`, no duplicates, no skips |
| Unconstrained request recheck | max abs diff **0.0** on all 156 ticks — the reported request is the uncapped hunger formula, never the capped flow |
| Journal account legality | `journal_account_check.status = OK` on **156 / 156** ticks; **2 616 002** journal legs checked, **0** invalid, 0 illegal account ids; 433 774 account-touches |
| Placebo equivalence | `placebo_soft_low_base` vs `soft_low_base`: comparison, scientific, final-state and journal digests **equal on all 3 seeds** |
| `rescue_cut` vs `soft_high` | comparison digest **equal** in both regimes on all 3 seeds (the hardness-only coordinate is inert here) |
| Arm-order independence | 13-arm forward and reversed sub-runs produce equal digests per arm (permanent guard; §11) |

Artifacts (`study-final/`, SHA-bound in its `manifest.json`): `trace.jsonl`,
`journal.parquet`, `organization_investment_credit_wip.parquet`,
`demand_by_axis.parquet`, `gap_summary.json`, `input_identity.json`,
`account_directory.json`, `resources.json`, `results.json`, `spec.json`.

`stock_close` is exported per tick for all 9 real `(commodity, stage)` cells,
each with its `cells` count and `source` string, so no `commodity_circuit`
quantity is fabricated.

---

## 4. Per-arm window totals, every seed

Four-quarter window sums per arm. `reqU` = unconstrained investment request
(independently recomputed and equal to the engine's own field to 0.0);
`appr` = new approvals; `inst` = capacity installed. Money columns are currency
units, WIP/activity columns physical or value aggregates; they are never summed
across kinds. The last column is the H0B-mapped counter, exported **as a
diagnostic only** — no verdict in this report rests on it.

**Seed 1729**

| arm | reqU | appr | inst | credit drawn | bailout req | bailout granted | activity realized | bottleneck (diag.) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `soft_low_base` | 42533.3179 | 42460.1717 | 33266.2571 | 254423.5002 | 0.0000 | 0.0000 | 975927.7731 | 100 |
| `hard_low_base` | 42074.5944 | 24927.8007 | 19588.3451 | 0.0000 | 35717.0260 | 0.0000 | 759570.3693 | 250 |
| `soft_high_base` | 66437.8831 | 66437.8831 | 50590.1109 | 272142.6187 | 0.0000 | 0.0000 | 984598.4170 | 100 |
| `hard_high_base` | 65317.4248 | 35937.7346 | 26416.6190 | 0.0000 | 47659.8852 | 0.0000 | 691028.4440 | 360 |
| `soft_low_reduced` | 42533.3179 | 42455.7044 | 33265.6673 | 215052.8856 | 0.0000 | 0.0000 | 988566.1816 | 100 |
| `hard_low_reduced` | 42070.8869 | 23874.1973 | 17767.1987 | 0.0000 | 41857.5590 | 0.0000 | 707262.4496 | 337 |
| `soft_high_reduced` | 66437.8831 | 66437.8831 | 50590.1109 | 235622.7042 | 0.0000 | 0.0000 | 997657.5627 | 100 |
| `hard_high_reduced` | 65284.4735 | 32924.7318 | 24351.7653 | 0.0000 | 56696.1497 | 0.0000 | 657010.5467 | 425 |
| `credit_cut_high_base` | 67564.8868 | 35993.0910 | 27816.7166 | 0.0000 | 35898.0604 | 24261.1970 | 742611.2591 | 279 |
| `rescue_cut_high_base` | 66437.8831 | 66437.8831 | 50590.1109 | 272142.6187 | 0.0000 | 0.0000 | 984598.4170 | 100 |
| `credit_cut_high_reduced` | 67967.1930 | 33139.3924 | 24584.3858 | 0.0000 | 40944.9720 | 25866.6659 | 672542.6363 | 425 |
| `rescue_cut_high_reduced` | 66437.8831 | 66437.8831 | 50590.1109 | 235622.7042 | 0.0000 | 0.0000 | 997657.5627 | 100 |
| `placebo_soft_low_base` | 42533.3179 | 42460.1717 | 33266.2571 | 254423.5002 | 0.0000 | 0.0000 | 975927.7731 | 100 |

**Seed 1730**

| arm | reqU | appr | inst | credit drawn | bailout req | bailout granted | activity realized | bottleneck (diag.) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `soft_low_base` | 42533.3179 | 42460.1107 | 33266.2585 | 252870.8622 | 0.0000 | 0.0000 | 976243.9795 | 100 |
| `hard_low_base` | 42074.5859 | 24917.2050 | 19578.2148 | 0.0000 | 35774.9679 | 0.0000 | 759802.9049 | 258 |
| `soft_high_base` | 66437.8831 | 66437.8831 | 50590.1109 | 272084.8150 | 0.0000 | 0.0000 | 984884.8107 | 100 |
| `hard_high_base` | 65317.4126 | 35912.0263 | 26399.8777 | 0.0000 | 47717.1085 | 0.0000 | 691255.4048 | 367 |
| `soft_low_reduced` | 42533.3179 | 42455.7067 | 33265.6687 | 215684.5209 | 0.0000 | 0.0000 | 988746.5566 | 100 |
| `hard_low_reduced` | 42070.8783 | 23882.5272 | 17774.9770 | 0.0000 | 41896.5888 | 0.0000 | 707216.9436 | 344 |
| `soft_high_reduced` | 66437.8831 | 66437.8831 | 50590.1109 | 235823.1217 | 0.0000 | 0.0000 | 997837.9381 | 100 |
| `hard_high_reduced` | 65284.7332 | 32899.3750 | 24337.7081 | 0.0000 | 56745.7726 | 0.0000 | 656789.8972 | 435 |
| `credit_cut_high_base` | 67564.8716 | 35969.3093 | 27802.1670 | 0.0000 | 35959.0691 | 24321.6267 | 742904.4800 | 286 |
| `rescue_cut_high_base` | 66437.8831 | 66437.8831 | 50590.1109 | 272084.8150 | 0.0000 | 0.0000 | 984884.8107 | 100 |
| `credit_cut_high_reduced` | 67967.4525 | 33118.2322 | 24578.8610 | 0.0000 | 40996.5737 | 25916.7900 | 672575.4227 | 434 |
| `rescue_cut_high_reduced` | 66437.8831 | 66437.8831 | 50590.1109 | 235823.1217 | 0.0000 | 0.0000 | 997837.9381 | 100 |
| `placebo_soft_low_base` | 42533.3179 | 42460.1107 | 33266.2585 | 252870.8622 | 0.0000 | 0.0000 | 976243.9795 | 100 |

**Seed 1731**

| arm | reqU | appr | inst | credit drawn | bailout req | bailout granted | activity realized | bottleneck (diag.) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `soft_low_base` | 42533.3179 | 42460.1482 | 33266.2577 | 254245.9634 | 0.0000 | 0.0000 | 975994.8669 | 100 |
| `hard_low_base` | 42074.5848 | 24922.7618 | 19582.3878 | 0.0000 | 35721.5670 | 0.0000 | 759478.6649 | 236 |
| `soft_high_base` | 66437.8831 | 66437.8831 | 50590.1109 | 272852.8947 | 0.0000 | 0.0000 | 984648.9077 | 100 |
| `hard_high_base` | 65317.4090 | 35850.4753 | 26381.9125 | 0.0000 | 47662.1952 | 0.0000 | 690993.2215 | 367 |
| `soft_low_reduced` | 42533.3179 | 42455.7427 | 33265.6679 | 215963.2836 | 0.0000 | 0.0000 | 988652.6071 | 100 |
| `hard_low_reduced` | 42070.8753 | 23863.0563 | 17753.6056 | 0.0000 | 41879.1897 | 0.0000 | 706955.3360 | 344 |
| `soft_high_reduced` | 66437.8831 | 66437.8831 | 50590.1109 | 235643.4214 | 0.0000 | 0.0000 | 997743.9869 | 100 |
| `hard_high_reduced` | 65284.6029 | 32937.4210 | 24354.5842 | 0.0000 | 56709.6018 | 0.0000 | 657056.0111 | 435 |
| `credit_cut_high_base` | 67564.8671 | 35915.7318 | 27782.0358 | 0.0000 | 35901.5047 | 24265.1110 | 742538.4602 | 286 |
| `rescue_cut_high_base` | 66437.8831 | 66437.8831 | 50590.1109 | 272852.8947 | 0.0000 | 0.0000 | 984648.9077 | 100 |
| `credit_cut_high_reduced` | 67967.3223 | 33155.7018 | 24591.0629 | 0.0000 | 40959.5273 | 25879.3169 | 672305.7726 | 434 |
| `rescue_cut_high_reduced` | 66437.8831 | 66437.8831 | 50590.1109 | 235643.4214 | 0.0000 | 0.0000 | 997743.9869 | 100 |
| `placebo_soft_low_base` | 42533.3179 | 42460.1482 | 33266.2577 | 254245.9634 | 0.0000 | 0.0000 | 975994.8669 | 100 |

Reading notes:

- **Credit drawn is exactly 0 in all four `hard` arms and both `credit_cut`
  arms, on every seed.** `credit_approved` is 0 there too, so the credit leg is
  a clean zero, not a rounding artefact.
- **Bailout is granted only in the two `credit_cut` arms**, on every seed
  (base ≈ 24 261–24 265, reduced ≈ 25 867–25 879). Every other arm, including
  both `hard` arms and both `rescue_cut` arms, records
  `bailout_granted_total = 0` while still *requesting* 35 717–56 746.
- `placebo_soft_low_base` is identical to `soft_low_base` in every column, as it
  must be.
- Final-quarter `shortage_expectation_mean` is 0.0000 in all 39 arm-seeds.
  Final-quarter `bailout_expectation_mean` is 0.157412 in every arm except the
  two `credit_cut` arms (0.209652 base / 0.219272 reduced, per seed). The two
  are exported as separate sequences; no slash composite is computed and no
  meaning is guessed.

---

## 5. First stages, adjudicated separately

### 5.1 Budget first stage — three legs, three verdicts

`soft`/`hard` is a **joint** intervention on two policy coordinates. It is
adjudicated as three legs, and **no result in this report is attributed to
hardness alone**.

| leg | what it compares | verdict (all 3 seeds × 2 regimes × 2 levels = 12 records) |
|---|---|---|
| **credit leg** | `credit_drawn` under `soft` (credit 0.5) vs `hard` (credit 0.0) | **BINDING** in 12 / 12 records; e.g. base low 254 423.50 → 0, base high 272 142.62 → 0, reduced low 215 052.89 → 0, reduced high 235 622.70 → 0 (seed 1729) |
| **rescue leg** | `bailout_granted` under `soft` vs `hard`, decomposed by `rescue_cut` / `credit_cut` | **NONBINDING** in 12 / 12 records, `reason = ZERO_OUTPUT` |
| **joint leg** | the `soft` vs `hard` contrast as actually run | **BINDING** in 12 / 12 records |

Decomposition, stated precisely:

- At the **low** level the record's `rescue_cut_bailout_granted` and
  `credit_cut_bailout_granted` are **`None`**, because `credit_cut` /
  `rescue_cut` exist only at the high investment setting. No high-level arm is
  silently reused for a low-level decomposition.
- At the **high** level, `rescue_cut` (hardness 1.0 at credit 0.5) is
  digest-identical to `soft_high` in both regimes on all three seeds:
  `budget_hardness` alone changes nothing on this branch, because no bailout is
  requested while credit is available, so
  `bailout_envelope_fraction × (1 − hardness)` never binds. The hardness
  coordinate can only bind where a bailout is actually granted somewhere in the
  comparison.
- `credit_cut` (credit 0.0 at hardness 0.0) is what moves the rescue channel:
  `bailout_granted` rises from 0 to ≈ 24 261 (base) and ≈ 25 867 (reduced)
  while installed capacity falls from 50 590.11 to ≈ 27 817 / ≈ 24 584.

So the observed fall in delivery under `hard`/`credit_cut` is a **joint credit +
hardness** effect with the credit leg binding and the rescue leg recorded
`NONBINDING`. It is not a pure hardness effect, and the rescue-only null is
reported as `NONBINDING`, never as "soft budget constraints are absent".

### 5.2 Investment first stage — BINDING in every regime, budget and seed

Δ(soft − hard) over the four-quarter window; the unconstrained request is the
real hunger formula (recheck 0.0), approvals are never read as delivery, and
installed capacity is never read as ordered capacity.

| regime | budget | seed 1729 Δ reqU / Δ appr / Δ inst | seed 1730 | seed 1731 | status |
|---|---|---|---|---|---|
| base | soft | 23904.5652 / 23977.7114 / 17323.8538 | 23904.5652 / 23977.7724 / 17323.8525 | 23904.5652 / 23977.7349 / 17323.8533 | BINDING |
| base | hard | 23242.8304 / 11009.9339 / 6828.2739 | 23242.8267 / 10994.8213 / 6821.6629 | 23242.8242 / 10927.7134 / 6799.5248 | BINDING |
| reduced | soft | 23904.5652 / 23982.1787 / 17324.4437 | 23904.5652 / 23982.1764 / 17324.4423 | 23904.5652 / 23982.1404 / 17324.4431 | BINDING |
| reduced | hard | 23213.5866 / 9050.5346 / 6584.5667 | 23213.8549 / 9016.8478 / 6562.7311 | 23213.7276 / 9074.3647 / 6600.9785 | BINDING |

### 5.3 Demand-regime first stage — BINDING, 9 channels, 18 records

All 18 records (3 seeds × {soft low, soft high, hard low, hard high, credit_cut
high, rescue_cut high}) are `BINDING`, with the same **9** household-good
channels differing between regimes: `energy`, `higher_value_food`, `light_goods`,
`passenger_car`, `personal_services`, `refrigerator`, `repair_services`,
`television`, `washing_machine`.

| seed | window weighted desired, base | window weighted desired, reduced | window weighted realized, base | window weighted realized, reduced |
|---|---:|---:|---:|---:|
| 1729 | 215062.9156 | 155477.3999 | 129976.2199 | 113705.4366 |
| 1730 | 214976.3576 | 155390.3975 | 130286.6244 | 114049.5028 |
| 1731 | 215032.4034 | 155443.9180 | 130281.7744 | 113924.6242 |

Channels whose base already equals their minimum behave exactly as the
preregistered floor rule says. Household series stay per channel and per
commodity; no cross-commodity welfare total is computed, and the regime is a
preregistered design setting, never a historical estimate.

---

## 6. Axis-scoped budget contrast, both investment levels

Gaps are compared only on **commonly observed** `commodity + stage + purpose`
axes, each carrying an explicit gross and funded ratio with numerator,
denominator and unit. Heterogeneous physical units are never summed across
commodities. The full per-seed, per-level, per-axis vector is kept in
`results.json → contrasts.by_seed_and_regime[*].axis_scoped_budget_contrast`;
nothing was selected after the fact.

### 6.1 Readable and non-falling axis counts

Per seed and per regime, the low and high investment levels are adjudicated
separately. `readable` counts axis-scoped gap metrics (24 commodity+stage+purpose
axes × gross/funded) with `status = OK` in both compared arms; `non-falling`
counts those whose contrast `Y(soft) − Y(hard) ≤ 0`, i.e. the shortage did not
fall when hardness rose and credit was cut. The verdict reads the criterion as
*at least one* non-falling axis at either level.

| regime | level | readable (per seed) | non-falling (per seed) | axes that do fall |
|---|---|---:|---:|---|
| base | low | 48 | **45** | 3 — `energy\|standard\|private_plot` gross and funded (+0.016386 each), `food\|raw\|intermediate` funded (+0.038716) |
| base | high | 48 | **46** | 2 — `durable_goods\|standard\|housing` gross and funded (+0.048111 each) |
| reduced | low | 48 | **48** | none |
| reduced | high | 48 | **46** | 2 — `durable_goods\|standard\|housing` gross and funded (+0.048111 each) |

These counts are **identical on all three seeds**; the falling/zero axis sets
are seed-invariant. Four axes read exactly 0.0 contrast
(`durable_goods|standard|household` gross+funded, and
`durable_goods|standard|housing` gross+funded at the low level), and a zero
contrast is a gap that did not move — it is counted as non-falling, not dropped.

Because the criterion is met at **both** levels and in **both** regimes, the
structural verdict does not depend on which level is read.

### 6.2 Representative axes (seed 1729, gross and funded gap)

| axis | level | soft | hard | contrast |
|---|---|---:|---:|---:|
| `capital_goods\|standard\|investment` gross | high | 0.1597 | 0.5564 | −0.3968 |
| `capital_goods\|standard\|investment` funded | high | 0.1547 | 0.1877 | −0.0329 |
| `construction\|standard\|investment` gross | high | 0.0289 | 0.5859 | −0.5569 |
| `construction\|standard\|investment` funded | high | 0.0226 | 0.2472 | −0.2246 |
| `consumer_goods\|standard\|procurement` gross | high | 0.3696 | 0.6844 | −0.3148 |
| `consumer_goods\|standard\|procurement` funded | high | 0.2078 | 0.5704 | −0.3626 |
| `food\|ready\|retail` gross | high | 0.2544 | 0.5918 | −0.3374 |
| `food\|ready\|retail` funded | high | 0.2543 | 0.5864 | −0.3320 |
| `durable_goods\|standard\|housing` gross | high | 0.0481 | 0.0000 | +0.0481 |

### 6.3 Difference-in-differences (high − low), per seed and regime

| metric | regime | budget contrast low | budget contrast high | DiD |
|---|---|---:|---:|---:|
| `credit_drawn_total` | base | 254423.5002 | 272142.6187 | 17719.1184 |
| `investment_approved_total` | base | 17532.3710 | 30500.1485 | 12967.7775 |
| `investment_installed_capacity_total` | base | 13677.9120 | 24173.4920 | 10495.5799 |
| `investment_request_unconstrained_total` | base | 458.7235 | 1120.4583 | 661.7348 |
| `activity_realized_total` | base | 216357.4038 | 293569.9730 | 77212.5692 |
| `bailout_granted_total` | base | 0.0000 | 0.0000 | 0.0000 |
| `credit_drawn_total` | reduced | 215052.8856 | 235622.7042 | 20569.8186 |
| `investment_approved_total` | reduced | 18581.5071 | 33513.1513 | 14931.6441 |
| `investment_installed_capacity_total` | reduced | 15498.4686 | 26238.3456 | 10739.8770 |
| `investment_request_unconstrained_total` | reduced | 462.4310 | 1153.4096 | 690.9786 |
| `activity_realized_total` | reduced | 281303.7320 | 340647.0161 | 59343.2840 |
| `bailout_granted_total` | reduced | 0.0000 | 0.0000 | 0.0000 |
| `credit_drawn_total` | base | 252870.8622 | 272084.8150 | 19213.9528 |
| `investment_approved_total` | base | 17542.9057 | 30525.8568 | 12982.9511 |
| `investment_installed_capacity_total` | base | 13688.0437 | 24190.2333 | 10502.1896 |
| `investment_request_unconstrained_total` | base | 458.7320 | 1120.4705 | 661.7385 |
| `activity_realized_total` | base | 216441.0747 | 293629.4060 | 77188.3313 |
| `bailout_granted_total` | base | 0.0000 | 0.0000 | 0.0000 |
| `credit_drawn_total` | reduced | 215684.5209 | 235823.1217 | 20138.6008 |
| `investment_approved_total` | reduced | 18573.1795 | 33538.5081 | 14965.3286 |
| `investment_installed_capacity_total` | reduced | 15490.6917 | 26252.4028 | 10761.7111 |
| `investment_request_unconstrained_total` | reduced | 462.4396 | 1153.1500 | 690.7103 |
| `activity_realized_total` | reduced | 281529.6130 | 341048.0409 | 59518.4279 |
| `bailout_granted_total` | reduced | 0.0000 | 0.0000 | 0.0000 |
| `credit_drawn_total` | base | 254245.9634 | 272852.8947 | 18606.9313 |
| `investment_approved_total` | base | 17537.3863 | 30587.4078 | 13050.0215 |
| `investment_installed_capacity_total` | base | 13683.8699 | 24208.1984 | 10524.3285 |
| `investment_request_unconstrained_total` | base | 458.7331 | 1120.4741 | 661.7410 |
| `activity_realized_total` | base | 216516.2020 | 293655.6862 | 77139.4842 |
| `bailout_granted_total` | base | 0.0000 | 0.0000 | 0.0000 |
| `credit_drawn_total` | reduced | 215963.2836 | 235643.4214 | 19680.1378 |
| `investment_approved_total` | reduced | 18592.6864 | 33500.4621 | 14907.7757 |
| `investment_installed_capacity_total` | reduced | 15512.0623 | 26235.5268 | 10723.4645 |
| `investment_request_unconstrained_total` | reduced | 462.4426 | 1153.2802 | 690.8376 |
| `activity_realized_total` | reduced | 281697.2711 | 340687.9758 | 58990.7047 |
| `bailout_granted_total` | reduced | 0.0000 | 0.0000 | 0.0000 |

### 6.4 Regime interaction and triple difference, per seed

With `BC(regime, level)` the budget contrast `Y(soft) − Y(hard)`:

- **regime interaction** = `BC(base, high) − BC(reduced, high)` — how the
  high-level budget contrast differs between demand regimes;
- **triple difference** = DiD(base) − DiD(reduced) =
  `[BC(base, high) − BC(base, low)] − [BC(reduced, high) − BC(reduced, low)]`.

| metric | seed 1729 regime interaction / triple | seed 1730 | seed 1731 |
|---|---|---|---|
| `credit_drawn_total` | 36519.9145 / −2850.7002 | 36261.6933 / −924.6481 | 37209.4732 / −1073.2065 |
| `investment_approved_total` | −3013.0028 / −1963.8666 | −3012.6513 / −1982.3775 | −2913.0543 / −1857.7542 |
| `investment_installed_capacity_total` | −2064.8536 / −244.2971 | −2062.1696 / −259.5216 | −2027.3284 / −199.1360 |
| `investment_request_unconstrained_total` | −32.9513 / −29.2438 | −32.6794 / −28.9718 | −32.8062 / −29.0967 |
| `activity_realized_total` | −47077.0431 / 17869.2851 | −47418.6349 / 17669.9034 | −47032.2896 / 18148.7795 |
| `bailout_granted_total` | 0.0000 / 0.0000 | 0.0000 / 0.0000 | 0.0000 / 0.0000 |
| `bailout_requested_total` | 9036.2645 / 2895.7315 | 9028.6641 / 2907.0432 | 9047.4066 / 2889.7839 |

These are **point values**. A four-quarter window with three robustness seeds
supports no confidence interval, and the seed count is never used to manufacture
significance. Regimes are never pooled into one series.

### 6.5 Gap-row census

`gap_summary.json` carries 8 424 rows = 216 declared
commodity+stage+purpose axes × 39 arm-seeds. Of these, **936 rows are
`OBSERVED`** (each contributing an `OK` gross_gap and an `OK` funded_gap with
numerator, denominator and unit) and **7 488 rows are `BLOCKED_METRIC`** on both
metrics — 1 872 `OK` metric values and 14 976 `BLOCKED_METRIC` values in total.
No observed axis had a zero denominator on this branch, so
`ZERO_DENOMINATOR` does not occur here; that path is covered permanently by a
real tiny-engine test that produces both statuses from a real run. A blocked
metric is exported with `value = null` and is never zero-filled.

---

## 7. Verdicts (three independent axes)

### Technical — `PASS` (`VERIFIED_BY_RUN`)

156/156 ticks passed the engine's own material and finance tolerance gate
(≤ 1) and advanced the material clock by exactly one quarter after the gate.
Largest observed ratios: material **0.03910827217608296**, finance
**0.0004547473508864434**.

### Structural — `REJECTED` in **both** demand regimes and at **both** levels (`VERIFIED_BY_RUN`)

The card's own falsification criterion is *"with hardness raised and credit cut,
the shortage metrics do not fall"*. Here the criterion **is met**: on 45–48 of
48 readable axis-scoped gap metrics per seed and level, the gap does not fall —
it rises, sharply and monotonically on the investment and procurement axes
(e.g. `construction|standard|investment` gross 0.0289 → 0.5859 at the high
level). Both regimes are adjudicated and both are `REJECTED`, at low and high
investment intensity, with 6 readable contrast vectors per regime (3 seeds ×
2 levels).

Scope of this rejection, stated plainly:

- It is a rejection of **this model, in this window, on this branch** — a
  four-quarter synthetic Intermediate-8 run over three robustness seeds. It is
  **not** a claim about 1957 Hungary and carries no historical weight.
- It rests on 48 readable axis-scoped metrics per seed and level (24 axes ×
  gross/funded), of which 45 (base low), 46 (base high), 48 (reduced low) and
  46 (reduced high) do not fall. The full vector is kept in `results.json`; no
  favourable column was selected after the fact.
- **Competing mediator, named explicitly**: under `hard` and `credit_cut` the
  fall in approvals, installed capacity and realized activity reflects **lost
  funds** (credit drawn falls to exactly 0), not greater resource efficiency.
  It must not be read as evidence that M2 holds historically.
- `SUPPORTED` is unreachable from this design and is reported as **false**:
  the card's sufficiency claim is about *sustained, demand-regime-independent*
  shortage, and a 4Q window on one synthetic branch cannot establish it. The
  verdict code therefore never returns `SUPPORTED`.

### Historical — `UNIDENTIFIED` / `NOT_ESTABLISHED` (`NOT_RUN`)

No admitted enterprise archive and no independent shortage observation was used.
The H0B registration for M2 is unchanged. A synthetic structural result cannot
fill that identification gap.

### F2 generalisation — `NOT_RUN`

Deliberately untouched: this study does not modify the F2 investment price axis.

---

## 8. Metric treatment (H0B blocked metrics, superseded explicitly)

| H0B blocked metric | treatment here |
|---|---|
| `aggregates.undelivered share` (no declared denominator) | Replaced by axis-scoped gross and funded gap ratios that export numerator, denominator and unit. Zero denominator ⇒ `value=null, status="ZERO_DENOMINATOR"`. Unrouted declared axis ⇒ `BLOCKED_METRIC`. Neither is zero-filled; neither is silently dropped. |
| `organization_diagnostics.credit_drawn/shortage_expectation_mean` (undeclared separator) | Split into two independent sequences. No slash composite is computed and no meaning is guessed. `shortage_expectation_mean` closes at 0.0000 in all 39 arm-seeds; `bailout_expectation_mean` closes at 0.157412 except in the two `credit_cut` arms. |
| `commodity_circuit.stock_close` (no producer) | Replaced by closing stock summed over the real `(commodity, stage)` state cells, exported per tick with its `cells` count and `source` string. No `commodity_circuit` quantity is fabricated. |

All new indicators are marked `study_level` in the spec.

---

## 9. Explicit `NOT_RUN`: finance cash / procurement intermediates

`trace.jsonl → finance_trace.status = NOT_RUN` on **156 / 156** ticks, and the
six corresponding columns in `organization_investment_credit_wip.parquet`
(`cash_available_for_goods`, `credit_approval_caps`, `input_order_cost`,
`old_project_cost`, `new_investment_request_cost`, `input_credit_earmarked`)
are **null in all 31 200 rows** — explicitly `null`, not `0`.

Reason, as recorded in the trace itself: the engine fills `procurement_trace`
only on its **H3B bank-lender path**. Passing credit caps here would switch the
journal account path away from the legacy Treasury-credit journal this
preregistered comparison is built on, and would break the comparison, final-state
and journal digests that make the placebo and reproduction checks meaningful.
The main study therefore keeps the legacy Treasury-credit journal and does not
claim to have measured cash availability, credit caps or order costs. No such
quantity is reported, estimated or imputed anywhere in this report.

---

## 10. Reproduction and regression

| Check | Command / basis | Result |
|---|---|---|
| Post-fix full run vs final full run | `study-fix` vs `study-final`, per-arm digests | **39 / 39** arms equal on all four digest classes: comparison, scientific, final-state, journal |
| Pre-fix vs post-fix full run | `study` vs `study-final` | **39 / 39** arms equal on comparison, final-state and journal digests. The **scientific** digest differs on all 39 arms *by design*: the fix round added new trace fields (`stock_close`, `finance_trace`, `journal_account_check`, `controls_binding`), which are inside the scientific digest but outside the comparison, final-state and journal digests. Comparison/final/journal invariance is the claim that matters and it holds exactly. |
| Directed pytest | `pytest tests/test_hist_enterprise_mechanisms.py tests/test_material.py tests/test_hist_procurement_credit.py tests/test_hist_price_investment_execution.py tests/test_hist_semantic_registry.py` | **168 passed** in 10.33 s |
| Full pytest | `pytest -q -p no:cacheprovider` | **1759 passed**, 180 warnings, in 194.98 s |
| Lint | `ruff check --no-cache src tests experiments` | **All checks passed** (exit 0). One real `F821` was found and fixed in the docs round: `tests/test_hist_enterprise_mechanisms.py:384` used `typing.Any` in an annotation without importing it. |
| Baseline contract | `hsm baseline verify --json` | `status: ok`, SHA matches expected `1f5b233f…1b6f` |
| Lock file | `uv lock --check --offline` | exit 0 |
| Legacy scenarios | `hsm run --scenario historical_f2_replay / historical_f2_trade_scenario`, seed 1729, six fresh directories C0, C1, C0a, C0b, C1a, C1b | 116 `completed_ticks` each, `status: completed`; `parameter_hash` and `deterministic_replay_digest` match the frozen 01 values **exactly**: C0/C0a/C0b `parameter_hash e27ade6a…0445`, digest `92f9ea0a…8a42d`; C1/C1a/C1b `parameter_hash 632ee6a6…c3b90`, digest `c4810481…e5d5` |
| Byte-level determinism | `diff -rq C0a C0b`, `diff -rq C1a C1b` | both **empty**, exit 0 |
| Run identity | `verify_run_identity` on all six directories | **6 / 6** pass against the expected digests |
| Protection hashes | BASELINE.md, `config/research_contract.json`, `uv.lock`, M2 card, `intermediate8`, `studies/M02/study_decl.json`, research overlay, and the two user-dirty docs | `diff` against the pre-run snapshot is **empty**; no protected file changed |

Regression logs, stdout/stderr/exit codes and their SHA-256s are recorded in
`impl/regression-summary.json` and under `outputs/…/impl/final/`. The docs-round
lint and directed-pytest logs are under `outputs/…/impl/final-docs/`.

---

## 11. What was not run

- **Checkpoint-resume replay: `NOT_RUN`.** No interrupted-and-resumed study was
  executed.
- **Hidden / sealed target data: not accessed.** `data/raw`, `data/observed`,
  `data/reconstructed`, `data/assumptions`, `data/private` and any target or
  sealed window were never read.
- **A2 / A3 (and M5 / M11): not started.** No directory, spec or run was created.
- **git push: not performed.** The scheduler makes one local commit of the
  whitelisted files after this review; nothing is pushed. No `reset`, `checkout`,
  `stash` or `clean` was run, and run outputs under `outputs/` are not committed.
- **Independent phase review: `PASS`.** The repository `phase-reviewer` (task
  `PrivateWildfowl`, `minimax-code-cn/MiniMax-M3:high`) returned PASS after
  recomputing hashes, inspecting the real study artifacts and independently
  re-running a 1-seed positive example and a rescue-only/zero-denominator
  negative example in `outputs/h5a-a1-review-20261021T200000Z/`. The full
  returned text is `studies/HIST_VNEXT/M02/REVIEW.md`. No PATCH or REDESIGN
  items were raised; the review does not promote the historical or sufficiency
  verdicts.
- **F2 investment price axis, H3G household channel, any `engine/`, `state/`,
  `storage/`, `config/` or `scenarios/` change**: none attempted.
- **Finance cash / procurement intermediates: `NOT_RUN`** (§9).

---

## 12. Failures found and fixed during implementation

Found and fixed in the implementation round:

1. `state.completed_ticks` was expected to advance inside `tick_material`. It
   does not — the engine contract advances the clock only *after*
   `check_material_invariants` passes. The runner now asserts the kernel left the
   clock untouched and increments it post-gate. Without this the engine re-read
   `forcing.quarters[0]` for all four quarters.
2. Investment-purpose procurement was aggregated with a per-demand-row mask over
   an already axis-grouped array, raising `IndexError`. Aggregation now reads
   the per-row flows directly.
3. The falsification test's sign was inverted: a positive soft-minus-hard gap
   contrast is a *fall* of shortage, so `contrast > 0` was wrongly read as
   "does not fall". Corrected; the structural verdict moved from a spurious
   `CONDITIONAL` to `REJECTED` on the same numbers.
4. The digest helper rejected the `MaterialNetwork` / `MaterialForcing`
   dataclasses. Dataclass fields are now digested structurally — a silent
   `repr` fallback would have embedded memory addresses.

Found and fixed in the fix round (each covered by a permanent test, with
fail-before logs in `impl/red-before-fix/`):

5. **Arm order was ignored.** `run_m02_study` executed in `spec.arms` order, so
   `--arms` only filtered the summary. It now executes strictly in the requested
   order; the guard reads the first tick's arm sequence out of the real
   `trace.jsonl` of both a forward and a reversed run and asserts the four
   digests match.
6. **Failure boundary was not restored.** `_halt` recorded the boundary hash but
   left the mutated state in place. It now records the failing-state hash,
   restores every field by `deepcopy` from the boundary, asserts the restored
   digest equals the boundary digest, and writes the effective material
   parameters, forcing quarters, `completed_ticks` and exception type into
   `failure.json`.
7. **The low level reused the high level's decomposition.** The rescue/credit
   decomposition now runs only at the high investment setting; at the low level
   `rescue_cut_bailout_granted` and `credit_cut_bailout_granted` are `None`
   rather than a borrowed high-level number.
8. **The baseline-collapse criterion was too weak.** It now also fires when
   `capital_goods` / `construction` / `consumer_goods` window `delivered` sums
   are all zero, and when household `consumer_goods` desired is positive while
   realized is all zero. A healthy tiny baseline must not trigger it.
9. **The structural verdict read only the high level.** Both preregistered
   levels are now adjudicated per regime, with the per-seed, per-level non-falling
   vector retained and `readable_contrasts` recorded by level.
10. **`stock_close` only entered the digest.** It is now exported per tick into
    `trace.jsonl` and the scientific quarter records, with `cells` and `source`.
11. **Cash / procurement intermediates were silently absent.** They were added,
    and the investigation showed the engine returns `status = NOT_RUN` with all
    totals `None` on the legacy Treasury-credit path. That is now an explicit,
    disclosed `NOT_RUN` with `null` (not `0`) parquet columns (§9) rather than an
    implicit gap.
12. **Account legality was unchecked.** An account directory is now built from
    the opening state, hashed into `input_identity.json`, written to
    `account_directory.json`, and every journal debit/credit id is validated
    against it each tick; an illegal id halts the run. 2 616 002 legs checked,
    0 invalid.
13. **`arms_with_zero_bailout_grant` repeated the same arm three times** across
    seeds; it is now a sorted set of 11 distinct arms.

Found and fixed in this docs round:

14. `ruff` reported `F821 Undefined name 'Any'` at
    `tests/test_hist_enterprise_mechanisms.py:384`. The missing
    `from typing import Any` import was added. `ruff check --no-cache src tests
    experiments` now passes with exit 0, and the directed pytest run is green
    (31 tests in that file).

---

## 13. Resources and model usage

Run resources, measured by the runner itself (`resources.json`):

| Run | wall (s) | peak RSS (bytes) | trace rows | journal rows | organization rows | demand rows |
|---|---:|---:|---:|---:|---:|---:|
| `study-final` (3 seeds × 13 arms × 4Q, COMPLETED) | 10.581 | 308 658 176 | 156 | 2 616 002 | 31 200 | 33 696 |
| `profile-fix` (1 seed × 13 arms × 4Q, PARTIAL) | 3.609 | 270 876 672 | 52 | 872 307 | 10 400 | 11 232 |

Python `3.12.14`, macOS `26.5-arm64`. The runner's own `model_usage` field is
`NOT_MEASURED` and correctly so: the simulation makes no model calls. Token and
cost accounting belongs to the calling orchestration session.

Actual MiniMax-M3 usage of the three orchestration sessions, from
`impl/model-usage.json`:

| session | assistant messages | input | output | cache read | total tokens | cost |
|---|---:|---:|---:|---:|---:|---:|
| probe (planning probes) | 1 | 1 877 | 15 | 128 | 2 020 | $0.000589 |
| impl (runner + tests + first docs) | 127 | 229 308 | 132 175 | 16 544 739 | 16 906 222 | $1.220087 |
| fix (defect round) | 141 | 219 298 | 115 332 | 21 095 970 | 21 430 600 | $1.469946 |
| docs (this session, partial: measured from the live session log while still running) | 50 | 148 873 | 29 187 | 4 212 290 | 4 390 350 | $0.332424 |

The docs row is a partial reading taken while the session was still executing;
it is a lower bound, not a final total. No figure was invented to fill any
unreadable field.

---

## 14. Rollback

The legacy entry points are untouched: `hsm baseline verify`, `hsm run
--scenario historical_f2_replay`, `hsm run --scenario
historical_f2_trade_scenario`, and `tests/test_material.py` all behave exactly as
before, with byte-identical deterministic outputs. This step added no engine,
state, storage, config or scenario change.

To disable this study, remove `experiments/hist_enterprise.py`,
`tests/test_hist_enterprise_mechanisms.py` and the four `studies/HIST_VNEXT/M02/`
documents from the tree, or simply stop invoking
`experiments.hist_enterprise::run_m02_study`. Nothing else depends on it.

To re-run the full design:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m experiments.hist_enterprise \
  --root . --spec studies/HIST_VNEXT/M02/spec.json \
  --output-dir outputs/<fresh-path>
```

A single-seed or single-arm subset is accepted through `--seeds` / `--arms` for
reproduction and is always reported `PARTIAL`; only the full 3 seeds × 13 arms
design is reported `COMPLETED`.