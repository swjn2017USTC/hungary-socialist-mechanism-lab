# H3C Independent Review — Final PASS

## Reviewer

Repository `phase-reviewer` subagent, read-only.  The reviewer did not edit
implementation files.  Actual model selector/effort/token/cost are
`deepseek/deepseek-flash` / `NOT_SET` / `NOT_MEASURED` / `0.0`; no paid model
call was made.

## Final verdict

**PASS** — no remaining blocking defect in the reviewed v2 candidate.

Acceptance is limited to the revised synthetic, full-information technical
routing/shortfall contract.  It is **not** historical validation, a national
infeasibility proof, or a uniquely identified bottleneck.

## History

- v1 full-demand plan: three independent reviews returned REDESIGN; the real
  F2 1957Q1 boundary physically lacked `g09_basic_food` and
  `g10_animal_food` supply.  The blocked candidate was preserved.
- The user then authorized a redesign (2026-10-18).  v2 added an explicit
  non-negative shortfall vector `s[D]`, `sum(x)+v+s=demand`, objective
  `min sum(s)`, and `EXECUTED` / `PARTIAL` statuses.
- v2 PATCH rounds repaired: gross-demand restoration, import double-count,
  fallback prior-tier bounds, certificate NaN/hash/row/optimality validation,
  household-checkout separation, regional plot funding identity, account-kind
  payment matching, full comparison evidence, supervisor terminal accounting,
  exact runner/Plan provenance, and solver-free dual KKT reuse.

## Independently exercised final verification

- Re-ran all **26 H3C tests**, including solver-free supplied-certificate
  execution (solver monkeypatched to fail), self-consistent suboptimal witness
  rejection, regional incoming/outgoing tampering, account-kind redirects and
  malformed certificate metadata.
- Reconstructed and validated all **12 exported profile certificates**,
  including sparse dual KKT evidence and three-level nesting.
- Replayed `historical_f2_replay`, seed 1729, complete gross demand:

| Quarter | Status | Shortfall |
|---|---|---:|
| 1957Q1 | PARTIAL | 30,576.498286 |
| 1957Q2 | PARTIAL | 16,848.748909 |
| 1957Q3 | PARTIAL | 36,665.006131 |
| 1957Q4 | PARTIAL | 49,158.479493 |

  Closing-state digests matched; clock reached four ticks; non-household edge
  and shortfall residuals were at most `2.84e-13`.
- Profile packages contain primal/shortfall vectors, sparse duals, row
  metadata/fingerprints, hashes, solver metadata, timings, nesting results,
  and LP-0/LP-1 comparison executions with journals and gate results.
- Exact supervisor accounting: all four mode directories sum to
  **439,547,446 bytes**, ledger equal, no violation; profile4 alone is
  438,570,202 bytes.
- Source, revised Plan, runner and output/log hashes match all four manifests
  and `verification/verification.json`; protected `BASELINE.md`, research
  contract and lock hashes remain unchanged.
- C0/C1 `verify_run_identity` accepted: 116 ticks through 1985Q4, seed 1729,
  prescribed parameter hashes and exact digests.
- Final hash-bound logs: **1,154 passed**, ruff clean.

## Known limits

- Historical status remains `UNIDENTIFIED / NOT_RUN`.
- The shortfall is a boundary-specific physical/routing result, not a national
  infeasibility theorem.
- The hard resource supervisor covers the four `run_h3c.py` modes; final
  pytest/ruff/lock/baseline/C0/C1 verification commands are hash-bound in
  `verification/verification.json` under the documented narrower v2 contract.
