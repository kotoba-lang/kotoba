# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24131504 — Container (segment 24).
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24131504"
UNISPSC_TITLE = "Container"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24131504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    volume_liters: float
    material_type: str
    seal_integrity: bool
    batch_id: str


def validate_container(state: State) -> dict[str, Any]:
    """Validates basic physical properties of the container."""
    inp = state.get("input") or {}
    vol = float(inp.get("volume", 100.0))
    mat = str(inp.get("material", "Industrial Plastic"))
    return {
        "log": [f"{UNISPSC_CODE}:validate_container"],
        "volume_liters": vol,
        "material_type": mat,
    }


def check_integrity(state: State) -> dict[str, Any]:
    """Checks the structural integrity based on volume and material."""
    vol = state.get("volume_liters", 0.0)
    # Industrial rule: large containers need manual certification
    integrity = True if vol < 1000.0 else False
    return {
        "log": [f"{UNISPSC_CODE}:check_integrity"],
        "seal_integrity": integrity,
        "batch_id": f"CONT-{UNISPSC_CODE}-{int(vol)}",
    }


def emit_manifest(state: State) -> dict[str, Any]:
    """Generates the final container record for the logistics system."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch": state.get("batch_id"),
            "status": "approved" if state.get("seal_integrity") else "flagged_for_review",
            "metadata": {
                "material": state.get("material_type"),
                "capacity": state.get("volume_liters"),
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_container)
_g.add_node("integrity", check_integrity)
_g.add_node("emit", emit_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "integrity")
_g.add_edge("integrity", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
