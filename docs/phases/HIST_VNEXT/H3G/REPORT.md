# HIST_VNEXT H3G: counterfactual procurement report

## Status: PASS — commit authorized

Independent review returned **PASS** after the metric, settlement, evidence and
documentation repairs.  The reviewed scope is the structural-null procurement
diagnostic; no historical verdict is upgraded.

## What changed

| File | Change |
|---|---|
| `src/hsm_lab/planning/counterfactual_profile.py` | New baseline-embedded controlled procurement profile: real residual demand, baseline edge settlement into inventory, A/B-only edge axis, no recipe variables |
| `src/hsm_lab/planning/proposals.py` | `edge_baseline` per-quarter lower bound, validated and hashed |
| `src/hsm_lab/planning/rolling.py` | Edge lower bounds use the baseline; non-controlled edges are fixed, controlled edges may add |
| `tests/test_hist_counterfactual_profile.py` | Real baseline, residual demand, no-recipe, A/B-scope and plan tests |
| `tests/test_hist_bounded_planning.py` | Edge-baseline incremental-request regression; bounded cash and shared-financing regressions |
| `docs/phases/HIST_VNEXT/H3G/{PLAN,REPORT}.md` | This phase |

H3E's engine, execution adapter, storage, targets and historical verdicts are
untouched.  The H3F full-network projection remains withdrawn.

## Evidence

Run: `outputs/hist-vnext-h3g-20261019-060258/results.json`
(arms hash `b3268ac9…675632`; 32.3 s wall; 616 MB peak RSS).  Jobs are
`witnesses/<arm>_tickN_journal.json.gz`; certificate witnesses are `.npz`.

| Arm | Ticks | Household realized | Household unmet | Plan − baseline realized | Submitted channel requested | Submitted channel delivered | Max material ratio | Max finance ratio | Max payment residual |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| historical rule | 4 | 75,219.8213 | 36,796.1003 | 0.0 | 1.0 | 529.2955 | 0.000957 | 5.684e-05 | 1.82e-11 |
| bounded planning | 4 | 75,219.8213 | 36,796.1003 | 1.98e-08 | 4.0 | 1,332.3652 | 0.000965 | 1.137e-04 | 1.82e-11 |
| full information | 4 | 75,219.8213 | 36,796.1003 | 1.98e-08 | 4.0 | 1,332.3652 | 0.000965 | 1.137e-04 | 1.82e-11 |

All certificates are `FEASIBLE`; all stock/bank residuals are ≤ 4.6e-10.
Execution is `EXECUTED`/`NO_REQUESTS`, with no rejected tick.

### Result — structural null

The controlled action space is live but **does not transmit to the household
channel within one tick**.  A forced-order sweep of 1,000,000 units on each
admissible commodity moves edge deliveries by up to −13,776 units, while
household realized and unmet change by exactly 0.0 in every probe.  The normal
arms submit 1–4 units and show the same like-for-like null (bounded delta
1.98e-08).  The household metric is therefore **not responsive to this action
space**; no planning benefit or crowd-out is claimed.  This is a bounded
negative mechanism result, not a household-mechanism finding.

## Acceptance checks

- `tests/test_hist_counterfactual_profile.py`: 2 passed.
- `tests/test_hist_bounded_planning.py`: 69 passed.
- Full repository suite: 1,326 passed.
- `ruff format` / `ruff check`: pass on changed source and tests.
- Evidence verifier: `H3G evidence verified: household action channel is
  structurally null`.
- Review verdict: **PASS** (independent reviewer; forced-invariance sweep and
  certificate recompute verified).

## Limits

1. **Procurement sub-model**: production is exogenous baseline; no recipe,
   investment or capacity decision is optimized.  "Submitted channel delivered"
   is total kernel throughput on the submitted (organization, commodity) demand
   masks; it is not the incremental request quantity.
2. **Residual demand**: demand is `max(0, ordered − delivered)` from the
   baseline tick; it is a real quantity, not a share.
3. **Baseline settlement**: baseline edge flows are moved into opening
   inventory before planning; the LP does not re-fund them.
4. **Additive action**: the kernel cannot cancel endogenous orders; the plan
   can only add procurement.  Within one tick the controlled hub-procurement
   channel is disconnected from household realized/unmet consumption, so a
   null household result is expected and a non-null would indicate a
   transmission change worth investigating.
5. **Bounded/full equality**: both arms receive the same opening reports.  This
   phase measures action-space effects, not private information.
6. **Decision organizations** are the first two sorted procurement hubs
   (346/347), not a size-ranked pair; this is a deterministic profile choice.
7. **No historical verdict** is upgraded; this is synthetic technical evidence.
