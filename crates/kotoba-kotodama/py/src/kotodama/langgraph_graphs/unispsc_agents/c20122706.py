# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122706"
UNISPSC_TITLE = "Grease"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122706"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    nlgi_grade: str
    thickener_base: str
    drop_point_c: int
    is_high_temp_rated: bool
    base_oil_viscosity: int


def evaluate_viscosity(state: State) -> dict[str, Any]:
    """Assess the NLGI consistency grade requirements for the grease lubricant."""
    inp = state.get("input") or {}
    target_grade = inp.get("grade", "NLGI 2")
    base_visc = inp.get("base_viscosity", 150)
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_viscosity"],
        "nlgi_grade": target_grade,
        "base_oil_viscosity": base_visc,
    }


def select_thickener(state: State) -> dict[str, Any]:
    """Determine the appropriate soap or synthetic thickener for the batch."""
    grade = state.get("nlgi_grade", "NLGI 2")
    # Industrial standard: NLGI 2 often uses Lithium Complex for versatility
    thickener = "Lithium Complex" if grade == "NLGI 2" else "Polyurea"
    return {
        "log": [f"{UNISPSC_CODE}:select_thickener"],
        "thickener_base": thickener,
        "drop_point_c": 260 if thickener == "Lithium Complex" else 240,
    }


def certify_lubricant(state: State) -> dict[str, Any]:
    """Finalize performance certification for industrial grease application."""
    drop_point = state.get("drop_point_c", 0)
    high_temp = drop_point > 250
    return {
        "log": [f"{UNISPSC_CODE}:certify_lubricant"],
        "is_high_temp_rated": high_temp,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "properties": {
                "nlgi_grade": state.get("nlgi_grade"),
                "thickener": state.get("thickener_base"),
                "drop_point": drop_point,
                "high_temp_certified": high_temp,
                "oil_viscosity_iso": state.get("base_oil_viscosity"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("evaluate", evaluate_viscosity)
_g.add_node("select", select_thickener)
_g.add_node("certify", certify_lubricant)

_g.add_edge(START, "evaluate")
_g.add_edge("evaluate", "select")
_g.add_edge("select", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
