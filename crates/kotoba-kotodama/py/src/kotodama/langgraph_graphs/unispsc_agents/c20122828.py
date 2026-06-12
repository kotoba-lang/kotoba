# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122828 — Connector (segment 20).

Bespoke graph for managing connector specifications and integrity verification
within the mining and well drilling machinery context.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122828"
UNISPSC_TITLE = "Connector"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122828"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Connector
    connection_type: str
    material_spec: str
    pressure_rating_psi: int
    seal_integrity_verified: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the physical specifications of the connector."""
    inp = state.get("input") or {}
    conn_type = inp.get("connection_type", "standard_threaded")
    material = inp.get("material", "AISI_4140")
    pressure = inp.get("pressure_rating", 5000)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "connection_type": conn_type,
        "material_spec": material,
        "pressure_rating_psi": pressure,
    }


def verify_seal(state: State) -> dict[str, Any]:
    """Checks seal integrity against the required pressure rating."""
    pressure = state.get("pressure_rating_psi", 0)
    # Simulate a verification process for deep-well environments
    is_safe = pressure <= 20000
    return {
        "log": [f"{UNISPSC_CODE}:verify_seal"],
        "seal_integrity_verified": is_safe,
    }


def finalize_connection(state: State) -> dict[str, Any]:
    """Emits the final validation result for the connector."""
    verified = state.get("seal_integrity_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_connection"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": verified,
            "details": {
                "connection_type": state.get("connection_type"),
                "material": state.get("material_spec"),
                "pressure_psi": state.get("pressure_rating_psi"),
                "certified": verified,
            },
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("verify_seal", verify_seal)
_g.add_node("finalize_connection", finalize_connection)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "verify_seal")
_g.add_edge("verify_seal", "finalize_connection")
_g.add_edge("finalize_connection", END)

graph = _g.compile()
