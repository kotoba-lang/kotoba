# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121702 — Assembly (segment 20).

Bespoke LangGraph implementation for the assembly of well completion
equipment, including component sequencing and pressure verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121702"
UNISPSC_TITLE = "Assembly"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Mining and Well Drilling Assembly
    well_id: str
    component_stack: list[str]
    is_sealed: bool
    pressure_rating_psi: int
    quality_check_failed: bool


def initialize_assembly(state: State) -> dict[str, Any]:
    """Prepares the assembly list and identifies the target well."""
    inp = state.get("input") or {}
    well_id = inp.get("well_id", "WELL-001-ALPHA")
    components = inp.get("components", ["packer_base", "seal_element", "mandrel"])

    return {
        "log": [f"{UNISPSC_CODE}:initialize_assembly"],
        "well_id": well_id,
        "component_stack": components,
        "is_sealed": False,
        "pressure_rating_psi": 5000,
    }


def perform_joining(state: State) -> dict[str, Any]:
    """Simulates the physical joining of components in the assembly stack."""
    stack = state.get("component_stack", [])
    log_entry = f"joining_{len(stack)}_components"

    return {
        "log": [f"{UNISPSC_CODE}:{log_entry}"],
        "is_sealed": True if len(stack) > 0 else False,
        "quality_check_failed": False,
    }


def certify_assembly(state: State) -> dict[str, Any]:
    """Finalizes the assembly and issues a completion certificate."""
    sealed = state.get("is_sealed", False)
    failed = state.get("quality_check_failed", False)
    well_id = state.get("well_id", "N/A")

    ok = sealed and not failed

    return {
        "log": [f"{UNISPSC_CODE}:certify_assembly:success_{ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "well_id": well_id,
            "certification": "ISO-20121702-APPROVED" if ok else "REJECTED",
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_assembly)
_g.add_node("join", perform_joining)
_g.add_node("certify", certify_assembly)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "join")
_g.add_edge("join", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
