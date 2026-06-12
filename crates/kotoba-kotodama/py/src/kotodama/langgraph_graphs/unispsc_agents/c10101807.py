# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10101807 — Procure (segment 10).

This bespoke graph manages the procurement workflow for live plant and animal
materials, ensuring source verification, health compliance, and shipment
authorization within the Etz Hayyim actor network.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10101807"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10101807"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Segment 10 (Live Materials) Procurement
    source_verified: bool
    health_certification: str
    transport_permit_id: str
    procurement_phase: str


def inspect_source(state: State) -> dict[str, Any]:
    """Validates the origin of the live material."""
    inp = state.get("input") or {}
    source = inp.get("source", "unknown_farm")
    is_verified = source.startswith("ETZ_CERT_")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_source(source={source}, verified={is_verified})"],
        "source_verified": is_verified,
        "procurement_phase": "source_inspected",
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Checks health and safety certifications for the live specimen."""
    inp = state.get("input") or {}
    cert_id = inp.get("health_cert", "PENDING")

    # Simulate a compliance check: certificates must be alphanumeric and > 5 chars
    is_compliant = len(cert_id) > 5 and cert_id.isalnum()
    status = "VALIDATED" if is_compliant else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance(cert={cert_id}, status={status})"],
        "health_certification": status,
        "procurement_phase": "compliance_verified",
    }


def authorize_shipment(state: State) -> dict[str, Any]:
    """Finalizes the procurement and issues a transport permit."""
    verified = state.get("source_verified", False)
    compliant = state.get("health_certification") == "VALIDATED"

    ok = verified and compliant
    permit = f"PERMIT-{UNISPSC_CODE}-{'OK' if ok else 'FAIL'}"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_shipment(authorized={ok})"],
        "transport_permit_id": permit,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": ok,
            "details": {
                "permit_id": permit,
                "source_verified": verified,
                "health_status": state.get("health_certification"),
            },
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_source)
_g.add_node("verify", verify_compliance)
_g.add_node("authorize", authorize_shipment)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "authorize")
_g.add_edge("authorize", END)

graph = _g.compile()
