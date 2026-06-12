# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171507 — Wiper (segment 25).

Bespoke graph logic for windshield or industrial wiper components.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171507"
UNISPSC_TITLE = "Wiper"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Wiper
    blade_material: str
    size_inches: int
    motor_type: str
    is_weatherproof: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Validate the incoming wiper specifications."""
    inp = state.get("input") or {}
    size = inp.get("size", 22)
    material = inp.get("material", "synthetic rubber")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "size_inches": size,
        "blade_material": material,
    }


def configure_assembly(state: State) -> dict[str, Any]:
    """Configure the wiper motor and arm assembly."""
    size = state.get("size_inches", 0)
    motor = "heavy-duty" if size > 24 else "standard"
    weatherproof = state.get("blade_material") == "silicone"

    return {
        "log": [f"{UNISPSC_CODE}:configure_assembly"],
        "motor_type": motor,
        "is_weatherproof": weatherproof,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Emit the final component manifest."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "spec": {
                "size": state.get("size_inches"),
                "material": state.get("blade_material"),
                "motor": state.get("motor_type"),
                "weatherproof": state.get("is_weatherproof"),
            },
            "status": "ready",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_specifications)
_g.add_node("configure", configure_assembly)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "configure")
_g.add_edge("configure", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
