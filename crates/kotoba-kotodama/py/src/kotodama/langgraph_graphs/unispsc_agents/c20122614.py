# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122614"
UNISPSC_TITLE = "Robot Assembly"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122614"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    chassis_serial: str
    component_manifest: list[str]
    assembly_step: int
    inspection_passed: bool


def configure_work_cell(state: State) -> dict[str, Any]:
    """Initializes the assembly environment and validates input manifest."""
    inp = state.get("input") or {}
    chassis = inp.get("chassis_serial", "SN-TEMP-000")
    manifest = inp.get("components", ["servo-base", "logic-board", "sensor-array"])

    return {
        "log": [f"{UNISPSC_CODE}:configure_work_cell"],
        "chassis_serial": chassis,
        "component_manifest": manifest,
        "assembly_step": 0,
    }


def perform_robotic_assembly(state: State) -> dict[str, Any]:
    """Simulates sequential assembly of robot components."""
    manifest = state.get("component_manifest", [])
    step_count = len(manifest)

    return {
        "log": [f"{UNISPSC_CODE}:perform_robotic_assembly:integrated_{step_count}_parts"],
        "assembly_step": step_count,
    }


def finalize_and_inspect(state: State) -> dict[str, Any]:
    """Performs final quality control and emits the finished assembly record."""
    step = state.get("assembly_step", 0)
    passed = step > 0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_and_inspect:score_{0.98 if passed else 0.0}"],
        "inspection_passed": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "chassis_serial": state.get("chassis_serial"),
            "status": "ASSEMBLY_COMPLETE" if passed else "FAILED",
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("configure", configure_work_cell)
_g.add_node("assemble", perform_robotic_assembly)
_g.add_node("inspect", finalize_and_inspect)

_g.add_edge(START, "configure")
_g.add_edge("configure", "assemble")
_g.add_edge("assemble", "inspect")
_g.add_edge("inspect", END)

graph = _g.compile()
