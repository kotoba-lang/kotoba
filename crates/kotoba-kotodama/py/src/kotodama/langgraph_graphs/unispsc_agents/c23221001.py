# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23221001 — Press.

This bespoke agent manages the lifecycle of a printing press job, encompassing
plate setup, cylinder engagement for impressions, and quality verification
of the final printed substrate.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23221001"
UNISPSC_TITLE = "Press"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23221001"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for Press operations
    ink_profile: dict[str, float]
    substrate_type: str
    impression_count: int
    registration_locked: bool
    qc_passed: bool


def setup_plates(state: State) -> dict[str, Any]:
    """Initializes the ink levels and substrate for the printing run."""
    inp = state.get("input") or {}
    substrate = inp.get("substrate", "100lb Coated Text")
    profile = inp.get("ink_profile", {"C": 0.8, "M": 0.8, "Y": 0.8, "K": 1.0})

    return {
        "log": [f"{UNISPSC_CODE}:setup_plates:substrate={substrate}"],
        "substrate_type": substrate,
        "ink_profile": profile,
        "registration_locked": False,
        "qc_passed": False
    }


def engage_cylinders(state: State) -> dict[str, Any]:
    """Simulates the mechanical impression process and locks registration."""
    inp = state.get("input") or {}
    requested_impressions = inp.get("impressions", 500)

    # Simulate a successful registration lock
    return {
        "log": [f"{UNISPSC_CODE}:engage_cylinders:impressions={requested_impressions}"],
        "impression_count": requested_impressions,
        "registration_locked": True,
        "qc_passed": True if requested_impressions > 0 else False
    }


def output_manifest(state: State) -> dict[str, Any]:
    """Finalizes the job and generates the output manifest for the actor."""
    qc = state.get("qc_passed", False)
    reg = state.get("registration_locked", False)

    return {
        "log": [f"{UNISPSC_CODE}:output_manifest:qc={qc}:reg={reg}"],
        "result": {
            "metadata": {
                "code": UNISPSC_CODE,
                "title": UNISPSC_TITLE,
                "segment": UNISPSC_SEGMENT,
                "did": UNISPSC_DID,
            },
            "output_details": {
                "impressions_completed": state.get("impression_count", 0),
                "substrate": state.get("substrate_type"),
                "status": "SUCCESS" if qc and reg else "FAILED"
            },
            "ok": qc and reg
        }
    }


_g = StateGraph(State)

_g.add_node("setup_plates", setup_plates)
_g.add_node("engage_cylinders", engage_cylinders)
_g.add_node("output_manifest", output_manifest)

_g.add_edge(START, "setup_plates")
_g.add_edge("setup_plates", "engage_cylinders")
_g.add_edge("engage_cylinders", "output_manifest")
_g.add_edge("output_manifest", END)

graph = _g.compile()
