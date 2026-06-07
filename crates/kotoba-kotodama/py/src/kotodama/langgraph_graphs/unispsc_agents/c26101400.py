# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101400"
UNISPSC_TITLE = "Motor Part"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101400"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Motor Part
    spec_verification: bool
    compatibility_score: float
    integrity_checked: bool
    batch_identifier: str


def inspect_specs(state: State) -> dict[str, Any]:
    """Inspects motor part specifications for compliance with engineering standards."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})
    # Check for core motor attributes: voltage or torque
    has_specs = "voltage" in specs or "torque" in specs
    return {
        "log": [f"{UNISPSC_CODE}:inspect_specs"],
        "spec_verification": has_specs,
        "integrity_checked": True,
    }


def assess_compatibility(state: State) -> dict[str, Any]:
    """Calculates compatibility score based on motor series and assembly requirements."""
    inp = state.get("input") or {}
    series = inp.get("series", "generic")
    # Simulation: obsolete series have low compatibility
    score = 0.95 if series != "obsolete" else 0.10
    return {
        "log": [f"{UNISPSC_CODE}:assess_compatibility"],
        "compatibility_score": score,
        "batch_identifier": f"LOT-{series.upper()}-2026",
    }


def catalog_part(state: State) -> dict[str, Any]:
    """Finalizes the part record within the UNISPSC asset registry."""
    is_valid = state.get("spec_verification", False)
    score = state.get("compatibility_score", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:catalog_part"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "verified": is_valid and score > 0.5,
            "batch": state.get("batch_identifier"),
            "integrity_ok": state.get("integrity_checked"),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_specs)
_g.add_node("assess", assess_compatibility)
_g.add_node("catalog", catalog_part)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "assess")
_g.add_edge("assess", "catalog")
_g.add_edge("catalog", END)

graph = _g.compile()
