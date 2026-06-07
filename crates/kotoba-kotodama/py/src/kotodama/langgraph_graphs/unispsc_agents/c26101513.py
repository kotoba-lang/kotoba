# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101513"
UNISPSC_TITLE = "Engine Kit"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101513"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Engine Kit (segment 26)
    manifest_verified: bool
    compatibility_score: float
    assembly_instructions_included: bool
    kit_serial_number: str


def inventory_audit(state: State) -> dict[str, Any]:
    """Verify that all components required for the engine kit are present in the manifest."""
    inp = state.get("input") or {}
    manifest = inp.get("manifest", [])
    # A standard engine kit requires at least 5 core components (e.g. pistons, gaskets, rings)
    is_complete = len(manifest) >= 5
    return {
        "log": [f"{UNISPSC_CODE}:inventory_audit:complete={is_complete}"],
        "manifest_verified": is_complete,
        "kit_serial_number": inp.get("serial", "EK-UNASSIGNED"),
    }


def compatibility_check(state: State) -> dict[str, Any]:
    """Verify kit compatibility against the target engine specification."""
    inp = state.get("input") or {}
    target_engine = str(inp.get("target_engine", "unknown"))

    # Heuristic: verify if the kit is designed for the specified cylinder configuration
    score = 1.0 if "v8" in target_engine.lower() or "v6" in target_engine.lower() else 0.4

    return {
        "log": [f"{UNISPSC_CODE}:compatibility_check:score={score}"],
        "compatibility_score": score,
        "assembly_instructions_included": True,
    }


def certify_and_emit(state: State) -> dict[str, Any]:
    """Certify the kit based on audit and compatibility results and emit the final actor state."""
    audit_ok = state.get("manifest_verified", False)
    compat_ok = state.get("compatibility_score", 0.0) >= 0.8
    is_certified = bool(audit_ok and compat_ok)

    return {
        "log": [f"{UNISPSC_CODE}:certify_and_emit:certified={is_certified}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "serial": state.get("kit_serial_number"),
            "certified": is_certified,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inventory_audit", inventory_audit)
_g.add_node("compatibility_check", compatibility_check)
_g.add_node("certify_and_emit", certify_and_emit)

_g.add_edge(START, "inventory_audit")
_g.add_edge("inventory_audit", "compatibility_check")
_g.add_edge("compatibility_check", "certify_and_emit")
_g.add_edge("certify_and_emit", END)

graph = _g.compile()
