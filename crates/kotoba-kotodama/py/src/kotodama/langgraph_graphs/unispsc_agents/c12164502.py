# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12164502 —  (segment 12).

Bespoke graph for wild animal monitoring and population tracking.
This agent handles habitat verification, health screenings, and
record finalization within the Etz Hayyim live animal domain.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12164502"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12164502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for wild animal management
    wildlife_record_id: str
    habitat_zone: str
    observation_quality: float
    alert_level: str


def validate_capture(state: State) -> dict[str, Any]:
    """Validates the initial capture data and habitat coordinates."""
    inp = state.get("input") or {}
    record_id = inp.get("id", "PENDING")
    zone = inp.get("zone", "unassigned")
    return {
        "log": [f"{UNISPSC_CODE}:validate_capture"],
        "wildlife_record_id": record_id,
        "habitat_zone": zone,
    }


def analyze_health(state: State) -> dict[str, Any]:
    """Performs an automated health screening based on visual sensors."""
    inp = state.get("input") or {}
    quality = inp.get("sensor_quality", 0.0)

    alert = "low"
    if quality < 0.5:
        alert = "high"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_health"],
        "observation_quality": quality,
        "alert_level": alert,
    }


def emit_result(state: State) -> dict[str, Any]:
    """Finalizes the processing and emits the tracking result."""
    ok = state.get("observation_quality", 0.0) > 0.1

    return {
        "log": [f"{UNISPSC_CODE}:emit_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "record_id": state.get("wildlife_record_id"),
            "status": "active" if ok else "unverified",
            "alert": state.get("alert_level"),
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_capture", validate_capture)
_g.add_node("analyze_health", analyze_health)
_g.add_node("emit_result", emit_result)

_g.add_edge(START, "validate_capture")
_g.add_edge("validate_capture", "analyze_health")
_g.add_edge("analyze_health", "emit_result")
_g.add_edge("emit_result", END)

graph = _g.compile()
