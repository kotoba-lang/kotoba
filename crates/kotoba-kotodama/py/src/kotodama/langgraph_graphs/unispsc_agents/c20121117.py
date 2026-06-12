# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121117"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121117"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    power_kw: float
    voltage: int
    is_explosion_proof: bool
    efficiency_rating: str


def validate_specs(state: State) -> dict[str, Any]:
    """Initial node to parse and validate motor power and voltage specifications."""
    inp = state.get("input") or {}
    kw = float(inp.get("power_kw", 0.0))
    v = int(inp.get("voltage", 400))
    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "power_kw": kw,
        "voltage": v,
    }


def verify_mining_compliance(state: State) -> dict[str, Any]:
    """Applies safety standards specific to Mining and Well Drilling environments."""
    v = state.get("voltage", 0)
    # Heavy duty mining motors often require explosion proofing for safety compliance
    ex_proof = v >= 400 or state.get("power_kw", 0) > 100
    return {
        "log": [f"{UNISPSC_CODE}:verify_mining_compliance"],
        "is_explosion_proof": ex_proof,
        "efficiency_rating": "IE3 Premium" if ex_proof else "IE2 High",
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Compiles the final state into the structured result for deployment."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "power_kw": state.get("power_kw"),
                "voltage": state.get("voltage"),
                "safety_rating": "Ex-Proof" if state.get("is_explosion_proof") else "Standard",
                "efficiency": state.get("efficiency_rating"),
            },
            "status": "validated",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("compliance", verify_mining_compliance)
_g.add_node("finalize", finalize_asset_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compliance")
_g.add_edge("compliance", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
