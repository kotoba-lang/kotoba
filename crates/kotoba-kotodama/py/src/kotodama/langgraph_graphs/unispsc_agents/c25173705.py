# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25173705 — Graph (segment 25).

Bespoke logic for graph structure validation, connectivity analysis, and
topological metadata extraction. This agent processes graph data for
transportation and technical drawing contexts within segment 25.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173705"
UNISPSC_TITLE = "Graph"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173705"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for "Graph"
    nodes_list: list[str]
    edges_list: list[tuple[str, str]]
    is_valid_structure: bool
    topology_type: str


def ingest_graph(state: State) -> dict[str, Any]:
    """Parses and validates the input graph structure from the payload."""
    inp = state.get("input") or {}
    nodes = inp.get("nodes", [])
    raw_edges = inp.get("edges", [])

    # Standardize edges as tuples
    edges = []
    for e in raw_edges:
        if isinstance(e, (list, tuple)) and len(e) == 2:
            edges.append((str(e[0]), str(e[1])))

    is_valid = isinstance(nodes, list) and len(nodes) > 0
    return {
        "log": [f"{UNISPSC_CODE}:ingest_graph"],
        "nodes_list": [str(n) for n in nodes],
        "edges_list": edges,
        "is_valid_structure": is_valid,
    }


def analyze_connectivity(state: State) -> dict[str, Any]:
    """Performs a basic connectivity and density analysis on the ingested graph."""
    if not state.get("is_valid_structure"):
        return {"log": [f"{UNISPSC_CODE}:analyze_connectivity:skipped"]}

    nodes = state.get("nodes_list", [])
    edges = state.get("edges_list", [])

    # Calculate degree of connectivity
    node_set = set(nodes)
    connected_nodes = set()
    for u, v in edges:
        connected_nodes.add(u)
        connected_nodes.add(v)

    is_fully_covered = node_set.issubset(connected_nodes)
    density = "dense" if len(edges) >= len(nodes) else "sparse"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_connectivity"],
        "topology_type": f"{density}_coverage_{'full' if is_fully_covered else 'partial'}"
    }


def finalize_graph_output(state: State) -> dict[str, Any]:
    """Produces the final diagnostic result and metadata for the Graph agent."""
    is_ok = state.get("is_valid_structure", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_graph_output"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "analysis": {
                "node_count": len(state.get("nodes_list", [])),
                "edge_count": len(state.get("edges_list", [])),
                "topology": state.get("topology_type", "unknown"),
            },
            "ok": is_ok,
            "status": "validated" if is_ok else "invalid_input"
        }
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_graph)
_g.add_node("analyze", analyze_connectivity)
_g.add_node("finalize", finalize_graph_output)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
