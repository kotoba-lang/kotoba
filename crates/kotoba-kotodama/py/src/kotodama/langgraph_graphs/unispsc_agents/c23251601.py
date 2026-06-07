# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23251601 — Rolling Machine (segment 23).

Bespoke logic for industrial rolling machinery, handling pressure
calibration and material processing cycles. This agent manages the
transition from raw input parameters to verified machine execution
states for metal or material deformation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251601"
UNISPSC_TITLE = "Rolling Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific state for a Rolling Machine
    material_grade: str
    target_thickness_mm: float
    applied_pressure_psi: float
    calibration_verified: bool


def setup_parameters(state: State) -> dict[str, Any]:
    """
    Initializes machine parameters from input configuration.
    Extracts material type and target thickness for the run.
    """
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:setup_parameters"],
        "material_grade": inp.get("material", "Standard Steel"),
        "target_thickness_mm": float(inp.get("target_mm", 5.0)),
        "calibration_verified": False,
    }


def calibrate_rollers(state: State) -> dict[str, Any]:
    """
    Simulates precision adjustment of roller gaps based on target thickness.
    Determines necessary pressure for the material grade.
    """
    target = state.get("target_thickness_mm", 5.0)
    # Heuristic calculation for rolling pressure based on thickness
    pressure = 10000.0 / (target if target > 0 else 1.0)
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_rollers"],
        "applied_pressure_psi": round(pressure, 2),
        "calibration_verified": True,
    }


def process_rolling_cycle(state: State) -> dict[str, Any]:
    """
    Executes the physical rolling process on the specified material.
    Records the operation outcome and material characteristics.
    """
    grade = state.get("material_grade", "Standard Steel")
    pressure = state.get("applied_pressure_psi", 0.0)
    return {
        "log": [f"{UNISPSC_CODE}:process_rolling_cycle"],
        "result": {
            "status": "Success",
            "material_processed": grade,
            "final_pressure_psi": pressure,
            "operation_mode": "Automated"
        }
    }


def finalize_output(state: State) -> dict[str, Any]:
    """
    Wraps result into standard UNISPSC agent response format.
    Ensures DID and UNISPSC metadata are included.
    """
    res = state.get("result") or {}
    res.update({
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "ok": state.get("calibration_verified", False),
    })
    return {
        "log": [f"{UNISPSC_CODE}:finalize_output"],
        "result": res,
    }


_g = StateGraph(State)
_g.add_node("setup", setup_parameters)
_g.add_node("calibrate", calibrate_rollers)
_g.add_node("process", process_rolling_cycle)
_g.add_node("finalize", finalize_output)

_g.add_edge(START, "setup")
_g.add_edge("setup", "calibrate")
_g.add_edge("calibrate", "process")
_g.add_edge("process", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
