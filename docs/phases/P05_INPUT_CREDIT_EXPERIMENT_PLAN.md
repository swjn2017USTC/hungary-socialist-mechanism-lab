# P05 — Structural experiment plan: earmarked working-capital credit for input orders

**This file specifies execution; it does not implement it.** No engine default, scenario
value or published artifact changes until Phase 1 is separately approved and Phase 0
has proved legacy reproduction.

- Base commit: `eca6286` (`fix(p05): publish the exact per-commodity expiry sink`).
- Suite baseline: **349 passed**, `ruff` clean, `.venv` python 3.12, Mac only.
- Replay baseline digest (5 000 households / 400 organizations / seed 1729, 116 ticks):
  `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`.

---

## 1. Why this experiment

The leak audit (`docs/phases/P05_LEAK_AUDIT.md`) closed every money and commodity
identity (max residual 2.2e-09 / 4.7e-10) and located three modelled withdrawals: paid
bank interest destroys deposits with no bank-spending path, household savings are parked
and never re-enter the consumption budget, and the treasury is a finite rescue fund with
no replenishment. None of those is an accounting error, so the question became: **which
structural rule, if changed, lets the physical circuit close again?**

The answer is measured, and it is the transport sector's financing order:

| tick | transport `realized` | `cash_open` | `credit_drawn` | `wage_paid` | `purchases` |
|---|---:|---:|---:|---:|---:|
| 0 | 54 000.0 | 28 246.2 | 0.0 | 14 123.1 | 6 957.5 |
| 2 | 52 118.2 | 7 747.5 | 7 458.0 | 14 123.1 | 1 533.0 |
| 5 | 11 096.7 | 3 359.8 | 7 000.9 | 14 123.1 | 702.2 |
| 115 | **0.0** | 0.0 | 5 668.5 | 5 668.5 | **0.0** |

(source: `outputs/p05-leak-audit/sector_circuit.parquet`, `organization_type="transport"`)

Transport realizes its full target at tick 0, decays, and is exactly **zero from tick 13
through tick 115** (100 of 116 ticks). Its cash is zero, every drawn rouble is spent on
wages, and **input purchases are zero** — so the carriers cannot buy the inputs that
produce freight. The chain is self-locking: no freight → no deliveries → no sales
receipts → no cash → no input purchases → no freight.

The ordering that produces it is declared in `engine/finance.py::run_domestic_finance_step`
("credit approval → wage payment → input payments") and in `engine/material.py` where the
goods budget is the **remainder** after wages:

```python
cash_for_goods = np.asarray(state.organization_cash, dtype=np.float64).copy()
funded_inputs = np.minimum(input_cost_by_org, cash_for_goods)
scale_inputs = _group_factor(input_cost_by_org, cash_for_goods)   # L1103
```

Instrumenting `_group_factor` by call site gives that site a mean factor of **0.606**
over 20.8 M units of need, with 14 851 need-groups funded at zero — the largest measured
contraction in the model. The transport sector is its sharpest case.

**Hypothesis under test:** the physical circuit closes if bank working-capital credit can
be **earmarked for input orders** (material-technical supply), instead of every rouble of
credit competing with the wage bill inside one envelope and wages taking first call on
the cash remainder.

## 2. Falsifiable hypotheses

| id | hypothesis | falsification criterion |
|---|---|---|
| **H1** | with earmarked input credit, transport `realized` never returns to zero | transport `realized` hits 0 for any tick after tick 20 in the best arm |
| **H2** | freight capacity stops binding: the logistics pool ÷ freight need rises above the baseline 0.54 and `physical_delivery_blocked` share falls | pool/need does not exceed the baseline by > 10% relative, or the physical share does not fall |
| **H3** | liveness responds monotonically to the earmark fraction | liveness is flat or non-monotone across the arm ladder |
| **H4** | earmarking is *sufficient*: liveness ≥ 0.8 and every frozen gate passes | any frozen gate still fails ⇒ the hypothesis is **partial**, and the report must say so |

Pre-registered kill condition: if H1 and H2 are both falsified, earmarking is not the
binding rule, the parameter is reported as such, and the next candidate (the interest
sink / treasury refill block) becomes the subject of a separate plan. **A partial result
must never be written up as a validated model.**

## 3. Minimal implementation design

### 3.1 Declaration (no hidden scalar)

- New field on `MaterialParameters` (`contract/material.py`, next to
  `credit_envelope_fraction` at line 1319):
  `input_credit_earmark_fraction: FiniteFraction = 0.0` using the existing
  `FiniteFraction` annotated type (`>= 0.0`, `<= 1.0`).
- It **must** be added explicitly to `MaterialParameters.flatten()` (line 1416 — an
  explicit dict, so a forgotten field would silently escape the parameter hash; note
  `credit_envelope_fraction` is listed there), so it enters the RunManifest parameter hash.
- Registry entry in `config/calibration/p05_parameters.yml` following the existing shape
  (`artifact_id`, `variable_id`, `literature_refs`, `present`). Justification text must
  state it is a **structural design parameter** (the Soviet material-technical supply
  credit institution), not a fitted coefficient.
- Classification: it is structurally determined by the declared rule, so it belongs to
  `fixed` **or** `weakly identified` — never `calibrated`. `calibrated` stays 0 unless a
  historical target linkage is separately declared, which is out of scope here.

### 3.2 Mechanism (finance step)

Inside `run_domestic_finance_step`, after the legacy `approve` is computed:

```
input_line   = min(input_order_cost, earmark_fraction * input_order_cost)          # purpose-tied
general_line = legacy approve computed on the request net of input_line
draw         = input_line + general_line
```

Payment order is unchanged: wages keep first call on **cash** (household income is not
sacrificed by this experiment), and the goods budget becomes

```
cash_for_goods = cash_after_wages + unspent(input_line)
```

so an earmarked line can only ever pay for inputs, and **at `earmark_fraction = 0.0` the
code path is identical to today's** (input_line = 0), which Phase 0 must prove by digest.

Both new legs go through the existing journal so the money identities hold unchanged:
`M_close = M_open + credit_drawn − principal_repaid − interest_paid`, and non-negative
cash/reserves as today.

### 3.3 Invariants that must not move

- `check_material_invariants` gates (all of them) stay enforced and passing.
- `pay_goods`/`pay_fee` still equal delivered quantities (no unfunded delivery).
- The published expiry sink (`national_accounts.expiry` == `tick_diagnostics.expired_services`)
  stays exact.
- No new flows field may be added that enters `canonical_material_bytes` without
  justification: adding a derived field changes the *behaviour* digest even when behaviour
  is unchanged (measured: it did, once, during the expiry fix).

## 4. Arms and controls

Swept with the existing tool (`hsm calibration axis-sweep`, extended with this axis so the
numbers stay reproducible):

| arm | `input_credit_earmark_fraction` | purpose |
|---|---|---|
| A0 | 0.0 | control; **must** reproduce digest `92f9ea0a…` and the baseline gate table |
| A1 | 0.25 | partial earmark |
| A2 | 0.50 | equal to the current `credit_envelope_fraction` |
| A3 | 1.00 | input orders fully credit-financed |
| A4 | 1.00 with `credit_envelope_fraction = 0.5` unchanged | isolate earmarking from envelope size |
| N1 | 0.0 with `credit_envelope_fraction = 1.0` | negative control: the already-measured envelope-only arm (liveness 0.0396) must stay unchanged |

`A4` and `N1` exist so the report can separate "earmarking works" from "more credit
works". A claim of earmarking-specific effect requires A3 > A4 in the frozen gates.

## 5. Metrics and acceptance

Per arm, from compact outputs only:

1. **Frozen gates (unchanged thresholds):** liveness ≥ 0.8; household delivered/funded ≥ 0.9
   for g03/g15/g16; treasury self-financing; per-commodity expiry ≤ 0.20 of available
   services; accounting invariants pass.
2. **Mechanism metrics:** transport `realized` trajectory and first-zero tick; carrier
   `cash_open`, `purchases`; logistics pool ÷ freight need; `physical_delivery_blocked`
   share; input-funding factor at `material.py:1103`.
3. **Guardrail metrics (anti-optimisation):** wage arrears must not grow *faster* than the
   baseline (relative test, since no absolute bound is established); household cash,
   spending and `household_availability_unmet` reported per arm. An arm that buys liveness
   by starving households or by unbounded arrears is **rejected**, not adopted.
4. **Conservation:** money-flow and commodity residuals within the existing tolerances for
   every arm (arms are rejected on any new residual).

## 6. Execution order (each phase is a gate)

- **Phase 0 — legacy reproduction.** Add the parameter with default 0.0, the flatten entry
  and the registry entry, and *no mechanism* yet. Run the replay baseline and assert digest
  `92f9ea0a…`, the gate table and the byte-identical original Parquet files. If anything
  moves, stop.
- **Phase 1 — mechanism.** Implement the earmark split behind the parameter (default 0.0),
  with tests: (i) legacy digest unchanged; (ii) at `f = 1.0` the carrier's goods budget
  increases by exactly the earmarked line; (iii) money identities and gates still pass;
  (iv) non-negative cash/reserves.
- **Phase 2 — arms.** Extend `axis_sweep` with the new axis; run A0–A4 and N1 (116 ticks
  each, compact outputs) and record the §5 metric table.
- **Phase 3 — mechanism trace.** For the best arm, verify H1/H2 directly against
  `sector_circuit`/`tick_diagnostics` and quantify the channel (carrier purchases →
  realized → freight pool → deliveries). Confirm or falsify H3 with the arm ladder.
- **Phase 4 — report and decision.** Write `docs/phases/P05_INPUT_CREDIT_EXPERIMENT.md`
  with the tables, the falsification outcomes, and the §7 decision rule outcome. State
  explicitly whether H4 held; if not, state the residual blocked gates.

Stop conditions: any Phase-0 digest change; any new accounting residual; any arm whose
guardrail metrics (arrears growth, household availability) are worse than the baseline
without a compensating gate gain.

## 7. Decision rules

| outcome | action |
|---|---|
| H1–H3 confirmed, H4 holds (all frozen gates pass) | propose adopting the earmark value as the F2 default with a registry entry and a manifest version bump; the classification records it as `fixed`/`weakly identified`, `calibrated` unchanged |
| H1–H3 confirmed, H4 partial (liveness improves, some gates still fail) | adopt nothing; the report names the remaining blocking gate and the next structural candidate (interest sink, treasury refill, savings draw) |
| H1/H2 falsified | abandon the earmarking direction; record it as measured-and-rejected with the arm table as evidence |
| mechanism works but the guardrails fail | reject the arm; the tension (physical circuit vs household income) is the finding, and the report states it as such |

## 8. Deliverables, budget, non-goals

- Code: the declared parameter + mechanism + tests (Phase 1).
- Data: per-arm compact outputs under git-ignored `outputs/`, plus the recorded arm table.
- Documents: `docs/phases/P05_INPUT_CREDIT_EXPERIMENT.md`; a short §E7 in
  `P05_REPORT.md` linking to it and updating the gate disposition.
- Commits: `feat(p05): declare the input-credit earmark parameter` (Phase 0),
  `feat(p05): earmark working-capital credit for input orders` (Phase 1),
  `docs(p05): record the input-credit experiment` (Phase 4). Nothing pushed.
- Budget: one 116-tick run ≈ 8 s; six arms ≈ 1 min; a full-suite run ≈ 50 s. Everything on
  Mac, no Windows, no ABC/pyABC, no hold-out targets.
- **Non-goals:** no change to wage seniority; no savings-draw mechanism; no bank-profit
  spending loop; no treasury revenue rule; no change to `credit_envelope_fraction` as a
  default; no calibration claim; no reopening of 1986Q1–1988Q4; no tuning outside the one
  declared axis.

---

## 9. Execution prompt (paste into a local Codex)

```text
Execute Phase 0..4 of docs/phases/P05_INPUT_CREDIT_EXPERIMENT_PLAN.md in this repository
(commit eca6286 or later, main). Read the plan, docs/phases/P05_LEAK_AUDIT.md §3-§4 and
the measured tables in docs/phases/P05_REPORT.md §E5-E6 before writing code.

Hard constraints:
- Phase 0 must prove the legacy path is untouched: same deterministic_replay_digest
  (92f9ea0a…), same gate table, byte-identical original Parquet files. Stop if not.
- Default value 0.0 keeps today's behaviour exactly; never change a default to make a gate pass.
- Declare the parameter in MaterialParameters AND in flatten(); add the registry entry.
- Do not add any derived ndarray to MaterialTickFlows (it changes the behaviour digest).
- Keep every existing accounting gate passing; reject any arm with a new residual.
- No ABC/pyABC, no hold-out targets, never simulate past 1985Q4, Mac only.
- Report partial results as partial: falsified hypotheses stay falsified, no "validated" claim.

For each phase: run the specific check that proves it, then commit with the message listed
in the plan. In your final reply give the arm table (frozen gates + mechanism metrics +
guardrails), the H1-H4 verdicts, the residual blocked gates, the commit hashes, and the
pytest result.
```
