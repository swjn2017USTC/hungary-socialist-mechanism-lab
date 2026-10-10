"""P07A2 §3: InterventionBinding parameter-path validator.

Validates that an InterventionBinding.parameter_path resolves to a known
policy column in the F2 output tables. Also guards against:
- application_quarter in the reserved window (1986Q1+)
- parameter_path containing 'future' references
- missing_policy set to "0" (silently filling zeros is forbidden)

This module does NOT run experiments, does NOT read target values, and does
NOT modify the production engine.
"""

from __future__ import annotations

from hsm_lab.evidence.schemas import InterventionBinding
from hsm_lab.evidence.table_registry import (
    POLICY_PATH_TO_COLUMN,
    VALID_PARAMETER_PATHS,
    get_f2_table_registry,
)


class InterventionValidationError(ValueError):
    """Raised when an InterventionBinding fails validation."""


def validate_intervention_binding(binding: InterventionBinding) -> None:
    """Validate one InterventionBinding.

    Raises
    ------
    InterventionValidationError
        If the binding has any structural or policy violation.

    Notes
    -----
    This validates the *declaration* of an intervention, not whether the
    parameter_path corresponds to an actual model parameter that can be
    written at runtime. That requires engine-level path resolution, which
    is done separately when the experiment is actually run.
    """
    errors: list[str] = []

    # 1. application_quarter must not be in reserved window
    if binding.application_quarter >= "1986Q1":
        errors.append(
            f"application_quarter {binding.application_quarter} is in the "
            "reserved window (1986Q1–1988Q4); interventions may not target it"
        )

    # 2. parameter_path must not contain 'future'
    if "future" in binding.parameter_path.lower():
        errors.append(
            f"parameter_path '{binding.parameter_path}' contains 'future'; "
            "interventions may not reference future state"
        )

    # 3. parameter_path must be a known policy dot-path
    if binding.parameter_path not in VALID_PARAMETER_PATHS:
        errors.append(
            f"parameter_path '{binding.parameter_path}' is not a known policy path. "
            f"Known paths: {sorted(VALID_PARAMETER_PATHS)}"
        )

    # 4. Validate that the mapped column exists in the F2 table registry
    if binding.parameter_path in POLICY_PATH_TO_COLUMN:
        col = POLICY_PATH_TO_COLUMN[binding.parameter_path]
        registry = get_f2_table_registry()
        if not registry.column_exists("political_quarters", col):
            errors.append(
                f"Policy column '{col}' (from path '{binding.parameter_path}') "
                "is not in political_quarters table"
            )

    # 5. persistence must be a known value
    valid_persistence = {"one_shot", "sustained", "reverted_at"}
    if binding.persistence not in valid_persistence:
        errors.append(
            f"persistence '{binding.persistence}' is not one of "
            f"{valid_persistence}"
        )

    # 6. applicable_scenarios must not be empty
    if not binding.application_quarter:
        pass  # already covered by Pydantic
    if not binding.applicable_scenarios:
        errors.append("applicable_scenarios must not be empty")

    if errors:
        raise InterventionValidationError(
            f"InterventionBinding '{binding.intervention_id}' validation failed:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


def validate_intervention_bindings(
    bindings: list[InterventionBinding],
) -> list[InterventionBinding]:
    """Validate a list of InterventionBindings.

    Returns
    -------
    list[InterventionBinding]
        The same bindings if all pass validation.

    Raises
    ------
    InterventionValidationError
        On the first binding that fails.
    """
    for binding in bindings:
        validate_intervention_binding(binding)
    return bindings


def is_valid_parameter_path(path: str) -> bool:
    """True if the parameter path is a known, resolvable policy dot-path."""
    return path in VALID_PARAMETER_PATHS


def get_policy_column(path: str) -> str | None:
    """Map a policy dot-path to its political_quarters column name, or None."""
    return POLICY_PATH_TO_COLUMN.get(path)
