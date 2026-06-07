# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121119 — Motor (segment 20).

Bespoke LangGraph implementation for Motor components. This agent handles
specification validation, performance modeling, and result emission for
industrial motors and related equipment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121119"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121119"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Motor
    specification_verified: bool
    operating_parameters: dict[str, Any]
    efficiency_rating: float
    torque_limit_reached: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates motor specifications such as voltage and RPM range."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})

    # Motor validation logic
    voltage = specs.get("voltage", 0)
    is_valid = 100 <= voltage <= 600

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "specification_verified": is_valid,
        "operating_parameters": specs
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Calculates expected efficiency based on load and speed."""
    specs = state.get("operating_parameters") or {}
    rpm = specs.get("rpm", 1800)
    load_factor = specs.get("load_factor", 0.75)

    # Mocked performance analysis
    efficiency = 0.92 if load_factor > 0.5 else 0.85
    is_over_torque = rpm > 4500

    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance"],
        "efficiency_rating": efficiency,
        "torque_limit_reached": is_over_torque
    }


def emit_certification(state: State) -> dict[str, Any]:
    """Finalizes the analysis and emits the motor certification status."""
    is_verified = state.get("specification_verified", False)
    efficiency = state.get("efficiency_rating", 0.0)
    over_torque = state.get("torque_limit_reached", False)

    status = "certified" if is_verified and not over_torque else "rejected"

    return {
        "log": [f"{UNISPSC_CODE}:emit_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": status,
            "efficiency": efficiency,
            "did": UNISPSC_DID,
            "ok": status == "certified",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("analyze", analyze_performance)
_g.add_node("emit", emit_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
