"""H1B §3: read-only calendar loading and event-as-of queries.

Loads RegimeCalendar from explicit JSON only; never scans history/data/targets.
All I/O errors become ConfigError with path context.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from hsm_lab.contract.base import ConfigError
from hsm_lab.institutions.schemas import DateInterval, InstitutionEvent, RegimeCalendar

# ---------------------------------------------------------------------------
# JSON loading
# ---------------------------------------------------------------------------

def load_calendar(path: Path) -> RegimeCalendar:
    """Load a RegimeCalendar from an explicit JSON file.

    Raises
    ------
    ConfigError
        If the file does not exist, contains invalid JSON, or yields an
        invalid RegimeCalendar (missing events, unknown fields, invalid
        records).
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(
            f"load_calendar: cannot read {path}: {exc}"
        ) from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"load_calendar: invalid JSON in {path}: {exc}"
        ) from exc

    try:
        return RegimeCalendar.model_validate(data)
    except Exception as exc:  # pydantic ValidationError
        raise ConfigError(
            f"load_calendar: validation failed for {path}: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Single-event query
# ---------------------------------------------------------------------------

def event_as_of(
    calendar: RegimeCalendar,
    *,
    event_id: str,
    decision_at: date,
) -> InstitutionEvent:
    """Return the event with the given ID, raising ConfigError if unavailable.

    Raises
    ------
    ConfigError
        - event_id not found in calendar
        - source_available_at is unknown (precision='unknown')
        - decision_at is earlier than source_available_at.latest
          (future knowledge not available at decision time)
    """
    event = calendar.event_by_id(event_id)
    if event is None:
        raise ConfigError(f"event_as_of: event_id '{event_id}' not found")

    # Check source availability using latest bound
    sav = event.source_available_at
    if sav.precision == "unknown":
        raise ConfigError(
            f"event_as_of: source_available_at for '{event_id}' is unknown; "
            "not available at any decision date"
        )
    if sav.latest is None:
        raise ConfigError(
            f"event_as_of: source_available_at for '{event_id}' has no latest bound"
        )
    if decision_at < sav.latest:
        raise ConfigError(
            f"event_as_of: decision_at {decision_at} is before source available "
            f"at {sav.latest}; knowledge not accessible at that date"
        )

    return event


# ---------------------------------------------------------------------------
# Date-interval helpers (used internally; not part of the public API)
# ---------------------------------------------------------------------------

def _interval_covers(interval: DateInterval, d: date) -> bool | None:
    """Return True/False/None for whether date d is in [earliest, latest]."""
    return interval.is_active_on(d)


def _effective_on(interval: DateInterval, d: date) -> bool | None:
    """Conservative date-coverage check: earliest.latest ≤ d means definitely active."""
    if interval.precision == "unknown":
        return None
    if interval.earliest is None:
        return None
    # We use the conservative rule: effective_from.latest ≤ d → definitely active
    if interval.latest is not None and interval.latest <= d:
        return True
    if interval.earliest is not None and d < interval.earliest:
        return False
    return None  # uncertain
