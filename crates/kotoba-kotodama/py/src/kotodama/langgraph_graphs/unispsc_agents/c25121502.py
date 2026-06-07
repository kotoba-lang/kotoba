# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25121502 — Locomotive (segment 25).

Bespoke graph logic for locomotive asset management, validating engine
specifications, tractive effort, and operational readiness.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25121502"
UNISPSC_TITLE = "Locomotive"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25121502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Locomotive
    engine_type: str  # e.g., Diesel-Electric, Electric, Steam
    tractive_effort_kn: float
    service_status: str
    gauge_mm: int


def validate_specs(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    engine = inp.get("engine_type", "Diesel-Electric")
    gauge = inp.get("gauge_mm", 1435)  # Standard gauge default
    effort = float(inp.get("tractive_effort_kn", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "engine_type": engine,
        "gauge_mm": gauge,
        "tractive_effort_kn": effort,
    }


def check_maintenance(state: State) -> dict[str, Any]:
    # Logic to determine service status based on tractive effort and gauge compatibility
    effort = state.get("tractive_effort_kn", 0.0)
    status = "Ready for Service" if effort > 0 else "Under Inspection"

    return {
        "log": [f"{UNISPSC_CODE}:check_maintenance"],
        "service_status": status,
    }


def finalize_asset(state: State) -> dict[str, Any]:
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "engine_type": state.get("engine_type"),
            "service_status": state.get("service_status"),
            "operational": state.get("service_status") == "Ready for Service",
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("check_maintenance", check_maintenance)
_g.add_node("finalize_asset", finalize_asset)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "check_maintenance")
_g.add_edge("check_maintenance", "finalize_asset")
_g.add_edge("finalize_asset", END)

graph = _g.compile()
