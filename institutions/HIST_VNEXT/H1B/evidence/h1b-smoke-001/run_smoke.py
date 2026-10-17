#!/usr/bin/env python3
"""H1B smoke: exercise regime calendar and authority API.

Exits 0 on success; 1 on any assertion failure.
All output is deterministic apart from the revision/hash manifest, which is
bound to the working-tree revision that produced the run.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

# repo root: evidence/h1b-smoke-001/ reaches _REPO_ROOT via parents[5]
_REPO_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from hsm_lab.contract.base import ConfigError  # noqa: E402
from hsm_lab.institutions.authority import authority_at  # noqa: E402
from hsm_lab.institutions.calendar import event_as_of, load_calendar  # noqa: E402
from hsm_lab.institutions.schemas import (  # noqa: E402
    AuthorityScope,
    DateInterval,
    InstitutionEvent,
    RegimeCalendar,
)

_CAL_PATH = _REPO_ROOT / "institutions" / "HIST_VNEXT" / "h1b_synthetic_calendar.json"
_HASHED_FILES = (
    "institutions/HIST_VNEXT/h1b_synthetic_calendar.json",
    "src/hsm_lab/institutions/schemas.py",
    "src/hsm_lab/institutions/calendar.py",
    "src/hsm_lab/institutions/authority.py",
    "institutions/HIST_VNEXT/H1B/evidence/h1b-smoke-001/run_smoke.py",
)

_results: dict[str, list] = {"passed": [], "failed": []}
_queries: list[dict] = []
_cal = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNAVAILABLE"


def _check(label: str, got: str, expected: str) -> None:
    if got == expected:
        _results["passed"].append(label)
    else:
        _results["failed"].append(f"{label}: got={got}, expected={expected}")


def _query(
    label: str,
    permission: str,
    decision_at: date,
    expected: str,
    *,
    organization_id: str = "ORG-ENT-A",
    sector_id: str = "industry",
    geographic_id: str = "national",
) -> None:
    result = authority_at(
        _cal,
        organization_id=organization_id,
        sector_id=sector_id,
        geographic_id=geographic_id,
        permission=permission,
        decision_at=decision_at,
    )
    _queries.append(
        {
            "label": label,
            "inputs": {
                "organization_id": organization_id,
                "sector_id": sector_id,
                "geographic_id": geographic_id,
                "permission": permission,
                "decision_at": decision_at.isoformat(),
            },
            "result": {
                "status": result.status,
                "active_event_ids": list(result.active_event_ids),
                "reason": result.reason,
            },
            "expected": expected,
        }
    )
    _check(label, result.status, expected)


def run() -> None:
    global _cal
    _cal = load_calendar(_CAL_PATH)

    # T1: lifecycle separation
    _query("T1:approval_only", "procurement", date(1966, 6, 1), "unknown")
    _query("T1:enactment_before_effective", "procurement", date(1967, 12, 1), "unknown")
    _query("T1:effective_latest", "procurement", date(1968, 3, 31), "granted")

    # T2: scope filtering
    _query("T2:wildcard_org", "procurement", date(1968, 6, 1), "granted")
    _query(
        "T2:excluded_sector",
        "price_setting",
        date(1968, 6, 1),
        "unknown",
        sector_id="agriculture",
    )
    _query("T2:included_sector", "price_setting", date(1968, 6, 1), "granted")
    _query(
        "T2:wrong_org",
        "investment_approval",
        date(1968, 6, 1),
        "unknown",
        organization_id="ORG-ENT-B",
    )

    # T3: revoke isolation
    _query("T3:ent_a_still_granted", "procurement", date(1973, 1, 1), "granted")
    _query(
        "T3:ent_b_revoked",
        "procurement",
        date(1973, 1, 1),
        "revoked",
        organization_id="ORG-ENT-B",
    )

    # T4: CMEA boundaries
    _query("T4:pre1975_active", "cmea_price_rule_pre1975", date(1974, 12, 31), "granted")
    _query("T4:pre1975_inactive", "cmea_price_rule_pre1975", date(1975, 1, 1), "unknown")
    _query("T4:post1975_active", "cmea_price_rule_post1975", date(1975, 1, 1), "granted")
    _query("T4:pre_inactive_1957", "cmea_price_rule_pre1975", date(1957, 1, 1), "unknown")

    # T5: future source raises
    ev_future = InstitutionEvent(
        event_id="EVT-FUTURE-SMOKE",
        permission="test",
        scope=AuthorityScope(),
        action="grant",
        proposal_date=DateInterval(
            earliest=date(1966, 5, 1), latest=date(1966, 5, 1), precision="day"
        ),
        approval_date=DateInterval(
            earliest=date(1966, 6, 1), latest=date(1966, 6, 1), precision="day"
        ),
        enactment_date=DateInterval(
            earliest=date(1967, 12, 1), latest=date(1967, 12, 1), precision="day"
        ),
        effective_from=DateInterval(
            earliest=date(1968, 1, 1), latest=date(1968, 1, 1), precision="day"
        ),
        source_available_at=DateInterval(
            earliest=date(1991, 1, 1), latest=date(1991, 1, 1), precision="day"
        ),
        issuer="test",
        legal_force="enactment",
        synthetic_flag=True,
        confidence_reason="",
        search_tags=(),
    )
    cal_fut = RegimeCalendar(events=(ev_future,))
    t5_trace = {
        "label": "T5",
        "event_id": "EVT-FUTURE-SMOKE",
        "decision_at": "1968-01-01",
        "source_available_at": "1991-01-01",
        "observed": None,
    }
    try:
        event_as_of(
            cal_fut, event_id="EVT-FUTURE-SMOKE", decision_at=date(1968, 1, 1)
        )
    except ConfigError as exc:
        t5_trace["observed"] = f"{type(exc).__name__}: {exc}"
        _results["passed"].append("T5:future_source_correctly_rejected")
    except Exception as exc:  # noqa: BLE001 - any other exception is a failure
        t5_trace["observed"] = f"UNEXPECTED {type(exc).__name__}: {exc}"
        _results["failed"].append(
            f"T5:future_source_unexpected_exception {type(exc).__name__}"
        )
    else:
        t5_trace["observed"] = "NO EXCEPTION"
        _results["failed"].append("T5:future_source_should_raise")
    _queries.append(t5_trace)

    output = {
        "manifest": {
            "smoke_id": "h1b-smoke-001",
            "revision": _revision(),
            "calendar_path": str(_CAL_PATH.relative_to(_REPO_ROOT)),
            "calendar_sha256": _sha256(_CAL_PATH),
            "file_sha256": {
                rel: _sha256(_REPO_ROOT / rel) for rel in _HASHED_FILES
            },
            "check_count": len(_results["passed"]) + len(_results["failed"]),
            "c0_c1_replay": "NOT_RUN",
        },
        "calendar_events": len(_cal.events),
        "queries": _queries,
        "results": _results,
    }
    out_path = Path(__file__).parent / "smoke_output.json"
    out_path.write_text(
        json.dumps(output, indent=2, default=str),
        encoding="utf-8",
    )

    if _results["failed"]:
        print("FAIL:", _results["failed"])
        sys.exit(1)
    print(f"PASS: {len(_results['passed'])} checks")
    sys.exit(0)


if __name__ == "__main__":
    run()
