# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23250000"
UNISPSC_TITLE = "Metal Forming"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23250000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Metal Forming domain state fields
    material_grade: str
    forming_process: str
    operating_temp_c: float
    applied_pressure_mpa: float
    safety_certification: bool


def analyze_forming_requirements(state: State) -> dict[str, Any]:
    """Evaluates the input requirements for material type and intended forming process."""
    inp = state.get("input") or {}
    grade = inp.get("material", "304 Stainless Steel")
    process = inp.get("process", "Deep Drawing")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_forming_requirements"],
        "material_grade": grade,
        "forming_process": process,
    }


def configure_process_parameters(state: State) -> dict[str, Any]:
    """Determines industrial setpoints for temperature and pressure based on forming method."""
    process = state.get("forming_process", "Unknown")

    # Process engineering heuristics for Metal Forming
    if process == "Deep Drawing":
        temp = 25.0  # Cold working
        pressure = 450.0
    elif process == "Hot Rolling":
        temp = 1250.0
        pressure = 150.0
    else:
        temp = 200.0
        pressure = 300.0

    return {
        "log": [f"{UNISPSC_CODE}:configure_process_parameters"],
        "operating_temp_c": temp,
        "applied_pressure_mpa": pressure,
        "safety_certification": True
    }


def finalize_production_spec(state: State) -> dict[str, Any]:
    """Compiles the validated metal forming specification into a result object."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_production_spec"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": {
                "material": state.get("material_grade"),
                "process": state.get("forming_process"),
                "parameters": {
                    "temperature_celsius": state.get("operating_temp_c"),
                    "pressure_mpa": state.get("applied_pressure_mpa")
                }
            },
            "status": "certified" if state.get("safety_certification") else "pending",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_forming_requirements)
_g.add_node("configure", configure_process_parameters)
_g.add_node("finalize", finalize_production_spec)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "configure")
_g.add_edge("configure", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
