VERDICT: PASS

# H4A-1 documentation repairs D1–D5 — independent re-audit

Read-only. No repository file was edited; tree state before/after my audit is identical (`git status --porcelain` = 10 M + 16 ??, same set).

## D1–D5 dispositions — all CLOSED, evidence-backed (not reworded)

| ID | Disposition | Evidence I observed |
|---|---|---|
| **D1** | CLOSED | `H1A_REPAIR.md:114–118` records the three `usage_limit_reached` failures under the old selector, the switch to `minimax-code-cn/MiniMax-M3:high`, and the real round-14 PASS, pointing to `H1A_REREVIEW_ROUND14_ATTEMPTS.md` for failures and `H1A_REREVIEW_ROUND14.md` for PASS. `H1A_REREVIEW_ROUND14_ATTEMPTS.md` independently lists 4 attempts (3× `usage_limit_reached`, 1× `429 余额不足…`) and states "No verdict was returned… it is not an independent verdict." Independently corroborated: `git diff .omp/config.yml` is exactly one line (`review: openai-codex/gpt-6.1-sol:high` → `review: minimax-code-cn/MiniMax-M3:high`); I reproduced every command ROUND14 claims (below). Chain verdicts read from each file's first line: rounds 1–13 `VERDICT: PATCH`, round 14 `**VERDICT: PASS**`. |
| **D2** | CLOSED | `H1A_REREVIEW_ROUND11.md` exists (9.4 KB), first line `VERDICT: PATCH`, substantive evidence table + repair dispositions; referenced at `H1A_REPAIR.md:24`. |
| **D3** | CLOSED | `REPORT.md:167–173` discloses the delta, names it a user configuration change, and excludes it from the planned commit. Observed `git diff -- .omp/config.yml`: single-line `review:` change, nothing else. |
| **D4** | CLOSED | `SAME_SEED_CONTROL.json` records `status=paused`, `completed_ticks=4`, `planned_ticks=116`, `horizon_reached=false`, `identity_verification=NOT_RUN` with the correct reason. Verified against artifacts: `synthetic_4Q/manifest.json` → `status=paused, completed_ticks=4, seed=1729`; `summary.json` → `planned_ticks=116, horizon_reached=false, last_completed_quarter=1957Q4`. `verify_run_identity` on that dir raises `ValueError: verify_run_identity: run status is 'paused', expected 'completed'` — exactly the stated reason. I re-ran the control independently (`hsm run --scenario historical_f2_replay --seed 1729 --until 1957Q4`, `/tmp`): digest `0d360553a9066dc60515bffd34abae80b5f556ed188609f0063ba6fd73e9fa03` reproduced exactly, run_id **differed** (`105735c0e81c4ee7a00d346b4308b219` vs `467b7d5a2ad747ecbc0f176d51c3ea8d`) — which both substantiates "independently reproduced" and demonstrates why a digest is not a byte proof. |
| **D5** | CLOSED | `REPORT.md:188–195` four-row byte-identity table (canonical `NOT_RUN`, checkpoint `NOT_RUN`, strict full-file `UNMET`, digest `PASS` + caveat); `:197–208` explicit BLOCKED/NOT_RUN acceptance table; `:210–270` 63 anchors by original `anchor_id`; `:272–307` per-region/national derived quantities with units. I verified the 63 ids programmatically against `config/initial_state/hist_vnext_v1/anchor_crosswalk.json` `records`: set equality both directions (0 report-only, 0 crosswalk-only), 63/63 classification match, all `blocked`. I recomputed all 20 region rows + national from the live CLI JSON: every value matches to the report's 10-significant-digit presentation rounding; national fsum `17000 / 5000 / 5100 / 6800 / 8500` exact. |

## Observed evidence (commands I ran)

| Check | Result |
|---|---|
| `shasum -a 256` of the seven reviewed files | All seven **byte-identical** to both `EXPERIMENT_INPUT_REVIEW.json` and `EXPERIMENT_INPUT_APPROVAL.json` scopes |
| review file sha vs `approval.review.sha256` | `4100afb8…` = `4100afb8…`; approval sha `c322f7bb…` = `ACTUAL_INPUT_MANIFEST.approval.sha256`; `logs/EXPERIMENT_INPUT_REVIEW.json` and `…APPROVAL.json` are byte-identical to the committed copies |
| experiment CLI, no approval | **exit 1**, `structural=PASS`, `admission=PENDING`, `approved_inputs=0`, `historical_inputs_admitted=0`, `runtime_connected=false` |
| experiment CLI, `--approval …/EXPERIMENT_INPUT_APPROVAL.json` | **exit 0**, `EXPERIMENT_ONLY`, `approved_inputs=3`, `historical=NOT_ESTABLISHED`, `errors=[]` |
| copied config, unit `M_forint` | **exit 2**, `structural=BLOCKED`, `admission=BLOCKED`, `approved_inputs=[]` |
| H1A CLI `…sources.admission --root .` | exit 1, structural PASS, historical BLOCKED; 4 candidates, 0 admitted, 63 blocked anchors, 5 blocked authorities, 10 candidate events, 4 review requests — matches ROUND14 |
| H4A-0 CLI `…h4_sources.admission --root . --verify-files` | exit 1, structural PASS, historical UNIDENTIFIED; 14 candidates, **0 approved inputs** — matches ROUND14 |
| `git diff --name-only -- history/HIST_VNEXT/h4_sources/ docs/phases/HIST_VNEXT/H4A-0/ data/` | **empty** — old statistical domain, old registry, old crosswalk approval set and data manifest byte-unchanged |
| `verify_run_identity` C0 | **VERIFIED** — 116 ticks, completed, parameter hash `e27ade6a…` = frozen pin |
| `verify_run_identity` C1 | **VERIFIED** — 116 ticks, completed, parameter hash `632ee6a6…` = frozen pin |
| `pytest tests/test_hist_experiment_initial_admission.py` | 36 passed |
| `pytest` experiment + H1A + H4A-0 crosswalk | 234 passed |
| full suite `pytest -q -p no:cacheprovider` | **1688 passed, 180 warnings in 106.70 s** (recorded log: 1688/180 in 103.17 s) |
| `ruff check` new module + tests | All checks passed |
| `hsm baseline verify --json` | `status=ok`, `1f5b233f…`; `git diff --stat BASELINE.md` empty → **no silent BASELINE change** |
| `uv lock --check --offline` | exit 0, 101 packages |
| recipe/scenario hashes recomputed independently | household `c879be08…`, material `b2c4122f…`, file `c58cdc79…`, `dwelling_per_person=0.4`, 20 regions / 20 counties, grade S / structural_assumption / synthetic — all as reported |
| user-dirty preservation | `05_REVISED_IMPLEMENTATION_PLAN.md`, `06_OMP_MINIMAX_HANDOFF.md`, root `H4A_1_前置补完_PLAN.md`, `09_BATCH02…md` all still match `logs/start_state.txt` byte-for-byte |
| engine/data/scenario untouched | `git diff --stat -- src/ data/ config/scenarios/` empty; no untracked files under `src/`, `data/`, `config/scenarios/`; `grep -rn "experiment_admission" src/` → no consumer (so `runtime_connected=false` is structurally true, not just declared) |

## Remaining defect (1, non-blocking, must NOT be edited)

- `docs/phases/HIST_VNEXT/H4A-1/H1A_REREVIEW_ROUND14.md:12` quotes the H4A-0 CLI command as `PYTHONDONDWRITEBYTECODE=1 …` (typo for `PYTHONDONTWRITEBYTECODE`). The claimed observation is true — I reproduced exit 1 / structural PASS / historical UNIDENTIFIED / 0 approved inputs. Evidence-string transcription defect only; no research claim is affected. **This file is inside the seven-file hash scope of `EXPERIMENT_INPUT_REVIEW.json`/`EXPERIMENT_INPUT_APPROVAL.json`; correcting the typo would invalidate the approval and require a fresh independent review.** Record it as a known artifact; leave the bytes alone.

No other defects found. No new defects introduced by the D1–D5 edits (the edits are confined to `H1A_REPAIR.md`, the new `H1A_REREVIEW_ROUND11.md`, `REPORT.md` and `SAME_SEED_CONTROL.json`, none of which is inside the approved hash scope except ROUND14, which is unchanged).

## Research-correctness audit (role rule 6)

- **Target leakage / forcing substitution:** none. `purpose` is `Literal["initial_state"]` in declaration, review and approval models; no `forcing`/`actor` path exists in the new domain; H1A blocks `purpose=forcing|actor`. The module never writes engine state and has no `src/` consumer.
- **Historical contamination:** record model admits no `source_id`/`source_sha256`/`pdf_page`/`value_ref`/`rights` (`StrictModel` rejects `source_id`, fixture-tested); `historical_status`, `runtime_connected`, `historical_inputs_admitted=0` are literals/hard-coded, not configuration.
- **Accounting/material-balance invariant:** `D_r = ratio × P_r`; national = `math.fsum` over regions; units declared (`persons`, `households`, `dwellings/person`→`dwellings`); positivity, `persons ≥ households`, finiteness, bool-masquerade, and 20-region one-to-one bijection all enforced fail-closed; no zero-fill, no national substitution for a missing region. Test `test_derived_quantities_are_complete` asserts the conservation identity, not the numbers.
- **Fake quarterly interpolation / fake stochastic replicates:** impossible this step — no engine change. The only stochastic object is the 4-tick pure-synthetic control, and its run JSON carries the standing research warnings ("Simulation is an argument, not evidence"; "A probability produced by an agent or decision model is not a historical probability").
- **Hold-out leakage:** no `1986|1987|1988|holdout` token in the new module; C0/C1 end at 1985Q4.
- **Multi-commodity shortcut:** none — the experiment derives per-region dwelling counts only and pins `baseline` to the existing `material_initial.dwelling_per_person` (0.4), so it cannot silently redefine the base recipe.
- **Tests assert research invariants, not implementation:** H1A suite = 99 behavioural tests (role separation, rights/excerpt provenance, authority coverage, date precision, legacy-artifact bijection, shared-root independence, structural exit-2 propagation); H4A-1 suite = 36 boundary/invalidations tests.
- **Software fixture is not historical evidence:** stated at `H1A_REPAIR.md:120–121` and in ROUND14's preservation section; no report passage treats `positive_software_fixture_reaches_exit_0` as a source.

## Scope boundaries (what this PASS does and does not cover)

1. PASS covers: the five documentation repairs, the seven-file byte-identity of the approved scope, CLI/approval semantics, H1A/H4A-0 regression preservation, C0/C1 identity against frozen pins, the truthful 4Q-control marking, and absence of overclaims. It does **not** authorize production initialization, measurement wiring, runtime connection, or any historical claim — all remain BLOCKED/NOT_RUN as documented.
2. Still unmet and correctly disclosed: H3F-D3 strict full-file C0/C1 byte gate; H3G same-tick `realized/unmet` structural null + missing standalone review; H4A-0 approved sets empty (0 approved inputs); no push.
3. **Commit-scope requirement for the main agent:** the H1A repair left five tracked files modified and unstaged (`history/HIST_VNEXT/sources/admission.py`, `tests/test_hist_source_admission.py`, `history/HIST_VNEXT/sources/batch01_candidates.json`, `history/HIST_VNEXT/event_candidates/events.json`, `config/initial_state/hist_vnext_v1/anchor_crosswalk.json`, `config/initial_state/hist_vnext_h4_v1/anchor_crosswalk.json`, plus `docs/phases/HIST_VNEXT/H1A/PLAN.md`). If the planned commit stages only the new H4A-1 files, the committed tree would ship the **old** H1A `admission.py` while the committed docs assert the repaired round-14 PASS — stage the H1A repair files in the same commit.
4. Must be excluded from that commit: `.omp/config.yml` (will correctly remain dirty after commit), `outputs/` (gitignored), user dirty `docs/upgrade_review/…/05_REVISED_IMPLEMENTATION_PLAN.md`, `…06_OMP_MINIMAX_HANDOFF.md`, `09_BATCH02_YEARBOOKS_D08_D10_INTAKE.md`, and the 11 untracked root `*_PLAN.md` files.
5. Not verifiable from the repository: the claim that a user message authorized the bounded H1A repair (`H1A_REPAIR.md:1–4`), and the raw reviewer transcripts behind `EXPERIMENT_INPUT_REVIEW.json` / the round files beyond the preserved artifacts (`logs/H1A_REREVIEW.md` is byte-identical to `docs/…/H1A_REREVIEW.md`, `95da4e54…`; no raw transcript is stored for round 14 or the experiment review). These are accepted as disclosed claims, not independently re-derived.
