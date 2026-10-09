"""Tests for the declared paired F1/F2 fidelity comparison."""

from __future__ import annotations

import numpy as np
import pytest

from hsm_lab.calibration.fidelity import compare_paired_summaries, latin_hypercube_prior

TOLERANCES = {
    "paired_median_bias_scale": 0.25,
    "paired_p90_abs_bias_scale": 0.5,
    "spearman_min": 0.9,
    "mechanism_direction_agreement": 0.9,
}


def test_smoke_paired_study_uses_declared_design_and_reports_real_metrics() -> None:
    vectors = latin_hypercube_prior(
        {"alpha": (0.1, 1.0), "beta": (2.0, 4.0)}, seed=1968, vectors=16
    )
    assert len(vectors) == 16
    assert len({row["alpha"] for row in vectors}) == 16
    assert len({row["beta"] for row in vectors}) == 16
    assert vectors == latin_hypercube_prior(
        {"alpha": (0.1, 1.0), "beta": (2.0, 4.0)}, seed=1968, vectors=16
    )

    base = np.repeat(np.arange(16, dtype=float), 3)
    offsets = np.tile(np.array([-0.01, 0.0, 0.01]), 16)
    result = compare_paired_summaries(
        {
            "training_statistic": {
                "f1": (base + offsets).tolist(),
                "f2": (base + offsets + 0.02).tolist(),
                "scale": 1.0,
            }
        },
        tolerances=TOLERANCES,
        prior_vectors=16,
        seed_pairs=3,
        design_seed=1968,
    )
    assert result["status"] == "ok"
    assert result["design"]["paired_observations_per_metric"] == 48
    assert result["declared_tolerances"] == TOLERANCES
    assert result["metrics"]["training_statistic"]["pass"] is True
    assert result["metrics"]["training_statistic"]["spearman"] == pytest.approx(1.0)
    assert result["all_metrics_pass"] is True
    assert "no target series consumed" in result["scope"]


def test_paired_study_refuses_degenerate_missing_pairs() -> None:
    with pytest.raises(ValueError, match="degenerate paired data"):
        compare_paired_summaries(
            {"training_statistic": {"f1": [1.0], "f2": [1.0], "scale": 1.0}},
            tolerances=TOLERANCES,
            prior_vectors=16,
            seed_pairs=3,
        )


def test_paired_study_refuses_constant_summary_even_with_full_pair_count() -> None:
    with pytest.raises(ValueError, match="Spearman correlation undefined"):
        compare_paired_summaries(
            {"training_statistic": {"f1": [1.0] * 48, "f2": [2.0] * 48, "scale": 1.0}},
            tolerances=TOLERANCES,
            prior_vectors=16,
            seed_pairs=3,
        )
