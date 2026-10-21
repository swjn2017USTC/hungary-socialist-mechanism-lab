"""H4B Pilot A runner: branch, nine arms, first-stage and state invariants."""

from __future__ import annotations

import json
from pathlib import Path

from studies.HIST_VNEXT.pilot_A.runner import run_pilot

REPO_ROOT = Path(__file__).resolve().parents[1]
BRANCH_SHA = "5085d82c8e0d9a226e673598f809f1b0e8d6028b2ae39c6a31ce2a1d2d4a1d9c"


def test_pilot_runs_all_arms_and_preserves_invariants(tmp_path: Path) -> None:
    result = run_pilot(REPO_ROOT, output_dir=tmp_path / "pilot")
    assert result["status"] == "COMPLETED"
    assert result["arms_executed"] == result["arms_declared"]
    assert result["branch"]["branch_quarter"] == "1968Q1"
    assert result["branch"]["branch_completed_ticks"] == 44
    assert result["branch"]["branch_state_sha256"] == BRANCH_SHA
    assert result["historical_status"] == "NOT_ESTABLISHED"
    assert result["price_regime"]["path"] == "config/price_regimes/hist_vnext_h4b_v1.json"

    arms = result["arms"]
    assert set(arms) == set(result["arms_declared"])
    for arm, record in arms.items():
        assert [trace["quarter"] for trace in record["trace"]] == [
            "1968Q1",
            "1968Q2",
            "1968Q3",
            "1968Q4",
        ], arm

    negative = arms["negative_control"]
    assert negative["decision_commits"] == 0
    assert all(value == 0.0 for value in negative["delta_vs_negative_control"].values())

    rejected = [
        "procurement_revoked",
        "procurement_unknown",
        "price_fixed",
        "investment_ungranted",
    ]
    for arm in rejected:
        record = arms[arm]
        assert record["decision_commits"] == 0
        assert record["final_state_sha256"] == negative["final_state_sha256"]
        assert all(value == 0.0 for value in record["delta_vs_negative_control"].values())

    procurement = arms["procurement_granted"]
    assert procurement["decision_commits"] == 4
    assert procurement["delta_vs_negative_control"]["delivered"] > 0.0
    assert procurement["delta_vs_negative_control"]["household_realized"] == 0.0
    assert procurement["delta_vs_negative_control"]["household_availability_unmet"] == 0.0

    price = arms["price_authorized"]
    assert price["decision_commits"] == 4
    assert price["trace"][0]["new_price"] > price["trace"][0]["old_price"]
    assert price["delta_vs_negative_control"]["delivered"] != 0.0

    investment = arms["investment_delegated"]
    assert investment["decision_commits"] == 4
    assert investment["trace"][0]["investment_approved"] <= (
        investment["trace"][0]["approved_capacity"] + 1e-9
    )
    assert investment["trace"][0]["baseline_investment_requested"] > (
        investment["trace"][0]["approved_capacity"] + 1e-9
    )

    combined = arms["combined"]
    assert combined["decision_commits"] == 4
    for trace in combined["trace"]:
        for key in (
            "old_price",
            "new_price",
            "procurement_delivered",
            "approved_capacity",
            "investment_requested",
            "investment_approved",
            "investment_cap_binding",
        ):
            assert key in trace
    assert combined["delta_vs_negative_control"]["delivered"] > 0.0
    assert combined["trace"][0]["investment_cap_binding"] is True

    metrics = json.loads((tmp_path / "pilot" / "arm_metrics.json").read_text())
    assert set(metrics) == set(result["arms_declared"])
    assert (tmp_path / "pilot" / "pilot_manifest.json").is_file()
