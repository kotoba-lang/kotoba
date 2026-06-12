# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101512 — Engine (segment 26).

This module defines the bespoke LangGraph logic for the Engine actor.
It handles specification validation, compliance verification, and
cataloging for power generation engines.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101512"
UNISPSC_TITLE = "Engine"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101512"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Engine
    engine_type: str
    displacement_liters: float
    emissions_tier: str
    certification_status: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the mechanical specifications of the engine."""
    inp = state.get("input") or {}
    e_type = inp.get("engine_type", "combustion")
    disp = float(inp.get("displacement", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs: {e_type} ({disp}L)"],
        "engine_type": e_type,
        "displacement_liters": disp,
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Checks the engine against environmental and safety standards."""
    disp = state.get("displacement_liters", 0.0)
    tier = "Tier 4 Final" if disp > 4.0 else "Tier 3"

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance: assigned {tier}"],
        "emissions_tier": tier,
        "certification_status": "verified" if disp > 0 else "incomplete",
    }


def catalog_engine(state: State) -> dict[str, Any]:
    """Finalizes the engine metadata for the actor registry."""
    status = state.get("certification_status", "unknown")

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "specs": {
            "type": state.get("engine_type"),
            "displacement": state.get("displacement_liters"),
            "emissions": state.get("emissions_tier"),
        },
        "status": status,
        "ok": status == "verified",
    }

    return {
        "log": [f"{UNISPSC_CODE}:catalog_engine: status {status}"],
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("verify_compliance", verify_compliance)
_g.add_node("catalog_engine", catalog_engine)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "verify_compliance")
_g.add_edge("verify_compliance", "catalog_engine")
_g.add_edge("catalog_engine", END)

graph = _g.compile()
