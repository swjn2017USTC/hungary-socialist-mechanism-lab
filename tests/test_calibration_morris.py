"""Morris is a reproducible sensitivity screen, never a calibration estimator."""

from __future__ import annotations

import pytest

from hsm_lab.calibration.morris import (
    MorrisFactor,
    morris_screen,
    run_sobol_analysis,
)


def test_morris_ranks_a_known_dominant_linear_input_deterministically() -> None:
    factors = [MorrisFactor("large", 0.0, 1.0), MorrisFactor("small", 0.0, 1.0)]
    def evaluate(values: dict[str, float]) -> float:
        return 2.0 * values["large"] + 0.05 * values["small"]
    first = morris_screen(factors, evaluate, trajectories=4, seed=1729)
    second = morris_screen(factors, evaluate, trajectories=4, seed=1729)
    assert first == second
    assert first[0].name == "large"
    assert first[0].mu_star == pytest.approx(2.0)
    assert first[1].mu_star == pytest.approx(0.05)


def test_morris_rejects_duplicate_or_degenerate_factors() -> None:
    with pytest.raises(ValueError, match="uniquely named"):
        morris_screen(
            [MorrisFactor("same", 0, 1), MorrisFactor("same", 0, 2)], lambda _: 0.0
        )
    with pytest.raises(ValueError, match="upper > lower"):
        MorrisFactor("flat", 1, 1)


def test_sobol_refuses_without_identified_parameter_set() -> None:
    with pytest.raises(ValueError, match="no identified parameter set"):
        run_sobol_analysis({"p04_coalition_prior": "unidentified"}, [])
    with pytest.raises(ValueError, match="non-identified"):
        run_sobol_analysis({"p04_coalition_prior": "unidentified"}, ["p04_coalition_prior"])
