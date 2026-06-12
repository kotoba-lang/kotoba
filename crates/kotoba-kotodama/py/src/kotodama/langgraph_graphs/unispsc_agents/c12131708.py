from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    reagent_id: str
    purity_check_passed: bool
    safety_clearance: bool
    log: Annotated[Sequence[str], operator.add]

def validate_reagent(state: ReagentState):
    # Simulated validation logic for chemical reagents
    is_pure = True
    return {"purity_check_passed": is_pure, "log": ["Purity validation completed"]}

def check_safety(state: ReagentState):
    # Verify dual-use/hazard compliance
    is_safe = True
    return {"safety_clearance": is_safe, "log": ["Safety clearance verified"]}

workflow = StateGraph(ReagentState)
workflow.add_node("validate", validate_reagent)
workflow.add_node("safety", check_safety)
workflow.set_entry_point("validate")
workflow.add_edge("validate", "safety")
workflow.add_edge("safety", END)

graph = workflow.compile()
