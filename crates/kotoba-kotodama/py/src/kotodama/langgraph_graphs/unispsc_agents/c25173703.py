# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25173703 — Manifold.
Bespoke logic for vehicle manifold component validation and testing.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173703"
UNISPSC_TITLE = "Manifold"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173703"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    manifold_type: str
    port_count: int
    test_pressure_psi: float
    integrity_verified: bool


def validate_spec(state: State) -> dict[str, Any]:
    """Validates the mechanical specifications of the manifold."""
    inp = state.get("input") or {}
    m_type = str(inp.get("manifold_type", "exhaust"))
    ports = int(inp.get("ports", 4))
    return {
        "log": [f"{UNISPSC_CODE}:validate_spec(type={m_type}, ports={ports})"],
        "manifold_type": m_type,
        "port_count": ports,
    }


def pressure_test(state: State) -> dict[str, Any]:
    """Simulates a pneumatic pressure test on the manifold ports."""
    ports = state.get("port_count", 0)
    # Higher port counts require more rigorous testing
    psi = 45.0 + (ports * 5.0)
    return {
        "log": [f"{UNISPSC_CODE}:pressure_test(psi={psi})"],
        "test_pressure_psi": psi,
        "integrity_verified": ports > 0,
    }


def emit_certification(state: State) -> dict[str, Any]:
    """Emits the final assembly certification and metadata."""
    success = state.get("integrity_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_certification(ok={success})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "type": state.get("manifold_type"),
                "ports": state.get("port_count"),
                "psi": state.get("test_pressure_psi"),
            },
            "status": "certified" if success else "rejected",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_spec)
_g.add_node("test", pressure_test)
_g.add_node("emit", emit_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "test")
_g.add_edge("test", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
