"""H1B verification tests: regime calendar and authority queries.

Run from repo root:
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from hsm_lab.contract.base import ConfigError
from hsm_lab.institutions.authority import authority_at
from hsm_lab.institutions.calendar import event_as_of, load_calendar
from hsm_lab.institutions.schemas import (
    AuthorityScope,
    DateInterval,
    InstitutionEvent,
    RegimeCalendar,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _di(earliest: date, latest: date, precision: str) -> DateInterval:
    """Keyword-argument wrapper for DateInterval (Pydantic v2 positional compat)."""
    return DateInterval(earliest=earliest, latest=latest, precision=precision)  # noqa: N816


# ---------------------------------------------------------------------------
# Shared calendar fixture (deterministic — no random seed needed)
# ---------------------------------------------------------------------------

_CALENDAR_PATH = (
    Path(__file__).parent.parent
    / "institutions"
    / "HIST_VNEXT"
    / "h1b_synthetic_calendar.json"
)


@pytest.fixture
def calendar(tmp_path) -> RegimeCalendar:
    if _CALENDAR_PATH.exists():
        return load_calendar(_CALENDAR_PATH)
    # Fallback: build in-memory calendar for isolated testing
    return _build_synthetic_calendar()


def _build_synthetic_calendar() -> RegimeCalendar:
    """Build the standard synthetic calendar used in all tests."""
    def _di(earliest: date, latest: date, precision: str) -> DateInterval:
        return DateInterval(earliest=earliest, latest=latest, precision=precision)  # noqa: N816

    ev1 = InstitutionEvent(
        event_id="EVT-1966-NEM-GRANT-PROCUREMENT",
        permission="procurement",
        scope=AuthorityScope(),
        action="grant",
        proposal_date=_di(date(1966, 5, 1), date(1966, 5, 1), "day"),
        approval_date=_di(date(1966, 6, 1), date(1966, 6, 1), "day"),
        enactment_date=_di(date(1967, 12, 1), date(1967, 12, 1), "day"),
        effective_from=_di(date(1968, 1, 1), date(1968, 3, 31), "quarter"),
        effective_to=None,
        observed_implementation_at=_di(date(1968, 3, 15), date(1968, 3, 15), "day"),
        source_available_at=_di(date(1957, 1, 1), date(1957, 1, 1), "day"),
        issuer="Hungarian Socialist Workers Party",
        legal_force="enactment",
        source_ids=("synthetic_h1b_design_note",),
        synthetic_flag=True,
        confidence_reason="Synthetic fixture",
        search_tags=("NEM", "1968", "procurement"),
    )
    ev2 = InstitutionEvent(
        event_id="EVT-1968-NEM-GRANT-INVESTMENT",
        permission="investment_approval",
        scope=AuthorityScope(
            organization_ids=("ORG-ENT-A",),
            sector_ids=("industry",),
            excluded_sector_ids=(),
            geographic_ids=(),
        ),
        action="grant",
        proposal_date=_di(date(1966, 5, 1), date(1966, 5, 1), "day"),
        approval_date=_di(date(1966, 6, 1), date(1966, 6, 1), "day"),
        enactment_date=_di(date(1967, 12, 1), date(1967, 12, 1), "day"),
        effective_from=_di(date(1968, 1, 1), date(1968, 1, 1), "day"),
        effective_to=None,
        observed_implementation_at=None,
        source_available_at=_di(date(1957, 1, 1), date(1957, 1, 1), "day"),
        issuer="Hungarian Socialist Workers Party",
        legal_force="enactment",
        source_ids=("synthetic_h1b_design_note",),
        synthetic_flag=True,
        confidence_reason="Synthetic fixture",
        search_tags=("NEM", "1968", "investment"),
    )
    ev3 = InstitutionEvent(
        event_id="EVT-1968-NEM-GRANT-PRICE-SETTING",
        permission="price_setting",
        scope=AuthorityScope(
            organization_ids=(),
            sector_ids=("industry", "agriculture"),
            excluded_sector_ids=("agriculture",),
            geographic_ids=(),
        ),
        action="grant",
        proposal_date=_di(date(1966, 5, 1), date(1966, 5, 1), "day"),
        approval_date=_di(date(1966, 6, 1), date(1966, 6, 1), "day"),
        enactment_date=_di(date(1967, 12, 1), date(1967, 12, 1), "day"),
        effective_from=_di(date(1968, 1, 1), date(1968, 1, 1), "day"),
        effective_to=None,
        observed_implementation_at=None,
        source_available_at=_di(date(1957, 1, 1), date(1957, 1, 1), "day"),
        issuer="Hungarian Socialist Workers Party",
        legal_force="enactment",
        source_ids=("synthetic_h1b_design_note",),
        synthetic_flag=True,
        confidence_reason="Synthetic fixture",
        search_tags=("NEM", "1968", "price"),
    )
    ev4 = InstitutionEvent(
        event_id="EVT-1968-NEM-REVOKE-PROCUREMENT-ENT-B",
        permission="procurement",
        scope=AuthorityScope(
            organization_ids=("ORG-ENT-B",),
            sector_ids=(),
            excluded_sector_ids=(),
            geographic_ids=(),
        ),
        action="revoke",
        revokes_event_id="EVT-1966-NEM-GRANT-PROCUREMENT",
        proposal_date=_di(date(1972, 11, 1), date(1972, 11, 1), "day"),
        approval_date=_di(date(1972, 11, 1), date(1972, 11, 1), "day"),
        enactment_date=_di(date(1972, 11, 15), date(1972, 11, 15), "day"),
        effective_from=_di(date(1972, 11, 15), date(1972, 11, 15), "day"),
        effective_to=None,
        observed_implementation_at=None,
        source_available_at=_di(date(1957, 1, 1), date(1957, 1, 1), "day"),
        issuer="Hungarian Socialist Workers Party",
        legal_force="enactment",
        source_ids=("synthetic_h1b_design_note",),
        synthetic_flag=True,
        confidence_reason="Synthetic fixture",
        search_tags=("NEM", "revoke"),
    )
    ev5 = InstitutionEvent(
        event_id="EVT-CMEA-PRE1975",
        permission="cmea_price_rule_pre1975",
        scope=AuthorityScope(),
        action="grant",
        proposal_date=_di(date(1969, 1, 1), date(1969, 1, 1), "day"),
        approval_date=_di(date(1970, 1, 1), date(1970, 1, 1), "day"),
        enactment_date=_di(date(1970, 1, 1), date(1970, 1, 1), "day"),
        effective_from=_di(date(1971, 1, 1), date(1971, 1, 1), "day"),
        effective_to=_di(date(1975, 1, 1), date(1974, 12, 31), "range"),
        observed_implementation_at=None,
        source_available_at=_di(date(1957, 1, 1), date(1957, 1, 1), "day"),
        issuer="CMEA",
        legal_force="enactment",
        source_ids=("synthetic_h1b_design_note",),
        synthetic_flag=True,
        confidence_reason="Synthetic CMEA pre-1975 fixture",
        search_tags=("CMEA", "pre_1975"),
    )
    ev6 = InstitutionEvent(
        event_id="EVT-CMEA-POST1975",
        permission="cmea_price_rule_post1975",
        scope=AuthorityScope(),
        action="grant",
        proposal_date=_di(date(1975, 1, 1), date(1975, 1, 1), "day"),
        approval_date=_di(date(1975, 1, 1), date(1975, 1, 1), "day"),
        enactment_date=_di(date(1975, 1, 1), date(1975, 1, 1), "day"),
        effective_from=_di(date(1975, 1, 1), date(1975, 1, 1), "day"),
        effective_to=_di(date(1980, 1, 1), date(1980, 1, 1), "day"),
        observed_implementation_at=None,
        source_available_at=_di(date(1957, 1, 1), date(1957, 1, 1), "day"),
        issuer="CMEA",
        legal_force="enactment",
        source_ids=("synthetic_h1b_design_note",),
        synthetic_flag=True,
        confidence_reason="Synthetic CMEA post-1975 fixture",
        search_tags=("CMEA", "post_1975"),
    )
    return RegimeCalendar(events=(ev1, ev2, ev3, ev4, ev5, ev6))


# ---------------------------------------------------------------------------
# Test 1 — proposal_date, approval_date, enactment_date separation
# ---------------------------------------------------------------------------

class TestLifecycleSeparation:
    def test_approval_date_not_enough(self, calendar):
        """Only enactment grants legal authority; proposal/approval alone are insufficient."""
        result = authority_at(
            calendar,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="procurement",
            decision_at=date(1966, 6, 1),  # approval date
        )
        assert result.status == "unknown"

    def test_enactment_before_effective_from(self, calendar):
        """Enactment before effective_from window opens returns unknown."""
        result = authority_at(
            calendar,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="procurement",
            decision_at=date(1967, 12, 1),  # enactment date, before effective
        )
        assert result.status == "unknown"

    def test_effective_from_granted(self, calendar):
        """At effective_from latest (1968-03-31) procurement is granted."""
        result = authority_at(
            calendar,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="procurement",
            decision_at=date(1968, 3, 31),
        )
        assert result.status == "granted"
        assert "EVT-1966-NEM-GRANT-PROCUREMENT" in result.active_event_ids

    def test_observed_implementation_still_granted(self, calendar):
        """Implementation observation does not retroactively affect legal status.

        effective_from quarter [1968-01-01, 1968-03-31]: decision_at=1968-03-31 equals
        effective_from.latest → conservative rule says definitely started → granted.
        The observation date (1968-03-15) does not retroactively grant earlier dates.
        """
        result = authority_at(
            calendar,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="procurement",
            decision_at=date(1968, 3, 31),  # effective_from.latest
        )
        assert result.status == "granted"


# ---------------------------------------------------------------------------
# Test 2 — DateInterval precision and bounds
# ---------------------------------------------------------------------------

class TestDateInterval:
    def test_unknown_interval_is_none(self):
        iv = DateInterval(earliest=None, latest=None, precision="unknown")
        assert iv.is_active_on(date(1968, 1, 15)) is None

    def test_day_precision_equal_bounds(self):
        iv = DateInterval(earliest=date(1968, 1, 1), latest=date(1968, 1, 1), precision="day")
        assert iv.is_active_on(date(1968, 1, 1)) is True
        assert iv.is_active_on(date(1968, 1, 2)) is False

    def test_reverse_bounds_rejected(self):
        with pytest.raises((ConfigError, Exception)):
            DateInterval(earliest=date(1968, 3, 31), latest=date(1968, 1, 1), precision="day")

    def test_day_precision_mismatched_bounds_rejected(self):
        with pytest.raises((ConfigError, Exception)):
            DateInterval(earliest=date(1968, 1, 1), latest=date(1968, 1, 15), precision="day")

    def test_precision_without_bounds_rejected(self):
        with pytest.raises((ConfigError, Exception)):
            DateInterval(earliest=None, latest=date(1968, 1, 1), precision="day")

    def test_quarter_active_in_window(self):
        iv = DateInterval(earliest=date(1968, 1, 1), latest=date(1968, 3, 31), precision="quarter")
        assert iv.is_active_on(date(1968, 1, 15)) is None  # uncertain within quarter
        assert iv.is_active_on(date(1968, 3, 31)) is True
        assert iv.is_active_on(date(1967, 12, 31)) is False
        assert iv.is_active_on(date(1968, 4, 1)) is False

    def test_unknown_effective_from_never_granted(self, calendar):
        """Events with unknown effective_from cannot return granted."""
        # This synthetic calendar has no unknown effective_from grants;
        # test at the structural level with a constructed event
        ev = InstitutionEvent(
            event_id="EVT-TEST-UNKNOWN",
            permission="test",
            scope=AuthorityScope(),
            action="grant",
            proposal_date=_di(date(1966, 5, 1), date(1966, 5, 1), "day"),
            approval_date=_di(date(1966, 6, 1), date(1966, 6, 1), "day"),
            enactment_date=_di(date(1967, 12, 1), date(1967, 12, 1), "day"),
            effective_from=DateInterval(earliest=None, latest=None, precision="unknown"),
            source_available_at=_di(date(1957, 1, 1), date(1957, 1, 1), "day"),
            issuer="test",
            legal_force="enactment",
            synthetic_flag=True,
            confidence_reason="",
            search_tags=(),
        )
        cal = RegimeCalendar(events=(ev,))
        result = authority_at(
            cal,
            organization_id="ORG-ANY",
            sector_id="any",
            geographic_id="national",
            permission="test",
            decision_at=date(1970, 1, 1),
        )
        assert result.status == "unknown"


# ---------------------------------------------------------------------------
# Test 3 — Scope: org, sector, geography filtering
# ---------------------------------------------------------------------------

class TestScopeFiltering:
    def test_wildcard_org_passes(self, calendar):
        result = authority_at(
            calendar,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="procurement",
            decision_at=date(1968, 6, 1),
        )
        assert result.status == "granted"

    def test_specific_org_passes(self, calendar):
        result = authority_at(
            calendar,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="investment_approval",
            decision_at=date(1968, 6, 1),
        )
        assert result.status == "granted"

    def test_wrong_org_unknown(self, calendar):
        result = authority_at(
            calendar,
            organization_id="ORG-ENT-B",
            sector_id="industry",
            geographic_id="national",
            permission="investment_approval",
            decision_at=date(1968, 6, 1),
        )
        assert result.status == "unknown"

    def test_excluded_sector_rejected(self, calendar):
        result = authority_at(
            calendar,
            organization_id="ORG-ENT-A",
            sector_id="agriculture",
            geographic_id="national",
            permission="price_setting",
            decision_at=date(1968, 6, 1),
        )
        assert result.status == "unknown"

    def test_included_sector_passes(self, calendar):
        result = authority_at(
            calendar,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="price_setting",
            decision_at=date(1968, 6, 1),
        )
        assert result.status == "granted"


# ---------------------------------------------------------------------------
# Test 4 — Revoke isolation and independent grants
# ---------------------------------------------------------------------------

class TestRevokeIsolation:
    def test_revoke_proc_only_affects_proc(self, calendar):
        """Revoking procurement does not affect investment_approval."""
        # ORG-ENT-B: procurement revoked at 1972-11-15, investment unknown
        result_proc = authority_at(
            calendar,
            organization_id="ORG-ENT-B",
            sector_id="industry",
            geographic_id="national",
            permission="procurement",
            decision_at=date(1973, 1, 1),
        )
        assert result_proc.status == "revoked"

        result_inv = authority_at(
            calendar,
            organization_id="ORG-ENT-B",
            sector_id="industry",
            geographic_id="national",
            permission="investment_approval",
            decision_at=date(1973, 1, 1),
        )
        # ORG-ENT-B has no investment_approval grant → unknown
        assert result_inv.status == "unknown"

    def test_revoke_specific_org_only(self, calendar):
        """Revoking procurement for ORG-ENT-B does not affect ORG-ENT-A."""
        result_a = authority_at(
            calendar,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="procurement",
            decision_at=date(1973, 1, 1),
        )
        assert result_a.status == "granted"

        result_b = authority_at(
            calendar,
            organization_id="ORG-ENT-B",
            sector_id="industry",
            geographic_id="national",
            permission="procurement",
            decision_at=date(1973, 1, 1),
        )
        assert result_b.status == "revoked"

    def test_revoke_nonexistent_target_rejected(self):
        ev = InstitutionEvent(
            event_id="EVT-BAD-REVOKE",
            permission="procurement",
            scope=AuthorityScope(),
            action="revoke",
            revokes_event_id="NONEXISTENT",
            proposal_date=_di(date(1972, 11, 1), date(1972, 11, 1), "day"),
            approval_date=_di(date(1972, 11, 1), date(1972, 11, 1), "day"),
            enactment_date=_di(date(1972, 11, 15), date(1972, 11, 15), "day"),
            effective_from=_di(date(1972, 11, 15), date(1972, 11, 15), "day"),
            source_available_at=_di(date(1957, 1, 1), date(1957, 1, 1), "day"),
            issuer="test",
            legal_force="enactment",
            synthetic_flag=True,
            confidence_reason="",
            search_tags=(),
        )
        # The revoke targets a nonexistent grant — the authority query should
        # return unknown (the target grant doesn't exist)
        cal = RegimeCalendar(events=(ev,))
        result = authority_at(
            cal,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="procurement",
            decision_at=date(1973, 1, 1),
        )
        assert result.status == "unknown"


# ---------------------------------------------------------------------------
# Test 5 — Future source availability
# ---------------------------------------------------------------------------

class TestSourceAvailability:
    def test_future_source_not_visible_at_past_date(self, calendar):
        """Querying before source_available_at latest must raise ConfigError.

        Uses a separate calendar with one event whose source_available_at=1991-01-01.
        """
        ev_future = InstitutionEvent(
            event_id="EVT-FUTURE-SOURCE",
            permission="test",
            scope=AuthorityScope(),
            action="grant",
            proposal_date=_di(date(1970, 1, 1), date(1970, 1, 1), "day"),
            approval_date=_di(date(1970, 1, 1), date(1970, 1, 1), "day"),
            enactment_date=_di(date(1970, 1, 1), date(1970, 1, 1), "day"),
            effective_from=_di(date(1970, 1, 1), date(1970, 1, 1), "day"),
            source_available_at=DateInterval(
                earliest=date(1991, 1, 1), latest=date(1991, 1, 1), precision="day"
            ),
            issuer="test",
            legal_force="enactment",
            synthetic_flag=True,
            confidence_reason="",
            search_tags=(),
        )
        cal_future = RegimeCalendar(events=(ev_future,))
        with pytest.raises(ConfigError, match="before source available"):
            event_as_of(cal_future, event_id="EVT-FUTURE-SOURCE", decision_at=date(1968, 1, 1))

    def test_future_source_not_in_authority_result(self, calendar):
        """A source available after the decision date cannot influence the result.

        This test uses a constructed calendar with one event whose source_available_at
        is in the future relative to the decision date. The authority query must
        return unknown (no visible grant) rather than granted.
        """
        ev_future = InstitutionEvent(
            event_id="EVT-FUTURE-PROC",
            permission="procurement",
            scope=AuthorityScope(),
            action="grant",
            proposal_date=_di(date(1966, 5, 1), date(1966, 5, 1), "day"),
            approval_date=_di(date(1966, 6, 1), date(1966, 6, 1), "day"),
            enactment_date=_di(date(1967, 12, 1), date(1967, 12, 1), "day"),
            effective_from=_di(date(1968, 1, 1), date(1968, 1, 1), "day"),
            source_available_at=DateInterval(
                earliest=date(1991, 1, 1), latest=date(1991, 1, 1), precision="day"
            ),
            issuer="test",
            legal_force="enactment",
            synthetic_flag=True,
            confidence_reason="",
            search_tags=(),
        )
        cal_future = RegimeCalendar(events=(ev_future,))
        result = authority_at(
            cal_future,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="procurement",
            decision_at=date(1968, 6, 1),
        )
        # Source available 1991 → not yet visible in 1968 → unknown
        assert result.status == "unknown"

    def test_unknown_source_available_rejected(self):
        """Event with unknown source_available_at cannot be loaded for any date."""
        ev = InstitutionEvent(
            event_id="EVT-UNK-SOURCE",
            permission="test",
            scope=AuthorityScope(),
            action="grant",
            proposal_date=_di(date(1966, 5, 1), date(1966, 5, 1), "day"),
            approval_date=_di(date(1966, 6, 1), date(1966, 6, 1), "day"),
            enactment_date=_di(date(1967, 12, 1), date(1967, 12, 1), "day"),
            effective_from=_di(date(1968, 1, 1), date(1968, 1, 1), "day"),
            source_available_at=DateInterval(earliest=None, latest=None, precision="unknown"),
            issuer="test",
            legal_force="enactment",
            synthetic_flag=True,
            confidence_reason="",
            search_tags=(),
        )
        cal = RegimeCalendar(events=(ev,))
        with pytest.raises(ConfigError, match="source_available_at"):
            event_as_of(cal, event_id="EVT-UNK-SOURCE", decision_at=date(2000, 1, 1))


# ---------------------------------------------------------------------------
# Test 6 — CMEA pre/post 1975 boundaries
# ---------------------------------------------------------------------------

class TestCMEABoundaries:
    def test_pre_1975_only_pre_active(self, calendar):
        result = authority_at(
            calendar,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="cmea_price_rule_pre1975",
            decision_at=date(1974, 12, 31),
        )
        assert result.status == "granted"

    def test_post_1975_only_post_active(self, calendar):
        result = authority_at(
            calendar,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="cmea_price_rule_post1975",
            decision_at=date(1975, 1, 1),
        )
        assert result.status == "granted"

    def test_pre_1975_inactive_at_1975(self, calendar):
        result = authority_at(
            calendar,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="cmea_price_rule_pre1975",
            decision_at=date(1975, 1, 1),
        )
        assert result.status == "unknown"

    def test_neither_active_in_1957(self, calendar):
        result_pre = authority_at(
            calendar,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="cmea_price_rule_pre1975",
            decision_at=date(1957, 1, 1),
        )
        result_post = authority_at(
            calendar,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="cmea_price_rule_post1975",
            decision_at=date(1957, 1, 1),
        )
        assert result_pre.status == "unknown"
        assert result_post.status == "unknown"


# ---------------------------------------------------------------------------
# Test 7 — JSON loading and structural validation
# ---------------------------------------------------------------------------

class TestJSONLoading:
    def test_load_valid_json(self, tmp_path):
        data = {
            "events": [
                {
                    "event_id": "EVT-SIMPLE",
                    "permission": "test",
                    "scope": {
                        "organization_ids": [],
                        "sector_ids": [],
                        "excluded_sector_ids": [],
                        "geographic_ids": [],
                    },
                    "action": "grant",
                    "proposal_date": {
                        "earliest": "1966-05-01",
                        "latest": "1966-05-01",
                        "precision": "day",
                    },
                    "approval_date": {
                        "earliest": "1966-06-01",
                        "latest": "1966-06-01",
                        "precision": "day",
                    },
                    "enactment_date": {
                        "earliest": "1967-12-01",
                        "latest": "1967-12-01",
                        "precision": "day",
                    },
                    "effective_from": {
                        "earliest": "1968-01-01",
                        "latest": "1968-01-01",
                        "precision": "day",
                    },
                    "source_available_at": {
                        "earliest": "1991-01-01",
                        "latest": "1991-01-01",
                        "precision": "day",
                    },
                    "issuer": "test",
                    "legal_force": "enactment",
                    "synthetic_flag": True,
                    "confidence_reason": "",
                    "search_tags": [],
                    "source_ids": [],
                    "implementation_evidence_ids": [],
                }
            ]
        }
        path = tmp_path / "calendar.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        cal = load_calendar(path)
        assert len(cal.events) == 1
        assert cal.events[0].event_id == "EVT-SIMPLE"

    def test_load_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(ConfigError, match="cannot read"):
            load_calendar(tmp_path / "does_not_exist.json")

    def test_load_invalid_json_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{ invalid json }", encoding="utf-8")
        with pytest.raises(ConfigError, match="invalid JSON"):
            load_calendar(path)

    def test_load_empty_events_array(self, tmp_path):
        """A legal empty events array loads and queries as unknown (no default rule).

        H1B plan §2: empty calendars are legal, must not synthesize an
        all-period default policy, and every query against them is unknown.
        """
        path = tmp_path / "empty.json"
        path.write_text('{"events": []}', encoding="utf-8")
        cal = load_calendar(path)
        assert cal.events == ()
        result = authority_at(
            cal,
            organization_id="ORG-ENT-A",
            sector_id="industry",
            geographic_id="national",
            permission="procurement",
            decision_at=date(1970, 1, 1),
        )
        assert result.status == "unknown"

    def test_unknown_field_rejected(self, tmp_path):
        data = {
            "events": [
                {
                    "event_id": "EVT-BAD",
                    "permission": "test",
                    "scope": {
                        "organization_ids": [],
                        "sector_ids": [],
                        "excluded_sector_ids": [],
                        "geographic_ids": [],
                    },
                    "action": "grant",
                    "proposal_date": {
                        "earliest": "1966-05-01",
                        "latest": "1966-05-01",
                        "precision": "day",
                    },
                    "approval_date": {
                        "earliest": "1966-06-01",
                        "latest": "1966-06-01",
                        "precision": "day",
                    },
                    "enactment_date": {
                        "earliest": "1967-12-01",
                        "latest": "1967-12-01",
                        "precision": "day",
                    },
                    "effective_from": {
                        "earliest": "1968-01-01",
                        "latest": "1968-01-01",
                        "precision": "day",
                    },
                    "source_available_at": {
                        "earliest": "1991-01-01",
                        "latest": "1991-01-01",
                        "precision": "day",
                    },
                    "issuer": "test",
                    "legal_force": "enactment",
                    "synthetic_flag": True,
                    "confidence_reason": "",
                    "search_tags": [],
                    "source_ids": [],
                    "implementation_evidence_ids": [],
                    "stock": 100,  # unknown field
                }
            ]
        }
        path = tmp_path / "bad_field.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ConfigError, match="validation failed|Extra inputs are not permitted"):
            load_calendar(path)

    def test_duplicate_event_id_rejected(self, tmp_path):
        ev = {
            "event_id": "EVT-DUP",
            "permission": "test",
            "scope": {
                "organization_ids": [],
                "sector_ids": [],
                "excluded_sector_ids": [],
                "geographic_ids": [],
            },
            "action": "grant",
            "proposal_date": {
                "earliest": "1966-05-01",
                "latest": "1966-05-01",
                "precision": "day",
            },
            "approval_date": {
                "earliest": "1966-06-01",
                "latest": "1966-06-01",
                "precision": "day",
            },
            "enactment_date": {
                "earliest": "1967-12-01",
                "latest": "1967-12-01",
                "precision": "day",
            },
            "effective_from": {
                "earliest": "1968-01-01",
                "latest": "1968-01-01",
                "precision": "day",
            },
            "source_available_at": {
                "earliest": "1991-01-01",
                "latest": "1991-01-01",
                "precision": "day",
            },
            "issuer": "test",
            "legal_force": "enactment",
            "synthetic_flag": True,
            "confidence_reason": "",
            "search_tags": [],
            "source_ids": [],
            "implementation_evidence_ids": [],
        }
        path = tmp_path / "dup.json"
        path.write_text(json.dumps({"events": [ev, ev]}), encoding="utf-8")
        with pytest.raises(ConfigError, match="Duplicate event_id"):
            load_calendar(path)

    def test_nonsynthetic_event_rejected(self, tmp_path):
        ev = {
            "event_id": "EVT-REAL",
            "permission": "test",
            "scope": {
                "organization_ids": [],
                "sector_ids": [],
                "excluded_sector_ids": [],
                "geographic_ids": [],
            },
            "action": "grant",
            "proposal_date": {
                "earliest": "1966-05-01",
                "latest": "1966-05-01",
                "precision": "day",
            },
            "approval_date": {
                "earliest": "1966-06-01",
                "latest": "1966-06-01",
                "precision": "day",
            },
            "enactment_date": {
                "earliest": "1967-12-01",
                "latest": "1967-12-01",
                "precision": "day",
            },
            "effective_from": {
                "earliest": "1968-01-01",
                "latest": "1968-01-01",
                "precision": "day",
            },
            "source_available_at": {
                "earliest": "1991-01-01",
                "latest": "1991-01-01",
                "precision": "day",
            },
            "issuer": "test",
            "legal_force": "enactment",
            "synthetic_flag": False,
            "confidence_reason": "",
            "search_tags": [],
            "source_ids": [],
            "implementation_evidence_ids": [],
        }
        path = tmp_path / "nonsynthetic.json"
        path.write_text(json.dumps({"events": [ev]}), encoding="utf-8")
        with pytest.raises(ConfigError, match="synthetic_flag=False"):
            load_calendar(path)


# ---------------------------------------------------------------------------
# Test 9 — review regressions
#   Bug 1: effective_to uses half-open [from, to) → decision_at >= to.latest expires
#   Bug 2: an empty (legal) calendar loads and queries as unknown
#   Bug 3: a wildcard grant must still accept contained sector revokes
# ---------------------------------------------------------------------------

def _regression_event(**overrides) -> InstitutionEvent:
    """Build a minimal valid synthetic event for the regression fixtures."""
    base = {
        "event_id": "EVT-REG-GRANT",
        "permission": "procurement",
        "scope": AuthorityScope(
            organization_ids=("ORG-A",),
            sector_ids=("industry",),
            excluded_sector_ids=(),
            geographic_ids=(),
        ),
        "action": "grant",
        "proposal_date": _di(date(1969, 1, 1), date(1969, 1, 1), "day"),
        "approval_date": _di(date(1969, 1, 1), date(1969, 1, 1), "day"),
        "enactment_date": _di(date(1969, 12, 31), date(1969, 12, 31), "day"),
        "effective_from": _di(date(1970, 1, 1), date(1970, 1, 1), "day"),
        "effective_to": None,
        "observed_implementation_at": None,
        "source_available_at": _di(date(1957, 1, 1), date(1957, 1, 1), "day"),
        "issuer": "synthetic regression fixture",
        "legal_force": "enactment",
        "source_ids": ("synthetic_h1b_design_note",),
        "synthetic_flag": True,
        "confidence_reason": "regression fixture",
        "search_tags": (),
    }
    base.update(overrides)
    return InstitutionEvent(**base)


class TestEffectiveToBoundaryRegression:
    """Bug 1: a revoke whose effective_to ends on the decision date is expired."""

    @staticmethod
    def _calendar(effective_to: DateInterval) -> RegimeCalendar:
        grant = _regression_event(event_id="EVT-REG-GRANT")
        revoke = _regression_event(
            event_id="EVT-REG-REVOKE",
            action="revoke",
            revokes_event_id="EVT-REG-GRANT",
            proposal_date=_di(date(1969, 12, 1), date(1969, 12, 1), "day"),
            approval_date=_di(date(1969, 12, 1), date(1969, 12, 1), "day"),
            enactment_date=_di(date(1969, 12, 31), date(1969, 12, 31), "day"),
            effective_from=_di(date(1969, 12, 31), date(1969, 12, 31), "day"),
            effective_to=effective_to,
        )
        return RegimeCalendar(events=(grant, revoke))

    @staticmethod
    def _status(calendar: RegimeCalendar, decision_at: date) -> str:
        return authority_at(
            calendar,
            organization_id="ORG-A",
            sector_id="industry",
            geographic_id="national",
            permission="procurement",
            decision_at=decision_at,
        ).status

    def test_revoke_range_end_on_decision_date_is_expired(self):
        """decision_at == effective_to.latest (range) → revoke definitely expired."""
        cal = self._calendar(_di(date(1970, 1, 1), date(1970, 3, 31), "range"))
        # Inside the end range → possibly expired → unknown
        assert self._status(cal, date(1970, 3, 30)) == "unknown"
        # On effective_to.latest → definitely expired → grant survives
        assert self._status(cal, date(1970, 3, 31)) == "granted"

    def test_revoke_month_end_on_decision_date_is_expired(self):
        """decision_at == effective_to.latest (month period) → revoke expired."""
        cal = self._calendar(_di(date(1970, 3, 1), date(1970, 3, 31), "month"))
        # Before the end period → revoke definitely not expired
        assert self._status(cal, date(1970, 2, 28)) == "revoked"
        # Inside the end period → possibly expired → unknown
        assert self._status(cal, date(1970, 3, 30)) == "unknown"
        # On the last day of the end period → definitely expired → granted
        assert self._status(cal, date(1970, 3, 31)) == "granted"


class TestEmptyCalendarRegression:
    """Bug 2: an empty calendar is legal and never yields a default policy."""

    def test_empty_calendar_loads_and_returns_unknown(self):
        cal = RegimeCalendar(events=())  # must not raise
        assert cal.events == ()
        result = authority_at(
            cal,
            organization_id="ORG-A",
            sector_id="industry",
            geographic_id="national",
            permission="procurement",
            decision_at=date(1970, 1, 1),
        )
        assert result.status == "unknown"
        assert result.active_event_ids == ()


class TestWildcardGrantRevokeScopeRegression:
    """Bug 3: a wildcard-sector grant accepts revokes contained in its coverage."""

    def test_wildcard_minus_exclusions_accepts_contained_revoke(self):
        grant = _regression_event(
            event_id="EVT-WILD-GRANT",
            permission="price_setting",
            scope=AuthorityScope(
                organization_ids=(),
                sector_ids=(),
                excluded_sector_ids=("agri",),
                geographic_ids=(),
            ),
        )
        revoke = _regression_event(
            event_id="EVT-WILD-REVOKE-INDUSTRY",
            permission="price_setting",
            scope=AuthorityScope(
                organization_ids=(),
                sector_ids=("industry",),
                excluded_sector_ids=(),
                geographic_ids=(),
            ),
            action="revoke",
            revokes_event_id="EVT-WILD-GRANT",
        )
        cal = RegimeCalendar(events=(grant, revoke))  # must not raise
        assert {ev.event_id for ev in cal.events} == {
            "EVT-WILD-GRANT",
            "EVT-WILD-REVOKE-INDUSTRY",
        }

    def test_unrestricted_wildcard_accepts_contained_revoke(self):
        grant = _regression_event(
            event_id="EVT-PURE-WILD-GRANT",
            permission="price_setting",
            scope=AuthorityScope(),
        )
        revoke = _regression_event(
            event_id="EVT-PURE-WILD-REVOKE-INDUSTRY",
            permission="price_setting",
            scope=AuthorityScope(sector_ids=("industry",)),
            action="revoke",
            revokes_event_id="EVT-PURE-WILD-GRANT",
        )
        cal = RegimeCalendar(events=(grant, revoke))  # must not raise
        assert len(cal.events) == 2

    def test_wildcard_grant_excluded_sector_revoke_still_rejected(self):
        grant = _regression_event(
            event_id="EVT-WILD-GRANT-2",
            permission="price_setting",
            scope=AuthorityScope(sector_ids=(), excluded_sector_ids=("agri",)),
        )
        revoke = _regression_event(
            event_id="EVT-WILD-REVOKE-AGRI",
            permission="price_setting",
            scope=AuthorityScope(sector_ids=("agri",)),
            action="revoke",
            revokes_event_id="EVT-WILD-GRANT-2",
        )
        with pytest.raises(ConfigError, match="exceeds grant"):
            RegimeCalendar(events=(grant, revoke))
