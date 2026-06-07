# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23251701 — Forge (segment 23).

Bespoke LangGraph logic for metal forging process automation, handling
thermal cycles and mechanical deformation workflows.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251701"
UNISPSC_TITLE = "Forge"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Forging machinery
    material_type: str
    furnace_temp_c: float
    pressure_psi: float
    cycles_completed: int
    cooling_method: str


def prepare_blank(state: State) -> dict[str, Any]:
    """Validates input specifications and initializes the workpiece."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:prepare_blank"],
        "material_type": inp.get("material", "AISI_1045"),
        "furnace_temp_c": 0.0,
        "pressure_psi": 0.0,
        "cycles_completed": 0,
        "cooling_method": inp.get("cooling", "oil_quench"),
    }


def thermal_cycle(state: State) -> dict[str, Any]:
    """Brings the forge furnace to operational temperature."""
    target_temp = 1150.0  # Typical forging temp for steel
    return {
        "log": [f"{UNISPSC_CODE}:thermal_cycle -> heating to {target_temp}C"],
        "furnace_temp_c": target_temp,
    }


def forge_press(state: State) -> dict[str, Any]:
    """Executes mechanical deformation via hydraulic or mechanical press."""
    target_pressure = 2500.0
    return {
        "log": [f"{UNISPSC_CODE}:forge_press -> applying {target_pressure} PSI"],
        "pressure_psi": target_pressure,
        "cycles_completed": state.get("cycles_completed", 0) + 1,
    }


def quality_assurance(state: State) -> dict[str, Any]:
    """Verifies process parameters and emits final production record."""
    ok = (
        state.get("furnace_temp_c", 0) >= 1100.0 and
        state.get("pressure_psi", 0) >= 2000.0 and
        state.get("cycles_completed", 0) > 0
    )
    return {
        "log": [f"{UNISPSC_CODE}:quality_assurance -> pass: {ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "COMPLETED" if ok else "FAILED",
            "material": state.get("material_type"),
            "final_cycles": state.get("cycles_completed"),
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("prepare", prepare_blank)
_g.add_node("heat", thermal_cycle)
_g.add_node("press", forge_press)
_g.add_node("qa", quality_assurance)

_g.add_edge(START, "prepare")
_g.add_edge("prepare", "heat")
_g.add_edge("heat", "press")
_g.add_edge("press", "qa")
_g.add_edge("qa", END)

graph = _g.compile()
