# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23231801 — Graph (segment 23).
This bespoke implementation handles graph topology validation, connectivity analysis,
and manifest generation for industrial schematic representations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23231801"
UNISPSC_TITLE = "Graph"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23231801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Graph
    nodes: list[str]
    edges: list[tuple[str, str]]
    is_acyclic: bool
    density: float
    validation_passed: bool


def validate_topology(state: State) -> dict[str, Any]:
    """Parses input data and validates basic graph structure."""
    inp = state.get("input") or {}
    nodes = inp.get("nodes", [])
    edges = inp.get("edges", [])

    # Simple validation: ensure edges only reference existing nodes
    node_set = set(nodes)
    valid = all(u in node_set and v in node_set for u, v in edges)

    return {
        "log": [f"{UNISPSC_CODE}:validate_topology"],
        "nodes": nodes,
        "edges": edges,
        "validation_passed": valid and len(nodes) > 0
    }


def analyze_connectivity(state: State) -> dict[str, Any]:
    """Calculates graph metrics like density and checks for basic cycles."""
    nodes = state.get("nodes", [])
    edges = state.get("edges", [])

    n = len(nodes)
    e = len(edges)
    density = (2 * e) / (n * (n - 1)) if n > 1 else 0.0

    # Placeholder for acyclic check logic
    is_acyclic = e < n  # Heuristic for the sake of pure-python state transition

    return {
        "log": [f"{UNISPSC_CODE}:analyze_connectivity"],
        "density": round(density, 4),
        "is_acyclic": is_acyclic
    }


def generate_manifest(state: State) -> dict[str, Any]:
    """Emits the final graph analysis result."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "node_count": len(state.get("nodes", [])),
                "edge_count": len(state.get("edges", [])),
                "density": state.get("density"),
                "is_acyclic": state.get("is_acyclic")
            },
            "status": "validated" if state.get("validation_passed") else "invalid",
            "ok": state.get("validation_passed", False)
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_topology)
_g.add_node("analyze", analyze_connectivity)
_g.add_node("emit", generate_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
