# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101610 — Graph (segment 24).

Bespoke graph logic for UNISPSC 24101610, handling structural graph data
validation and topological metadata extraction.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101610"
UNISPSC_TITLE = "Graph"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101610"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for "Graph"
    graph_id: str
    nodes: list[str]
    edges: list[tuple[str, str]]
    is_directed: bool
    is_valid: bool


def ingest_graph(state: State) -> dict[str, Any]:
    """Parses raw input into graph components."""
    inp = state.get("input") or {}
    raw_nodes = inp.get("nodes", [])
    raw_edges = inp.get("edges", [])

    return {
        "log": [f"{UNISPSC_CODE}:ingest_graph"],
        "nodes": [str(n) for n in raw_nodes],
        "edges": [(str(u), str(v)) for u, v in raw_edges],
        "graph_id": inp.get("id", "default-graph"),
        "is_directed": inp.get("directed", True),
    }


def validate_topology(state: State) -> dict[str, Any]:
    """Ensures all edges refer to existing nodes."""
    nodes_set = set(state.get("nodes", []))
    edges = state.get("edges", [])

    # Validation logic: check if every edge endpoint is in the node list
    valid = all(u in nodes_set and v in nodes_set for u, v in edges)

    return {
        "log": [f"{UNISPSC_CODE}:validate_topology"],
        "is_valid": valid,
    }


def synthesize_result(state: State) -> dict[str, Any]:
    """Constructs the final actor response."""
    nodes = state.get("nodes", [])
    edges = state.get("edges", [])
    is_valid = state.get("is_valid", False)

    return {
        "log": [f"{UNISPSC_CODE}:synthesize_result"],
        "result": {
            "actor": UNISPSC_DID,
            "graph_id": state.get("graph_id"),
            "metrics": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "valid": is_valid,
            },
            "status": "success" if is_valid else "invalid_topology",
        },
    }


_g = StateGraph(State)

_g.add_node("ingest", ingest_graph)
_g.add_node("validate", validate_topology)
_g.add_node("synthesize", synthesize_result)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "validate")
_g.add_edge("validate", "synthesize")
_g.add_edge("synthesize", END)

graph = _g.compile()
