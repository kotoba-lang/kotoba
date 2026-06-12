# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174004 — Engine Coolant (segment 25).
Bespoke logic for chemical composition analysis, thermal performance verification,
and specification issuance for vehicle engine cooling systems.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174004"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174004"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Engine Coolant processing
    coolant_type: str
    thermal_compliance: bool
    corrosion_inhibition_level: float
    boiling_point_c: float
    freeze_point_c: float


def analyze_chemistry(state: State) -> dict[str, Any]:
    """Analyzes the chemical base and concentration of the engine coolant."""
    inp = state.get("input") or {}
    composition = inp.get("composition", {})
    c_type = composition.get("type", "unknown")
    inhibitor_level = composition.get("inhibitor_pct", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_chemistry"],
        "coolant_type": c_type,
        "corrosion_inhibition_level": inhibitor_level,
    }


def verify_thermal_specs(state: State) -> dict[str, Any]:
    """Checks the boiling and freezing points against vehicle safety standards."""
    inp = state.get("input") or {}
    specs = inp.get("thermal_specs", {})
    bp = specs.get("boiling_point", 100.0)
    fp = specs.get("freeze_point", 0.0)

    # Simple compliance logic: needs to exceed water performance
    compliant = bp > 105.0 and fp < -15.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_thermal_specs"],
        "boiling_point_c": bp,
        "freeze_point_c": fp,
        "thermal_compliance": compliant,
    }


def issue_specification(state: State) -> dict[str, Any]:
    """Finalizes the technical data sheet and approval status."""
    compliant = state.get("thermal_compliance", False)
    status = "approved" if compliant else "rejected"

    return {
        "log": [f"{UNISPSC_CODE}:issue_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "coolant_type": state.get("coolant_type"),
            "status": status,
            "ok": compliant,
            "specs": {
                "boiling_point": state.get("boiling_point_c"),
                "freeze_point": state.get("freeze_point_c"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_chemistry", analyze_chemistry)
_g.add_node("verify_thermal_specs", verify_thermal_specs)
_g.add_node("issue_specification", issue_specification)

_g.add_edge(START, "analyze_chemistry")
_g.add_edge("analyze_chemistry", "verify_thermal_specs")
_g.add_edge("verify_thermal_specs", "issue_specification")
_g.add_edge("issue_specification", END)

graph = _g.compile()
