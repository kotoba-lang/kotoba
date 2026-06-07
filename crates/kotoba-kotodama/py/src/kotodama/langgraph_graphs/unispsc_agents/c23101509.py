# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23101509 — Motor (segment 23).

This bespoke implementation handles motor specification validation,
winding configuration assignment, and performance datasheet generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23101509"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23101509"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    rpm_rating: int
    voltage_v: int
    phase_count: int
    efficiency_class: str


def evaluate_requirements(state: State) -> dict[str, Any]:
    """Extracts and validates motor technical requirements from input."""
    inp = state.get("input") or {}
    rpm = inp.get("rpm", 1800)
    voltage = inp.get("voltage", 460)

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_requirements"],
        "rpm_rating": rpm,
        "voltage_v": voltage,
    }


def configure_winding(state: State) -> dict[str, Any]:
    """Determines phase configuration and efficiency rating based on specs."""
    voltage = state.get("voltage_v", 460)
    rpm = state.get("rpm_rating", 1800)

    # Simple logic to simulate motor configuration
    phase = 3 if voltage >= 208 else 1
    eff = "IE4" if rpm > 1500 and phase == 3 else "IE3"

    return {
        "log": [f"{UNISPSC_CODE}:configure_winding"],
        "phase_count": phase,
        "efficiency_class": eff,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Generates the final motor datasheet and certification result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specs": {
                "rpm": state.get("rpm_rating"),
                "voltage": state.get("voltage_v"),
                "phases": state.get("phase_count"),
                "efficiency": state.get("efficiency_class"),
            },
            "status": "certified",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("evaluate", evaluate_requirements)
_g.add_node("configure", configure_winding)
_g.add_node("finalize", finalize_certification)

_g.add_edge(START, "evaluate")
_g.add_edge("evaluate", "configure")
_g.add_edge("configure", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
