# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23221000 — Machine Spec (segment 23).

Bespoke graph for validating and analyzing industrial machine specifications,
ensuring compliance with engineering tolerances and safety standards.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23221000"
UNISPSC_TITLE = "Machine Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23221000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Machine Spec
    machine_id: str
    tolerance_check_passed: bool
    safety_protocol_version: str
    maintenance_interval_hours: int


def validate_machine_specs(state: State) -> dict[str, Any]:
    """Validates the incoming machine specification data for completeness."""
    inp = state.get("input") or {}
    machine_id = inp.get("machine_id", "UNKNOWN")
    specs = inp.get("specifications", {})

    # Simple validation logic for machine specs
    has_tolerances = "tolerances" in specs

    return {
        "log": [f"{UNISPSC_CODE}:validate_machine_specs"],
        "machine_id": machine_id,
        "tolerance_check_passed": has_tolerances,
    }


def analyze_safety_compliance(state: State) -> dict[str, Any]:
    """Analyzes the safety protocols associated with the machine spec."""
    inp = state.get("input") or {}
    protocol = inp.get("safety_protocol", "v1.0-standard")

    # Determine maintenance interval based on machine type
    m_type = inp.get("type", "general")
    interval = 5000 if m_type == "heavy" else 2000

    return {
        "log": [f"{UNISPSC_CODE}:analyze_safety_compliance"],
        "safety_protocol_version": protocol,
        "maintenance_interval_hours": interval,
    }


def finalize_machine_record(state: State) -> dict[str, Any]:
    """Finalizes the machine specification record for integration."""
    is_valid = state.get("tolerance_check_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_machine_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "machine_id": state.get("machine_id"),
            "verified": is_valid,
            "maintenance": {
                "protocol": state.get("safety_protocol_version"),
                "interval": state.get("maintenance_interval_hours"),
            },
            "status": "OPERATIONAL" if is_valid else "REQUIRE_REVISION",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_machine_specs)
_g.add_node("safety_check", analyze_safety_compliance)
_g.add_node("finalize", finalize_machine_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "safety_check")
_g.add_edge("safety_check", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
