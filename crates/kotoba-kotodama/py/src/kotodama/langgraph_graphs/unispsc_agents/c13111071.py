from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
import operator

class PetroState(TypedDict):
    commodity_code: str
    purity: float
    safety_check_passed: bool
    log: Annotated[List[str], operator.add]

def validate_quality(state: PetroState) -> PetroState:
    purity = state.get("purity", 0)
    passed = purity >= 98.5
    return {"safety_check_passed": passed, "log": [f"Quality validation: {passed} (purity: {purity})"]}

def check_compliance(state: PetroState) -> PetroState:
    if not state["safety_check_passed"]:
        return {"log": ["Compliance check skipped due to quality failure"]}
    return {"log": ["Compliance check passed: Hazardous materials protocols confirmed"]}

builder = StateGraph(PetroState)
builder.add_node("validate", validate_quality)
builder.add_node("compliance", check_compliance)
builder.set_entry_point("validate")
builder.add_edge("validate", "compliance")
builder.add_edge("compliance", END)
graph = builder.compile()
