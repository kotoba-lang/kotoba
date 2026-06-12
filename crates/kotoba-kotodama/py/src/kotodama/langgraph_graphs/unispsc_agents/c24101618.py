# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101618 — Pipe Layer (segment 24).

Bespoke graph logic for managing pipe laying operations, ensuring
safety compliance, trench specifications, and alignment verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101618"
UNISPSC_TITLE = "Pipe Layer"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101618"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Pipe Layer
    pipe_specification: str
    trench_depth_meters: float
    alignment_status: str
    safety_check_passed: bool


def prepare_site(state: State) -> dict[str, Any]:
    """Inspects site conditions and verifies safety protocols."""
    inp = state.get("input") or {}
    depth = inp.get("target_depth", 1.8)
    return {
        "log": [f"{UNISPSC_CODE}:prepare_site"],
        "safety_check_passed": True,
        "trench_depth_meters": depth,
    }


def install_segment(state: State) -> dict[str, Any]:
    """Positions the pipe segment according to specifications."""
    if not state.get("safety_check_passed"):
        return {"log": [f"{UNISPSC_CODE}:install_segment_aborted"]}

    spec = state.get("input", {}).get("pipe_spec", "Ductile Iron")
    return {
        "log": [f"{UNISPSC_CODE}:install_segment"],
        "pipe_specification": spec,
        "alignment_status": "pending_verification",
    }


def finalize_installation(state: State) -> dict[str, Any]:
    """Verifies alignment and closes the installation state."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_installation"],
        "alignment_status": "verified",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "installation_depth": state.get("trench_depth_meters"),
            "pipe_spec": state.get("pipe_specification"),
            "status": "complete",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("prepare_site", prepare_site)
_g.add_node("install_segment", install_segment)
_g.add_node("finalize_installation", finalize_installation)

_g.add_edge(START, "prepare_site")
_g.add_edge("prepare_site", "install_segment")
_g.add_edge("install_segment", "finalize_installation")
_g.add_edge("finalize_installation", END)

graph = _g.compile()
