# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111908 —  (segment 26).

Bespoke graph logic for evaluating photovoltaic performance and certifying
solar cell characteristics within the power generation machinery domain.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111908"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111908"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    efficiency_pct: float
    voc_volts: float
    substrate_type: str
    quality_verified: bool


def ingest_specifications(state: State) -> dict[str, Any]:
    """Node: Extract and validate photovoltaic parameters."""
    inp = state.get("input") or {}
    eff = float(inp.get("efficiency", 0.0))
    voc = float(inp.get("voc", 0.0))
    sub = str(inp.get("substrate", "monocrystalline silicon"))

    return {
        "log": [f"{UNISPSC_CODE}:ingest_specifications"],
        "efficiency_pct": eff,
        "voc_volts": voc,
        "substrate_type": sub,
    }


def analyze_cell_quality(state: State) -> dict[str, Any]:
    """Node: Evaluate efficiency against technical benchmarks."""
    eff = state.get("efficiency_pct", 0.0)
    # Standard high-performance threshold for commercial cells
    is_efficient = eff >= 18.5

    return {
        "log": [f"{UNISPSC_CODE}:analyze_cell_quality"],
        "quality_verified": is_efficient,
    }


def generate_certification(state: State) -> dict[str, Any]:
    """Node: Construct the final domain-specific actor response."""
    verified = state.get("quality_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:generate_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "verified": verified,
            "specs": {
                "efficiency": state.get("efficiency_pct"),
                "voltage_oc": state.get("voc_volts"),
                "substrate": state.get("substrate_type"),
            },
            "status": "certified" if verified else "non-compliant",
        },
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_specifications)
_g.add_node("analyze", analyze_cell_quality)
_g.add_node("generate", generate_certification)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "analyze")
_g.add_edge("analyze", "generate")
_g.add_edge("generate", END)

graph = _g.compile()
