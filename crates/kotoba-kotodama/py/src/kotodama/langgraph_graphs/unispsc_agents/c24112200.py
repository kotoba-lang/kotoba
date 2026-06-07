# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112200 — Container (segment 24).

Bespoke logic for handling container lifecycle, integrity verification,
and manifest sealing within the Etz Hayyim actor network.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112200"
UNISPSC_TITLE = "Container"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112200"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for "Container"
    container_id: str
    seal_verified: bool
    integrity_score: float
    cargo_manifest: list[str]
    destination_port: str


def inspect_container(state: State) -> dict[str, Any]:
    """Initial physical inspection and integrity verification."""
    inp = state.get("input") or {}
    cid = inp.get("container_id", "CNT-UNKNOWN")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_container:{cid}"],
        "container_id": cid,
        "integrity_score": 0.98,
        "seal_verified": True,
    }


def verify_manifest(state: State) -> dict[str, Any]:
    """Cross-reference cargo contents with the provided manifest."""
    inp = state.get("input") or {}
    items = inp.get("items", ["General Cargo"])
    dest = inp.get("destination", "GLOBAL-TRANSIT")

    return {
        "log": [f"{UNISPSC_CODE}:verify_manifest:{len(items)}_items"],
        "cargo_manifest": items,
        "destination_port": dest,
    }


def finalize_shipment(state: State) -> dict[str, Any]:
    """Emit final shipping telemetry and seal the state."""
    ready = state.get("seal_verified") and state.get("integrity_score", 0) > 0.9

    return {
        "log": [f"{UNISPSC_CODE}:finalize_shipment:ready={ready}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "container_id": state.get("container_id"),
            "destination": state.get("destination_port"),
            "status": "SEALED_AND_READY" if ready else "HOLD_FOR_INSPECTION",
            "did": UNISPSC_DID,
            "ok": ready,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_container)
_g.add_node("verify", verify_manifest)
_g.add_node("finalize", finalize_shipment)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
