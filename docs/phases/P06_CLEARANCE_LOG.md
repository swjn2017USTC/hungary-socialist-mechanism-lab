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
