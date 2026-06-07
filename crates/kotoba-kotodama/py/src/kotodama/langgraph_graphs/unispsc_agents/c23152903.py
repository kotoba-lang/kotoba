# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23152903"
UNISPSC_TITLE = "Welding"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23152903"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_spec: str
    weld_method: str
    amperage_target: int
    gas_shielding: bool


def validate_weld_requirements(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    spec = inp.get("material", "mild_steel")
    return {
        "log": [f"{UNISPSC_CODE}:validate_weld_requirements"],
        "material_spec": str(spec),
    }


def determine_welding_process(state: State) -> dict[str, Any]:
    spec = state.get("material_spec", "mild_steel").lower()
    # GTAW (TIG) for Aluminum, GMAW (MIG) for Stainless, SMAW (Stick) for others
    if "aluminum" in spec:
        method, gas = "GTAW", True
    elif "stainless" in spec:
        method, gas = "GMAW", True
    else:
        method, gas = "SMAW", False

    return {
        "log": [f"{UNISPSC_CODE}:determine_welding_process"],
        "weld_method": method,
        "gas_shielding": gas,
    }


def calculate_electrical_params(state: State) -> dict[str, Any]:
    method = state.get("weld_method", "SMAW")
    # Base amperage targets for 1/8 inch thickness simulation
    targets = {"GTAW": 120, "GMAW": 190, "SMAW": 105}
    return {
        "log": [f"{UNISPSC_CODE}:calculate_electrical_params"],
        "amperage_target": targets.get(method, 100),
    }


def finalize_fabrication_order(state: State) -> dict[str, Any]:
    return {
        "log": [f"{UNISPSC_CODE}:finalize_fabrication_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": {
                "method": state.get("weld_method"),
                "amperage": state.get("amperage_target"),
                "shielding_active": state.get("gas_shielding"),
                "material": state.get("material_spec"),
            },
            "status": "ready",
        },
    }


_g = StateGraph(State)
_g.add_node("validate_weld_requirements", validate_weld_requirements)
_g.add_node("determine_welding_process", determine_welding_process)
_g.add_node("calculate_electrical_params", calculate_electrical_params)
_g.add_node("finalize_fabrication_order", finalize_fabrication_order)

_g.add_edge(START, "validate_weld_requirements")
_g.add_edge("validate_weld_requirements", "determine_welding_process")
_g.add_edge("determine_welding_process", "calculate_electrical_params")
_g.add_edge("calculate_electrical_params", "finalize_fabrication_order")
_g.add_edge("finalize_fabrication_order", END)

graph = _g.compile()
