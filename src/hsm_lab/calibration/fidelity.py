"""P05 F1 paired-fidelity stage (plan §F / §175).

``prior_fidelity`` studies how the active summaries respond to prior draws, so a
surrogate (F1) posterior is only promoted to F2 when it reproduces the training
statistics.  The study needs a declared *candidate parameter set*; when the
identifiability screen finds none, this stage stops and reports
``NO_IDENTIFIABLE_PARAMETERS`` instead of inventing vectors or a compensation
model.  The paired-study algorithm itself is declared but not implemented: it is
recorded as the required input for whenever a candidate set exists.
"""

from __future__ import annotations

import json
from pathlib import Path

from hsm_lab.calibration.screen import screen_parameters

STAGES = ("prior", "posterior")


def prior_fidelity(root: Path, *, config: Path, stage: str = "prior") -> dict[str, object]:
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

    # A candidate set exists. The paired study (16 maximin Latin-hypercube prior
    # vectors x 3 seed pairs, paired median bias <= 0.25 scale, 90th absolute bias
    # <= 0.5 scale, Spearman >= 0.9 under sufficient variation, >= 90 % direction
    # agreement) is declared by the plan but not implemented yet.
    tolerances = control.get("tolerances", {})
    seeds = control.get("seed_banks", {})
    return {
        "status": "PAIRED_STUDY_NOT_IMPLEMENTED",
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
            "a candidate set exists; the paired-fidelity algorithm is a declared "
            "but unimplemented work item and must not be replaced by a hold-out-"
            "trained F1->F2 compensation model"
        ),
    }
