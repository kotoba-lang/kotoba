# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23151501 — Generator Spec (segment 23).

Bespoke graph logic for industrial generator specification management.
Ensures technical parameters meet safety and performance standards for
power generation equipment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151501"
UNISPSC_TITLE = "Generator Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    power_kw: float
    fuel_type: str
    voltage_range: list[int]
    is_compliant: bool


def validate_input_specs(state: State) -> dict[str, Any]:
    """Extracts and validates core generator specifications from input."""
    inp = state.get("input") or {}
    power = float(inp.get("power_kw", 0.0))
    fuel = str(inp.get("fuel", "unknown")).lower()

    log_msg = f"{UNISPSC_CODE}:validate_input_specs -> {fuel} @ {power}kW"
    return {
        "log": [log_msg],
        "power_kw": power,
        "fuel_type": fuel,
        "is_compliant": power > 0 and fuel != "unknown"
    }


def analyze_technical_feasibility(state: State) -> dict[str, Any]:
    """Performs feasibility check based on fuel and power rating."""
    power = state.get("power_kw", 0.0)
    fuel = state.get("fuel_type", "")

    # Mock engineering constraint: high-output generators typically require diesel or gas
    feasible = True
    if power > 500 and fuel == "gasoline":
        feasible = False

    # Voltage configuration based on scale
    voltage = [220, 440] if power >= 100 else [110, 220]

    return {
        "log": [f"{UNISPSC_CODE}:analyze_technical_feasibility -> feasible={feasible}"],
        "voltage_range": voltage,
        "is_compliant": state.get("is_compliant", False) and feasible
    }


def finalize_spec_manifest(state: State) -> dict[str, Any]:
    """Generates the final spec sheet and verification status."""
    is_ok = state.get("is_compliant", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "spec_sheet": {
            "power_rating_kw": state.get("power_kw"),
            "fuel_source": state.get("fuel_type"),
            "supported_voltages": state.get("voltage_range"),
        },
        "status": "APPROVED" if is_ok else "REJECTED_TECHNICAL_INCONSISTENCY",
        "ok": is_ok,
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_spec_manifest"],
        "result": res
    }


_g = StateGraph(State)
_g.add_node("validate", validate_input_specs)
_g.add_node("analyze", analyze_technical_feasibility)
_g.add_node("finalize", finalize_spec_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
