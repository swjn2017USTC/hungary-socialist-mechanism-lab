# P05 Track A2 — source availability across tier rounds

Status: pre-registered experiment plan. This tests an existing declared rule without
changing the default or adding an unidentifiable coefficient.

## Candidate and rationale

The circuit audit ranks tier allocation as the second-largest source contraction (mean
factor 0.799 / 0.209, 14,618 zero-capacity groups; 13.0M / 4.2M units of need). The
allocation loop claims source-cell stock in sequential production/investment tiers and then
applies the existing same-commodity fallback round. `MaterialParameters.allocation_order`
is already declared and flattened, with `production_first` as the default and
`investment_first` as its alternative. This experiment tests whether letting investment
claims access each tier's available source stocks first changes terminal outcomes. It does
not add cross-region sourcing: the catalog does not model inter-regional routing, so pooling
inventories across regions would violate the transport/source identity.

## Arms and decision rules

- A2-B0: unchanged `production_first` control.
- A2-I: `investment_first` only; all other parameters remain the historical F2 defaults.

Run 116 ticks (1957Q1–1985Q4) on Mac. Record frozen gates, T1–T3, production and household
consumption terminal means, source allocation residuals, service funding, expiry, treasury,
transport realization, freight pool/need, physical delivery block share, household unmet
availability, cash, and wage arrears. Any accounting residual rejects the arm. A guardrail
regression (terminal consumption or household unmet availability worse than control) rejects
an arm absent compensating terminal-gate gains. No defaults change.

H-A2: source-tier priority is binding. It is supported only if A2-I improves T1 and T2 over
A2-B0 without a guardrail regression and passes all accounting checks. It is falsified if
neither terminal improves or if improvement requires a guardrail regression. Frozen gate
and terminal failures are reported individually; no partial result is called validation.

If neither T1 nor T2 is met by a valid arm, continue to A3 as directed by the master plan.
