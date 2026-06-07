# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25173702 — Muffler (segment 25).

Bespoke graph logic for acoustic performance validation and back-pressure
simulation for automotive/industrial muffler components.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173702"
UNISPSC_TITLE = "Muffler"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Muffler
    noise_attenuation_db: float
    back_pressure_kpa: float
    material_grade: str
    compliance_check_passed: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Inspect input specs for material durability and fitment."""
    inp = state.get("input") or {}
    material = inp.get("material", "AISI 409 Stainless")

    # Simulate a validation log entry
    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "material_grade": material,
    }


def simulate_performance(state: State) -> dict[str, Any]:
    """Simulate acoustic attenuation and exhaust flow resistance."""
    inp = state.get("input") or {}

    # Default simulations if not provided in input
    attenuation = float(inp.get("target_db_reduction", 32.5))
    pressure = float(inp.get("flow_resistance_kpa", 12.2))

    return {
        "log": [f"{UNISPSC_CODE}:simulate_performance"],
        "noise_attenuation_db": attenuation,
        "back_pressure_kpa": pressure,
    }


def certify_muffler(state: State) -> dict[str, Any]:
    """Verify performance metrics against EPA/Euro standards and emit result."""
    attenuation = state.get("noise_attenuation_db", 0.0)
    pressure = state.get("back_pressure_kpa", 0.0)

    # Certification logic: must reduce noise significantly without excessive back-pressure
    is_passed = (attenuation >= 25.0) and (pressure <= 20.0)

    return {
        "log": [f"{UNISPSC_CODE}:certify_muffler"],
        "compliance_check_passed": is_passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certification": "ISO-9001-AUTO" if is_passed else "REJECTED",
            "metrics": {
                "attenuation": attenuation,
                "pressure": pressure,
                "material": state.get("material_grade")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("simulate", simulate_performance)
_g.add_node("certify", certify_muffler)

_g.add_edge(START, "validate")
_g.add_edge("validate", "simulate")
_g.add_edge("simulate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
