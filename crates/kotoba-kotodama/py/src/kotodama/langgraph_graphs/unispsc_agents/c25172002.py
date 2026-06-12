# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172002 — Suspension (segment 25).

Bespoke graph logic for vehicle suspension systems. This agent manages
specifications for load capacity, damping rates, and structural durability
certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172002"
UNISPSC_TITLE = "Suspension"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172002"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific suspension fields
    load_capacity_kg: float
    damping_ratio: float
    suspension_type: str
    qc_certified: bool


def validate_configuration(state: State) -> dict[str, Any]:
    """Validates the mechanical configuration for the suspension component."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:validate_configuration"],
        "load_capacity_kg": float(inp.get("load_capacity", 1500.0)),
        "damping_ratio": float(inp.get("damping", 0.7)),
        "suspension_type": str(inp.get("type", "multi-link")),
    }


def analyze_stress_load(state: State) -> dict[str, Any]:
    """Performs a simulated stress test analysis based on load and type."""
    load = state.get("load_capacity_kg", 0.0)
    stype = state.get("suspension_type", "")

    # Logic: heavy loads require robust types
    heavy_load = load > 3000.0
    is_safe = not (heavy_load and stype == "leaf-spring")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_stress_load"],
        "qc_certified": is_safe,
    }


def emit_compliance_record(state: State) -> dict[str, Any]:
    """Finalizes the suspension actor result and compliance status."""
    is_ok = state.get("qc_certified", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_compliance_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if is_ok else "FAILED_INSPECTION",
            "metadata": {
                "configured_type": state.get("suspension_type"),
                "rated_load": state.get("load_capacity_kg"),
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_configuration)
_g.add_node("analyze", analyze_stress_load)
_g.add_node("emit", emit_compliance_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
