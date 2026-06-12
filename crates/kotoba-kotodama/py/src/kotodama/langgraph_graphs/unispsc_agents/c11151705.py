# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11151705 — Precious Metal (segment 11).

This bespoke agent handles the lifecycle of precious metal assets, focusing
on assay verification, purity standards, and secure vault allocation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11151705"
UNISPSC_TITLE = "Precious Metal"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11151705"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Precious Metals
    metal_type: str
    purity_fineness: float
    weight_troy_oz: float
    assay_status: str
    vault_id: str


def inspect_assay(state: State) -> dict[str, Any]:
    """Performs the initial inspection and assay verification."""
    inp = state.get("input") or {}
    metal = inp.get("metal", "Gold")
    purity = inp.get("purity", 0.999)
    weight = inp.get("weight", 1.0)

    # Simple logic: anything below 0.90 fineness is rejected
    status = "Certified" if purity >= 0.90 else "Below Grade"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_assay"],
        "metal_type": metal,
        "purity_fineness": purity,
        "weight_troy_oz": weight,
        "assay_status": status,
    }


def secure_storage(state: State) -> dict[str, Any]:
    """Determines appropriate vault storage based on metal type."""
    metal = state.get("metal_type", "Unknown")
    vault = "VLT-AU-99" if metal.lower() == "gold" else "VLT-GEN-04"

    return {
        "log": [f"{UNISPSC_CODE}:secure_storage"],
        "vault_id": vault,
    }


def record_transaction(state: State) -> dict[str, Any]:
    """Finalizes the metadata and emits the asset record."""
    is_ok = state.get("assay_status") == "Certified"

    return {
        "log": [f"{UNISPSC_CODE}:record_transaction"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "Accepted" if is_ok else "Rejected",
            "vault": state.get("vault_id"),
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_assay", inspect_assay)
_g.add_node("secure_storage", secure_storage)
_g.add_node("record_transaction", record_transaction)

_g.add_edge(START, "inspect_assay")
_g.add_edge("inspect_assay", "secure_storage")
_g.add_edge("secure_storage", "record_transaction")
_g.add_edge("record_transaction", END)

graph = _g.compile()
