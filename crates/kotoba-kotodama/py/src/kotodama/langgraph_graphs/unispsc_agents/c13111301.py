# codemod:2605231400-unispsc-gemini-bespoke v1
import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111301"
UNISPSC_TITLE = "Coke Procurement"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111301"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Coke Procurement
    sulfur_content: float
    ash_content: float
    fixed_carbon: float
    grade_category: str
    verification_status: str


def inspect_specification(state: State) -> dict[str, Any]:
    """Inspects the chemical properties of the coke batch."""
    inp = state.get("input") or {}
    # Extract metrics or use defaults for the batch
    sulfur = float(inp.get("sulfur", 0.85))
    ash = float(inp.get("ash", 12.5))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specification"],
        "sulfur_content": sulfur,
        "ash_content": ash,
        "verification_status": "batch_received"
    }


def determine_grade(state: State) -> dict[str, Any]:
    """Categorizes the coke based on sulfur and ash content."""
    sulfur = state.get("sulfur_content", 1.0)
    ash = state.get("ash_content", 15.0)

    # Simple grading logic for procurement routing
    if sulfur < 0.7 and ash < 10.0:
        grade = "premium_metallurgical"
    elif sulfur < 1.0 and ash < 14.0:
        grade = "standard_industrial"
    else:
        grade = "low_grade_utility"

    carbon_estimate = 100.0 - (sulfur + ash + 0.5) # 0.5 for volatile matter/moisture

    return {
        "log": [f"{UNISPSC_CODE}:determine_grade"],
        "grade_category": grade,
        "fixed_carbon": carbon_estimate,
        "verification_status": "grade_assigned"
    }


def certify_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement record and certifies the batch."""
    grade = state.get("grade_category", "unknown")
    carbon = state.get("fixed_carbon", 0.0)

    is_compliant = carbon > 80.0 and grade != "low_grade_utility"

    return {
        "log": [f"{UNISPSC_CODE}:certify_procurement"],
        "verification_status": "certified" if is_compliant else "rejected",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "grade": grade,
            "fixed_carbon_yield": f"{carbon:.2f}%",
            "compliance_verified": is_compliant,
            "status": "APPROVED" if is_compliant else "REJECTED"
        }
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_specification)
_g.add_node("grade", determine_grade)
_g.add_node("certify", certify_procurement)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "grade")
_g.add_edge("grade", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
