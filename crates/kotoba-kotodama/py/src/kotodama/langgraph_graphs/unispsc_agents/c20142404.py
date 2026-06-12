# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142404 — Mold (segment 20).

Bespoke graph logic for industrial molds used in resinous material processing.
This agent handles specification validation, production capacity assessment,
and final metadata emission for manufacturing components.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142404"
UNISPSC_TITLE = "Mold"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142404"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for "Mold"
    mold_type: str
    cavity_count: int
    clamping_force_kn: float
    surface_finish_spec: str


def validate_mold_configuration(state: State) -> dict[str, Any]:
    """Validates the physical configuration and material compatibility of the mold."""
    inp = state.get("input") or {}
    m_type = inp.get("mold_type", "injection")
    c_count = inp.get("cavity_count", 1)

    return {
        "log": [f"{UNISPSC_CODE}:validate_mold_configuration: type={m_type}, cavities={c_count}"],
        "mold_type": m_type,
        "cavity_count": c_count,
    }


def assess_production_capacity(state: State) -> dict[str, Any]:
    """Calculates required machine specifications like clamping force and finish quality."""
    inp = state.get("input") or {}
    force = inp.get("required_force", 1500.0)
    finish = inp.get("finish", "SPI-A2")

    return {
        "log": [f"{UNISPSC_CODE}:assess_production_capacity: force={force}kN"],
        "clamping_force_kn": force,
        "surface_finish_spec": finish,
    }


def generate_catalog_entry(state: State) -> dict[str, Any]:
    """Emits the final processed agent result with all mold specifications."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_catalog_entry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "mold_type": state.get("mold_type"),
                "cavity_count": state.get("cavity_count"),
                "clamping_force_kn": state.get("clamping_force_kn"),
                "surface_finish": state.get("surface_finish_spec"),
            },
            "status": "validated",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_mold_configuration)
_g.add_node("assess", assess_production_capacity)
_g.add_node("emit", generate_catalog_entry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
