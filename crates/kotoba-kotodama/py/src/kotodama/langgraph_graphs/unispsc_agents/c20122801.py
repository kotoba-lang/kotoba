# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122801 — Connector (segment 20).

Bespoke graph for mining and drilling connectors, managing specifications,
safety margin verification, and final configuration reporting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122801"
UNISPSC_TITLE = "Connector"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Connector-specific domain fields
    connection_type: str
    pressure_rating_psi: int
    material_grade: str
    is_explosion_proof: bool
    verification_status: str


def analyze_specifications(state: State) -> dict[str, Any]:
    """Extracts and validates basic connector specifications from input."""
    inp = state.get("input") or {}
    conn_type = inp.get("type", "threaded")
    pressure = int(inp.get("pressure_psi", 3000))
    material = inp.get("material", "Carbon Steel")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_specifications"],
        "connection_type": conn_type,
        "pressure_rating_psi": pressure,
        "material_grade": material,
    }


def verify_safety_standards(state: State) -> dict[str, Any]:
    """Checks if the connector meets safety thresholds for drilling environments."""
    pressure = state.get("pressure_rating_psi", 0)
    # High-pressure connectors (>10k PSI) require specialized certification
    requires_cert = pressure > 10000
    is_ex_proof = state.get("input", {}).get("explosion_proof", False)

    status = "VERIFIED"
    if requires_cert and not is_ex_proof:
        status = "CERTIFICATION_REQUIRED"

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_standards"],
        "is_explosion_proof": is_ex_proof,
        "verification_status": status,
    }


def finalize_asset_data(state: State) -> dict[str, Any]:
    """Compiles the final result based on analyzed and verified state."""
    status = state.get("verification_status", "UNKNOWN")
    is_ok = status == "VERIFIED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "connection": state.get("connection_type"),
                "max_pressure": state.get("pressure_rating_psi"),
                "material": state.get("material_grade"),
                "ex_proof": state.get("is_explosion_proof"),
                "status": status,
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_specifications)
_g.add_node("verify", verify_safety_standards)
_g.add_node("finalize", finalize_asset_data)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
