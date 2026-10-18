# H3A Independent Review

## Reviewer
Repository `phase-reviewer` subagent, read-only (`@review` entry in
`.omp/agents/phase-reviewer.md`). Actual selector/effort/token/cost are
`NOT_SET`; no paid fallback was used. The reviewer did not edit files.

## History
1. **PATCH** — round 1 found three defects:
   - `network.A.sort_indices()` / `network.B.sort_indices()` mutated caller-owned
     sparse matrices; canonical state/flow bytes did not catch it.
   - only an all-cells-missing network was rejected, so a declared non-stockable
     commodity with zero cells could produce a fake zero row.
   - evidence lacked REPORT, raw gate/household observations and hash manifests.
2. **PASS** — round 2, after the repairs below.

## Final verdict
**PASS** — no reproducible blocking defect remains in the repaired
observation layer.

## Repairs between rounds
- Removed both in-place CSR sorts; the module now aliases `network.A`/`network.B`
  for row traversal only.
- Added per-declared-commodity missing-cell rejection with a named
  `ResearchGateError`.
- Added `REPORT.md` and the evidence package
  (`manifest.json`, input/output SHA files, command/model/resource/failure
  records, final reproduce and 4Q/16Q smoke artifacts).
- Added `test_service_measurement_does_not_sort_network_matrices` and
  `test_service_measurement_rejects_partial_missing_service_cells`.

## Reviewer-executed verification (round 2)
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_hist_service_semantics.py
# 9 passed in 0.68s
```

The reviewer also ran the two repair-specific tests: **2 passed**, and
independently reproduced:
- reversed F2 A row 0 and B row 150, measured, and confirmed all six
  `indptr`/`indices`/`data` byte buffers unchanged and both sorted flags still
  false;
- a declared g16 with no cells → `ResearchGateError:
  hist-service-semantics-v1: declared non-stockable service(s) have no stock
  cell: 'g16_housing_public_services'`;
- a fresh 16Q paired smoke for seed 1729 (memory-only writer): control and
  observed bytes identical at every tick, output exactly matching the final
  artifact, ticks 0–15, ending 1960Q4;
- fresh `reproduce`/`reproduce_fuel`: exact match; control tuples
  `5/5/3/2/10`, `3/3/3/0/10`, `0/0/0/0/0`, `5/5/3/2/10`; fuel use `5/3/0`;
- all 12 input and 12 output hash bindings: zero mismatches;
- `verify_run_identity` for C0/C1: passed, 116 ticks each, frozen digests
  preserved;
- across 60 smoke records and 180 service balances, maximum absolute service
  residual `8.731149137020111e-11`; all gate ratios passed;
- resource/model fields remain honest `NOT_SET`; no tracked existing-file diff,
  no default-runner integration, no target/hold-out access, no historical claim.

Full-suite and lint results were inspected as reported evidence, not rerun in
the second audit (the candidate bytes were unchanged by the audit).

## Known limits
- The measurement is default-off and not wired into the runner.
- Formal budgets and model usage are `NOT_SET`; the review establishes code and
  evidence validity, not budget compliance.
- Historical verdict remains `UNIDENTIFIED / NOT_RUN`.

## Addendum after review (implementer note, not reviewer text)
The user approved the formal budgets and paid-model use on 2026-10-18. No code
changed after the PASS. The final commands were rerun under
`run_logged.py` with the caps in `resource-budget.json`: 11/11 runs exited 0,
max wall 98.79 s, max sampled process-tree RSS 1,086,701,568 B, max new output
20,111,463 B. No paid model call was needed. Monitored C0/C1 identities and the
reproduce/4Q/16Q artifacts matched the reviewed bytes. Resource-monitored
verification is therefore established separately from, and without altering,
the reviewer's code verdict.
