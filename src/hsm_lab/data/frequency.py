"""Period parsing and frequency-boundary aggregations (BASELINE §24).

Monthly->quarterly and quarterly->annual only. There is deliberately no
annual->quarterly interpolation API: annual outcomes are compared after
aggregating the quarterly simulation, never by faking quarterly observations.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

import polars as pl

from hsm_lab.contract.schemas import ConfigError, Frequency, ResearchGateError

_MONTHLY_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
_QUARTERLY_RE = re.compile(r"^(\d{4})Q([1-4])$")
_ANNUAL_RE = re.compile(r"^(\d{4})$")
_DATED_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

Aggregation = Literal["sum", "mean", "end_of_period"]

PERIOD_COLUMN = "period"
VALUE_COLUMN = "value"


def validate_period(text: str, frequency: Frequency) -> None:
    """Raise ConfigError unless ``text`` is a valid period for ``frequency``."""
    if not isinstance(text, str) or not text:
        raise ConfigError(f"period must be a non-empty string, got {text!r}")
    if frequency is Frequency.MONTHLY and not _MONTHLY_RE.match(text):
        raise ConfigError(f"invalid monthly period {text!r}: expected YYYY-MM")
    if frequency is Frequency.QUARTERLY and not _QUARTERLY_RE.match(text):
        raise ConfigError(f"invalid quarterly period {text!r}: expected YYYYQ[1-4]")
    if frequency is Frequency.ANNUAL and not _ANNUAL_RE.match(text):
        raise ConfigError(f"invalid annual period {text!r}: expected YYYY")
    if frequency is Frequency.DATED:
        if _DATED_RE.match(text) is None:
            raise ConfigError(f"invalid dated period {text!r}: expected YYYY-MM-DD")
        try:
            date.fromisoformat(text)
        except ValueError as exc:
            raise ConfigError(f"invalid dated period {text!r}: {exc}") from exc
    # static: any non-empty literal is accepted.


def period_sort_key(text: str, frequency: Frequency) -> tuple[int, ...]:
    """A sortable key for periods of one frequency (static has none)."""
    validate_period(text, frequency)
    if frequency is Frequency.MONTHLY:
        year, month = text.split("-")
        return (int(year), int(month))
    if frequency is Frequency.QUARTERLY:
        return (int(text[:4]), int(text[-1]))
    if frequency is Frequency.ANNUAL:
        return (int(text),)
    if frequency is Frequency.DATED:
        year, month, day = text.split("-")
        return (int(year), int(month), int(day))
    raise ConfigError("static periods have no total order")


def _key_columns(frame: pl.DataFrame) -> list[str]:
    return [c for c in frame.columns if c not in (PERIOD_COLUMN, VALUE_COLUMN)]


def _check_duplicates(frame: pl.DataFrame) -> None:
    duplicated = (
        frame.group_by(_key_columns(frame) + [PERIOD_COLUMN])
        .len()
        .filter(pl.col("len") > 1)
    )
    if duplicated.height:
        raise ResearchGateError(
            f"duplicate period rows within a group: {duplicated.head(3).to_dicts()}"
        )


def _value_expr(aggregation: Aggregation) -> pl.Expr:
    if aggregation == "sum":
        return pl.col(VALUE_COLUMN).sum()
    if aggregation == "mean":
        return pl.col(VALUE_COLUMN).mean()
    # end_of_period: last row when periods are ordered within the group
    return pl.col(VALUE_COLUMN).sort_by(pl.col(PERIOD_COLUMN)).last()


def _validate_frame(frame: pl.DataFrame, frequency: Frequency) -> list[str]:
    if PERIOD_COLUMN not in frame.columns or VALUE_COLUMN not in frame.columns:
        raise ConfigError("frame must contain 'period' and 'value' columns")
    for period in frame[PERIOD_COLUMN].to_list():
        validate_period(period, frequency)
    _check_duplicates(frame)
    return _key_columns(frame)


def monthly_to_quarterly(frame: pl.DataFrame, aggregation: Aggregation) -> pl.DataFrame:
    """Aggregate monthly rows to quarterly by complete 3-month groups.

    Duplicate periods or missing months fail; nothing is implicitly filled.
    """
    keys = _validate_frame(frame, Frequency.MONTHLY)
    enriched = frame.with_columns(
        pl.col(PERIOD_COLUMN).str.slice(0, 4).alias("_year"),
        pl.col(PERIOD_COLUMN).str.slice(5, 7).cast(pl.Int32).alias("_month"),
    ).with_columns(((pl.col("_month") - 1) // 3 + 1).alias("_quarter"))

    per_quarter = enriched.group_by(keys + ["_year", "_quarter"]).agg(
        pl.col("_month").n_unique().alias("_distinct"),
        pl.len().alias("_rows"),
    )
    bad = per_quarter.filter((pl.col("_distinct") != 3) | (pl.col("_rows") != 3))
    if bad.height:
        raise ResearchGateError(
            "incomplete month-of-quarter group (expected exactly months "
            f"{(1, 2, 3)} per quarter): {bad.drop('_distinct', '_rows').head(3).to_dicts()}"
        )

    # Aggregate while the original monthly periods are still present so that
    # end_of_period sorts by true month order; then relabel to quarterly.
    aggregated = enriched.group_by(keys + ["_year", "_quarter"]).agg(
        _value_expr(aggregation)
    )
    return aggregated.with_columns(
        (pl.col("_year") + "Q" + pl.col("_quarter").cast(pl.Utf8)).alias(PERIOD_COLUMN)
    ).drop("_year", "_quarter")

def quarterly_to_annual(frame: pl.DataFrame, aggregation: Aggregation) -> pl.DataFrame:
    """Aggregate quarterly rows to annual; each year must have exactly 4 quarters."""
    keys = _validate_frame(frame, Frequency.QUARTERLY)
    enriched = frame.with_columns(
        pl.col(PERIOD_COLUMN).str.slice(0, 4).alias("_year"),
        pl.col(PERIOD_COLUMN).str.slice(5, 1).alias("_quarter"),
    )
    per_year = enriched.group_by(keys + ["_year"]).agg(
        pl.col("_quarter").n_unique().alias("_distinct"),
        pl.len().alias("_rows"),
    )
    bad = per_year.filter((pl.col("_distinct") != 4) | (pl.col("_rows") != 4))
    if bad.height:
        raise ResearchGateError(
            "incomplete quarter-of-year group (expected exactly quarters "
            f"{(1, 2, 3, 4)} per year): {bad.drop('_distinct', '_rows').head(3).to_dicts()}"
        )
    aggregated = enriched.group_by(keys + ["_year"]).agg(_value_expr(aggregation))
    return aggregated.with_columns(pl.col("_year").alias(PERIOD_COLUMN)).drop("_year")
