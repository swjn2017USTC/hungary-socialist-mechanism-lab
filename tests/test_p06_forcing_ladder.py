"""D2 H0-H4 diagnostic forcing ladder is declared and F2-bound."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hsm_lab.calibration.forcing_ladder import (
    load_forcing_ladder_config,
    run_forcing_ladder,
)

ROOT = Path(__file__).resolve().parents[1]


def test_ladder_declares_h0_to_h4_and_binds_to_intermediate8() -> None:
    config = load_forcing_ladder_config(ROOT)
    assert config.scenario_id == "intermediate8"
    assert [rung.rung_id for rung in config.rungs] == ["H0", "H1", "H2", "H3", "H4"]
    assert [rung.credit_envelope_fraction for rung in config.rungs] == [
        0.5,
        0.6,
        0.7,
        0.8,
        0.9,
    ]
    assert config.forcing_variable == "credit_envelope_fraction"
    assert "Track A" in config.f2_binding


def test_ladder_refuses_an_f2_catalog(tmp_path: Path) -> None:
    path = tmp_path / "config/p06/forcing_ladder.json"
    path.parent.mkdir(parents=True)
    payload = json.loads((ROOT / "config/p06/forcing_ladder.json").read_text())
    payload["scenario_id"] = "historical_f2_replay"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_forcing_ladder_config(tmp_path)


def test_ladder_runs_all_rungs_on_intermediate8(tmp_path: Path) -> None:
    target = tmp_path / "ladder"
    payload = run_forcing_ladder(ROOT, target, diagnostic_ticks=8, seed=1729)
    assert payload["scenario_id"] == "intermediate8"
    assert payload["inference_status"] == "NOT_RUN"
    assert [row["rung_id"] for row in payload["rungs"]] == ["H0", "H1", "H2", "H3", "H4"]
    assert all((target / f"H{i}.json").is_file() for i in range(5))
