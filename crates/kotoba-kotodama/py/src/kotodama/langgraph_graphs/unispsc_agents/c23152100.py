# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23152100 — Graph (segment 23).
Provides bespoke processing for industrial graphing media and layout specifications.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23152100"
UNISPSC_TITLE = "Graph"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23152100"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Graph
    graph_topology: str
    grid_resolution: str
    axis_scaling: str
    is_certified: bool


def ingest_specifications(state: State) -> dict[str, Any]:
    """Ingests and sanitizes graph layout specifications."""
    inp = state.get("input") or {}
    topology = inp.get("topology", "rectilinear")
    return {
        "log": [f"{UNISPSC_CODE}:ingest_specifications"],
        "graph_topology": topology,
        "is_certified": "spec_sheet" in inp,
    }


def compute_layout(state: State) -> dict[str, Any]:
    """Calculates the physical grid resolution and axis scaling."""
    topology = state.get("graph_topology", "rectilinear")
    res = "0.1mm" if topology == "rectilinear" else "1.0 degree"
    scale = "logarithmic" if "log" in topology else "linear"
    return {
        "log": [f"{UNISPSC_CODE}:compute_layout"],
        "grid_resolution": res,
        "axis_scaling": scale,
    }


def generate_manifest(state: State) -> dict[str, Any]:
    """Generates the final production manifest for the graph product."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "topology": state.get("graph_topology"),
                "resolution": state.get("grid_resolution"),
                "scaling": state.get("axis_scaling"),
                "certified": state.get("is_certified"),
            },
            "status": "active",
        },
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_specifications)
_g.add_node("layout", compute_layout)
_g.add_node("manifest", generate_manifest)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "layout")
_g.add_edge("layout", "manifest")
_g.add_edge("manifest", END)

graph = _g.compile()
