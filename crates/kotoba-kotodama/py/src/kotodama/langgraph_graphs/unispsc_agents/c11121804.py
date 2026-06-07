# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11121804 — Natural Gasoline (segment 11).

Bespoke graph logic for handling natural gasoline feedstock specifications,
including RVP (Reid Vapor Pressure) and octane verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11121804"
UNISPSC_TITLE = "Natural Gasoline"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11121804"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Natural Gasoline
    rvp_psi: float
    octane_rating: float
    sulfur_ppm: float
    is_merchantable: bool


def inspect_raw_stock(state: State) -> dict[str, Any]:
    """Inspects the incoming natural gasoline specifications."""
    inp = state.get("input") or {}
    rvp = float(inp.get("rvp_psi", 10.5))
    octane = float(inp.get("octane_rating", 70.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_raw_stock: rvp={rvp}, octane={octane}"],
        "rvp_psi": rvp,
        "octane_rating": octane,
        "sulfur_ppm": float(inp.get("sulfur_ppm", 5.0)),
    }


def verify_blending_spec(state: State) -> dict[str, Any]:
    """Verifies if the stock meets merchantable blending standards."""
    rvp = state.get("rvp_psi", 0.0)
    # Typical Natural Gasoline RVP (Reid Vapor Pressure) is 10-15 psi
    is_ok = 9.0 <= rvp <= 15.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_blending_spec: merchantable={is_ok}"],
        "is_merchantable": is_ok,
    }


def finalize_batch(state: State) -> dict[str, Any]:
    """Finalizes the processing and prepares the output record."""
    is_ok = state.get("is_merchantable", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": is_ok,
            "properties": {
                "rvp": state.get("rvp_psi"),
                "octane": state.get("octane_rating"),
                "sulfur": state.get("sulfur_ppm"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_raw_stock)
_g.add_node("verify", verify_blending_spec)
_g.add_node("finalize", finalize_batch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
