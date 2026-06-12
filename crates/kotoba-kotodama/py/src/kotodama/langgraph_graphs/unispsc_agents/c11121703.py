# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11121703"
UNISPSC_TITLE = "Element Process"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11121703"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    geochem_sample_id: str
    target_elements: list[str]
    processing_stage: str
    purity_reached: float


def validate_geochem_input(state: State) -> dict[str, Any]:
    """Validates the incoming geochemical sample data and identification targets."""
    inp = state.get("input") or {}
    sample_id = inp.get("sample_id", "GEO-UNKNOWN")
    targets = inp.get("targets", ["Rare Earths"])
    return {
        "log": [f"{UNISPSC_CODE}:validate_geochem_input"],
        "geochem_sample_id": sample_id,
        "target_elements": targets,
        "processing_stage": "VALIDATED",
    }


def process_elemental_separation(state: State) -> dict[str, Any]:
    """Simulates high-precision chemical separation of elements from the matrix."""
    return {
        "log": [f"{UNISPSC_CODE}:process_elemental_separation"],
        "processing_stage": "SEPARATED",
        "purity_reached": 0.9995,
    }


def certify_element_purity(state: State) -> dict[str, Any]:
    """Finalizes the process by certifying the purity of the isolated elements."""
    purity = state.get("purity_reached", 0.0)
    return {
        "log": [f"{UNISPSC_CODE}:certify_element_purity"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "sample_id": state.get("geochem_sample_id"),
            "targets": state.get("target_elements"),
            "purity": purity,
            "certified": purity > 0.99,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_geochem_input)
_g.add_node("process", process_elemental_separation)
_g.add_node("certify", certify_element_purity)

_g.add_edge(START, "validate")
_g.add_edge("validate", "process")
_g.add_edge("process", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
