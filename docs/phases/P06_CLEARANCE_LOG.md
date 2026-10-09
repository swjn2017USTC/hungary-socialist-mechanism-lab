# P06 clearance work log

Append-only record required by `P05_P06_GATE_CLEARANCE_PLAN.md`. Each entry names its
own exit evidence and implementation commit; open gates remain explicitly open.

## 2026-10-10 — C1 Registry consistency — PASS

- Evidence: `config/calibration/p05.json`; `tests/test_p06_clearance.py`.
- Change: `scenarios.historical_replay` now names `historical_f2_replay`; regression
  test verifies every scenario name in the control file belongs to
  `AVAILABLE_SCENARIOS`.
- Check: `.venv/bin/ruff check tests/test_p06_clearance.py`;
  `.venv/bin/pytest -q tests/test_p06_clearance.py tests/test_calibration_p05.py`
  → 8 passed.
- Commit: `47de204 fix(p05): align the historical replay scenario registry`.

## 2026-10-10 — D1 Mechanism-card schema — PASS

- Evidence: `config/p06/mechanism_card.schema.json`,
  `src/hsm_lab/calibration/mechanism_cards.py`,
  `tests/test_p06_mechanism_cards.py`.
- Change: strict M1–M11 pre-registration schema and validator for the OMP_PLAN §10.5
  fields; only the five allowed result categories are accepted. No verdicts were assigned.
- Check: `.venv/bin/ruff check src tests` → clean;
  `.venv/bin/pytest -q` → 358 passed.
- Commit: `2eae29b feat(p06): add mechanism card schema and validator`.

## 2026-10-10 — D2 Forcing ladder — PASS WITH H4 CERTIFICATE FAILURE RECORDED

- Evidence: `config/p06/forcing_ladder.json`,
  `docs/phases/P06_FORCING_LADDER.md`,
  `outputs/p06-forcing-ladder-intermediate8-envelope/`.
- Change: configured H0–H4 as the declared `credit_envelope_fraction` ramp 0.5–0.9,
  with an explicit `intermediate8`-only runner and refusal of any other catalog. A
  preliminary certified-price intervention was discarded after it hit the existing
  deposit-coverage invariant; no gate was relaxed. F2 remains bound to Track A.
- Check: `.venv/bin/hsm calibration forcing-ladder --output-dir
  outputs/p06-forcing-ladder-intermediate8-envelope --json` completed 232 synthetic
  ticks for all five rungs. H0–H3 certificates pass; H4 records periodic output residual
  `1.3666e-6` against the `1e-6` cutoff. All accounting checks pass.
  `.venv/bin/ruff check src tests` → clean; `.venv/bin/pytest -q` → 361 passed.
- Commit: `021197b feat(p06): add intermediate H0-H4 forcing ladder`.

## 2026-10-10 — A0 Terminal-floor declaration and arm metrics — PASS

- Evidence: `config/calibration/p05.json` `gates.terminal_floor`; axis-sweep JSON output
  at `outputs/p06-a0-terminal-floor-smoke/`.
- Change: declared T1 production ≥35,092, T2 household consumption ≥2,085, and T3
  treasury solvent at tick 115 or zero treasury rescue grants across the final 20 ticks.
  Values are marked research declarations, not fitted values. Every sweep arm reports
  the three measurements and booleans; frozen acceptance gates remain unchanged.
- Check: `.venv/bin/hsm calibration axis-sweep --axis credit_envelope_fraction
  --points 0.5 --output-dir outputs/p06-a0-terminal-floor-smoke --json` → 116 ticks;
  T1 28,074.08 (fail), T2 1,667.96 (fail), T3 pass. `ruff check src tests` clean;
  `.venv/bin/pytest -q -p no:cacheprovider` → 362 passed.
- Commit: pending.
