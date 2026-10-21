## Independent H5A-A1 / M02 phase review

### Verdict

PASS

### Evidence

#### 1. Scope and whitelist
- `git status --porcelain` shows only additions under `experiments/`, `tests/test_hist_enterprise_mechanisms.py`, `studies/HIST_VNEXT/M02/`. The 22-line porcelain shows the three pre-existing user-dirty items (`M .omp/config.yml`, `M docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md`, `M docs/upgrade_review/HIST_VNEXT/06_OMP_MINIMAX_HANDOFF.md`) plus pre-existing untracked PLAN files; everything else is whitelisted M02 work.
- Engine/state/storage/config/scenario clean: `git status engine/ src/hsm_lab/engine/ src/hsm_lab/state/ src/hsm_lab/storage/ config/ scenarios/` ⇒ "nothing to commit, working tree clean".
- `git diff --check` exits silent (no whitespace conflicts).
- `git log` last commit `e761950 feat(hist-vnext): execute H4C Pilot B conditional transmission`, pre-existing; no commits were made during this delivery.

#### 2. Preregistration hashes (recomputed)
| File | Declared | Recomputed | Match |
|---|---|---|---|
| `studies/HIST_VNEXT/M02/PLAN.md` | 1ae544a6...0768d | 1ae544a6...0768d | ✓ |
| `studies/HIST_VNEXT/M02/spec.json` | 35b5b7ff...9bd78b | 35b5b7ff...9bd78b | ✓ |
| `studies/HIST_VNEXT/M02/REPORT.md` | afce89cf...a2778 | afce89cf...a2778 | ✓ |
| `config/p06/cards/M2.json` | 0da621e5...0589 | 0da621e5...0589 | ✓ |
| `config/scenarios/intermediate8.json` | 07b0a1fa...f94b | 07b0a1fa...f94b | ✓ |
| `BASELINE.md` | 1f5b233f...1b6f | 1f5b233f...1b6f | ✓ |
| `config/research_contract.json` | 6f54522a...2c82 | 6f54522a...2c82 | ✓ |
| `uv.lock` | 9fd79b62...82b9 | 9fd79b62...82b9 | ✓ |
| user-dirty `05/06` | bc45bc84... / 5fcb75b4... | bc45bc84... / 5fcb75b4... | ✓ |

`spec.json` (`spec.json:13-310`) declares `schema_version="hist_vnext_h5a_a1_m02_v1"`, `phase_id="H5A-A1"`, `mechanism_id="M2"`, `study_id="M02"`, 13 arms in the exact preregistered order, households=1000, ticks=4, window 1957Q1-Q4, seeds [1729,1730,1731], no warmup, no auto-extension, intensity block `{low:1.0, high:2.0}`, fixed `central_target:null`, fixed `investment_approvals:null`. The runner (`experiments/hist_enterprise.py:455-465,1212-1214,1576-1581`) enforces every one of these before model initialisation and refuses `intensity=2.5` (test `test_runner_rejects_out_of_bounds_intensity_before_initialising_a_model` ⇒ 1 passed).

#### 3. Runner behaviour and study-final evidence
- 156 trace ticks in `study-final/trace.jsonl` (`ticks_executed=156` in `results.json`).
- Conservation summary: `max_material_tolerance_ratio=0.03910827217608296`, `max_finance_tolerance_ratio=0.0004547473508864434` (gate ≤1); `material_clock_advanced_per_quarter=1`.
- Per-seed opening state shared by all 13 arms: opening_state_digest sets (1729, 1730, 1731) = `3107...38`, `cabe...84`, `4601...80` (single value per seed, verified in results.json).
- Account-directory legality: 156/156 ticks `status=OK`; 2 616 002 journal legs checked; 0 invalid; 433 774 account-touches; account_directory_sha256 = `da9078d9...57a8d`, 3841 accounts per seed.
- Unconstrained-request recheck: 0.0 max-abs diff on all 156 ticks (`investment_request_recheck_max_abs_diff == 0.0` for every record); uncapped hunger formula equals flows field everywhere.
- Per-arm credit_drawn exactly 0.0 in 18/18 (seed, arm) cells for the 6 hard/credit_cut arms; non-zero only in the 7 soft/rescue_cut/placebo arms.
- Bailout granted only in the 2 credit_cut arms (base ≈ 24 261–24 265; reduced ≈ 25 867–25 879); 11 other arms grant 0.0; 11 are deduped (defect 13 fix).
- Placebo (`placebo_soft_low_base`) digests (comparison, scientific, final-state, journal) equal `soft_low_base` on all three seeds; per-seed comparison digest repeats the values reported in the manifest (`092b8ef...`, `0f06762...`, `0a2c56f...`).
- Demand-regime first stage: 9 channels differ (energy, higher_value_food, light_goods, passenger_car, personal_services, refrigerator, repair_services, television, washing_machine); 18/18 records BINDING.
- stock_close exported per tick for all `(commodity, stage)` cells with `cells`, `source="sum of state.stock_value over its cells"`; no fabricated `commodity_circuit`.
- demand_by_axis.parquet schema: `axis_status ∈ {OBSERVED, BLOCKED_METRIC}`, 216 axes, 24 OBSERVED per arm-seed (9 capitals/energy/food/consumer/durable/transport mixes), 192 BLOCKED_METRIC per arm-seed; zero-denominator path not triggered on this branch (real tiny-engine test `test_zero_denominator_and_missing_axis_never_become_zero_shortage` exercises both statuses from a real run, passes).
- organization_investment_credit_wip.parquet has 31 200 rows and the 6 cash columns null in all 31 200 rows (not 0).
- study-final manifest SHA matches its declared value (`673bff2b...e583aa`); all 10 artifact SHAs recomputed and match exactly.
- Reversed arm-order run does not contaminate a later arm (`test_arm_order_does_not_contaminate_a_later_arm`); forward vs reverse digests equal per-arm for all 13 arms.
- `RUN_NOT_RUN` finance probe: `finance_trace.status=NOT_RUN` on 156/156 ticks, with the recorded reason stating the engine fills `procurement_trace` only on its H3B bank-lender path and that switching would break the preregistered comparison/final-state/journal digests.

#### 4. Independent re-runs (fresh directory `outputs/h5a-a1-review-20261021T200000Z/`)
Positive (1 seed × 8 arms × 4Q = 32 ticks, PARTIAL): reproduced all expected characteristics.
```
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m experiments.hist_enterprise \
  --root . --spec studies/HIST_VNEXT/M02/spec.json --seeds 1729 \
  --arms soft_low_base,hard_low_base,rescue_cut_high_base,credit_cut_high_base,soft_high_base,soft_low_reduced,hard_low_reduced,placebo_soft_low_base \
  --output-dir outputs/h5a-a1-review-20261021T200000Z/positive
```
Result: status=PARTIAL, ticks=32, placebo digest `092b8efe8caad716d072a1ff658afa...` (byte-identical to `study-final` for seed 1729), rescue_cut_high_base == soft_high_base comparison digest `a24cc173...37045f` (byte-identical to `study-final`).

Negative (rescue_cut vs soft_high digest equality, plus the permanent tiny-engine test):
```
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m experiments.hist_enterprise \
  --root . --spec studies/HIST_VNEXT/M02/spec.json --seeds 1729 \
  --arms rescue_cut_high_base,soft_high_base \
  --output-dir outputs/h5a-a1-review-20261021T200000Z/negative
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_hist_enterprise_mechanisms.py::test_zero_denominator_and_missing_axis_never_become_zero_shortage
```
Result: both rescued_cut and soft_high_base share digest `a24cc1739400612f5608159930baba...37045f`; the zero-denominator/axis-blocked guard test passes.

#### 5. Structural / historical / F2 verdict
- `verdicts.structural.by_regime.base.verdict = "REJECTED"`, `levels_adjudicated=["low","high"]`, `readable_contrasts_by_level={"high":3, "low":3}` (3 seeds × 2 levels = 6).
- `verdicts.structural.by_regime.reduced.verdict = "REJECTED"`, `levels_adjudicated=["low","high"]`, same readable counts.
- `supported_claim = null`; `SUPPORTED` not produced in any sub-record.
- `rescue_leg_nonbinding_records = 12`, `credit_leg_nonbinding_records = 0`: joint credit + hardness is the binding leg, hardness-only is NONBINDING (`ZERO_OUTPUT`) on all 12 records; this matches the §5.1 decomposition.
- `historical.identification_status = "UNIDENTIFIED"`, `historical_support = "NOT_ESTABLISHED"`, `level = "NOT_RUN"`; `f2_generalisation.status = "NOT_RUN"`.
- `bottleneck_demand_count` is exported but explicitly labelled "diagnostic_only"; no verdict depends on it. Regimes never pooled; triple-difference and regime-interaction values are reported per seed.

#### 6. Regression / legacy
- Six legacy directories C0, C1, C0a, C0b, C1a, C1b each have 116 completed ticks, status=completed, parameter_hash and deterministic_replay_digest equal to the frozen 01 values: C0-family `parameter_hash=e27ade6a...0445`, digest `92f9ea0a...8a42d`; C1-family `parameter_hash=632ee6a6...c3b90`, digest `c4810481...e5d5`. `diff -rq C0a C0b` and `diff -rq C1a C1b` empty. `verify_run_identity` passes 6/6.
- pytest directed: 168 passed; pytest full: 1759 passed, 180 warnings; 31 hist-enterprise tests pass on re-run.
- `ruff check --no-cache src tests experiments`: "All checks passed!" (the previously-fixed `tests/test_hist_enterprise_mechanisms.py:384 F821` now imports `from typing import Any`; ruff exit 0 on this round).
- `hsm baseline verify --json`: `status: ok`, sha256 matches `1f5b233f...1b6f`.
- `uv lock --check --offline`: exit 0.
- `protection_diff_against_pre_run_snapshot` empty; user-dirty 05/06 SHA values unchanged.

#### 7. finance_trace=NOT_RUN disclosure — adjudicated honestly
The disclosure is complete: `finance_trace.status = NOT_RUN` on 156/156 ticks with the recorded reason (engine fills `procurement_trace` only on the H3B bank-lender path; passing `credit_approval_caps` would switch the journal account path and break the preregistered comparison/final-state/journal digests that the placebo and reproducibility checks rely on). All six procurement intermediates are null in all 31 200 parquet rows (not 0); the columns exist in the schema and are forwarded into the per-org table. The plan contract accepts "if a column can't be filled on this branch, just skip it and label accordingly": the runner explicitly does that (NOT_RUN status, null values, transparent disclosure in REPORT §9 and EVIDENCE_MANIFEST.not_run). No quantity is imputed, estimated or reported.

#### 8. Manifest integrity
- 64-char SHAs (recomputed `35b5b7ff…`, `afce89cf…`, etc.) match.
- `studies/HIST_VNEXT/M02/EVIDENCE_MANIFEST.json` is `SELF_EXCLUDED` in its own commit_table.
- No stale profile/1-seed numbers; the manifest references three fully-executed runs (study-final COMPLETED, study-fix COMPLETED, profile-fix PARTIAL with status correctly labelled).
- `review.reviewer=null`, `verdict=null`, `status=PENDING`; `not_run` contains "independent phase-reviewer review and studies/HIST_VNEXT/M02/REVIEW.md".
- `studies/HIST_VNEXT/M02/REVIEW.md` does not exist before this review (verified).

### What remains unestablished

Technical:
- Long-run (multi-year) equilibration; the preregistered window is fixed at `1957Q1-Q4` with `warmup_quarters=0` and `auto_extension=false`, and the spec refuses both warmup and auto-extension.
- Behaviour on a branch other than `intermediate8`; out-of-scope by whitelisted source-scenario rule.

Structural:
- The card's "sustained, demand-regime-independent shortage" claim — by design not reachable from a 4Q synthetic window; explicitly returned as a level-`NOT_RUN` historical/sufficiency verdict with `supported_claim=null`. No `SUPPORTED`.
- Generalisation outside the preregistered 13 arms; the runner refuses unregistered arms before any model is initialised.

Historical / cross-cutting:
- Enterprise-archive identification status remains `UNIDENTIFIED`; no admitted archive or independent shortage observation was used; this delivery cannot promote the historical verdict.
- F2 investment price axis: deliberately `NOT_RUN`.
- H0B registration for M02 is unchanged: one mapped counter stays mapped (used as diagnostic only), three blocked metrics stay blocked, no registration status flipped.
- H3G family channel and any `src/engine|state|storage` change: deliberately not touched.
- Seed count is never used to manufacture significance; regimes are never pooled into a confidence interval.
- The journal path is the legacy Treasury-credit path; `procurement_trace` cash/cap intermediates are honestly null until a H3B bank-lender journal is exercised.

### Independent review files
- Fresh re-run outputs: `outputs/h5a-a1-review-20261021T200000Z/{positive,negative}/` with their own manifests (`positivesha256=9bc6f1db...2da9`, `negativesha256=3bdbd88d...70de`); `account_directory.json` SHA = `876d4a8e...3acbdb` (matches the seeded intermediate8 directory).
- All artifacts traced, all digests recomputed. No PATCH/REDESIGN items.
- No implementation files were edited by this review; no commit, push, reset, checkout, stash or clean.
