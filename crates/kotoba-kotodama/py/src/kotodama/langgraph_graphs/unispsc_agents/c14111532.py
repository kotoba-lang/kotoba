# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111532 — Paper Procurement (segment 14).
Handles specification validation, sustainability auditing, and requisition issuance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111532"
UNISPSC_TITLE = "Paper Procurement"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111532"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain state
    paper_spec: str
    ream_count: int
    is_fsc_compliant: bool
    requisition_id: str


def evaluate_specs(state: State) -> dict[str, Any]:
    """Validate paper specifications and ream requirements."""
    inp = state.get("input") or {}
    spec = inp.get("spec", "Standard 80gsm")
    count = inp.get("count", 10)

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_specs: {spec} x{count}"],
        "paper_spec": spec,
        "ream_count": count,
        "requisition_id": f"REQ-PPR-{UNISPSC_CODE}-{abs(hash(spec)) % 10000:04d}",
    }


def audit_sustainability(state: State) -> dict[str, Any]:
    """Verify Forest Stewardship Council (FSC) compliance for the paper stock."""
    spec = state.get("paper_spec", "")
    # Logic: Virgin paper without FSC label is marked non-compliant
    is_compliant = "Virgin" not in spec or "FSC" in spec

    return {
        "log": [f"{UNISPSC_CODE}:audit_sustainability: compliant={is_compliant}"],
        "is_fsc_compliant": is_compliant,
    }


def issue_requisition(state: State) -> dict[str, Any]:
    """Issue the final procurement requisition and record results."""
    count = state.get("ream_count", 0)
    is_fsc = state.get("is_fsc_compliant", False)

    return {
        "log": [f"{UNISPSC_CODE}:issue_requisition"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "requisition_id": state.get("requisition_id"),
            "fsc_verified": is_fsc,
            "status": "APPROVED" if count > 0 and is_fsc else "PENDING_REVIEW",
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("evaluate", evaluate_specs)
_g.add_node("audit", audit_sustainability)
_g.add_node("issue", issue_requisition)

_g.add_edge(START, "evaluate")
_g.add_edge("evaluate", "audit")
_g.add_edge("audit", "issue")
_g.add_edge("issue", END)

graph = _g.compile()
