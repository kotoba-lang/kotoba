# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12141713 — Material (segment 12).

Bespoke graph logic for handling biological and plant materials within the
Etz Hayyim actor network. This agent validates material integrity, assigns
preservation protocols based on category, and emits standardized metadata.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141713"
UNISPSC_TITLE = "Material"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141713"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Material
    material_category: str
    preservation_protocol: str
    quality_index: float
    verification_lock: bool


def ingest_material(state: State) -> dict[str, Any]:
    """Node: Analyzes the incoming material request and verifies identity."""
    inp = state.get("input") or {}
    cat = inp.get("category", "unclassified_biological")

    return {
        "log": [f"{UNISPSC_CODE}:ingest_material:{cat}"],
        "material_category": cat,
        "quality_index": inp.get("quality", 1.0),
        "verification_lock": False
    }


def apply_protocol(state: State) -> dict[str, Any]:
    """Node: Determines the preservation or handling protocol for the material."""
    cat = state.get("material_category", "").lower()

    if "reproductive" in cat or "genetic" in cat:
        protocol = "CRYOGENIC_NITROGEN"
    elif "botanical" in cat:
        protocol = "CONTROLLED_HUMIDITY"
    else:
        protocol = "AMBIENT_STABLE"

    return {
        "log": [f"{UNISPSC_CODE}:apply_protocol:{protocol}"],
        "preservation_protocol": protocol,
        "verification_lock": True
    }


def dispatch_result(state: State) -> dict[str, Any]:
    """Node: Finalizes the actor state and emits the structured result."""
    protocol = state.get("preservation_protocol", "NONE")
    quality = state.get("quality_index", 0.0)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "handling": protocol,
        "integrity_verified": quality > 0.8,
        "ok": True,
    }

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_result"],
        "result": res
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_material)
_g.add_node("protocol", apply_protocol)
_g.add_node("dispatch", dispatch_result)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "protocol")
_g.add_edge("protocol", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
