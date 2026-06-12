# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10122003 — Drill.
Segment 10: Live Plant and Animal Material and Accessories and Supplies.
This agent manages the lifecycle and care protocols for Drills (Mandrillus leucophaeus),
ensuring species-specific husbandry and quarantine compliance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10122003"
UNISPSC_TITLE = "Drill"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10122003"


class State(TypedDict, total=False):
    # Core fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Primate husbandry domain fields
    species_validation: bool
    health_assessment_score: float
    quarantine_period_days: int
    dietary_strategy: str
    assigned_enclosure: str


def validate_specimen(state: State) -> dict[str, Any]:
    """Checks taxonomic identification and health baseline for the specimen."""
    inp = state.get("input") or {}
    species = str(inp.get("species", "")).lower()

    # Taxonomic check for Mandrillus leucophaeus
    is_drill = any(term in species for term in ["drill", "leucophaeus", "mandrillus"])
    h_score = float(inp.get("health_score", 0.75))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specimen(species_ok={is_drill})"],
        "species_validation": is_drill,
        "health_assessment_score": h_score
    }


def determine_husbandry(state: State) -> dict[str, Any]:
    """Assigns quarantine and nutritional requirements based on health status."""
    valid = state.get("species_validation", False)
    score = state.get("health_assessment_score", 0.0)

    # Drills require specialized social and dietary care
    q_days = 45 if score < 0.6 else 21
    diet = "Omnivorous/Frugivorous (Primates): Root vegetables, insects, and seasonal fruit" if valid else "Standard"

    return {
        "log": [f"{UNISPSC_CODE}:determine_husbandry(q_period={q_days}d)"],
        "quarantine_period_days": q_days,
        "dietary_strategy": diet,
        "assigned_enclosure": "PRIMATE-BLOCK-A-UNIT-04"
    }


def emit_care_record(state: State) -> dict[str, Any]:
    """Finalizes the animal record for integration into the etzhayyim registry."""
    success = state.get("species_validation", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_care_record(complete={success})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "record": {
                "scientific_name": "Mandrillus leucophaeus",
                "husbandry_protocol": state.get("dietary_strategy"),
                "quarantine_requirement": f"{state.get('quarantine_period_days')} days",
                "location": state.get("assigned_enclosure")
            },
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specimen", validate_specimen)
_g.add_node("determine_husbandry", determine_husbandry)
_g.add_node("emit_care_record", emit_care_record)

_g.add_edge(START, "validate_specimen")
_g.add_edge("validate_specimen", "determine_husbandry")
_g.add_edge("determine_husbandry", "emit_care_record")
_g.add_edge("emit_care_record", END)

graph = _g.compile()
