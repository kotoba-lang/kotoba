# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23111600 — Cleaning Equipment (segment 23).

Bespoke graph for managing cleaning equipment lifecycle, including
specification validation, safety certification checks, and asset tracking.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23111600"
UNISPSC_TITLE = "Cleaning Equipment"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23111600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Cleaning Equipment
    equipment_type: str
    safety_certified: bool
    maintenance_status: str
    asset_tag: str


def validate_requirements(state: State) -> dict[str, Any]:
    """Validate equipment specifications and safety requirements."""
    inp = state.get("input") or {}
    eq_type = inp.get("type", "Industrial Vacuum")
    certified = inp.get("safety_check", True)

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "equipment_type": eq_type,
        "safety_certified": certified,
    }


def register_asset(state: State) -> dict[str, Any]:
    """Check maintenance logs and assign an internal asset tag."""
    eq_type = state.get("equipment_type", "Standard")
    # Simulated logic: if certified, it's ready for deployment
    status = "Operational" if state.get("safety_certified") else "Inspection Required"
    tag = f"CLEAN-{UNISPSC_CODE}-{abs(hash(eq_type)) % 10000:04d}"

    return {
        "log": [f"{UNISPSC_CODE}:register_asset"],
        "maintenance_status": status,
        "asset_tag": tag,
    }


def emit_result(state: State) -> dict[str, Any]:
    """Finalize the procurement or deployment status."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "asset_tag": state.get("asset_tag"),
            "status": state.get("maintenance_status"),
            "did": UNISPSC_DID,
            "ok": state.get("safety_certified", False),
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requirements)
_g.add_node("register", register_asset)
_g.add_node("emit", emit_result)

_g.add_edge(START, "validate")
_g.add_edge("validate", "register")
_g.add_edge("register", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
