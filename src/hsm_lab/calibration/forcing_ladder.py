"""Configured H0–H4 closure diagnostic ladder, restricted to intermediate8."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from hsm_lab.calibration.closure import diagnose_kernel_closure
from hsm_lab.contract.guards import load_research_contract, load_scenario


class ForcingRung(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rung_id: Literal["H0", "H1", "H2", "H3", "H4"]
    name: str = Field(min_length=1)
    credit_envelope_fraction: float = Field(ge=0.0, le=1.0)


class ForcingLadderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"]
    scenario_id: Literal["intermediate8"]
    diagnostic_ticks: int = Field(ge=8)
    seed: int = Field(ge=0)
    forcing_variable: Literal["credit_envelope_fraction"]
    f2_binding: str = Field(min_length=1)
    rungs: list[ForcingRung] = Field(min_length=5, max_length=5)

    def validate_sequence(self) -> None:
        expected = ["H0", "H1", "H2", "H3", "H4"]
        if [rung.rung_id for rung in self.rungs] != expected:
            raise ValueError(f"rungs must be ordered exactly as {expected}")


def load_forcing_ladder_config(root: Path) -> ForcingLadderConfig:
    path = root / "config" / "p06" / "forcing_ladder.json"
    config = ForcingLadderConfig.model_validate_json(path.read_text(encoding="utf-8"))
    config.validate_sequence()
    return config


def run_forcing_ladder(
    root: Path,
    output_dir: Path,
    *,
    diagnostic_ticks: int | None = None,
    seed: int | None = None,
) -> dict[str, object]:
    """Run configured diagnostic rungs on the toy/intermediate catalog only."""
    if output_dir.exists():
        raise FileExistsError(f"forcing-ladder output directory exists: {output_dir}")
    config = load_forcing_ladder_config(root)
    contract = load_research_contract(root)
    spec = load_scenario(root, config.scenario_id)
    ticks = config.diagnostic_ticks if diagnostic_ticks is None else int(diagnostic_ticks)
    effective_seed = config.seed if seed is None else int(seed)
    if ticks < 8 or effective_seed < 0:
        raise ValueError("diagnostic_ticks must be >= 8 and seed must be non-negative")

    output_dir.mkdir(parents=True)
    results: list[dict[str, object]] = []
    for rung in config.rungs:
        parameters = spec.material_parameters
        if parameters is None:
            raise ValueError("intermediate8 scenario has no material parameters")
        rung_spec = spec.model_copy(
            update={
                "material_parameters": parameters.model_copy(
                    update={"credit_envelope_fraction": rung.credit_envelope_fraction}
                )
            }
        )
        certificate = diagnose_kernel_closure(
            rung_spec,
            contract,
            diagnostic_ticks=ticks,
            seed=effective_seed,
        )
        payload = {
            "rung_id": rung.rung_id,
            "name": rung.name,
            "scenario_id": config.scenario_id,
            "diagnostic_ticks": ticks,
            "seed": effective_seed,
            "forcing_variable": config.forcing_variable,
            "credit_envelope_fraction": rung.credit_envelope_fraction,
            "certificate": certificate.to_json(),
        }
        (output_dir / f"{rung.rung_id}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        results.append(
            {
                "rung_id": rung.rung_id,
                "status": certificate.status,
                "passed": certificate.passed,
                "output_liveness": certificate.output_liveness,
                "max_finance_tolerance_ratio": certificate.max_finance_tolerance_ratio,
                "max_material_tolerance_ratio": certificate.max_material_tolerance_ratio,
            }
        )
    payload = {
        "status": "measured",
        "scenario_id": config.scenario_id,
        "diagnostic_ticks": ticks,
        "seed": effective_seed,
        "inference_status": "NOT_RUN",
        "f2_binding": config.f2_binding,
        "rungs": results,
    }
    (output_dir / "forcing_ladder.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload
