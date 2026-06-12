# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121311 — Crane Part (segment 20).
Bespoke logic for crane part validation, load-rating verification, and asset recording.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121311"
UNISPSC_TITLE = "Crane Part"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121311"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    serial_number: str
    material_grade: str
    max_load_rating: float
    integrity_verified: bool


def validate_part(state: State) -> dict[str, Any]:
    """Validates the physical serial number and basic material properties."""
    inp = state.get("input") or {}
    sn = inp.get("sn", "CN-UNKNOWN")
    grade = inp.get("grade", "ASTM-A36")

    # Logic: Validate serial prefix for Crane Parts (Segment 20)
    is_valid_prefix = sn.startswith("CN-") or sn.startswith("CR-")

    return {
        "log": [f"{UNISPSC_CODE}:validate_part:{sn}"],
        "serial_number": sn,
        "material_grade": grade,
        "integrity_verified": is_valid_prefix,
    }


def verify_load_rating(state: State) -> dict[str, Any]:
    """Calculates safe operating load based on material grade."""
    grade = state.get("material_grade", "Standard")
    # Simulate load rating lookup
    rating_map = {"ASTM-A36": 5000.0, "ASTM-A514": 12000.0}
    rating = rating_map.get(grade, 2000.0)

    return {
        "log": [f"{UNISPSC_CODE}:verify_load_rating:{rating}kg"],
        "max_load_rating": rating,
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Prepares the final structured record for the crane component."""
    sn = state.get("serial_number")
    verified = state.get("integrity_verified", False)
    rating = state.get("max_load_rating", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "asset": {
                "serial": sn,
                "load_limit": f"{rating}kg",
                "grade": state.get("material_grade"),
                "status": "APPROVED" if verified else "QUARANTINE"
            },
            "ok": verified,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_part)
_g.add_node("verify_load", verify_load_rating)
_g.add_node("finalize", finalize_asset_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify_load")
_g.add_edge("verify_load", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
