PASS

# H4B-ID deterministic identity — independent review

Reviewer: repository `phase-reviewer` subagent, read-only. The reviewer did not edit implementation
or phase files. Actual selector/effort/tokens/cost are `NOT_MEASURED`; no paid fallback. The reviewer
independently re-ran the new tests, full suite, C0/C1/checkpoint pairs, `verify_run_identity`, the
legacy control, resume probes, ruff, baseline, and lock checks.

**Final verdict: PASS for the deterministic-identity change.** Pilot A is **not** signed.

## Round 1 — PATCH

Independent re-verification (HEAD `1b4e7b61…`) confirmed the core gate, verifier, legacy path,
fixed-clock binding, seed/scenario/clock sensitivity, and checkpoint-pair byte equality. Findings:

### P1 (blocking) — run id did not bind the declared run boundary

`src/hsm_lab/engine/material.py:5273-5298` included `resume_completed_ticks` but omitted `until` and
`checkpoint_every`. Reproduction (separate processes, same code):

```
u1  --until 1957Q1  --deterministic-identity → 13e37659fb9795ba1135eaef8f487cfb  (1 tick, paused)
u2  --until 1957Q2  --deterministic-identity → 13e37659fb9795ba1135eaef8f487cfb  (2 ticks, paused)
ck1 --until 1957Q4 --checkpoint-every 1      → 13e37659fb9795ba1135eaef8f487cfb  (4 ticks + checkpoints)
C0a (116 ticks, completed)                   → 13e37659fb9795ba1135eaef8f487cfb
```

`diff -rq` between u1/u2/C0a shows different tables and checkpoint sets: four materially different
output trees under one id. `src/hsm_lab/evidence/loader.py:1716-1718` collapses verified runs with
`by_run_id.setdefault(...)`, so boundary variants were indistinguishable to the evidence loader.

Repair: add `"until"` and `"checkpoint_every"` to the payload; add a regression test; regenerate
evidence and ids.

### P2 (blocking for evidence integrity) — stored checkpoint evidence predated the final code

The cited checkpoint pair carried `cbf8ac24…`, from before the final edit. Pair equality reproduced,
but the cited bytes/id did not. Repair: regenerate the checkpoint evidence under final code.

### P3 (documentation) — cited evidence paths did not exist

- `REPORT.md:41` and `COMMANDS.md:5` cited `…-final-20261021T021233Z/`; the actual root was
  `…-final-20261021T021224Z/`.
- `REPORT.md:78` cited an evidence root containing only `COMMANDS.md`; logs were in a sibling
  directory.

Repair: consolidate one evidence root and correct all paths.

### P4 (test gap) — no clock or boundary sensitivity assertion

Tests asserted seed/scenario/resume sensitivity only. Add boundary (`until`, `checkpoint_every`) and
clock sensitivity.

## Round 2 — PASS

All four repairs verified on current bytes.

### P1 — boundary binding fixed

`src/hsm_lab/engine/material.py:5293-5294` includes `"until"` and `"checkpoint_every"`. Independent
CLI reproduction (separate processes, same seed/scenario):

| Input | Run id |
|---|---|
| `--until 1957Q1` | `0d7bc1763b1bade3b3ddec937ad77771` |
| `--until 1957Q2` | `318b2a4cad0cd988cb289ab66eec48d2` |
| `--until 1957Q1 --checkpoint-every 1` | `224ec4781f865e76067750ce0f7f8e0b` |

Full-run ids regenerated and reproducible: C0 `887a6826a9d78a940116c32f4ca98afb`, C1
`512f26408836c95169fd1f1ac930ac66`, checkpoint `109829c14dab9e1a0126f9b98e06120f`. Fresh runs under
final code are byte-identical to the stored trees (`diff -rq` exit 0 for C0, C1 and ck), so the
id/clock/until binding no longer collapses distinct trees.

### P2 — checkpoint evidence regenerated and reproducible

Fresh `--until 1957Q4 --checkpoint-every 1` run = `109829c1…`; `diff -rq` against `runs/ck1` exit 0;
stored `ck1/ck2` diff exit 0, 104 files / 27,691,230 B each. The stale `cbf8ac24…` tree is no longer
cited.

### P3 — paths fixed

No stale `021233/021400/021311/021224` references remain under the phase docs or the evidence root.
`REPORT.md:78` and `COMMANDS.md:4-5` point at `outputs/hist-vnext-h4b-id-20261021T022120Z/`
(`runs/` included), which contains `COMMANDS.md`, all logs, diffs and JSONs.

### P4 — tests fixed

`pytest tests/test_hist_deterministic_identity.py` → **6 passed**. New
`test_run_id_binds_boundary_and_clock` asserts four distinct ids (until Q1, until Q2, shifted clock,
`checkpoint_every=1`). Evidence `identity_tests.log` and `full_pytest.log` agree.

## Independent gates

| Check | Result |
|---|---|
| C0/C1/ck `diff -rq` | exit 0; 32/9,771,034 B, 32/9,107,710 B, 104/27,691,230 B |
| Digests / parameters | `92f9ea0a…` / `e27ade6a…` and `c4810481…` / `632ee6a6…` — frozen pins |
| `verify_run_identity` C0a/C1a | passes; `completed`, 116 ticks, pinned hashes |
| Fixed clock in manifests | `started_at == finished_at == 2020-01-01T00:00:00Z`; timings zeroed, `deterministic_identity: true` |
| Legacy control (fresh, no flags) | random id, digest `92f9ea0a…`, `trajectory.duckdb` 15,216,640 B, nonzero timings, no marker; 19 files |
| Resume (new + legacy) | both exit 1 with the same pre-existing `stage_balances` residual — byte identity still **not claimed** |
| Full suite | **1694 passed, 180 warnings, 109.71 s** (report 109.41 s; count/warnings match) |
| ruff / baseline / lock | clean / `status=ok 1f5b233f…` / 101 packages |
| Frozen + staging | BASELINE, research contract, `uv.lock`, scenarios unchanged; `git diff --cached` empty; `.omp/config.yml` still only an unstaged pre-existing edit |

No new overclaim: `REPORT.md` §3/§5 keeps checkpoint-resume byte identity explicitly unclaimed and
keeps the other two H4B blockers open. **Pilot A is not signed.**

## Non-blocking erratum

`REPORT.md:58` stated the legacy control was `20,111,471 B`, but the evidence instance
(`runs/legacy_C0`) and `COMMANDS.md` said `20,111,461 B` (a fresh legacy run measured
`20,111,464 B`; legacy totals vary with timing-digit widths). File count (19) and the digest pin
match. Corrected in the report to the evidence instance value; the figure is illustrative.

The earlier `--resume` resolution against process CWD (`material.py:5268`) remains, but is
immaterial to this gate and to the unclaimed resume path.

## Scope boundaries

1. PASS covers the deterministic-identity change and the strict byte gate for fresh runs on the same
   host/commit/tree. It does not claim cross-platform reproducibility.
2. Checkpoint-resume byte identity is not claimed; the historical scenario checkpoint residual gate
   is pre-existing and reproduced on the legacy path.
3. The other two H4B blockers remain open: price/investment execution mapping and H4A runtime/
   measurement connection.
4. Only the nine whitelisted files may be committed. No push.
