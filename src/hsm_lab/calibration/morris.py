"""Morris elementary-effects screening for declared structural inputs.

This ranks declared inputs by deterministic screening effects. It is not an
estimator and has no posterior or identified-parameter interpretation.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class MorrisFactor:
    name: str
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if not self.name or not np.isfinite(self.lower) or not np.isfinite(self.upper):
            raise ValueError("Morris factors require a name and finite bounds")
        if self.upper <= self.lower:
            raise ValueError(f"Morris factor {self.name!r} requires upper > lower")


@dataclass(frozen=True)
class MorrisEffect:
    name: str
    mu: float
    mu_star: float
    sigma: float
    effects: tuple[float, ...]


def morris_screen(
    factors: list[MorrisFactor],
    evaluate: Callable[[dict[str, float]], float],
    *,
    trajectories: int = 4,
    levels: int = 4,
    seed: int = 1729,
) -> list[MorrisEffect]:
    """Compute normalized elementary effects over reproducible random trajectories."""
    if not factors or len({factor.name for factor in factors}) != len(factors):
        raise ValueError("Morris screening requires uniquely named factors")
    if trajectories < 1 or levels < 3:
        raise ValueError("trajectories must be positive and levels must be at least 3")
    delta = levels / (2.0 * (levels - 1.0))
    rng = np.random.default_rng(seed)
    collected: dict[str, list[float]] = {factor.name: [] for factor in factors}
    widths = {factor.name: factor.upper - factor.lower for factor in factors}

    for _ in range(trajectories):
        point: dict[str, float] = {}
        directions: dict[str, float] = {}
        for factor in factors:
            direction = 1.0 if rng.integers(0, 2) else -1.0
            if direction > 0:
                coordinate = int(rng.integers(0, levels // 2)) / (levels - 1.0)
            else:
                coordinate = float(rng.integers(levels // 2, levels)) / (levels - 1.0)
            point[factor.name] = coordinate
            directions[factor.name] = direction
        order = list(rng.permutation(len(factors)))
        response = float(evaluate(_scale_point(point, factors)))
        if not np.isfinite(response):
            raise ValueError("Morris evaluator returned a non-finite response")
        for index in order:
            factor = factors[int(index)]
            old = point[factor.name]
            point[factor.name] = old + directions[factor.name] * delta
            changed = float(evaluate(_scale_point(point, factors)))
            if not np.isfinite(changed):
                raise ValueError("Morris evaluator returned a non-finite response")
            normalized = (changed - response) / (delta * widths[factor.name])
            collected[factor.name].append(normalized)
            response = changed

    effects = []
    for factor in factors:
        values = np.asarray(collected[factor.name], dtype=np.float64)
        effects.append(
            MorrisEffect(
                name=factor.name,
                mu=float(values.mean()),
                mu_star=float(np.abs(values).mean()),
                sigma=float(values.std(ddof=0)),
                effects=tuple(float(value) for value in values),
            )
        )
    return sorted(effects, key=lambda item: item.mu_star, reverse=True)


def _scale_point(point: dict[str, float], factors: list[MorrisFactor]) -> dict[str, float]:
    by_name = {factor.name: factor for factor in factors}
    return {
        name: by_name[name].lower + value * (by_name[name].upper - by_name[name].lower)
        for name, value in point.items()
    }


def run_sobol_analysis(
    identification: dict[str, str],
    parameter_ids: list[str],
) -> None:
    """Guard the prohibited Sobol path; this reproduction study has no estimator."""
    if not parameter_ids:
        raise ValueError("Sobol analysis refused: no identified parameter set is declared")
    unresolved = [
        parameter
        for parameter in parameter_ids
        if identification.get(parameter) != "identified"
    ]
    if unresolved:
        raise ValueError(f"Sobol analysis refused for non-identified parameters: {unresolved}")
    raise NotImplementedError("Sobol estimation is outside the P06 reproduction-scope plan")


def run_structural_morris(
    root: Path,
    output_dir: Path,
    *,
    trajectories: int = 2,
    levels: int = 4,
    seed: int = 1729,
) -> dict[str, object]:
    """Run the declared eight-input Morris screen on the intermediate8 catalog."""
    from hsm_lab.calibration.axis_sweep import _gate_metrics
    from hsm_lab.contract.guards import load_research_contract, load_scenario
    from hsm_lab.data.registry import DataRegistry
    from hsm_lab.engine.material import run_material
    from hsm_lab.provenance.manifest import canonical_digest

    root = Path(root)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Morris output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    spec = load_scenario(root, "intermediate8")
    contract = load_research_contract(root)
    registry = DataRegistry.load(root, allowed_commodities=spec.commodities)
    if spec.material_parameters is None:
        raise ValueError("intermediate8 lacks material parameters")
    baseline = spec.material_parameters
    factors = [
        MorrisFactor("bailout_envelope_fraction", 0.15, 0.35),
        MorrisFactor("wage_rate", 5.0, 7.0),
        MorrisFactor("service_split.0", 0.55, 0.82),
        MorrisFactor("service_split.1", 0.12, 0.28),
        MorrisFactor("service_split.2", 0.05, 0.15),
        MorrisFactor("handling_work_per_unit.scale", 0.8, 1.2),
        MorrisFactor("trade.cmea_export_demands.scale", 0.8, 1.2),
        MorrisFactor("trade.convertible_export_demands.scale", 0.8, 1.2),
    ]
    terminal_floor = json.loads((root / "config/calibration/p05.json").read_text())[
        "gates"
    ]["terminal_floor"]
    arm_records: list[dict[str, object]] = []
    counter = 0

    def evaluate(values: dict[str, float]) -> float:
        nonlocal counter
        counter += 1
        updates: dict[str, object] = {
            "bailout_envelope_fraction": values["bailout_envelope_fraction"],
            "wage_rate": values["wage_rate"],
            "service_split": [
                values["service_split.0"],
                values["service_split.1"],
                values["service_split.2"],
            ],
        }
        split = updates["service_split"]
        total = sum(split)  # type: ignore[arg-type]
        updates["service_split"] = [item / total for item in split]  # type: ignore[union-attr]
        updates["handling_work_per_unit"] = [
            item * values["handling_work_per_unit.scale"]
            for item in baseline.handling_work_per_unit
        ]
        trade = baseline.trade.model_copy(
            update={
                "cmea_export_demands": [
                    item * values["trade.cmea_export_demands.scale"]
                    for item in baseline.trade.cmea_export_demands
                ],
                "convertible_export_demands": [
                    item * values["trade.convertible_export_demands.scale"]
                    for item in baseline.trade.convertible_export_demands
                ],
            }
        )
        updates["trade"] = trade
        parameters = baseline.model_copy(update=updates)
        arm_spec = spec.model_copy(update={"material_parameters": parameters})
        intervention_hash = canonical_digest(values)
        arm_dir = output_dir / f"arm-{counter:03d}"
        run = run_material(arm_spec, arm_dir, contract, registry, checkpoint_every=0)
        metrics = _gate_metrics(arm_dir, terminal_floor)
        arm_records.append(
            {
                "arm": arm_dir.name,
                "status": run.status,
                "ticks": run.completed_ticks,
                "parameter_hash": run.parameter_hash,
                "seed": spec.seed,
                "intervention_hash": intervention_hash,
                "deterministic_replay_digest": run.deterministic_replay_digest,
                "values": values,
                "metrics": metrics,
            }
        )
        return float(metrics["production_last_10"])

    effects = morris_screen(
        factors,
        evaluate,
        trajectories=trajectories,
        levels=levels,
        seed=seed,
    )
    payload: dict[str, object] = {
        "status": "screened",
        "scope": "declared structural sensitivity only; not estimation or identification",
        "scenario_id": "intermediate8",
        "trajectories": trajectories,
        "levels": levels,
        "seed": seed,
        "response": "production_last_10",
        "effects": [
            {
                "name": effect.name,
                "mu": effect.mu,
                "mu_star": effect.mu_star,
                "sigma": effect.sigma,
                "effects": list(effect.effects),
            }
            for effect in effects
        ],
        "arms": arm_records,
    }
    (output_dir / "morris.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload
