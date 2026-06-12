# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151816"
UNISPSC_TITLE = "Welding Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151816"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Welding Spec
    base_material: str
    process_type: str
    filler_metal: str
    shielding_gas: str
    is_compliant: bool


def evaluate_requirements(state: State) -> dict[str, Any]:
    """Analyzes the input material and selects the appropriate welding process."""
    inp = state.get("input") or {}
    material = inp.get("material", "Carbon Steel")

    # Logic to determine welding process based on material
    if "Aluminum" in material:
        process = "GTAW (TIG)"
        filler = "ER4043"
    elif "Stainless" in material:
        process = "GMAW (MIG)"
        filler = "ER308L"
    else:
        process = "SMAW (Stick)"
        filler = "E7018"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_requirements"],
        "base_material": material,
        "process_type": process,
        "filler_metal": filler,
    }


def configure_environment(state: State) -> dict[str, Any]:
    """Sets up shielding gas and compliance parameters for the selected process."""
    process = state.get("process_type", "SMAW (Stick)")

    # Determine shielding gas based on process
    if "TIG" in process or "MIG" in process:
        gas = "100% Argon" if "TIG" in process else "75% Ar / 25% CO2"
    else:
        gas = "None (Flux Shielded)"

    return {
        "log": [f"{UNISPSC_CODE}:configure_environment"],
        "shielding_gas": gas,
        "is_compliant": True,
    }


def compile_specification(state: State) -> dict[str, Any]:
    """Constructs the final welding specification datasheet."""
    compliant = state.get("is_compliant", False)

    spec_data = {
        "unispsc": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "parameters": {
            "material": state.get("base_material"),
            "process": state.get("process_type"),
            "filler": state.get("filler_metal"),
            "gas": state.get("shielding_gas"),
        },
        "verification": {
            "status": "VALIDATED",
            "did": UNISPSC_DID,
            "compliant": compliant
        },
        "ok": compliant,
    }

    return {
        "log": [f"{UNISPSC_CODE}:compile_specification"],
        "result": spec_data,
    }


_g = StateGraph(State)
_g.add_node("evaluate", evaluate_requirements)
_g.add_node("configure", configure_environment)
_g.add_node("compile", compile_specification)

_g.add_edge(START, "evaluate")
_g.add_edge("evaluate", "configure")
_g.add_edge("configure", "compile")
_g.add_edge("compile", END)

graph = _g.compile()
