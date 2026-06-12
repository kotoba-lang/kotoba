# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101508"
UNISPSC_TITLE = "Chemical Ingest"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Chemical Ingest
    msds_verified: bool
    toxicity_rating: float
    containment_protocol: str
    purity_level: float


def validate_chemical_specs(state: State) -> dict[str, Any]:
    """Validates the chemical specifications and MSDS documentation."""
    inp = state.get("input") or {}
    msds_present = inp.get("msds_documented", False)
    purity = inp.get("purity", 0.0)
    return {
        "log": [f"{UNISPSC_CODE}:validate_chemical_specs: purity={purity}"],
        "msds_verified": msds_present,
        "purity_level": purity,
    }


def assess_toxicity(state: State) -> dict[str, Any]:
    """Analyzes toxicity levels to determine containment requirements."""
    inp = state.get("input") or {}
    concentration = inp.get("concentration", 0.0)
    # Determine toxicity score (0-10 scale)
    tox_score = min(10.0, concentration * 100.0)
    protocol = "LEVEL_1_STANDARD" if tox_score < 3.0 else "LEVEL_4_BIOHAZARD"
    return {
        "log": [f"{UNISPSC_CODE}:assess_toxicity: rating={tox_score}"],
        "toxicity_rating": tox_score,
        "containment_protocol": protocol,
    }


def record_ingest_event(state: State) -> dict[str, Any]:
    """Finalizes the ingest record for the actor log."""
    is_safe = state.get("msds_verified", False)
    protocol = state.get("containment_protocol", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:record_ingest_event: protocol={protocol}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ingest_verified": is_safe,
            "audit_payload": {
                "tox_rating": state.get("toxicity_rating"),
                "purity": state.get("purity_level"),
                "containment": protocol
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate_chemical_specs", validate_chemical_specs)
_g.add_node("assess_toxicity", assess_toxicity)
_g.add_node("record_ingest_event", record_ingest_event)

_g.add_edge(START, "validate_chemical_specs")
_g.add_edge("validate_chemical_specs", "assess_toxicity")
_g.add_edge("assess_toxicity", "record_ingest_event")
_g.add_edge("record_ingest_event", END)

graph = _g.compile()
