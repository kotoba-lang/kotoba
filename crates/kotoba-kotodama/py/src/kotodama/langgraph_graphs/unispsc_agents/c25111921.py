# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111921 — Marine (segment 25).
Bespoke logic for marine animal logistics and environmental monitoring.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111921"
UNISPSC_TITLE = "Marine"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111921"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Marine animals
    water_salinity: float
    oxygen_level: float
    habitat_integrity: bool
    specimen_count: int
    health_certified: bool


def inspect_habitat(state: State) -> dict[str, Any]:
    """Node: Validate environmental conditions for marine specimens."""
    inp = state.get("input") or {}
    salinity = inp.get("salinity", 35.0)
    oxygen = inp.get("oxygen", 6.5)

    # Simple validation logic: check if salinity and oxygen levels are viable
    integrity = (20.0 <= salinity <= 40.0) and oxygen > 4.5

    return {
        "log": [f"{UNISPSC_CODE}:inspect_habitat -> salinity={salinity}, integrity={integrity}"],
        "water_salinity": salinity,
        "oxygen_level": oxygen,
        "habitat_integrity": integrity,
    }


def catalog_specimens(state: State) -> dict[str, Any]:
    """Node: Process specimen count and verify health status."""
    inp = state.get("input") or {}
    count = inp.get("count", 1)

    # Health certification depends on environmental integrity
    is_healthy = state.get("habitat_integrity", False) and count > 0

    return {
        "log": [f"{UNISPSC_CODE}:catalog_specimens -> count={count}, certified={is_healthy}"],
        "specimen_count": count,
        "health_certified": is_healthy,
    }


def issue_manifest(state: State) -> dict[str, Any]:
    """Node: Emit final marine manifest and approval status."""
    is_certified = state.get("health_certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:issue_manifest -> status={'APPROVED' if is_certified else 'REJECTED'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if is_certified else "FLAGGED",
            "manifest": {
                "specimen_count": state.get("specimen_count", 0),
                "environment": {
                    "salinity": state.get("water_salinity"),
                    "oxygen": state.get("oxygen_level"),
                }
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_habitat", inspect_habitat)
_g.add_node("catalog_specimens", catalog_specimens)
_g.add_node("issue_manifest", issue_manifest)

_g.add_edge(START, "inspect_habitat")
_g.add_edge("inspect_habitat", "catalog_specimens")
_g.add_edge("catalog_specimens", "issue_manifest")
_g.add_edge("issue_manifest", END)

graph = _g.compile()
