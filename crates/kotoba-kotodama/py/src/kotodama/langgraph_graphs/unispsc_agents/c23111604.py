# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23111604 — Metal Forming (segment 23).

Bespoke graph for Metal Forming operations, managing material specs,
forming parameters, and quality control transitions.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23111604"
UNISPSC_TITLE = "Metal Forming"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23111604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    material_spec: str
    forming_operation: str
    forming_pressure_psi: float
    operating_temperature: int
    is_structurally_sound: bool


def configure_metallurgy(state: State) -> dict[str, Any]:
    """Sets material specs and intended operation from job input."""
    inp = state.get("input") or {}
    mat = inp.get("material", "SAE 1020 Steel")
    op = inp.get("op", "Extrusion")
    return {
        "log": [f"{UNISPSC_CODE}:configure_metallurgy -> {mat}"],
        "material_spec": mat,
        "forming_operation": op,
    }


def execute_deformation(state: State) -> dict[str, Any]:
    """Applies forming forces and records physical state changes."""
    op = state.get("forming_operation", "Bending")
    is_hot = "Hot" in op or op in ["Forging", "Extrusion"]
    temp = 1150 if is_hot else 22
    pressure = 4500.5 if is_hot else 1200.0

    return {
        "log": [f"{UNISPSC_CODE}:execute_deformation -> temp:{temp}C pressure:{pressure}psi"],
        "operating_temperature": temp,
        "forming_pressure_psi": pressure,
        "is_structurally_sound": True
    }


def verify_integrity(state: State) -> dict[str, Any]:
    """Conducts final inspection and package delivery metadata."""
    sound = state.get("is_structurally_sound", False)
    return {
        "log": [f"{UNISPSC_CODE}:verify_integrity -> sound: {sound}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "integrity_check": sound,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("configure", configure_metallurgy)
_g.add_node("deform", execute_deformation)
_g.add_node("verify", verify_integrity)

_g.add_edge(START, "configure")
_g.add_edge("configure", "deform")
_g.add_edge("deform", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
