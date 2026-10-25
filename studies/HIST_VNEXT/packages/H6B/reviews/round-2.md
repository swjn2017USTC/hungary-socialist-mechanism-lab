## VERDICT: **PATCH**

Read-only second review. I edited nothing in the repo: `git status --porcelain=v1` = 32 lines before and after (= the 29 snapshot paths + `src/hsm_lab/evidence/package_export.py`, `tests/test_hist_package_contract.py`, `studies/HIST_VNEXT/packages/`), nothing staged, `git diff --check` clean. All my artifacts live in `/tmp/h6b-r2/` (git-archive clone, APFS-cloned sandbox, probe scripts).

---

### 1. Round-1 repairs P1–P7 — verified independently

| # | Result | Evidence |
|---|---|---|
| P1 symlink escape | **FIXED** | `ln -sfn ../../../../data/private …/H6B/privlink`, index M01 → that path: `{"error": "symlink rejected before open/hash: 'studies/HIST_VNEXT/packages/H6B/privlink'", "exit_code": 2}`, 411 open events, **0 restricted opens**. `guard()` (`:392-427`) rejects every symlink component pre-resolution, then re-checks resolved parts + symlinked ancestors. Permanent test `test_restricted_symlink_is_rejected_before_resolution` present. |
| P2 asserted real-card checks | **FIXED for the enumerated scope; residual → new P9** | 18-mutation battery on **cloned copies of the real artifacts** (`/tmp/h6b-r2/mut`): all 5 round-1 mutations now flip the target check to `BLOCKED` **and** the card to `complete=false` — M01 null lever metric, M01 `cut_first_stage.status=DEGRADED`, M01 non-binding lever, M01 `historical_status=SUPPORTED`, M02 null `shortage_expectation_mean`, M02 budget/investment `NONBINDING`, M04 null `formal_unmet_total`, M04 zeroed `tolerance_05` (monotonicity), M04 `treatment_only=false`, M02 manifest `ticks_failed=3` / `invalid_legs=7`, M01 `failures`/`completed_arms=77`. 13/13 as expected. |
| P3 snapshot | **FIXED** | 29/29 entries decoded, exist, sha256 **and** byte-length match the live files; live `git status --porcelain=v1 -z` = exactly those 29 + 3 H6B paths. |
| P4 cold-local index | **FIXED** | `build --mode local-data` **inside** `outputs/…/cold-local` (isolated `PYTHONPATH`, original interpreter) → exit 0, `complete=0/blocked=11`, honest reason `"fresh_root and repeat_root must both be present for an independent replay"`. |
| P5 line anchors | **PARTIAL** | M01 (`REPORT.md:162` = “Result: **UNIDENTIFIED**…”, `:60` = “**Empty C0 political tables:**…”) and M09 (`:106/:122/:205`) now support their reasons. Residual on a *complete* card → new **P10**. |
| P6 dead `pair_control` | **FIXED** | zero occurrences in `package_export.py` / tests (only in REPORT/round-1 prose). |
| P7 traceability | **FIXED** | `commands.json` now has `repo` and `python` absolute paths; `REVIEW.md` still pending (expected pre-commit). |

### 2. Independent reproductions (all pass)

- **Export determinism**: rebuilt `local-data` and `git-only` into `/tmp` → `diff -r` **identical** to the delivered `exports/`; `package_digest` `2bc2f606…` / `1dbbcfc0…`; `verify` exit 0 on all four directories.
- **Cold start**: rebuilt the git-only export inside the `git archive HEAD` checkout (no `.git`, no ignored outputs, isolated `PYTHONPATH`) → **byte-identical** to the delivered git-only export.
- **C0/C1**: `verify_run_identity` → both frozen 01 digests, 116 ticks, frozen parameter hashes `e27ade6a…` / `632ee6a6…`. M02 fresh vs repeat differ in exactly **2 leaves** (`resources.wall_seconds`, `resources.max_rss_bytes`).
- **No restricted access**: audit-hook probe — git-only: 490 opens, **0** under `outputs/`, **0** under `data/`; local-data: 258 opens under `outputs/`, all inside declared index roots; 2 opens under `history/` (rights metadata only).
- **Export hygiene**: no `original_excerpt|ocr_text|translation|local_path|secret`; no absolute paths (only relative `.venv/bin/python …` reproduction argv); no timestamps; **no historical SUPPORTED claim** (every “SUPPORTED” occurrence is a negation or a structural label).
- **3/8 classification independently justified from raw artifacts**: M01 78 arms / 3 seeds / exactly one opening digest per seed / 8 ticks per arm / max material 9.52e-4, finance 2.70e-5 / `failures []`; M02 `COMPLETED` 156 ticks / 39 arm-seeds / placebo digest-equal in all 3 seeds / conservation 156 passed 0 failed / 2,616,002 journal legs, 0 invalid; M04 144 arm-ticks / `tolerance_0 < 0.5 < 1` in every seed / zero arm = 0 / F2 residuals 1.14e-13 & 1.42e-14. M09’s “no negative control” is real: its preregistered spec has 4 arms and **0** occurrences of `negative|control|placebo|null`. All 41 legacy metric strings preserved **exactly and in order** vs `config/p06/cards/M*.json` (registry 11/41/14/27).
- **Gates**: `pytest -q -p no:cacheprovider` → **1898 passed, 180 warnings in 216.45 s**; `ruff check --no-cache src tests` → All checks passed; `uv lock --check --offline` → Resolved 101 packages (exit 0); `hsm baseline verify --json` → status ok, SHA `1f5b233f…`; `BASELINE.md` unchanged; 20/20 `protected_hashes.json` match.
- No target leakage, no fake interpolation, no fake replicates, no hold-out leakage, no LLM-probability-as-history, no single-commodity shortcut (H6B adds no simulation and no time series).

---

### 3. New defects (bounded, inside the H6B whitelist)

**P8 — MEDIUM · `--root` does not bind `studies/manifest.json`; the audit is CWD-dependent**
`src/hsm_lab/evidence/package_export.py:3020` → `load_evidence_manifest(root, Path("studies/manifest.json"))`. The loader resolves `manifest_path` against the **process CWD** (`loader.py:2094`), while the evidence index *is* root-bound (`:520 root / path`) and the repo convention joins root (`loader.load_all_evidence_records` → `root/"studies"/"manifest.json"`).

```
# (a) cwd without studies/manifest.json
build --root /Users/…/cold-neg4   →  exit 2
  "study manifest/cards failed verification: Evidence manifest not found:
   studies/manifest.json (relative to root /private/tmp/h6b-r2/cold-neg4)"

# (b) cwd with a schema-valid but FOREIGN manifest (10 of 11 records)
build --root /Users/…/hungary-socialist-mechanism-lab --mode git-only
  → exit 0, package_digest 1dbbcfc0…  (identical to the delivered export)
```
Consequence: the card/sidecar binding gate (`verify_study_manifest_cards`) can verify a manifest that does **not** belong to `--root`; in (b) the `P07A1-M11` record was never verified while the audit claimed root binding. Fix (one line): `load_evidence_manifest(root, root / "studies" / "manifest.json")`, plus a permanent test that a cwd-foreign manifest is ignored. (The frozen plan’s literal `Path("studies/manifest.json")` is ambiguous; the module’s own index handling and the repo convention are not.)

**P9 — MEDIUM · two of the eleven checks on the three *complete* cards are still asserted, not derived**
Hardcoded `_ok(...)` at `:1142` (M01 sensitivity), `:1146` (M01 counterevidence), `:1477`/`:1494` (M02), `:1904`/`:1922` (M04) — the same class as round-1’s P2, which the repair only covered for `first_stage_checked`/`metrics_generated`/`historical_evidence_grade`. Demonstrated on a cloned artifact set (`/tmp/h6b-r2/mut`, `verdict.levers.welfare_cut.status="SUPPORTED"` applied consistently to the existing study **and** both replay roots so the reproduction digest still matches):

```
build --mode local-data → exit 0
M01 research_package_complete: True package_status: complete
counterevidence: PASS | "welfare lever is UNIDENTIFIED, …"
historical_counterevidence[0].statement: "welfare_cut history contrast is UNIDENTIFIED …"
   refs.status: SUPPORTED
verdicts.structural: "import_cut=…; income_cut=…; welfare_cut=SUPPORTED"
```
The public export thus certifies `complete` while contradicting itself about the same lever. The **current** artifacts are truthful (`welfare_cut` really is `UNIDENTIFIED` — verified), so this is gate under-derivation, not a present false claim; but the frozen plan requires the eleven checks to be artifact-derived (“技术完整性不得由…单独推导”; check #10 forbids passing on assertion). Fix: derive both checks from the artifacts (M01: welfare lever status + ablation rows; M02: `results.json#/verdicts/structural` falsification flags + non-empty contrasts; M04: manifest `statistical_summary.first_stage`/capacity ceiling) and `BLOCKED` on contradiction. The M09 equivalents (`:2147`, `:2158`) are lower priority (card already blocked).

**P10 — LOW · residual non-supporting line anchors (round-1 P5 class) on a complete card**
`:1497` cites `studies/HIST_VNEXT/M02/REPORT.md:1` — the title line `# H5A-A1 / M02 — soft budget and investment hunger…` — for the claim “the card’s falsification criterion is met in this window (non-falling shortage axes); SUPPORTED is explicitly unreachable”. The falsification text actually lives in `results.json#/verdicts/structural` (“the card’s own falsification criterion is met in this model and window: on at least one preregistered shortage axis…”) and in the spec’s `falsification_rule`. M03/M06/M07 blocked checks likewise anchor at line 1 for specific blocker ids. Fix: re-anchor M02 to the falsification paragraph or the JSON pointer; use manifest pointers for M03/M06/M07.

---

### 4. Pre-commit checklist (not defects; required by the frozen delivery list)

`studies/HIST_VNEXT/packages/H6B/{REVIEW.md, EVIDENCE_MANIFEST.json, COMMIT_RECEIPT.json}` do not exist yet. `REVIEW.md` is expected after this verdict; `EVIDENCE_MANIFEST.json` must cover every delivered file’s SHA/length and exclude itself and the post-commit receipt; the receipt follows the commit. `model_usage.json` must gain the round-2 entry.

### 5. Open, already-disclosed deviation (not new)

Implementation was executed in the supervisor session by `deepseek/deepseek-flash` instead of the prescribed separate `minimax-code-cn/MiniMax-M3` task (`model_usage.json`, REPORT §1); the frozen plan forbids role fallback. Usage is honestly `NOT_MEASURED`, never zero.

**Why not PASS / not REDESIGN:** the architecture (separate package layer, root-guarded reads, strict index, deterministic export, recomputing verifier) is sound and the science is right — the 3 complete / 8 blocked classification is reproducible from the artifacts and no historical SUPPORTED claim exists. But P8 breaks the root binding of the manifest check the plan mandates, and P9 leaves two of the eleven checks asserted on exactly the three cards the package certifies as complete; both are demonstrable, in-whitelist, one-to-two-line fixes. No architectural or scientific failure → not REDESIGN; new defects → PATCH.