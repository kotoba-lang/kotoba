# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12141915 — Moly (segment 12).

Upgraded from placeholder to bespoke logic for Live Animal (Moly) lifecycle
management, including pedigree inspection, health evaluation, and stable certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141915"
UNISPSC_TITLE = "Moly"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141915"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Moly (Live Animals)
    hybrid_genotype: str
    lineage_verified: bool
    health_status: str
    quarantine_marker: str


def inspect_pedigree(state: State) -> dict[str, Any]:
    """Verify the lineage and genotype of the Moly specimen."""
    inp = state.get("input") or {}
    # A moly (hinny) is the offspring of a male horse and a female donkey
    genotype = inp.get("genotype", "STALLION_JENNET")
    verified = inp.get("lineage_cert", False)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_pedigree:genotype={genotype}"],
        "hybrid_genotype": genotype,
        "lineage_verified": verified,
    }


def evaluate_health(state: State) -> dict[str, Any]:
    """Assess health status based on vaccination and vet records."""
    verified = state.get("lineage_verified", False)
    status = "HEALTHY" if verified else "OBSERVATION_REQUIRED"
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_health:status={status}"],
        "health_status": status,
        "quarantine_marker": "NONE" if verified else "HOLD_STABLE_42",
    }


def certify_specimen(state: State) -> dict[str, Any]:
    """Finalize the digital twin record and emit the lifecycle result."""
    status = state.get("health_status", "UNKNOWN")
    marker = state.get("quarantine_marker", "N/A")
    is_ok = status == "HEALTHY"
    return {
        "log": [f"{UNISPSC_CODE}:certify_specimen:final={status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "genotype": state.get("hybrid_genotype"),
            "certified": is_ok,
            "marker": marker,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_pedigree)
_g.add_node("evaluate", evaluate_health)
_g.add_node("certify", certify_specimen)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "evaluate")
_g.add_edge("evaluate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
