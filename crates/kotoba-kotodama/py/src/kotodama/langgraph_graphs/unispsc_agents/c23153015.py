# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153015 — Motor (segment 23).
Bespoke logic for electrical specification validation, safety compliance checking,
and industrial efficiency rating.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153015"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153015"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Motor processing
    specs_valid: bool
    compliance_status: str
    efficiency_class: str
    certification_id: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validates electrical specifications (voltage, power, phases)."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})

    # Requirement: Must have voltage and power rating
    valid = "voltage" in specs and "power_rating" in specs
    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "specs_valid": valid,
    }


def check_compliance(state: State) -> dict[str, Any]:
    """Verifies safety standards compliance (e.g., UL, CE)."""
    if not state.get("specs_valid"):
        return {
            "log": [f"{UNISPSC_CODE}:check_compliance:denied_precheck"],
            "compliance_status": "spec_validation_failed",
        }

    inp = state.get("input") or {}
    standards = inp.get("standards", [])
    has_ul = "UL" in standards or "CE" in standards

    return {
        "log": [f"{UNISPSC_CODE}:check_compliance:verified"],
        "compliance_status": "compliant" if has_ul else "pending_review",
    }


def emit_certification(state: State) -> dict[str, Any]:
    """Generates industrial certification and efficiency rating."""
    compliant = state.get("compliance_status") == "compliant"
    cert_id = f"CERT-{UNISPSC_CODE}-INDUSTRIAL" if compliant else "NONE"

    # Mock efficiency calculation
    efficiency = "IE3" if compliant else "UNRATED"

    return {
        "log": [f"{UNISPSC_CODE}:emit_certification"],
        "efficiency_class": efficiency,
        "certification_id": cert_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification": cert_id,
            "efficiency": efficiency,
            "ok": compliant,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("check_compliance", check_compliance)
_g.add_node("emit_certification", emit_certification)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "check_compliance")
_g.add_edge("check_compliance", "emit_certification")
_g.add_edge("emit_certification", END)

graph = _g.compile()
