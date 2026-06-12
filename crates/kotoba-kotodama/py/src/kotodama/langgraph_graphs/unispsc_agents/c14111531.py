# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111531 — Paper (segment 14).

Bespoke logic for paper manufacturing and inventory management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111531"
UNISPSC_TITLE = "Paper"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111531"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    gsm_weight: int
    finish: str
    is_fsc_certified: bool
    recycled_percentage: float


def validate_specification(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    gsm = inp.get("gsm", 80)
    finish = inp.get("finish", "uncoated")

    # Simple validation: Paper usually ranges from 40 to 450 GSM
    valid_gsm = 40 <= gsm <= 450

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification(gsm={gsm}, finish={finish})"],
        "gsm_weight": gsm,
        "finish": finish,
        "is_fsc_certified": inp.get("fsc", False)
    }


def assess_sustainability(state: State) -> dict[str, Any]:
    # Logic to calculate environmental impact score
    recycled = state.get("input", {}).get("recycled_content", 0.0)
    certified = state.get("is_fsc_certified", False)

    impact_score = "high"
    if certified and recycled > 0.5:
        impact_score = "low"
    elif certified or recycled > 0.3:
        impact_score = "medium"

    return {
        "log": [f"{UNISPSC_CODE}:assess_sustainability(recycled={recycled}, impact={impact_score})"],
        "recycled_percentage": recycled
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specs": {
                "gsm": state.get("gsm_weight"),
                "finish": state.get("finish"),
                "recycled": state.get("recycled_percentage"),
                "fsc": state.get("is_fsc_certified")
            },
            "status": "ready_for_dispatch",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specification)
_g.add_node("sustainability", assess_sustainability)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "sustainability")
_g.add_edge("sustainability", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
