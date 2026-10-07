"""SocioVerse2 minimal real-store smoke (pinned ``socioverse2==0.2.0``).

This exercises the real DuckDB/Parquet trajectory store and its actual API -
no mocks, no LLM, no external event client, no economic computation. The
integration imports lazily: ``socioverse`` never enters the probe runtime.

Pinned-0.2.0 API notes (verified against the installed wheel):
- ``TrajectoryRecord`` has NO ``action_source`` field (main branch added it
  later); only agent_id/step/state/action_kind/action_payload are used.
- ``DuckDbTrajectoryStore.open()`` unlinks an existing DB, so the caller must
  pass a fresh directory.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

from hsm_lab.contract.schemas import ResearchGateError

STUDY_ID = "p00-smoke"


def smoke_socioverse(directory: Path) -> dict[str, Any]:
    """Write/read a real 2-agent, 2-step trajectory store in ``directory``.

    ``directory`` must be fresh (the upstream store unlinks existing DBs).
    Returns SQL/parquet evidence; raises with the real traceback on failure.
    """
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ResearchGateError(f"socioverse smoke directory not fresh: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    db_path = directory / "study.duckdb"

    trajectory = import_module("socioverse.schemas.trajectory")
    duckdb_store = import_module("socioverse.io.duckdb_store")

    TrajectoryRecord = trajectory.TrajectoryRecord
    DuckDbTrajectoryStore = duckdb_store.DuckDbTrajectoryStore
    open_readonly = duckdb_store.open_readonly

    store = DuckDbTrajectoryStore(db_path, study_id=STUDY_ID, export_parquet=True)
    store.open()
    for step in (0, 1):
        store.record(
            [
                TrajectoryRecord(
                    agent_id=f"probe-{agent}",
                    step=step,
                    state={"probe_value": step, "synthetic": True},
                    action_kind=None,
                    action_payload={},
                )
                for agent in (0, 1)
            ]
        )
        store.record_metrics({"step": step, "probe_total": 2 * step})
        if step == 1:
            store.record_events(step, ["p00-synthetic-event"])
    store.finalize()

    evidence: dict[str, Any] = {"study_id": STUDY_ID, "db_path": db_path.name}
    connection = open_readonly(db_path)
    try:
        panel_rows = connection.execute(
            "SELECT agent_id, step, CAST(state AS VARCHAR) AS state, action_kind, "
            "CAST(action_payload AS VARCHAR) AS action_payload "
            "FROM panel ORDER BY agent_id, step"
        ).fetchall()
        evidence["panel_rows"] = len(panel_rows)
        evidence["panel_primary_keys_unique"] = len(
            {(agent, step) for agent, step, *_ in panel_rows}
        ) == len(panel_rows)
        evidence["state_probe_values"] = {
            f"step{step}": sorted(
                int(row[0]) for row in connection.execute(
                    f"SELECT json_extract(state, '$.probe_value') FROM panel WHERE step = {step}"
                ).fetchall()
            )
            for step in (0, 1)
        }
        metrics_rows = connection.execute(
            "SELECT step, probe_total FROM metrics ORDER BY step"
        ).fetchall()
        evidence["metrics"] = [list(row) for row in metrics_rows]
        events_rows = connection.execute("SELECT step, note FROM events ORDER BY step").fetchall()
        evidence["events"] = [list(row) for row in events_rows]
    finally:
        connection.close()

    import polars as pl

    # Content-level round-trip equality: compare every field, semantically
    # for JSON columns; disagreement fails the smoke instead of flagging.
    def _json_or_none(text: object) -> object:
        import json as _json

        return _json.loads(str(text)) if text is not None else None

    panel_parquet = pl.read_parquet(directory / "panel.parquet")
    metrics_parquet = pl.read_parquet(directory / "metrics.parquet")
    panel_from_parquet = sorted(
        (
            row[0],
            row[1],
            _json_or_none(row[2]),
            row[3],
            _json_or_none(row[4]),
        )
        for row in panel_parquet.iter_rows()
    )
    panel_from_db = sorted(
        (row[0], row[1], _json_or_none(row[2]), row[3], _json_or_none(row[4]))
        for row in panel_rows
    )
    metrics_from_parquet = sorted(
        (row[0], row[1]) for row in metrics_parquet.iter_rows()
    )
    metrics_from_db = sorted((row[0], row[1]) for row in metrics_rows)
    if panel_from_parquet != panel_from_db:
        raise ResearchGateError(
            "socioverse smoke: panel.parquet content disagrees with the DuckDB panel:\n"
            f"  parquet: {panel_from_parquet}\n  db:      {panel_from_db}"
        )
    if metrics_from_parquet != metrics_from_db:
        raise ResearchGateError(
            "socioverse smoke: metrics.parquet content disagrees with the DuckDB "
            f"metrics:\n  parquet: {metrics_from_parquet}\n  db:      {metrics_from_db}"
        )
    evidence["panel_parquet_rows"] = panel_parquet.height
    evidence["metrics_parquet_rows"] = metrics_parquet.height
    evidence["panel_parquet_matches_db"] = True  # enforced above, else raised
    evidence["metrics_parquet_matches_db"] = True
    return evidence
