# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111807 — Paper (segment 14).

Bespoke graph logic for handling paper product specifications,
inventory validation, and order finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111807"
UNISPSC_TITLE = "Paper"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111807"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    grammage_gsm: int
    finish_type: str
    brightness_level: int
    recycled_content_pct: float
    is_fsc_certified: bool


def specify_grade(state: State) -> dict[str, Any]:
    """Analyzes input to determine paper grade and technical specifications."""
    inp = state.get("input") or {}
    grammage = inp.get("gsm", 80)
    finish = inp.get("finish", "matte")
    return {
        "log": [f"{UNISPSC_CODE}:specify_grade"],
        "grammage_gsm": grammage,
        "finish_type": finish,
        "is_fsc_certified": inp.get("fsc", True)
    }


def validate_stock(state: State) -> dict[str, Any]:
    """Simulates checking mill availability for the requested paper specifications."""
    grammage = state.get("grammage_gsm", 80)
    brightness = 92 if grammage < 100 else 96
    return {
        "log": [f"{UNISPSC_CODE}:validate_stock"],
        "brightness_level": brightness,
        "recycled_content_pct": 30.0
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Constructs the final product manifest and metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "specs": {
                "gsm": state.get("grammage_gsm"),
                "finish": state.get("finish_type"),
                "brightness": state.get("brightness_level"),
                "fsc": state.get("is_fsc_certified")
            },
            "did": UNISPSC_DID,
            "status": "ready"
        },
    }


_g = StateGraph(State)
_g.add_node("specify", specify_grade)
_g.add_node("stock_check", validate_stock)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "specify")
_g.add_edge("specify", "stock_check")
_g.add_edge("stock_check", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
