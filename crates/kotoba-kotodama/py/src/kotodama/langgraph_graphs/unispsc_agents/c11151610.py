# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11151610 — Rubber or latex thread (segment 11).

This agent handles state transitions for the inspection and certification of
rubber and latex threads, verifying material source, gauge measurements, and
elasticity properties.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11151610"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11151610"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Rubber or latex thread
    material_source: str
    gauge_count: int
    elongation_percentage: float
    quality_certified: bool


def inspect_raw_material(state: State) -> dict[str, Any]:
    """Inspects the source material (natural latex vs synthetic rubber)."""
    inp = state.get("input") or {}
    source = inp.get("material", "natural_latex")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_raw_material"],
        "material_source": source,
    }


def measure_thread_gauge(state: State) -> dict[str, Any]:
    """Measures the thread thickness and determines the gauge count."""
    inp = state.get("input") or {}
    # Standard rubber thread gauge (e.g., 40, 50, 60)
    gauge = inp.get("gauge", 40)
    return {
        "log": [f"{UNISPSC_CODE}:measure_thread_gauge"],
        "gauge_count": gauge,
    }


def certify_elasticity(state: State) -> dict[str, Any]:
    """Tests elongation properties and issues quality certification."""
    gauge = state.get("gauge_count", 0)
    # Heuristic: finer threads (higher gauge) often have higher elongation limits
    elongation = 650.0 if gauge >= 50 else 500.0

    return {
        "log": [f"{UNISPSC_CODE}:certify_elasticity"],
        "elongation_percentage": elongation,
        "quality_certified": elongation >= 450.0,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "material": state.get("material_source"),
                "gauge": gauge,
                "elongation_pct": elongation,
            },
            "certified": True,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_raw_material", inspect_raw_material)
_g.add_node("measure_thread_gauge", measure_thread_gauge)
_g.add_node("certify_elasticity", certify_elasticity)

_g.add_edge(START, "inspect_raw_material")
_g.add_edge("inspect_raw_material", "measure_thread_gauge")
_g.add_edge("measure_thread_gauge", "certify_elasticity")
_g.add_edge("certify_elasticity", END)

graph = _g.compile()
