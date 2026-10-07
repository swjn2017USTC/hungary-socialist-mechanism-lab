"""D3: frequency-boundary aggregation with concrete numeric examples."""

from __future__ import annotations

import polars as pl
import pytest

from hsm_lab.contract.schemas import ConfigError, ResearchGateError
from hsm_lab.data.frequency import monthly_to_quarterly, quarterly_to_annual, validate_period


def frame(periods: list[str], values: list[float], variable: str = "oil") -> pl.DataFrame:
    return pl.DataFrame(
        {
            "variable_id": [variable] * len(periods),
            "period": periods,
            "value": values,
        }
    )


@pytest.mark.parametrize(
    ("aggregation", "expected"),
    [("mean", 20.0), ("sum", 60.0), ("end_of_period", 30.0)],
)
def test_monthly_to_quarterly_numeric(aggregation, expected) -> None:
    result = monthly_to_quarterly(
        frame(["1970-01", "1970-02", "1970-03"], [10.0, 20.0, 30.0]), aggregation
    )
    assert result["period"].to_list() == ["1970Q1"]
    assert result["value"].to_list() == [expected]


@pytest.mark.parametrize(
    ("aggregation", "expected"),
    [("mean", 2.5), ("sum", 10.0), ("end_of_period", 4.0)],
)
def test_quarterly_to_annual_numeric(aggregation, expected) -> None:
    result = quarterly_to_annual(
        frame(["1970Q1", "1970Q2", "1970Q3", "1970Q4"], [1.0, 2.0, 3.0, 4.0]), aggregation
    )
    assert result["period"].to_list() == ["1970"]
    assert result["value"].to_list() == [expected]


def test_missing_month_fails() -> None:
    with pytest.raises(ResearchGateError, match="incomplete"):
        monthly_to_quarterly(frame(["1970-01", "1970-02"], [1.0, 2.0]), "sum")


def test_missing_quarter_fails() -> None:
    with pytest.raises(ResearchGateError, match="incomplete"):
        quarterly_to_annual(frame(["1970Q1", "1970Q2", "1970Q3"], [1.0, 2.0, 3.0]), "mean")


def test_duplicate_period_fails() -> None:
    with pytest.raises(ResearchGateError, match="duplicate"):
        monthly_to_quarterly(
            frame(["1970-01", "1970-01", "1970-02"], [1.0, 5.0, 2.0]), "sum"
        )


def test_unordered_quarters_end_of_period_uses_period_order() -> None:
    result = quarterly_to_annual(
        frame(["1970Q3", "1970Q1", "1970Q2", "1970Q4"], [30.0, 10.0, 20.0, 40.0]),
        "end_of_period",
    )
    assert result["value"].to_list() == [40.0]


def test_groups_aggregate_independently() -> None:
    mixed = pl.DataFrame(
        {
            "variable_id": ["a", "a", "a", "b", "b", "b"],
            "period": ["1970-01", "1970-02", "1970-03",
                       "1970-01", "1970-02", "1970-03"],
            "value": [1.0, 2.0, 3.0, 10.0, 20.0, 30.0],
        }
    )
    result = monthly_to_quarterly(mixed, "sum").sort("variable_id")
    assert result["variable_id"].to_list() == ["a", "b"]
    assert result["value"].to_list() == [6.0, 60.0]


def test_cross_year_boundary_not_merged() -> None:
    with pytest.raises(ResearchGateError, match="incomplete"):
        monthly_to_quarterly(
            frame(["1970-11", "1970-12", "1971-01"], [1.0, 2.0, 3.0]), "sum"
        )


def test_period_format_validation() -> None:
    from hsm_lab.contract.schemas import Frequency

    validate_period("1970-01", Frequency.MONTHLY)
    validate_period("1970Q1", Frequency.QUARTERLY)
    validate_period("1970", Frequency.ANNUAL)
    validate_period("1970-01-01", Frequency.DATED)
    with pytest.raises(ConfigError):
        validate_period("1970-13", Frequency.MONTHLY)
    with pytest.raises(ConfigError):
        validate_period("1970Q0", Frequency.QUARTERLY)
    with pytest.raises(ConfigError):
        validate_period("1970-02-30", Frequency.DATED)


# ----------------------------------------------------------------------
# Review round 2 (R4): complete observations and declared aggregations only.
# ----------------------------------------------------------------------
def _strict_frame(periods, values):
    return pl.DataFrame(
        {"variable_id": ["oil"] * len(periods), "period": periods, "value": values},
        schema={"variable_id": pl.String, "period": pl.String, "value": pl.Float64},
    )


MONTHS = ["1970-01", "1970-02", "1970-03"]
QUARTERS = ["1970Q1", "1970Q2", "1970Q3", "1970Q4"]


def test_null_value_rejected() -> None:
    with pytest.raises(ResearchGateError, match="null value"):
        monthly_to_quarterly(_strict_frame(MONTHS, [10.0, None, 30.0]), "sum")


def test_all_null_values_rejected() -> None:
    with pytest.raises(ResearchGateError, match="null value"):
        quarterly_to_annual(_strict_frame(QUARTERS, [None] * 4), "mean")


def test_nan_value_rejected() -> None:
    with pytest.raises(ResearchGateError, match="non-finite"):
        quarterly_to_annual(_strict_frame(QUARTERS, [1.0, float("nan"), 3.0, 4.0]), "mean")


def test_inf_value_rejected() -> None:
    with pytest.raises(ResearchGateError, match="non-finite"):
        monthly_to_quarterly(_strict_frame(MONTHS, [1.0, float("inf"), 3.0]), "sum")


def test_non_numeric_value_column_rejected() -> None:
    frame = pl.DataFrame(
        {"variable_id": ["oil"] * 3, "period": MONTHS, "value": ["a", "b", "c"]}
    )
    with pytest.raises(ResearchGateError, match="Float64"):
        monthly_to_quarterly(frame, "sum")


def test_undeclared_aggregation_rejected_without_fallback() -> None:
    good = _strict_frame(MONTHS, [10.0, 20.0, 30.0])
    with pytest.raises(ConfigError, match="unsupported aggregation"):
        monthly_to_quarterly(good, "interpolate")  # type: ignore[arg-type]
    good_q = _strict_frame(QUARTERS, [1.0, 2.0, 3.0, 4.0])
    with pytest.raises(ConfigError, match="unsupported aggregation"):
        quarterly_to_annual(good_q, "interpolate")  # type: ignore[arg-type]


def test_overflowed_aggregations_refused_without_fabrication() -> None:
    """1e308 inputs: the sum overflows; polars' mean goes through the same
    overflowing sum, so both are refused rather than emitted as Inf or
    silently replaced by a fabricated finite value."""
    huge = 1e308
    monthly = _strict_frame(["1970-01", "1970-02", "1970-03"], [huge, huge, huge])
    with pytest.raises(ResearchGateError, match="non-finite or unrepresentable"):
        monthly_to_quarterly(monthly, "sum")
    with pytest.raises(ResearchGateError, match="non-finite or unrepresentable"):
        monthly_to_quarterly(monthly, "mean")
    quarterly = _strict_frame(
        ["1970Q1", "1970Q2", "1970Q3", "1970Q4"], [huge, huge, huge, huge]
    )
    with pytest.raises(ResearchGateError, match="non-finite or unrepresentable"):
        quarterly_to_annual(quarterly, "sum")
    # representable arithmetic still passes exactly
    normal = _strict_frame(["1970-01", "1970-02", "1970-03"], [10.0, 20.0, 30.0])
    assert monthly_to_quarterly(normal, "mean")["value"].to_list() == [20.0]
