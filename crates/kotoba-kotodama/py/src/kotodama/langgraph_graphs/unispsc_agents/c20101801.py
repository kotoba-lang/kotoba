# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20101801"
UNISPSC_TITLE = "Commodity"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20101801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for mining and well drilling commodities
    specification_match: bool
    batch_identifier: str
    quality_index: float
    origin_verified: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Check if the provided commodity data matches required industrial standards."""
    inp = state.get("input") or {}
    req_grade = inp.get("required_grade", 80)
    actual_grade = inp.get("actual_grade", 85)

    match = actual_grade >= req_grade
    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications(match={match})"],
        "specification_match": match,
        "quality_index": float(actual_grade)
    }


def verify_origin(state: State) -> dict[str, Any]:
    """Verify the geological or manufacturing origin of the commodity batch."""
    inp = state.get("input") or {}
    source = inp.get("origin", "UNKNOWN")

    verified = source != "UNKNOWN"
    return {
        "log": [f"{UNISPSC_CODE}:verify_origin(source={source}, verified={verified})"],
        "origin_verified": verified,
        "batch_identifier": f"BATCH-{UNISPSC_CODE}-{source}"
    }


def emit_commodity_status(state: State) -> dict[str, Any]:
    """Finalize the state and emit the compliance and process result."""
    is_valid = state.get("specification_match", False) and state.get("origin_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_commodity_status(valid={is_valid})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": is_valid,
            "batch": state.get("batch_identifier", "PENDING"),
            "quality": state.get("quality_index", 0.0)
        }
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("verify", verify_origin)
_g.add_node("emit", emit_commodity_status)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
