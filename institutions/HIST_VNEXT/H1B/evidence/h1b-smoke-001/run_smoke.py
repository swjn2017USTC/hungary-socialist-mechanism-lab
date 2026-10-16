#!/usr/bin/env python3
"""H1B smoke: exercise regime calendar and authority API.

Exits 0 on success; 1 on any assertion failure.
All output is deterministic (no random seed).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

# repo root: smoke/evidence/h1b-smoke-001/ → 0=smoke, 1=evidence, 2=H1B, 3=HIST_VNEXT, 4=institutions, 5=repo
_REPO_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from hsm_lab.institutions.schemas import (
    AuthorityScope,
    DateInterval,
    InstitutionEvent,
    RegimeCalendar,
)
from hsm_lab.institutions.calendar import event_as_of, load_calendar
from hsm_lab.institutions.authority import authority_at

_CAL_PATH = _REPO_ROOT / "institutions" / "HIST_VNEXT" / "h1b_synthetic_calendar.json"

# Results collector (mutable closure)
_results = {"passed": [], "failed": []}


def _check(label: str, got: str, expected: str) -> None:
    if got == expected:
        _results["passed"].append(label)
    else:
        _results["failed"].append(f"{label}: got={got}, expected={expected}")


def run() -> None:
    # Load calendar
    cal = load_calendar(_CAL_PATH)

    # T1: lifecycle separation
    for lbl, dt, exp in [
        ("approval_only", date(1966, 6, 1), "unknown"),
        ("enactment_before_effective", date(1967, 12, 1), "unknown"),
        ("effective_latest", date(1968, 3, 31), "granted"),
    ]:
        r = authority_at(
            cal,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="procurement",
            decision_at=dt,
        )
        _check(f"T1:{lbl}", r.status, exp)

    # T2: scope filtering
    _check(
        "T2:wildcard_org",
        authority_at(
            cal, organization_id="ORG-ENT-A", sector_id="industry",
            geographic_id="national", permission="procurement",
            decision_at=date(1968, 6, 1),
        ).status,
        "granted",
    )
    _check(
        "T2:excluded_sector",
        authority_at(
            cal, organization_id="ORG-ENT-A", sector_id="agriculture",
            geographic_id="national", permission="price_setting",
            decision_at=date(1968, 6, 1),
        ).status,
        "unknown",
    )
    _check(
        "T2:included_sector",
        authority_at(
            cal, organization_id="ORG-ENT-A", sector_id="industry",
            geographic_id="national", permission="price_setting",
            decision_at=date(1968, 6, 1),
        ).status,
        "granted",
    )
    _check(
        "T2:wrong_org",
        authority_at(
            cal, organization_id="ORG-ENT-B", sector_id="industry",
            geographic_id="national", permission="investment_approval",
            decision_at=date(1968, 6, 1),
        ).status,
        "unknown",
    )

    # T3: revoke isolation
    _check(
        "T3:ent_a_still_granted",
        authority_at(
            cal, organization_id="ORG-ENT-A", sector_id="industry",
            geographic_id="national", permission="procurement",
            decision_at=date(1973, 1, 1),
        ).status,
        "granted",
    )
    _check(
        "T3:ent_b_revoked",
        authority_at(
            cal, organization_id="ORG-ENT-B", sector_id="industry",
            geographic_id="national", permission="procurement",
            decision_at=date(1973, 1, 1),
        ).status,
        "revoked",
    )

    # T4: CMEA boundaries
    _check(
        "T4:pre1975_active",
        authority_at(
            cal, organization_id="ORG-ENT-A", sector_id="industry",
            geographic_id="national", permission="cmea_price_rule_pre1975",
            decision_at=date(1974, 12, 31),
        ).status,
        "granted",
    )
    _check(
        "T4:pre1975_inactive",
        authority_at(
            cal, organization_id="ORG-ENT-A", sector_id="industry",
            geographic_id="national", permission="cmea_price_rule_pre1975",
            decision_at=date(1975, 1, 1),
        ).status,
        "unknown",
    )
    _check(
        "T4:post1975_active",
        authority_at(
            cal, organization_id="ORG-ENT-A", sector_id="industry",
            geographic_id="national", permission="cmea_price_rule_post1975",
            decision_at=date(1975, 1, 1),
        ).status,
        "granted",
    )
    _check(
        "T4:pre_inactive_1957",
        authority_at(
            cal, organization_id="ORG-ENT-A", sector_id="industry",
            geographic_id="national", permission="cmea_price_rule_pre1975",
            decision_at=date(1957, 1, 1),
        ).status,
        "unknown",
    )

    # T5: future source raises
    ev_future = InstitutionEvent(
        event_id="EVT-FUTURE-SMOKE",
        permission="test",
        scope=AuthorityScope(),
        action="grant",
        proposal_date=DateInterval(earliest=date(1966, 5, 1), latest=date(1966, 5, 1), precision="day"),
        approval_date=DateInterval(earliest=date(1966, 6, 1), latest=date(1966, 6, 1), precision="day"),
        enactment_date=DateInterval(earliest=date(1967, 12, 1), latest=date(1967, 12, 1), precision="day"),
        effective_from=DateInterval(earliest=date(1968, 1, 1), latest=date(1968, 1, 1), precision="day"),
        source_available_at=DateInterval(earliest=date(1991, 1, 1), latest=date(1991, 1, 1), precision="day"),
        issuer="test",
        legal_force="enactment",
        synthetic_flag=True,
        confidence_reason="",
        search_tags=(),
    )
    cal_fut = RegimeCalendar(events=(ev_future,))
    try:
        event_as_of(cal_fut, event_id="EVT-FUTURE-SMOKE", decision_at=date(1968, 1, 1))
        _results["failed"].append("T5:future_source_should_raise")
    except Exception:
        _results["passed"].append("T5:future_source_correctly_rejected")

    # Write output
    out_path = Path(__file__).parent / "smoke_output.json"
    out_path.write_text(
        json.dumps(
            {"calendar_events": len(cal.events), "results": _results},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    if _results["failed"]:
        print("FAIL:", _results["failed"])
        sys.exit(1)
    print(f"PASS: {len(_results['passed'])} checks")
    sys.exit(0)


if __name__ == "__main__":
    run()
