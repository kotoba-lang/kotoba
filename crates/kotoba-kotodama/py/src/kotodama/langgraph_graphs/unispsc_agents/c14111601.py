# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
# Ensure typing components are available for state definition
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

# Verbatim preservation of UNISPSC metadata constants
UNISPSC_CODE = "14111601"
UNISPSC_TITLE = "Paper Procurement"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111601"


class State(TypedDict, total=False):
    """
    State schema for Paper Procurement agent.
    Tracks requisition details, sustainability audit status, and workflow logs.
    """
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Paper Procurement
    paper_specs: dict[str, Any]
    sustainability_status: str
    requisition_id: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming paper procurement request details."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})
    req_id = inp.get("id", "REQ-UNASSIGNED")

    # Verify that essential paper characteristics (quantity, type) are provided
    quantity = specs.get("quantity", 0)
    has_specs = quantity > 0 and "type" in specs

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "paper_specs": specs,
        "requisition_id": req_id,
        "sustainability_status": "VALIDATED" if has_specs else "INCOMPLETE"
    }


def audit_sustainability(state: State) -> dict[str, Any]:
    """Performs an environmental audit on the paper source."""
    specs = state.get("paper_specs") or {}

    # Check for environmental certifications (e.g., FSC) or high recycled content
    is_fsc = specs.get("fsc_certified", False)
    recycled_pct = specs.get("recycled_content_percent", 0)

    is_sustainable = is_fsc or recycled_pct > 30
    status = "SUSTAINABLE" if is_sustainable else "CONVENTIONAL"

    # Ensure validation state is respected
    if state.get("sustainability_status") == "INCOMPLETE":
        status = "REJECTED_AUDIT"

    return {
        "log": [f"{UNISPSC_CODE}:audit_sustainability"],
        "sustainability_status": status
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement transaction and records the result."""
    req_id = state.get("requisition_id")
    audit_res = state.get("sustainability_status")

    # Determine approval based on audit results
    is_approved = audit_res in ["SUSTAINABLE", "CONVENTIONAL"]

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition_id": req_id,
            "status": "APPROVED" if is_approved else "DENIED",
            "audit_trail": audit_res,
            "ok": True,
        },
    }


# Graph construction using the defined State and nodes
_g = StateGraph(State)
_g.add_node("validate", validate_requisition)
_g.add_node("audit", audit_sustainability)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "audit")
_g.add_edge("audit", "finalize")
_g.add_edge("finalize", END)

# The exported graph object is compiled for execution
graph = _g.compile()
