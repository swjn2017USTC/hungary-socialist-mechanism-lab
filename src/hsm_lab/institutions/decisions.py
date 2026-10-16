"""H2A §2: decision and proposal schemas — frozen, no state patches.

All decision models are strict frozen Pydantic models.  Stock/cash assignment
fields are absent by design; proposals express legal choices only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from enum import Enum
from typing import Literal

from hsm_lab.contract.base import StrictModel


class ActorRole(Enum):
    """Three synthetic minimal roles for H2A."""

    PROCUREMENT_ORGANIZATION = "procurement_organization"
    APPROVER = "approver"
    HOUSEHOLD_RECEIVER = "household_receiver"


# ---------------------------------------------------------------------------
# Decision — base class (frozen, no fields that imply state mutation)
# ---------------------------------------------------------------------------


class Decision(StrictModel, ABC):
    """A read-only decision record: who decided what, when, and on what information.

    Decisions do NOT contain stock or cash assignment fields.
    Subclasses represent specific choice types.
    """

    decision_id: str
    actor_role: ActorRole
    organization_id: str
    sector_id: str
    quarter: str  # ISO quarter label, e.g. "1968Q1"
    decision_at: date
    available_at: date  # information cutoff for this decision
    # The information available at decision time is a separate observation object,
    # not embedded here.

    @abstractmethod
    def choice_summary(self) -> str:
        """Human-readable one-line summary of the choice made."""
        ...

    @abstractmethod
    def validate_legality(self) -> tuple[bool, str]:
        """Return (is_legal, reason)."""
        ...


# ---------------------------------------------------------------------------
# Concrete decision types
# ---------------------------------------------------------------------------


class ProcurementChoiceKind(Enum):
    REQUEST = "request"
    CANCEL = "cancel"


class ProcurementDecision(Decision):
    """Procurement organization requests a quantity of one commodity."""

    kind: ProcurementChoiceKind = ProcurementChoiceKind.REQUEST
    commodity_id: str
    requested_quantity: float  # must be >= 0; zero = no request

    def choice_summary(self) -> str:
        kind_str = self.kind.value
        return (
            f"{self.actor_role.value}/{self.organization_id}: "
            f"{kind_str} {self.requested_quantity} of {self.commodity_id} "
            f"for {self.quarter}"
        )

    def validate_legality(self) -> tuple[bool, str]:
        import math
        if self.requested_quantity < 0:
            return False, f"requested_quantity cannot be negative: {self.requested_quantity}"
        if not math.isfinite(self.requested_quantity):
            return False, f"requested_quantity must be finite: {self.requested_quantity}"
        if not self.commodity_id or not self.commodity_id.strip():
            return False, "commodity_id must be non-empty"
        if self.available_at > self.decision_at:
            msg = (f"available_at {self.available_at} cannot be after "
                   f"decision_at {self.decision_at}")
            return False, msg
        return True, "legal procurement request"


class PriceProposalKind(Enum):
    SET = "set"
    ADJUST = "adjust"


class PriceProposalDecision(Decision):
    """Approver proposes or adjusts an administered price for one commodity."""

    kind: PriceProposalKind = PriceProposalKind.SET
    commodity_id: str
    proposed_price: float  # must be >= 0

    def choice_summary(self) -> str:
        return (
            f"{self.actor_role.value}/{self.organization_id}: "
            f"{self.kind.value} price {self.proposed_price} for {self.commodity_id} "
            f"for {self.quarter}"
        )

    def validate_legality(self) -> tuple[bool, str]:
        import math
        if self.proposed_price < 0:
            return False, f"proposed_price cannot be negative: {self.proposed_price}"
        if not math.isfinite(self.proposed_price):
            return False, f"proposed_price must be finite: {self.proposed_price}"
        if not self.commodity_id or not self.commodity_id.strip():
            return False, "commodity_id must be non-empty"
        if self.available_at > self.decision_at:
            msg = (f"available_at {self.available_at} cannot be after "
                   f"decision_at {self.decision_at}")
            return False, msg
        return True, "legal price proposal"


class InvestmentDecision(Decision):
    """Enterprise requests approval for an investment project."""

    kind: Literal["request", "withdraw"] = "request"
    project_id: str
    requested_amount: float  # must be >= 0

    def choice_summary(self) -> str:
        return (
            f"{self.actor_role.value}/{self.organization_id}: "
            f"{self.kind} investment {self.requested_amount} "
            f"for project {self.project_id} in {self.quarter}"
        )

    def validate_legality(self) -> tuple[bool, str]:
        import math
        if self.requested_amount < 0:
            return False, f"requested_amount cannot be negative: {self.requested_amount}"
        if not math.isfinite(self.requested_amount):
            return False, f"requested_amount must be finite: {self.requested_amount}"
        if not self.project_id or not self.project_id.strip():
            return False, "project_id must be non-empty"
        if self.available_at > self.decision_at:
            msg = (f"available_at {self.available_at} cannot be after "
                   f"decision_at {self.decision_at}")
            return False, msg
        return True, "legal investment request"


class HouseholdNeedKind(Enum):
    REGISTER = "register"
    UPDATE = "update"


class HouseholdNeedDecision(Decision):
    """Household receiver registers or updates a claimed need."""

    kind: HouseholdNeedKind = HouseholdNeedKind.REGISTER
    household_id: str
    commodity_id: str
    claimed_quantity: float  # must be >= 0

    def choice_summary(self) -> str:
        kind_str = self.kind.value
        return (
            f"{self.actor_role.value}/{self.household_id}: "
            f"{kind_str} need {self.claimed_quantity} "
            f"of {self.commodity_id} for {self.quarter}"
        )

    def validate_legality(self) -> tuple[bool, str]:
        import math
        if self.claimed_quantity < 0:
            return False, f"claimed_quantity cannot be negative: {self.claimed_quantity}"
        if not math.isfinite(self.claimed_quantity):
            return False, f"claimed_quantity must be finite: {self.claimed_quantity}"
        if not self.household_id or not self.household_id.strip():
            return False, "household_id must be non-empty"
        if not self.commodity_id or not self.commodity_id.strip():
            return False, "commodity_id must be non-empty"
        if self.available_at > self.decision_at:
            msg = (f"available_at {self.available_at} cannot be after "
                   f"decision_at {self.decision_at}")
            return False, msg
        return True, "legal household need registration"
