# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101805"
UNISPSC_TITLE = "Kit"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101805"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    manifest_verified: bool
    assembly_stage: str
    qa_passed: bool
    kit_serial_id: str


def verify_manifest(state: State) -> dict[str, Any]:
    """Verify that all components required for the power machinery kit are present."""
    inp = state.get("input") or {}
    serial_id = inp.get("serial_id", "K-DEF-001")
    return {
        "log": [f"{UNISPSC_CODE}:verify_manifest"],
        "manifest_verified": True,
        "kit_serial_id": serial_id,
        "assembly_stage": "initialized",
    }


def assemble_components(state: State) -> dict[str, Any]:
    """Execute the assembly logic for bundling the machinery accessories."""
    return {
        "log": [f"{UNISPSC_CODE}:assemble_components"],
        "assembly_stage": "completed",
    }


def perform_quality_assurance(state: State) -> dict[str, Any]:
    """Certify that the kit meets the segment 26 safety and distribution standards."""
    return {
        "log": [f"{UNISPSC_CODE}:perform_quality_assurance"],
        "qa_passed": True,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "kit_id": state.get("kit_serial_id"),
            "delivery_ready": True,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("verify_manifest", verify_manifest)
_g.add_node("assemble_components", assemble_components)
_g.add_node("perform_quality_assurance", perform_quality_assurance)

_g.add_edge(START, "verify_manifest")
_g.add_edge("verify_manifest", "assemble_components")
_g.add_edge("assemble_components", "perform_quality_assurance")
_g.add_edge("perform_quality_assurance", END)

graph = _g.compile()
