# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11191605"
UNISPSC_TITLE = "Refining"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11191605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    feedstock_quality: float
    refinement_temp: float
    purity_attained: float
    byproduct_yield: float


def inspect_feed(state: State) -> dict[str, Any]:
    """Validates the input material quality for the refining process."""
    inp = state.get("input") or {}
    quality = float(inp.get("quality", 0.82))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_feed quality={quality}"],
        "feedstock_quality": quality,
        "refinement_temp": 450.0 + (1.0 - quality) * 100.0,
    }


def refine_batch(state: State) -> dict[str, Any]:
    """Simulates the chemical or physical refinement of the material."""
    quality = state.get("feedstock_quality", 0.0)
    # Refinement efficiency model: higher quality feed yields better purity
    purity = quality + (1.0 - quality) * 0.94
    return {
        "log": [f"{UNISPSC_CODE}:refine_batch purity={purity:.4f}"],
        "purity_attained": purity,
        "byproduct_yield": (1.0 - purity) * 0.8,
    }


def finalize_output(state: State) -> dict[str, Any]:
    """Finalizes refinement data and prepares the agent result."""
    purity = state.get("purity_attained", 0.0)
    is_merchantable = purity > 0.95
    return {
        "log": [f"{UNISPSC_CODE}:finalize_output merchantable={is_merchantable}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "purity": purity,
            "byproduct": state.get("byproduct_yield"),
            "ok": is_merchantable,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_feed)
_g.add_node("refine", refine_batch)
_g.add_node("finalize", finalize_output)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "refine")
_g.add_edge("refine", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
