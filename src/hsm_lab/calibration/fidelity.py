"""P05 F1 paired-fidelity stage (plan §F / §175).

``prior_fidelity`` studies how active summaries respond to declared prior draws.
The paired comparison operates on paired F1/F2 summary arrays and never reads
targets. A real model comparison requires a declared candidate parameter set and
the F1/F2 runs; until then the infrastructure can only be smoke-tested on synthetic
summary arrays, not used to make a convergence claim.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from hsm_lab.calibration.screen import screen_parameters

STAGES = ("prior", "posterior")


def latin_hypercube_prior(
    bounds: dict[str, tuple[float, float]], *, seed: int = 1968, vectors: int = 16
) -> list[dict[str, float]]:
    """Return a deterministic, independently stratified prior design.

    This is a design helper only: callers must run each row through F1 and F2
    with the same seed pairs. It does not select or fit parameters.
    """
    if vectors < 2 or not bounds:
        raise ValueError("paired fidelity needs at least two vectors and one parameter")
    names = sorted(bounds)
    for name, (low, high) in bounds.items():
        if not np.isfinite([low, high]).all() or high <= low:
            raise ValueError(f"invalid prior bounds for {name!r}")
    rng = np.random.default_rng(seed)
    unit = np.empty((vectors, len(names)), dtype=np.float64)
    for column in range(len(names)):
        unit[:, column] = (rng.permutation(vectors) + rng.random(vectors)) / vectors
    return [
        {
            name: float(bounds[name][0] + unit[row, col] * (bounds[name][1] - bounds[name][0]))
            for col, name in enumerate(names)
        }
        for row in range(vectors)
    ]


def compare_paired_summaries(
    summaries: dict[str, dict[str, Any]],
    *,
    tolerances: dict[str, float],
    prior_vectors: int,
    seed_pairs: int,
    design_seed: int = 1968,
) -> dict[str, Any]:
    """Compare already-computed F1/F2 summaries from a paired design.

    Each metric supplies equally sized ``f1`` and ``f2`` arrays plus a positive
    ``scale`` declared from the training-statistic definition. Values are
    ordered vector-major, then seed-pair. This routine deliberately accepts no
    observed target series, so it cannot consume hold-out or reserved values.
    """
    if not summaries:
        raise ValueError("paired summaries are empty")
    if prior_vectors < 2 or seed_pairs < 1:
        raise ValueError("paired design is degenerate: require >=2 vectors and >=1 seed pair")
    expected = prior_vectors * seed_pairs
    required = {
        "paired_median_bias_scale",
        "paired_p90_abs_bias_scale",
        "spearman_min",
        "mechanism_direction_agreement",
    }
    missing = required - tolerances.keys()
    if missing:
        raise ValueError(f"missing declared fidelity tolerances: {sorted(missing)}")

    metric_results: dict[str, Any] = {}
    for name, item in sorted(summaries.items()):
        f1 = np.asarray(item.get("f1", []), dtype=np.float64)
        f2 = np.asarray(item.get("f2", []), dtype=np.float64)
        scale = float(item.get("scale", 0.0))
        if f1.ndim != 1 or f2.ndim != 1 or len(f1) != expected or len(f2) != expected:
            raise ValueError(
                f"metric {name!r} has degenerate paired data: expected {expected} F1/F2 values"
            )
        if not np.isfinite(f1).all() or not np.isfinite(f2).all() or not np.isfinite(scale):
            raise ValueError(f"metric {name!r} contains non-finite values")
        if scale <= 0.0:
            raise ValueError(f"metric {name!r} requires a positive declared scale")
        delta = (f2 - f1) / scale
        median_abs = float(np.median(np.abs(delta)))
        p90_abs = float(np.quantile(np.abs(delta), 0.9))
        # Rank correlation is undefined for constant summaries; refuse rather
        # than silently treating a degenerate statistic as agreement.
        if np.ptp(f1) == 0.0 or np.ptp(f2) == 0.0:
            raise ValueError(f"metric {name!r} is degenerate: Spearman correlation undefined")
        rank1 = np.argsort(np.argsort(f1, kind="mergesort"), kind="mergesort").astype(float)
        rank2 = np.argsort(np.argsort(f2, kind="mergesort"), kind="mergesort").astype(float)
        spearman = float(np.corrcoef(rank1, rank2)[0, 1])
        # Direction is assessed relative to the first prior vector, averaging
        # the declared seed replicates within each vector. The baseline itself
        # has no direction and is excluded from the denominator.
        f1_by_vector = f1.reshape(prior_vectors, seed_pairs).mean(axis=1)
        f2_by_vector = f2.reshape(prior_vectors, seed_pairs).mean(axis=1)
        d1 = np.sign(f1_by_vector[1:] - f1_by_vector[0])
        d2 = np.sign(f2_by_vector[1:] - f2_by_vector[0])
        informative = (d1 != 0.0) & (d2 != 0.0)
        if not informative.any():
            raise ValueError(f"metric {name!r} is degenerate: no directional variation")
        direction = float(np.mean(d1[informative] == d2[informative]))
        metric_results[name] = {
            "paired_median_abs_bias_scale": median_abs,
            "paired_p90_abs_bias_scale": p90_abs,
            "spearman": spearman,
            "mechanism_direction_agreement": direction,
            "pass": bool(
                median_abs <= tolerances["paired_median_bias_scale"]
                and p90_abs <= tolerances["paired_p90_abs_bias_scale"]
                and spearman >= tolerances["spearman_min"]
                and direction >= tolerances["mechanism_direction_agreement"]
            ),
        }
    return {
        "status": "ok",
        "design": {
            "prior_vectors": prior_vectors,
            "seed_pairs": seed_pairs,
            "latin_hypercube_seed": design_seed,
            "paired_observations_per_metric": expected,
            "ordering": "vector-major, then seed-pair",
        },
        "declared_tolerances": {key: float(tolerances[key]) for key in sorted(required)},
        "metrics": metric_results,
        "all_metrics_pass": all(result["pass"] for result in metric_results.values()),
        "scope": "synthetic/smoke paired summaries only; no target series consumed",
    }


def prior_fidelity(
    root: Path,
    *,
    config: Path,
    stage: str = "prior",
    paired_summaries: dict[str, dict[str, Any]] | None = None,
) -> dict[str, object]:
    """Report the F1 paired-fidelity preconditions for the declared control file."""
    if stage not in STAGES:
        raise ValueError(f"unknown fidelity stage {stage!r}; expected one of {STAGES}")
    control = json.loads(config.read_text(encoding="utf-8"))
    screen = screen_parameters(root, config=config)
    identified = list(screen["identified"])

    if not identified:
        return {
            "status": "NO_IDENTIFIABLE_PARAMETERS",
            "command": "calibration fidelity",
            "stage": stage,
            "screen_status": screen["status"],
            "admissible_targets": screen["admissible_targets"],
            "blocking_reasons": list(screen["blocking_reasons"]),
            "declared_linkage": list(screen["declared_linkage"]),
            "paired_study": None,
            "inference_status": "NOT_RUN",
            "note": (
                "no paired F1 study is run: there is no candidate parameter set to "
                "perturb, so no F1->F2 convergence claim can be made"
            ),
        }

    tolerances = control.get("tolerances", {})
    seeds = control.get("seed_banks", {})
    if paired_summaries is not None:
        paired = compare_paired_summaries(
            paired_summaries,
            tolerances=tolerances,
            prior_vectors=int(seeds["prior_vectors"]),
            seed_pairs=int(seeds["initial_seed_pairs"]),
            design_seed=int(seeds["f1_latin_hypercube_seed"]),
        )
        return {
            "status": "PAIRED_COMPARISON_COMPLETE",
            "command": "calibration fidelity",
            "stage": stage,
            "screen_status": screen["status"],
            "candidates": identified,
            "paired_study": paired,
            "inference_status": "NOT_RUN",
            "note": "paired comparison only; this does not run inference or validate the model",
        }

    # A candidate set exists, but no paired simulator outputs were supplied.
    # Keep this precondition report distinct from an executed comparison.
    return {
        "status": "PAIRED_RUNS_REQUIRED",
        "command": "calibration fidelity",
        "stage": stage,
        "screen_status": screen["status"],
        "candidates": identified,
        "required_inputs": {
            "prior_vectors": seeds.get("prior_vectors"),
            "latin_hypercube_seed": seeds.get("f1_latin_hypercube_seed"),
            "seed_pairs": seeds.get("initial_seed_pairs"),
            "paired_median_bias_scale": tolerances.get("paired_median_bias_scale"),
            "paired_p90_abs_bias_scale": tolerances.get("paired_p90_abs_bias_scale"),
            "spearman_min": tolerances.get("spearman_min"),
            "mechanism_direction_agreement": tolerances.get("mechanism_direction_agreement"),
        },
        "paired_study": None,
        "note": (
            "the comparison implementation is ready; declared paired F1/F2 runs are "
            "required before it can report a model result, and must not be replaced "
            "by a hold-out-trained F1->F2 compensation model"
        ),
    }
