"""H2A §2: decision and proposal schemas — frozen, no state patches.

All decision models are strict frozen Pydantic models.  Stock/cash assignment
fields are absent by design; proposals express legal choices only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from enum import Enum
from typing import Any, Literal

from pydantic import model_validator

from hsm_lab.contract.base import StrictModel


class ActorRole(Enum):
    """Four synthetic minimal roles for H2A."""

    PROCUREMENT_ORGANIZATION = "procurement_organization"
    INVESTMENT_ORGANIZATION = "investment_organization"
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

    def __init__(self, **data):
        # Field-specific exact-type gate BEFORE Pydantic processes the input.
        # Pydantic would otherwise coerce payloads through
        # __float__/__int__/__str__(enum value), executing untrusted code.
        cls = type(self)
        if cls is ProcurementDecision:
            field_types = DECISION_FIELD_TYPES[ProcurementDecision]
        elif cls is PriceProposalDecision:
            field_types = DECISION_FIELD_TYPES[PriceProposalDecision]
        elif cls is InvestmentDecision:
            field_types = DECISION_FIELD_TYPES[InvestmentDecision]
        elif cls is HouseholdNeedDecision:
            field_types = DECISION_FIELD_TYPES[HouseholdNeedDecision]
        else:
            raise TypeError("decision type is not a registered H2A type")
        for key, value in data.items():
            if type(key) is not str:
                raise TypeError("decision field name must be exactly str")
            allowed = field_types.get(key)
            if allowed is None:
                raise TypeError("decision field name is not registered")
            if not decision_field_value_allowed(value, allowed):
                raise TypeError(
                    "decision field value has a disallowed exact type"
                )
        super().__init__(**data)

    @model_validator(mode="after")
    def _reject_date_subclasses(self) -> Decision:
        """Reject date subclasses that may carry mutable state."""
        for field_name in ("decision_at", "available_at"):
            value = getattr(self, field_name)
            if type(value) is not date:
                raise TypeError(
                    "decision date fields must be plain dates; "
                    "date subclasses may carry mutable state"
                )
        return self

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
        if self.actor_role != ActorRole.PROCUREMENT_ORGANIZATION:
            return False, (
                f"ProcurementDecision may only be issued by "
                f"PROCUREMENT_ORGANIZATION, got {self.actor_role.value}"
            )
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
        if self.actor_role != ActorRole.APPROVER:
            return False, (
                f"PriceProposalDecision may only be issued by "
                f"APPROVER, got {self.actor_role.value}"
            )
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
        if self.actor_role != ActorRole.INVESTMENT_ORGANIZATION:
            return False, (
                f"InvestmentDecision may only be issued by "
                f"INVESTMENT_ORGANIZATION, got {self.actor_role.value}"
            )
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
        if self.actor_role != ActorRole.HOUSEHOLD_RECEIVER:
            return False, (
                f"HouseholdNeedDecision may only be issued by "
                f"HOUSEHOLD_RECEIVER, got {self.actor_role.value}"
            )
        if self.claimed_quantity < 0:
            return False, f"claimed_quantity cannot be negative: {self.claimed_quantity}"
        if not math.isfinite(self.claimed_quantity):
            return False, f"claimed_quantity must be finite: {self.claimed_quantity}"
        if type(self.household_id) is not str or type(self.organization_id) is not str:
            return False, "household identity must be exact strings"
        if not self.household_id or not self.household_id.strip():
            return False, "household_id must be non-empty"
        # Identity binding: a receiver may only claim needs for itself.  There is
        # no implicit delegation; an authorized delegation would have to be
        # declared explicitly by the institutional layer.
        if self.household_id != self.organization_id:
            return False, (
                "household_id must equal organization_id; "
                "implicit delegation is not authorized"
            )
        if not self.commodity_id or not self.commodity_id.strip():
            return False, "commodity_id must be non-empty"
        if self.available_at > self.decision_at:
            msg = (f"available_at {self.available_at} cannot be after "
                   f"decision_at {self.decision_at}")
            return False, msg
        return True, "legal household need registration"


# Field-specific exact types.  Defined after the concrete classes; the
# constructor and the validator resolve these at call time.  Enum fields are
# additionally restricted to declared members (identity, never ``__eq__``).
DECISION_FIELD_TYPES: dict[type, dict[str, tuple[type, ...]]] = {
    ProcurementDecision: {
        "decision_id": (str,),
        "actor_role": (ActorRole,),
        "organization_id": (str,),
        "sector_id": (str,),
        "quarter": (str,),
        "decision_at": (date,),
        "available_at": (date,),
        "kind": (ProcurementChoiceKind,),
        "commodity_id": (str,),
        "requested_quantity": (float,),
    },
    PriceProposalDecision: {
        "decision_id": (str,),
        "actor_role": (ActorRole,),
        "organization_id": (str,),
        "sector_id": (str,),
        "quarter": (str,),
        "decision_at": (date,),
        "available_at": (date,),
        "kind": (PriceProposalKind,),
        "commodity_id": (str,),
        "proposed_price": (float,),
    },
    InvestmentDecision: {
        "decision_id": (str,),
        "actor_role": (ActorRole,),
        "organization_id": (str,),
        "sector_id": (str,),
        "quarter": (str,),
        "decision_at": (date,),
        "available_at": (date,),
        "kind": (str,),
        "project_id": (str,),
        "requested_amount": (float,),
    },
    HouseholdNeedDecision: {
        "decision_id": (str,),
        "actor_role": (ActorRole,),
        "organization_id": (str,),
        "sector_id": (str,),
        "quarter": (str,),
        "decision_at": (date,),
        "available_at": (date,),
        "kind": (HouseholdNeedKind,),
        "household_id": (str,),
        "commodity_id": (str,),
        "claimed_quantity": (float,),
    },
}

# Declared members per enum class.  ``object.__new__(EnumClass)`` can fabricate
# a non-member whose ``_value_`` triggers arbitrary callbacks during coercion;
# membership is checked by identity against these tuples.
ENUM_MEMBER_ALLOWLIST: dict[type, tuple[Enum, ...]] = {
    ActorRole: (ActorRole.PROCUREMENT_ORGANIZATION,
                ActorRole.INVESTMENT_ORGANIZATION,
                ActorRole.APPROVER,
                ActorRole.HOUSEHOLD_RECEIVER),
    ProcurementChoiceKind: (ProcurementChoiceKind.REQUEST,
                            ProcurementChoiceKind.CANCEL),
    PriceProposalKind: (PriceProposalKind.SET, PriceProposalKind.ADJUST),
    HouseholdNeedKind: (HouseholdNeedKind.REGISTER,
                        HouseholdNeedKind.UPDATE),
}


def decision_field_value_allowed(
    value: Any, allowed: tuple[type, ...]
) -> bool:
    """Identity-only field check, including declared enum membership."""
    actual = type(value)
    for candidate in allowed:
        if actual is candidate:
            members = ENUM_MEMBER_ALLOWLIST.get(candidate)
            if members is None:
                return True
            for member in members:
                if value is member:
                    return True
            return False
    return False
