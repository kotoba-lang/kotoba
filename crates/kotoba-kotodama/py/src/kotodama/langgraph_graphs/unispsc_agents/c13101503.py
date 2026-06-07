# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13101503"
UNISPSC_TITLE = "Diamond Process"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13101503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Diamond Process (Segment 13: Resin/Industrial Material)
    carat_density: float
    curing_pressure: int
    impurity_threshold: float
    process_certified: bool


def inspect_raw_substrate(state: State) -> dict[str, Any]:
    """Node 1: Inspects the incoming material substrate for Diamond Process compatibility."""
    inp = state.get("input") or {}
    density = float(inp.get("density", 3.51))  # Standard diamond density
    threshold = float(inp.get("impurity_max", 0.02))
    pressure = int(inp.get("pressure_psi", 55000))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_raw_substrate"],
        "carat_density": density,
        "impurity_threshold": threshold,
        "curing_pressure": pressure,
    }


def execute_molecular_bonding(state: State) -> dict[str, Any]:
    """Node 2: Executes the carbon-molecular bonding sequence of the Diamond Process."""
    pressure = state.get("curing_pressure", 0)
    threshold = state.get("impurity_threshold", 1.0)

    # Diamond Process requires high pressure and low impurities
    is_success = pressure >= 50000 and threshold <= 0.05

    return {
        "log": [f"{UNISPSC_CODE}:execute_molecular_bonding -> success: {is_success}"],
        "process_certified": is_success,
    }


def emit_industrial_certificate(state: State) -> dict[str, Any]:
    """Node 3: Issues the final industrial certificate for the processed material."""
    certified = state.get("process_certified", False)
    density = state.get("carat_density", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:emit_industrial_certificate"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_status": "VALIDATED" if certified else "REJECTED",
            "final_density": density,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_raw_substrate)
_g.add_node("process", execute_molecular_bonding)
_g.add_node("emit", emit_industrial_certificate)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "process")
_g.add_edge("process", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
