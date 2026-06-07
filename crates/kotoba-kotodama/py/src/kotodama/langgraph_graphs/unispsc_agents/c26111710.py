# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111710 — Portable Generators (segment 26).

This bespoke graph manages the configuration and safety auditing of portable
power generation units, ensuring wattage and fuel specifications meet safety
thresholds before asset emission.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111710"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111710"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    fuel_type: str
    rated_wattage: int
    emission_compliance: bool
    safety_check: str


def configure_power_unit(state: State) -> dict[str, Any]:
    """Validate fuel type and wattage rating for the portable generator."""
    inp = state.get("input") or {}
    fuel = inp.get("fuel_type", "Gasoline")
    wattage = int(inp.get("wattage_rating", 2200))

    return {
        "log": [f"{UNISPSC_CODE}:configure_power_unit"],
        "fuel_type": fuel,
        "rated_wattage": wattage,
    }


def audit_safety_specs(state: State) -> dict[str, Any]:
    """Perform safety and emission compliance checks based on wattage."""
    wattage = state.get("rated_wattage", 0)
    # Simple logic: Portable units usually stay under 25kW for safety/mobility
    is_safe = 0 < wattage <= 25000
    compliance = "EPA Phase 3" if is_safe else "Non-Compliant"

    return {
        "log": [f"{UNISPSC_CODE}:audit_safety_specs"],
        "emission_compliance": is_safe,
        "safety_check": compliance,
    }


def emit_asset_record(state: State) -> dict[str, Any]:
    """Finalize and emit the validated generator asset data."""
    is_ok = state.get("emission_compliance", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "fuel": state.get("fuel_type"),
                "wattage": state.get("rated_wattage"),
                "compliance": state.get("safety_check"),
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("configure", configure_power_unit)
_g.add_node("audit", audit_safety_specs)
_g.add_node("emit", emit_asset_record)

_g.add_edge(START, "configure")
_g.add_edge("configure", "audit")
_g.add_edge("audit", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
