"""Output writers for the synthetic smoke run: Parquet + DuckDB.

``ensemble_compact`` writes aggregates/summary/trajectory only. ``research_full``
additionally streams per-tick micro long-form Parquet for households and
enterprises (never accumulating the full micro panel in memory); the DuckDB
file exposes those files as views instead of copying them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import polars as pl
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

AGGREGATE_COLUMNS = [
    "tick",
    "quarter",
    "actor_kind",
    "region_id",
    "commodity_id",
    "count",
    "weight_sum",
    "probe_sum",
    "probe_mean",
]
EVENT_COLUMNS = ["tick", "quarter", "event"]
MICRO_COLUMNS = [
    "tick",
    "quarter",
    "actor_id",
    "region_id",
    "commodity_id",
    "weight",
    "probe_value",
]

_AGGREGATE_SCHEMA = pa.schema(
    [
        ("tick", pa.int64()),
        ("quarter", pa.string()),
        ("actor_kind", pa.string()),
        ("region_id", pa.string()),
        ("commodity_id", pa.string()),
        ("count", pa.int64()),
        ("weight_sum", pa.float64()),
        ("probe_sum", pa.float64()),
        ("probe_mean", pa.float64()),
    ]
)

_MICRO_SCHEMA = pa.schema(
    [
        ("tick", pa.int64()),
        ("quarter", pa.string()),
        ("actor_id", pa.int64()),
        ("region_id", pa.string()),
        ("commodity_id", pa.string()),
        ("weight", pa.float64()),
        ("probe_value", pa.float64()),
    ]
)


class MicroWriter:
    """Streaming per-tick micro long-form Parquet writer."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._writer = pq.ParquetWriter(path, _MICRO_SCHEMA)

    def write_tick(
        self,
        tick: int,
        quarter: str,
        actor_ids: np.ndarray,
        region_index: np.ndarray,
        region_names: list[str],
        commodity_ids: list[str],
        weights: np.ndarray,
        probe_matrix: np.ndarray,
    ) -> None:
        """Append one tick of micro rows (actor-major, commodity-minor)."""
        n_actors, n_commodities = probe_matrix.shape
        region_per_actor = np.asarray(region_names, dtype=object)[region_index]
        table = pa.table(
            {
                "tick": pa.array(np.full(n_actors * n_commodities, tick, dtype=np.int64)),
                "quarter": pa.array([quarter] * (n_actors * n_commodities)),
                "actor_id": pa.array(np.repeat(actor_ids, n_commodities)),
                "region_id": pa.array(np.repeat(region_per_actor, n_commodities)),
                "commodity_id": pa.array(
                    np.tile(np.asarray(commodity_ids, dtype=object), n_actors)
                ),
                "weight": pa.array(np.repeat(weights, n_commodities)),
                "probe_value": pa.array(np.ascontiguousarray(probe_matrix).reshape(-1)),
            },
            schema=_MICRO_SCHEMA,
        )
        self._writer.write_table(table)

    def close(self) -> None:
        self._writer.close()


def write_aggregates(frame: pl.DataFrame, directory: Path) -> Path:
    path = directory / "aggregates.parquet"
    frame.write_parquet(path)
    return path


def write_summary(summary: dict[str, Any], directory: Path) -> Path:
    path = directory / "summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_duckdb(
    directory: Path,
    aggregates: pl.DataFrame,
    events: pl.DataFrame,
    micro_parquets: dict[str, Path] | None = None,
) -> Path:
    """Materialize aggregates/events; full-policy micro becomes parquet views."""
    path = directory / "trajectory.duckdb"
    connection = duckdb.connect(str(path))
    try:
        connection.execute("SET threads TO 1")
        connection.register("aggregates_arrow", aggregates.to_arrow())
        connection.execute("CREATE TABLE aggregates AS SELECT * FROM aggregates_arrow")
        connection.unregister("aggregates_arrow")
        connection.register("events_arrow", events.to_arrow())
        connection.execute("CREATE TABLE events AS SELECT * FROM events_arrow")
        connection.unregister("events_arrow")
        for view_name, parquet_path in (micro_parquets or {}).items():
            connection.execute(
                f"CREATE VIEW {view_name} AS SELECT * FROM read_parquet('{parquet_path}')"
            )
    finally:
        connection.close()
    return path
