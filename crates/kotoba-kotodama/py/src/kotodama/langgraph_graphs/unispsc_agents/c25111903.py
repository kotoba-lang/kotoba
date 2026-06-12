# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111903 — Sail Order (segment 25).

Bespoke graph logic for handling sail orders, ensuring vessel compatibility,
routing to destination ports, and manifest validation for maritime logistics.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111903"
UNISPSC_TITLE = "Sail Order"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111903"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Sail Order
    vessel_id: str
    destination_port: str
    cargo_type: str
    manifest_verified: bool
    order_status: str


def validate_sail_order(state: State) -> dict[str, Any]:
    """Validates the sail order input for required maritime parameters."""
    inp = state.get("input") or {}
    vessel = inp.get("vessel_id", "UNDEFINED")
    port = inp.get("destination_port", "UNSET")
    cargo = inp.get("cargo_type", "GENERAL")

    is_valid = vessel != "UNDEFINED" and port != "UNSET"

    return {
        "log": [f"{UNISPSC_CODE}:validate_sail_order -> {vessel} bound for {port}"],
        "vessel_id": vessel,
        "destination_port": port,
        "cargo_type": cargo,
        "order_status": "VALIDATED" if is_valid else "INVALID",
    }


def process_manifest(state: State) -> dict[str, Any]:
    """Processes and verifies the cargo manifest for the sail order."""
    status = state.get("order_status")
    cargo = state.get("cargo_type")

    # Simulate manifest verification logic
    verified = status == "VALIDATED" and cargo is not None
    log_msg = f"{UNISPSC_CODE}:process_manifest -> {'verified' if verified else 'failed'}"

    return {
        "log": [log_msg],
        "manifest_verified": verified,
        "order_status": "PROCESSED" if verified else "FAILED",
    }


def finalize_sail_order(state: State) -> dict[str, Any]:
    """Finalizes the order and generates the formal sail order result."""
    status = state.get("order_status")
    vessel = state.get("vessel_id")
    port = state.get("destination_port")
    verified = state.get("manifest_verified", False)

    success = status == "PROCESSED" and verified

    return {
        "log": [f"{UNISPSC_CODE}:finalize_sail_order -> success: {success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "vessel": vessel,
            "destination": port,
            "verified": verified,
            "ok": success,
            "did": UNISPSC_DID,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_sail_order)
_g.add_node("process", process_manifest)
_g.add_node("finalize", finalize_sail_order)

_g.add_edge(START, "validate")
_g.add_edge("validate", "process")
_g.add_edge("process", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
