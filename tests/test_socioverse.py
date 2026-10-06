"""D8: real SocioVerse2 store smoke with the network disabled.

The store is the real DuckDbTrajectoryStore from the pinned socioverse2==0.2.0
wheel; nothing here mocks the upstream package. A monkeypatched socket.connect
proves the smoke needs no network, no API key and no LLM client.
"""

from __future__ import annotations

import socket

import pytest

from hsm_lab.integrations.socioverse import smoke_socioverse
from tests.conftest import REPO_ROOT


@pytest.fixture(autouse=True)
def no_network(monkeypatch) -> None:
    def refused(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("network access attempted during socioverse smoke")

    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket.socket, "connect_ex", refused)


def test_socioverse_store_smoke(tmp_path) -> None:
    evidence = smoke_socioverse(tmp_path / "store")
    assert evidence["panel_rows"] == 4
    assert evidence["panel_primary_keys_unique"] is True
    assert evidence["state_probe_values"] == {"step0": [0, 0], "step1": [1, 1]}
    assert evidence["metrics"] == [[0, 0], [1, 2]]
    assert evidence["events"] == [[1, "p00-synthetic-event"]]
    assert evidence["panel_parquet_matches_db"] is True
    assert evidence["metrics_parquet_matches_db"] is True
    assert (tmp_path / "store" / "study.duckdb").stat().st_size > 0
    assert (tmp_path / "store" / "panel.parquet").stat().st_size > 0


def test_socioverse_refuses_non_fresh_directory(tmp_path) -> None:
    store = tmp_path / "notfresh"
    store.mkdir()
    (store / "sentinel").write_text("x", encoding="utf-8")
    from hsm_lab.contract.schemas import ResearchGateError

    with pytest.raises(ResearchGateError, match="not fresh"):
        smoke_socioverse(store)
    assert (store / "sentinel").read_text(encoding="utf-8") == "x"


def test_pinned_distribution_present() -> None:
    from importlib.metadata import version

    assert version("socioverse2") == "0.2.0"


def test_socioverse_never_imports_into_runtime() -> None:
    """The integration stays lazy: importing the engine must not pull it in."""
    import subprocess
    import sys

    code = (
        "import sys, hsm_lab.engine.smoke; "
        "assert not any(m.startswith('socioverse') for m in sys.modules); print('lazy-ok')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "lazy-ok"
