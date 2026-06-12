# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151817"
UNISPSC_TITLE = "Welding"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151817"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    welding_process: str
    material_type: str
    voltage_setting: float
    gas_flow_rate: float
    inspection_passed: bool


def configure_welder(state: State) -> dict[str, Any]:
    """Sets initial welding parameters based on input specifications."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:configure_welder"],
        "welding_process": inp.get("process", "GMAW"),
        "material_type": inp.get("material", "Carbon Steel"),
        "voltage_setting": float(inp.get("voltage", 24.5)),
        "gas_flow_rate": float(inp.get("gas_flow", 30.0)),
    }


def perform_fusion(state: State) -> dict[str, Any]:
    """Simulates the welding fusion process and checks for parameter stability."""
    process = state.get("welding_process", "Unknown")
    voltage = state.get("voltage_setting", 0.0)
    # Nominal operating window for high-quality fusion
    is_stable = 18.0 <= voltage <= 32.0
    return {
        "log": [f"{UNISPSC_CODE}:perform_fusion via {process}"],
        "inspection_passed": is_stable,
    }


def validate_weld_integrity(state: State) -> dict[str, Any]:
    """Final quality assurance check for the welded joint."""
    passed = state.get("inspection_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:validate_weld_integrity"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if passed else "REJECTED",
            "ok": passed,
            "metadata": {
                "process": state.get("welding_process"),
                "material": state.get("material_type")
            }
        },
    }


_g = StateGraph(State)
_g.add_node("configure", configure_welder)
_g.add_node("fuse", perform_fusion)
_g.add_node("validate", validate_weld_integrity)

_g.add_edge(START, "configure")
_g.add_edge("configure", "fuse")
_g.add_edge("fuse", "validate")
_g.add_edge("validate", END)

graph = _g.compile()
